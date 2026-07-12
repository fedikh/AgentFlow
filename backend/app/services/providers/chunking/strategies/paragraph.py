"""Paragraph-based chunking — each paragraph (blank-line separated) is a unit;
paragraphs are packed up to the target size. Over-long paragraphs are split.
"""
import re
from ..base import iterate_blocks

_PARA = re.compile(r"\n\s*\n")


def chunk(blocks, opts):
    size = opts.chunk_size
    strat = opts.strategy or "PARAGRAPH"

    def split_text(text):
        if not text:
            return []
        paras = [p.strip() for p in _PARA.split(text) if p.strip()]
        out, cur = [], ""
        for p in paras:
            if len(p) > size * 1.5:
                if cur:
                    out.append(cur)
                    cur = ""
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                sp = RecursiveCharacterTextSplitter(
                    chunk_size=size, chunk_overlap=opts.chunk_overlap
                )
                out.extend(sp.split_text(p))
            elif cur and len(cur) + 2 + len(p) > size:
                out.append(cur)
                cur = p
            else:
                cur = f"{cur}\n\n{p}".strip()
        if cur:
            out.append(cur)
        return out

    return iterate_blocks(blocks, split_text, strat)
