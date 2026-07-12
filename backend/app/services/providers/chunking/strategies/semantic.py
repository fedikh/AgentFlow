"""Semantic chunking — split where the topic changes, using embeddings to detect
boundaries (SemanticChunker). Falls back to fixed if embeddings are unavailable.
"""
import logging
from ..base import table_chunk, image_chunk, mk_chunk

logger = logging.getLogger(__name__)


def chunk(blocks, opts):
    max_chunk_size = opts.chunk_size
    strat = opts.strategy or "SEMANTIC"
    chunks, idx = [], 0

    try:
        # SemanticChunker lives in langchain_experimental; fall back to the
        # (older) text_splitters location if that's where it is.
        try:
            from langchain_experimental.text_splitter import SemanticChunker
        except Exception:
            from langchain_text_splitters import SemanticChunker
        from langchain.embeddings import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        semantic_splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=75,
        )
    except Exception as e:
        logger.warning(f"SemanticChunker init failed, falling back to FIXED: {e}")
        from . import fixed
        return fixed.chunk(blocks, opts)

    for block in blocks:
        btype = block.get("type", "text")
        if btype == "table":
            chunks.append(table_chunk(block, idx, strat))
            idx += 1
            continue
        if btype == "image":
            chunks.append(image_chunk(block, idx, strat))
            idx += 1
            continue

        text_content = block.get("content", "")
        if len(text_content) < 100:
            if text_content.strip():
                chunks.append(mk_chunk(text_content, block.get("page", 1), idx, strat))
                idx += 1
            continue

        try:
            from langchain.schema import Document as LCDoc
            sem_docs = semantic_splitter.split_documents([LCDoc(page_content=text_content)])
            for d in sem_docs:
                content = d.page_content.strip()
                if not content:
                    continue
                if len(content) > max_chunk_size * 1.5:
                    from langchain_text_splitters import RecursiveCharacterTextSplitter
                    sub = RecursiveCharacterTextSplitter(chunk_size=max_chunk_size, chunk_overlap=50)
                    for s in sub.split_text(content):
                        chunks.append(mk_chunk(s, block.get("page", 1), idx, strat))
                        idx += 1
                else:
                    chunks.append(mk_chunk(content, block.get("page", 1), idx, strat))
                    idx += 1
        except Exception as e:
            logger.warning(f"Semantic split failed for block, using fixed: {e}")
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            fb = RecursiveCharacterTextSplitter(chunk_size=max_chunk_size, chunk_overlap=50)
            for s in fb.split_text(text_content):
                chunks.append(mk_chunk(s, block.get("page", 1), idx, strat))
                idx += 1

    return chunks
