"""Section / header-based chunking — split on document structure (Markdown
headings, ALL-CAPS titles, trailing-colon labels). Each section becomes a chunk;
over-long sections are sub-split. Excellent for Markdown, DOCX and manuals.
"""
from ..base import iterate_blocks


def _is_header(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return True
    return len(s) < 80 and (s.isupper() or s.endswith(":"))


def chunk(blocks, opts):
    size = opts.chunk_size
    strat = opts.strategy or "HEADER"

    def split_text(text):
        if not text:
            return []
        sections, cur = [], []
        for line in text.split("\n"):
            if _is_header(line) and cur:
                sections.append("\n".join(cur).strip())
                cur = [line]
            else:
                cur.append(line)
        if cur:
            sections.append("\n".join(cur).strip())

        out = []
        for sec in sections:
            if not sec:
                continue
            if len(sec) > size * 2:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                sp = RecursiveCharacterTextSplitter(
                    chunk_size=size, chunk_overlap=opts.chunk_overlap
                )
                out.extend(sp.split_text(sec))
            else:
                out.append(sec)
        return out

    return iterate_blocks(blocks, split_text, strat)
