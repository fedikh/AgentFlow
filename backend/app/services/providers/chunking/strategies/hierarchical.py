"""Hierarchical (parent-child) chunking — two levels:
  - Parents (~chunk_size*4) carry rich context
  - Children (~chunk_size) are the precise retrieval units, linked to their parent
Retrieve the child, expand with the parent. Used in advanced RAG.
"""
from ..base import table_chunk, image_chunk, mk_chunk


def chunk(blocks, opts):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    strat = opts.strategy or "HIERARCHICAL"
    parent_size = opts.chunk_size * 4
    child_size = opts.chunk_size

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_size, chunk_overlap=opts.chunk_overlap,
        length_function=len, separators=["\n\n", "\n", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size, chunk_overlap=opts.chunk_overlap,
        length_function=len, separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks, idx = [], 0
    for block in blocks:
        btype = block.get("type", "text")
        if btype == "table":
            c = table_chunk(block, idx, strat)
            c.update({"chunk_level": "standard", "parent_id": None})
            chunks.append(c)
            idx += 1
            continue
        if btype == "image":
            chunks.append(image_chunk(block, idx, strat))
            idx += 1
            continue

        text_content = block.get("content", "")
        if len(text_content) <= child_size:
            if text_content.strip():
                chunks.append(mk_chunk(
                    text_content, block.get("page", 1), idx, strat,
                    chunk_level="standard", parent_id=None,
                ))
                idx += 1
            continue

        for parent_doc in parent_splitter.split_text(text_content):
            parent_idx = idx
            chunks.append(mk_chunk(
                parent_doc, block.get("page", 1), parent_idx, strat,
                chunk_level="parent", parent_id=None,
            ))
            idx += 1
            for child in child_splitter.split_text(parent_doc):
                chunks.append(mk_chunk(
                    child, block.get("page", 1), idx, strat,
                    chunk_level="child", parent_id=parent_idx,
                ))
                idx += 1

    return chunks
