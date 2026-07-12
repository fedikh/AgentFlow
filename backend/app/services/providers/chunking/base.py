"""
Chunking base — shared types & helpers for every strategy module.

Mirrors the loader/parser layout: each strategy lives in its own module under
`strategies/` and exposes a single `chunk(blocks, opts) -> list[dict]`.

A "block" is the parser output from ParsedDocument.to_content_blocks():
    {"type": "text"|"table"|"image", "content": str, "page": int, "image_path"?: str}

A "chunk" is the dict persisted by rag_service.process_document:
    {"content", "page", "chunk_index", "type", "strategy",
     optional: "chunk_level", "parent_id", "image_path"}

Most strategies only differ in HOW they split a TEXT block. They implement a
`split_text(text) -> list[str]` and hand it to `iterate_blocks(...)`, which keeps
tables intact and turns images into their own chunk automatically. Strategies
that need cross-block logic (page, semantic, hierarchical) implement `chunk()`
directly.
"""
from dataclasses import dataclass


@dataclass
class ChunkOptions:
    chunk_size: int = 512       # target size (chars, or tokens for token strategy)
    chunk_overlap: int = 50
    strategy: str = "FIXED"     # canonical name of the running strategy


def mk_chunk(content, page, idx, strategy, ctype="text", **extra):
    c = {
        "content": content,
        "page": page,
        "chunk_index": idx,
        "type": ctype,
        "strategy": strategy,
    }
    c.update(extra)
    return c


def table_chunk(block, idx, strategy):
    """A table block is never split — one chunk, marked so it stays intact."""
    return mk_chunk(
        f"[TABLE]\n{block.get('content', '')}",
        block.get("page", 1), idx, strategy, ctype="table",
    )


def image_chunk(block, idx, strategy):
    """An image block becomes its own chunk (Gemini summary = embeddable text)."""
    return mk_chunk(
        block.get("content", ""),
        block.get("page", 1), idx, strategy,
        ctype="image_summary",
        image_path=block.get("image_path", ""),
    )


def detect_section_title(text: str) -> str:
    """Heuristic: a short ALL-CAPS or trailing-colon line near the top is a title."""
    for line in text.split("\n")[:5]:
        s = line.strip()
        if s and len(s) < 80 and (s.isupper() or s.endswith(":")):
            return s
    return ""


def iterate_blocks(blocks, split_text, strategy) -> list[dict]:
    """
    Generic driver used by every text-splitting strategy.
      - table blocks  → kept intact (one chunk)
      - image blocks  → one image_summary chunk
      - text blocks   → split via split_text(text) -> list[str]
    Empty pieces are dropped. chunk_index is assigned in order.
    """
    chunks: list[dict] = []
    idx = 0
    for b in blocks:
        btype = b.get("type", "text")
        if btype == "table":
            chunks.append(table_chunk(b, idx, strategy))
            idx += 1
        elif btype == "image":
            chunks.append(image_chunk(b, idx, strategy))
            idx += 1
        else:
            for piece in (split_text(b.get("content", "")) or []):
                piece = (piece or "").strip()
                if not piece:
                    continue
                chunks.append(mk_chunk(piece, b.get("page", 1), idx, strategy))
                idx += 1
    return chunks
