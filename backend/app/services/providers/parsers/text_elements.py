"""
Element builders for plain text (.txt) and Markdown (.md).

Produce the same element schema (heading / paragraph / list_item / table /
code / image) as the PDF/DOCX/PPTX parsers, so text and markdown flow through
the identical hierarchy builder, cleaner, chunker and frontend viewer.

  * Markdown → parsed structurally: ATX headings (#…######), fenced code
    blocks, pipe tables, ordered/unordered (nested) lists, images, paragraphs.
  * Plain text → inferred heuristically: numbered / ALL-CAPS / short isolated
    headings, bullet lists, blank-line-separated paragraphs.

Each builder returns (elements, sections, tables) — the caller wraps them in a
ParsedDocument, attaches metadata, and runs the hierarchy builder.
"""
import re
from app.services.providers.parsers.parsed_document import Section, Table


class _Emitter:
    """Assigns sequential ids + reading order to emitted elements."""

    def __init__(self):
        self.elements = []
        self._ro = 0

    def emit(self, el_type, content, level=None, list_level=None, page=1):
        self._ro += 1
        el = {
            "id": f"e{self._ro}",
            "type": el_type,
            "content": content,
            "location": {"page": page, "bbox": []},
            "hierarchy": {"parent": None, "parent_section": None},
            "metadata": {"reading_order": self._ro},
        }
        if level is not None:
            el["level"] = level
        if list_level:
            el["metadata"]["list_level"] = list_level
        self.elements.append(el)


# ══════════════════════════════════════════════════════════════
#  Markdown  (CommonMark + GFM via markdown-it-py — token stream)
# ══════════════════════════════════════════════════════════════

def _inline_text(inline):
    """Plain text of an `inline` token (strips **bold**/_italic_/link syntax)."""
    if inline is None:
        return ""
    children = getattr(inline, "children", None)
    if not children:
        return (inline.content or "").strip()
    out = []
    for c in children:
        if c.type in ("text", "code_inline"):
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
        elif c.type == "image":
            out.append(c.content or "")
    return "".join(out).strip()


def _single_image(inline):
    """If a paragraph's inline is just one image, return (alt, src), else None."""
    children = getattr(inline, "children", None) if inline else None
    if not children:
        return None
    imgs = [c for c in children if c.type == "image"]
    other = [c for c in children
             if c.type not in ("image", "softbreak", "hardbreak")
             and (c.content or "").strip()]
    if len(imgs) == 1 and not other:
        img = imgs[0]
        return (img.content or img.attrGet("alt") or ""), (img.attrGet("src") or "")
    return None


def _table_tokens(tokens, start):
    """Parse table_open…table_close → (headers, row_dicts, markdown, end_index)."""
    headers, rows, cur = [], [], []
    in_head = False
    i = start + 1
    while i < len(tokens) and tokens[i].type != "table_close":
        t = tokens[i]
        if t.type == "thead_open":
            in_head = True
        elif t.type == "thead_close":
            in_head = False
        elif t.type == "tr_open":
            cur = []
        elif t.type == "tr_close":
            if in_head:
                headers = cur[:]
            else:
                rows.append(cur[:])
        elif t.type in ("th_open", "td_open"):
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            cur.append(_inline_text(nxt) if nxt and nxt.type == "inline" else "")
        i += 1
    row_dicts = [
        {headers[k] if k < len(headers) else f"col{k}": (r[k] if k < len(r) else "")
         for k in range(len(headers))}
        for r in rows
    ]
    md_lines = [" | ".join(headers), " | ".join("---" for _ in headers)]
    md_lines += [" | ".join(r) for r in rows]
    return headers, row_dicts, "\n".join(md_lines), i + 1


def build_markdown(raw_text):
    from markdown_it import MarkdownIt
    tokens = MarkdownIt().enable("table").parse(raw_text)

    em = _Emitter()
    sections, tables = [], []
    cur_heading, cur_level, cur_lines = "", 1, []
    list_depth = 0

    def flush_section():
        content = "\n".join(cur_lines).strip()
        if cur_heading or content:
            sections.append(Section(heading=cur_heading, content=content,
                                    level=cur_level, page=1))

    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        typ = t.type

        if typ == "heading_open":
            flush_section(); cur_lines = []
            cur_level = int(t.tag[1])          # h1 → 1 … h6 → 6
            cur_heading = _inline_text(tokens[i + 1] if i + 1 < n else None)
            em.emit("heading", {"text": cur_heading}, level=cur_level)
            i += 3                              # heading_open, inline, heading_close
            continue

        if typ in ("fence", "code_block"):
            lang = (t.info or "").strip() if typ == "fence" else ""
            code = (t.content or "").rstrip("\n")
            em.emit("code", {"text": code, "language": lang})
            cur_lines.append(code)
            i += 1
            continue

        if typ in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1; i += 1; continue
        if typ in ("bullet_list_close", "ordered_list_close"):
            list_depth = max(0, list_depth - 1); i += 1; continue

        if typ == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < n else None
            img = _single_image(inline)
            if img:
                em.emit("image", {"image_path": img[1], "caption": img[0],
                                  "text_for_embedding": "", "ocr_text": ""})
                cur_lines.append(img[0] or img[1])
            else:
                text = _inline_text(inline)
                if text:
                    if list_depth > 0:          # a paragraph inside a list item
                        em.emit("list_item", {"text": text}, list_level=list_depth)
                    else:
                        em.emit("paragraph", {"text": text})
                    cur_lines.append(text)
            i += 3                              # paragraph_open, inline, paragraph_close
            continue

        if typ == "table_open":
            headers, rows, md_tbl, end = _table_tokens(tokens, i)
            em.emit("table", {"caption": "", "headers": headers,
                              "rows": rows, "markdown": md_tbl})
            tables.append(Table(content=md_tbl, headers=headers, num_rows=len(rows),
                                num_cols=len(headers), page=1))
            cur_lines.append(md_tbl)
            i = end
            continue

        i += 1

    flush_section()
    return em.elements, sections, tables


# ══════════════════════════════════════════════════════════════
#  Plain text
# ══════════════════════════════════════════════════════════════

_TXT_BULLET = re.compile(r"^(\s*)(?:[-*•●▪◦‣·]|\d+\s*[.)]|[a-z]\))\s+(.+)$")
_NUM_HEADING = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+\S")


def _is_text_heading(s, isolated):
    t = s.strip()
    if not t or len(t) > 100:
        return False
    if _NUM_HEADING.match(t):
        return True
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 3 and all(c.isupper() for c in letters):
        return True
    # short, title-like line — only when it stands alone (avoids treating the
    # first line of a wrapped paragraph as a heading)
    if isolated:
        words = t.split()
        if len(words) <= 8 and t[-1] not in ".,:;!?" and t[0].isupper():
            return True
    return False


def build_plaintext(raw_text):
    em = _Emitter()
    sections = []
    cur_heading, cur_lines = "", []
    para = []

    def flush_para():
        if para:
            text = " ".join(p.strip() for p in para).strip()
            if text:
                em.emit("paragraph", {"text": text})
                cur_lines.append(text)
            para.clear()

    def flush_section():
        content = "\n".join(cur_lines).strip()
        if cur_heading or content:
            sections.append(Section(heading=cur_heading, content=content, level=1, page=1))

    lines = raw_text.split("\n")
    for idx, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            flush_para()
            continue

        mb = _TXT_BULLET.match(raw)
        if mb:
            flush_para()
            indent = len(mb.group(1).replace("\t", "  "))
            em.emit("list_item", {"text": mb.group(2).strip()},
                    list_level=indent // 2 + 1)
            cur_lines.append(mb.group(2).strip())
            continue

        isolated = (idx + 1 >= len(lines)) or (not lines[idx + 1].strip())
        if _is_text_heading(s, isolated):
            flush_para(); flush_section(); cur_lines = []
            cur_heading = s
            em.emit("heading", {"text": s}, level=1)
            continue

        para.append(s)

    flush_para()
    flush_section()
    return em.elements, sections
