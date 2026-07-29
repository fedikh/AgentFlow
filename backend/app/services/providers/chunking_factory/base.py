"""
Chunking base — shared types, element accessors, chunk helpers, and the text
splitters reused by every category.

The parsers emit TWO element envelope families:
  * Family A (documents + web): {id, type, content, location{page,bbox},
    hierarchy{parent, parent_section}, metadata{reading_order, list_level},
    level(heading only)}. Ordering key = metadata.reading_order. Always has page.
  * Family B (json/xml/csv/xlsx): {id, parent_id, type, hierarchy{depth,level},
    location{path|xpath|sheet,range}, content, metadata{order,...},
    relationships{parent,children,previous,next}}. Ordering key = metadata.order.
    No page.

The accessors below (text_of / page_of / parent_of / depth_of / order_of /
image_path_of) are the single choke point, so no strategy hard-codes a family.

A chunk is the dict persisted by rag_service.process_document:
    {content, page, chunk_index, type("text"|"table"|"image_summary"),
     strategy, optional: image_path, chunk_level, parent_index,
     section (heading breadcrumb, e.g. "3. Conges > 3.2 Conges annuels")}
"""
from dataclasses import dataclass, field


@dataclass
class ChunkConfig:
    """Resolved chunking request: a strategy name + its tuned parameters."""
    strategy: str
    params: dict = field(default_factory=dict)
    file_type: str = ""          # extension (pdf/json/csv…) → picks the category

    def p(self, key, default=None):
        """Param value, treating None as absent (so partial payloads fall back)."""
        v = self.params.get(key, default)
        return default if v is None else v


# ══════════════════════════════════════════════════════════════
#  Element accessors (family-agnostic)
# ══════════════════════════════════════════════════════════════

def _content(el):  return el.get("content") or {}
def _meta(el):     return el.get("metadata") or {}
def _loc(el):      return el.get("location") or {}


def order_of(el) -> int:
    m = _meta(el)
    return m.get("reading_order", m.get("order", 0)) or 0


def page_of(el) -> int:
    return _loc(el).get("page", 1) or 1


def parent_of(el):
    return el.get("parent_id") or (el.get("hierarchy") or {}).get("parent")


def depth_of(el) -> int:
    return (el.get("hierarchy") or {}).get("depth") or el.get("level") or 1


def image_path_of(el) -> str:
    c = _content(el)
    return c.get("image_path") or c.get("src") or ""


def is_table(el) -> bool:
    return el.get("type") == "table"


def is_image(el) -> bool:
    return el.get("type") == "image"


def _img_fallback(c) -> str:
    cap = (c.get("caption") or c.get("alt") or "").strip()
    ocr = (c.get("ocr_text") or "").strip()
    if cap and ocr:
        return f"{cap} — {ocr}"
    return cap or ocr


def table_text(el) -> str:
    """Readable text for a table element (documents/web use markdown; tabular
    tables carry columns+rows and no markdown — render them 'col: val | …').
    Machine-generated table names (uuids from on-disk filenames) are dropped —
    they are token noise, not information."""
    import re as _re
    c = _content(el)
    md = c.get("markdown")
    if md:
        return md
    name = (c.get("table_name") or c.get("caption") or "").strip()
    if _re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^[0-9a-f]{16,}$",
                 name, _re.IGNORECASE):
        name = ""
    headers = c.get("headers") or [col.get("name") for col in (c.get("columns") or [])]
    generic = _re.compile(r"^(col|column)\s*_?\d+$|^unnamed", _re.IGNORECASE)
    lines = [f"Table: {name}"] if name else []
    for r in (c.get("rows") or []):
        vals = r.get("values") if isinstance(r, dict) and "values" in r else r
        if not isinstance(vals, dict):
            continue
        items = [(h, vals.get(h)) for h in headers] if headers else list(vals.items())
        parts = []
        for h, v in items:
            if v in (None, "", " "):
                continue
            parts.append(str(v) if (not h or generic.match(str(h))) else f"{h}: {v}")
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def text_of(el) -> str:
    """Best embeddable text for any element, type/family-aware."""
    t = el.get("type", "")
    c = _content(el)
    if t == "table":
        return table_text(el)
    if t == "image":
        return (c.get("text_for_embedding") or "").strip() or _img_fallback(c)
    if t == "cell_block":
        return (c.get("text") or "").strip()
    if t == "formula":
        f = c.get("formula") or ""
        cv = c.get("calculated_value")
        cell = c.get("cell", "")
        return f"{cell}: {f}".strip(": ") + (f" = {cv}" if cv not in (None, "") else "")
    if t == "merged_cell":
        v = c.get("value")
        return f"{c.get('range', '')}: {v}".strip(": ") if v not in (None, "") else ""
    # semantic_text-bearing (json/xml/workbook/sheet/chart)
    if c.get("semantic_text"):
        return str(c["semantic_text"]).strip()
    if c.get("normalized_text"):
        return str(c["normalized_text"]).strip()
    # plain text (heading/paragraph/list_item/code/quote)
    return (c.get("text") or "").strip()


def ordered(elements) -> list:
    return sorted(elements or [], key=order_of)


def elements_of(parsed) -> list:
    """The parsed document's flat element list (dicts), reading-ordered.

    Repeated page furniture (letterheads, dates, legal boilerplate that the
    parser tagged metadata.boilerplate — same text on 2+ pages) is EXCLUDED:
    the first occurrence stays, so the information is embedded exactly once
    instead of polluting every page's chunks.

    Fallback: some documents carry only the legacy sections/tables/images (the
    fast PyMuPDF PDF path, or docs parsed before the element schema existed). For
    those we synthesize equivalent elements so every strategy still works.
    """
    els = getattr(parsed, "elements", None) or []
    if els:
        return ordered([e for e in els
                        if not (e.get("metadata") or {}).get("boilerplate")])
    return _sections_to_elements(parsed)


def _sections_to_elements(parsed) -> list:
    out, ro = [], 0

    def emit(etype, content, page):
        nonlocal ro
        ro += 1
        out.append({"id": f"f{ro}", "type": etype, "content": content,
                    "location": {"page": page or 1}, "metadata": {"reading_order": ro}})

    for s in (getattr(parsed, "sections", None) or []):
        heading = getattr(s, "heading", "") or ""
        content = getattr(s, "content", "") or ""
        page = getattr(s, "page", 1) or 1
        if heading:
            emit("heading", {"text": heading}, page)
        if content:
            emit("paragraph", {"text": content}, page)
    for t in (getattr(parsed, "tables", None) or []):
        emit("table", {"markdown": getattr(t, "content", "") or ""}, getattr(t, "page", 1) or 1)
    for im in (getattr(parsed, "images", None) or []):
        emit("image", {"text_for_embedding": getattr(im, "text_for_embedding", "") or "",
                       "image_path": getattr(im, "image_path", "") or "",
                       "caption": getattr(im, "caption", "") or "",
                       "ocr_text": getattr(im, "ocr_text", "") or ""},
             getattr(im, "page", 1) or 1)
    return out


# ══════════════════════════════════════════════════════════════
#  Chunk builders
# ══════════════════════════════════════════════════════════════

def mk_chunk(content, page, idx, strategy, ctype="text", **extra):
    c = {"content": content, "page": page or 1, "chunk_index": idx,
         "type": ctype, "strategy": strategy}
    c.update({k: v for k, v in extra.items() if v is not None})
    return c


def table_chunk(el, idx, strategy, heading=""):
    """A table is never split — one chunk, prefixed with [TABLE] and (when known)
    its section breadcrumb so the table is self-describing for retrieval."""
    body = f"[TABLE]\n{table_text(el)}"
    content = f"{heading}\n{body}" if heading else body
    return mk_chunk(content, page_of(el), idx, strategy, ctype="table",
                    section=heading or None)


def image_chunk(el, idx, strategy, heading=""):
    """An image → one image_summary chunk (embed text = the vision summary),
    carrying image_path/src so the chat can render it inline."""
    txt = text_of(el)
    content = f"{heading}\n{txt}" if heading and txt else txt
    return mk_chunk(content, page_of(el), idx, strategy,
                    ctype="image_summary", image_path=image_path_of(el),
                    section=heading or None)


# ══════════════════════════════════════════════════════════════
#  Text splitters (shared by fixed / recursive / sentence / semantic)
# ══════════════════════════════════════════════════════════════

# All splitters are backed by LlamaIndex node parsers (token-aware, the RAG
# standard). Public signatures stay in CHARS so callers/params are unchanged;
# we convert to tokens internally (~4 chars/token). Splitter instances are
# cached — building a tokenizer on every call is wasteful.
from functools import lru_cache


def _toks(chars) -> int:
    return max(16, int(chars) // 4)


@lru_cache(maxsize=128)
def _sentence_splitter(size_tok, overlap_tok):
    from llama_index.core.node_parser import SentenceSplitter
    overlap_tok = min(overlap_tok, max(0, size_tok - 1))
    return SentenceSplitter(chunk_size=size_tok, chunk_overlap=overlap_tok)


@lru_cache(maxsize=128)
def _token_splitter(size_tok, overlap_tok):
    from llama_index.core.node_parser import TokenTextSplitter
    overlap_tok = min(overlap_tok, max(0, size_tok - 1))
    return TokenTextSplitter(chunk_size=size_tok, chunk_overlap=overlap_tok)


def split_recursive(text, size, overlap):
    """Sentence/paragraph-aware split (LlamaIndex SentenceSplitter).
    size/overlap given in chars; converted to tokens internally."""
    if not text or not text.strip():
        return []
    sp = _sentence_splitter(_toks(size), _toks(overlap))
    return [t for t in sp.split_text(text) if t.strip()]


def split_fixed(text, size, overlap):
    """Fixed token windows (LlamaIndex TokenTextSplitter). size/overlap in chars."""
    if not text or not text.strip():
        return []
    sp = _token_splitter(_toks(size), _toks(overlap))
    return [t for t in sp.split_text(text) if t.strip()]


def split_sentences(text, max_chars, overlap_sentences=0):
    """Fine sentence-level split (LlamaIndex SentenceSplitter) — never breaks a
    sentence. overlap_sentences is approximated as a small token overlap."""
    if not text or not text.strip():
        return []
    sp = _sentence_splitter(_toks(max_chars), _toks(max(0, overlap_sentences) * 25))
    return [t for t in sp.split_text(text) if t.strip()]


# ── Semantic: LlamaIndex SemanticSplitterNodeParser + HF embeddings ──
_EMBED_MODEL = {}
_SEMANTIC_PARSER = {}


def _embed_model():
    """Sentence embedder for the semantic splitter. MULTILINGUAL by default —
    the old all-MiniLM-L6-v2 was English-only, so on French/Arabic documents
    its similarity scores were near-random and the topic-change detection
    produced arbitrary cuts."""
    if "m" not in _EMBED_MODEL:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        try:
            _EMBED_MODEL["m"] = HuggingFaceEmbedding(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        except Exception:
            _EMBED_MODEL["m"] = HuggingFaceEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _EMBED_MODEL["m"]


def _semantic_parser(threshold):
    key = int(threshold)
    if key not in _SEMANTIC_PARSER:
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        _SEMANTIC_PARSER[key] = SemanticSplitterNodeParser(
            buffer_size=1, breakpoint_percentile_threshold=key,
            embed_model=_embed_model())
    return _SEMANTIC_PARSER[key]


def make_semantic_split(max_chars, threshold=75):
    """Return a split_fn that cuts on embedding topic shift. Falls back to the
    sentence splitter if embeddings can't be loaded (e.g. offline)."""
    def _fallback(text):
        return split_recursive(text, max_chars, max(32, max_chars // 10))

    try:
        parser = _semantic_parser(threshold)
    except Exception:
        parser = None
    if parser is None:
        return _fallback

    from llama_index.core import Document

    def _split(text):
        if not text or len(text) < 200:
            return _fallback(text)
        try:
            out = []
            for n in parser.get_nodes_from_documents([Document(text=text)]):
                t = (n.text or "").strip()
                if not t:
                    continue
                if len(t) > max_chars * 1.5:        # cap runaway segments
                    out.extend(_fallback(t))
                else:
                    out.append(t)
            return out or _fallback(text)
        except Exception:
            return _fallback(text)
    return _split


# ══════════════════════════════════════════════════════════════
#  Generic drivers used by many strategies
# ══════════════════════════════════════════════════════════════

def has_real_image_text(el) -> bool:
    """True only if an image carries a genuine description (vision summary / OCR /
    alt text) — not the bare 'Image' placeholder. Placeholder images are skipped
    so they don't pollute the index with meaningless chunks."""
    c = _content(el)
    return bool((c.get("text_for_embedding") or "").strip()
                or (c.get("ocr_text") or "").strip()
                or (c.get("alt") or "").strip())


class _HeadingStack:
    """Tracks the current heading path by level, so nested headings produce a
    breadcrumb like 'Data models > User'. A heading NEVER emits a chunk on its
    own — it only sets the context for the content beneath it (this is what kills
    the lonely 'User' / 'Data models' heading-only chunks)."""

    def __init__(self):
        self.stack = []          # list of (level, text)

    def push(self, level, text):
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        if text:
            self.stack.append((level, text))

    def crumb(self):
        return " > ".join(t for _, t in self.stack if t)


def flatten_split(elements, split_fn, strategy, breadcrumb=True):
    """Split the document into size-bounded chunks that PRESERVE structure:

      * a new section starts at each heading — chunks never span two sections,
      * the section breadcrumb (all enclosing headings) is prepended to EVERY
        chunk of that section, including tables and images, so each chunk is
        self-describing for retrieval,
      * headings alone never become a chunk (no orphan 'User' / 'Data models'),
      * tables stay intact, images become their own chunk only when they carry a
        real description (placeholder 'Image' entries are dropped).
    """
    chunks, idx = [], 0
    buf, buf_page = [], None
    heads = _HeadingStack()

    def crumb():
        return heads.crumb() if breadcrumb else ""

    def flush():
        nonlocal idx, buf, buf_page
        if not buf:
            return
        head = crumb()
        for piece in split_fn("\n\n".join(buf)):
            piece = (piece or "").strip()
            if not piece:
                continue
            content = f"{head}\n{piece}" if head and head not in piece else piece
            chunks.append(mk_chunk(content, buf_page or 1, idx, strategy,
                                   section=head or None))
            idx += 1
        buf, buf_page = [], None

    for el in ordered(elements):
        t = el.get("type")
        if t == "heading":
            flush()                              # close the previous section
            heads.push(el.get("level") or 1, text_of(el))
            continue
        if is_table(el):
            flush()
            chunks.append(table_chunk(el, idx, strategy, heading=crumb())); idx += 1
        elif is_image(el):
            flush()
            if has_real_image_text(el):
                chunks.append(image_chunk(el, idx, strategy, heading=crumb())); idx += 1
        else:
            txt = text_of(el)
            if not txt:
                continue
            if buf_page is None:
                buf_page = page_of(el)
            buf.append(txt)
    flush()
    return chunks


def element_chunks(elements, strategy, min_chars=0):
    """One element = one chunk. Headings become the section breadcrumb (never a
    chunk on their own) and are prepended to each element's chunk; tables/images
    carry it too. Text elements shorter than min_chars merge into the previous
    text chunk. (json/xml have no headings, so this is the plain one-node-per-
    chunk behaviour with tiny-leaf merging.)"""
    chunks, idx = [], 0
    heads = _HeadingStack()
    for el in ordered(elements):
        t = el.get("type")
        if t == "heading":
            heads.push(el.get("level") or 1, text_of(el))
            continue
        head = heads.crumb()
        if is_table(el):
            chunks.append(table_chunk(el, idx, strategy, heading=head)); idx += 1
            continue
        if is_image(el):
            if has_real_image_text(el):
                chunks.append(image_chunk(el, idx, strategy, heading=head)); idx += 1
            continue
        txt = text_of(el)
        if not txt:
            continue
        if (min_chars and chunks and chunks[-1]["type"] == "text"
                and chunks[-1]["page"] == page_of(el)
                and len(chunks[-1]["content"]) < min_chars):
            chunks[-1]["content"] += "\n" + txt
        else:
            content = f"{head}\n{txt}" if head and head not in txt else txt
            chunks.append(mk_chunk(content, page_of(el), idx, strategy,
                                   section=head or None)); idx += 1
    return chunks


def document_stream(elements):
    """The whole document as one ordered text stream + (offset, page) markers.
    Used by the mechanical fixed-size cutter, which ignores structure."""
    parts, offsets, pos = [], [], 0
    for el in ordered(elements):
        if is_image(el):
            if not has_real_image_text(el):
                continue
            t = text_of(el)
        elif is_table(el):
            t = table_text(el)
        else:
            t = text_of(el)
        if not t:
            continue
        offsets.append((pos, page_of(el)))
        parts.append(t)
        pos += len(t) + 2                      # +2 for the "\n\n" join
    return "\n\n".join(parts), offsets


def _page_at(offsets, pos):
    page = offsets[0][1] if offsets else 1
    for start, pg in offsets:
        if start <= pos:
            page = pg
        else:
            break
    return page


def fixed_chunks(elements, size, overlap, strategy="fixed"):
    """TRUE fixed-size chunking: cut the whole document into uniform windows of
    exactly `size` characters (with `overlap`), cutting straight through
    sections and tables. Deterministic and structure-agnostic — the predictable
    baseline. For structure-aware splitting use recursive/heading instead."""
    text, offsets = document_stream(elements)
    if not text.strip():
        return []
    if size <= 0:
        return [mk_chunk(text, _page_at(offsets, 0), 0, strategy)]
    ov = max(0, min(int(overlap), size - 1))
    step = max(1, size - ov)
    chunks, idx, i, n = [], 0, 0, len(text)
    while i < n:
        piece = text[i:i + size]
        if piece.strip():
            chunks.append(mk_chunk(piece, _page_at(offsets, i), idx, strategy))
            idx += 1
        i += step
    return chunks


def structure_chunks(elements, strategy, max_chars):
    """Element / Structure-Based — one COHERENT chunk per section: the heading
    plus ALL its body elements (paragraphs, lists, code, tables, images) kept
    together inline, preserving the document structure and hierarchy. So
    'Heading → Paragraph → Code → Table' becomes one chunk. A section larger than
    max_chars is recursively split as a fallback; headings never chunk alone."""
    chunks, idx = [], 0
    heads = _HeadingStack()
    buf, buf_page = [], None

    def flush():
        nonlocal idx, buf, buf_page
        if not buf:
            return
        head = heads.crumb()
        body = "\n\n".join(buf)
        full = f"{head}\n{body}" if head and head not in body else body
        pieces = [full] if len(full) <= max_chars else split_recursive(full, max_chars, 60)
        for p in pieces:
            p = p.strip()
            if p:
                chunks.append(mk_chunk(p, buf_page or 1, idx, strategy,
                                       section=head or None))
                idx += 1
        buf, buf_page = [], None

    for el in ordered(elements):
        t = el.get("type")
        if t == "heading":
            flush()
            heads.push(el.get("level") or 1, text_of(el))
            continue
        if is_image(el):
            if not has_real_image_text(el):
                continue
            txt = text_of(el)
        elif is_table(el):
            txt = f"[TABLE]\n{table_text(el)}"
        else:
            txt = text_of(el)
        if not txt:
            continue
        if buf_page is None:
            buf_page = page_of(el)
        buf.append(txt)
    flush()
    return chunks


def pack_paragraphs(text, max_chars):
    """Pack whole paragraphs (blank-line separated) up to max_chars, never
    splitting a paragraph — except a single paragraph that alone exceeds
    max_chars, which is recursively split as a fallback."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    out, cur = [], ""

    def flush():
        nonlocal cur
        if cur:
            out.append(cur)
            cur = ""

    for p in paras:
        if len(p) > max_chars:
            flush()
            out.extend(split_recursive(p, max_chars, 40))
        elif cur and len(cur) + len(p) + 2 > max_chars:
            flush()
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    flush()
    return out


def group_by_page(elements, strategy):
    """One chunk per page/slide (bucket by page_of, keep tables/images inline)."""
    from itertools import groupby
    chunks, idx = [], 0
    els = ordered(elements)
    for page, group in groupby(els, key=page_of):
        parts = []
        for el in group:
            if is_image(el) and not has_real_image_text(el):
                continue
            t = table_text(el) if is_table(el) else text_of(el)
            if t:
                parts.append(t)
        if parts:
            chunks.append(mk_chunk("\n\n".join(parts), page, idx, strategy)); idx += 1
    return chunks


def _is_heading(el) -> bool:
    return el.get("type") == "heading"


def iter_sections(elements):
    """Split the reading-ordered elements into (heading_text, body_elements)
    sections, opening a new section at each heading. Shared by the heading and
    hierarchical strategies."""
    sections, cur_head, cur_body = [], "", []
    for el in ordered(elements):
        if _is_heading(el):
            if cur_head or cur_body:
                sections.append((cur_head, cur_body))
            cur_head, cur_body = text_of(el), []
        else:
            cur_body.append(el)
    if cur_head or cur_body:
        sections.append((cur_head, cur_body))
    return sections


def group_by_heading(elements, strategy, max_chars):
    """Group every element under the heading that precedes it (a section). Split
    a section that exceeds max_chars with the recursive splitter. Elements before
    the first heading form an intro section."""
    chunks, idx = [], 0
    for head, body in iter_sections(elements):
        # tables/images inside a section stay their own chunks
        text_parts, page = [], None
        for el in body:
            if is_table(el):
                if text_parts:
                    idx = _emit_section(chunks, head, text_parts, page, idx, strategy, max_chars)
                    text_parts, page = [], None
                chunks.append(table_chunk(el, idx, strategy, heading=head)); idx += 1
            elif is_image(el):
                if has_real_image_text(el):
                    if text_parts:
                        idx = _emit_section(chunks, head, text_parts, page, idx, strategy, max_chars)
                        text_parts, page = [], None
                    chunks.append(image_chunk(el, idx, strategy, heading=head)); idx += 1
            else:
                t = text_of(el)
                if not t:
                    continue
                if page is None:
                    page = page_of(el)
                text_parts.append(t)
        if text_parts or (head and not body):
            idx = _emit_section(chunks, head, text_parts, page, idx, strategy, max_chars)
    return chunks


def _emit_section(chunks, head, text_parts, page, idx, strategy, max_chars):
    body = "\n".join(text_parts).strip()
    full = f"{head}\n{body}".strip() if head else body
    if not full:
        return idx
    if len(full) <= max_chars:
        chunks.append(mk_chunk(full, page or 1, idx, strategy,
                               section=head or None)); idx += 1
        return idx
    # oversize section → recursive split, re-prefix the heading on each piece
    for piece in split_recursive(body or full, max_chars, 50):
        piece = piece.strip()
        if not piece:
            continue
        content = f"{head}\n{piece}" if head and head not in piece else piece
        chunks.append(mk_chunk(content, page or 1, idx, strategy)); idx += 1
    return idx
