"""
Chunking Factory — 3 strategies configurables par espace RAG.

FIXED:        RecursiveCharacterTextSplitter (existant, migré ici)
SEMANTIC:     SemanticChunker de LangChain — coupe par changement de sujet
HIERARCHICAL: Parent-child — gros chunks parents + petits chunks enfants

Usage:
    from app.services.providers.chunking_factory import chunk_document
    chunks = chunk_document(content_blocks, space)
"""

import logging
from app.models.rag_space import ChunkStrategy

logger = logging.getLogger(__name__)


def chunk_document(content_blocks: list[dict], space) -> list[dict]:
    """
    Point d'entrée unique. Lit space.chunk_strategy et appelle la bonne méthode.

    Args:
        content_blocks: résultat de extract_document() — list[{type, content, page}]
        space: RAGSpace model avec chunk_strategy, chunk_size, chunk_overlap

    Returns:
        list[dict] — chaque dict a : content, page, chunk_index, type, parent_id (optionnel)
    """
    strategy = space.chunk_strategy or "FIXED"
    chunk_size = space.chunk_size or 512
    chunk_overlap = space.chunk_overlap or 50

    logger.info(f"Chunking with strategy={strategy}, size={chunk_size}, overlap={chunk_overlap}")

    if strategy == "SEMANTIC" or strategy == ChunkStrategy.SEMANTIC:
        return _chunk_semantic(content_blocks, chunk_size)
    elif strategy == "HIERARCHICAL" or strategy == ChunkStrategy.HIERARCHICAL:
        return _chunk_hierarchical(content_blocks, chunk_size, chunk_overlap)
    else:
        return _chunk_fixed(content_blocks, chunk_size, chunk_overlap)


# ══════════════════════════════════════════════════════
# FIXED — RecursiveCharacterTextSplitter
# ══════════════════════════════════════════════════════

def _chunk_fixed(content_blocks: list[dict], chunk_size: int, chunk_overlap: int) -> list[dict]:
    """
    Découpe tous les N caractères avec chevauchement.
    Tables = jamais coupées (un seul chunk).
    Titres de sections détectés et préfixés.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document as LCDoc

    chunks = []
    idx = 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    for block in content_blocks:
        if block["type"] == "table":
            chunks.append({
                "content": f"[TABLE]\n{block['content']}",
                "page": block["page"],
                "chunk_index": idx,
                "type": "table",
                "strategy": "FIXED",
            })
            idx += 1
        elif block["type"] == "text":
            text_content = block["content"]
            current_title = _detect_section_title(text_content)

            if len(text_content) <= chunk_size:
                content = f"[Section: {current_title}]\n{text_content}" if current_title else text_content
                chunks.append({
                    "content": content,
                    "page": block["page"],
                    "chunk_index": idx,
                    "type": "text",
                    "strategy": "FIXED",
                })
                idx += 1
            else:
                lc_docs = splitter.split_documents([LCDoc(page_content=text_content)])
                for doc in lc_docs:
                    content = doc.page_content
                    if current_title and current_title not in content:
                        content = f"[Section: {current_title}]\n{content}"
                    chunks.append({
                        "content": content,
                        "page": block["page"],
                        "chunk_index": idx,
                        "type": "text",
                        "strategy": "FIXED",
                    })
                    idx += 1

    return chunks


# ══════════════════════════════════════════════════════
# SEMANTIC — coupe par changement de sujet
# ══════════════════════════════════════════════════════

def _chunk_semantic(content_blocks: list[dict], max_chunk_size: int) -> list[dict]:
    """
    Utilise les embeddings pour détecter les frontières de sujet.

    Comment ça marche :
    1. On découpe le texte en phrases
    2. On embed chaque phrase
    3. On compare les embeddings de phrases consécutives
    4. Quand la similarité chute → on coupe (changement de sujet)

    Les chunks sont de taille variable mais chacun couvre un sujet cohérent.
    max_chunk_size est utilisé comme limite haute pour éviter les chunks géants.
    """
    chunks = []
    idx = 0

    try:
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
        logger.warning(f"SemanticChunker failed to init, falling back to FIXED: {e}")
        return _chunk_fixed(content_blocks, max_chunk_size, 50)

    for block in content_blocks:
        if block["type"] == "table":
            chunks.append({
                "content": f"[TABLE]\n{block['content']}",
                "page": block["page"],
                "chunk_index": idx,
                "type": "table",
                "strategy": "SEMANTIC",
            })
            idx += 1
        elif block["type"] == "text":
            text_content = block["content"]

            if len(text_content) < 100:
                chunks.append({
                    "content": text_content,
                    "page": block["page"],
                    "chunk_index": idx,
                    "type": "text",
                    "strategy": "SEMANTIC",
                })
                idx += 1
                continue

            try:
                from langchain.schema import Document as LCDoc
                sem_docs = semantic_splitter.split_documents([LCDoc(page_content=text_content)])

                for doc in sem_docs:
                    content = doc.page_content.strip()
                    if not content:
                        continue

                    # Si le chunk sémantique est trop gros, le re-découper en fixe
                    if len(content) > max_chunk_size * 1.5:
                        from langchain.text_splitter import RecursiveCharacterTextSplitter
                        sub_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=max_chunk_size, chunk_overlap=50
                        )
                        sub_docs = sub_splitter.split_documents([LCDoc(page_content=content)])
                        for sub in sub_docs:
                            chunks.append({
                                "content": sub.page_content,
                                "page": block["page"],
                                "chunk_index": idx,
                                "type": "text",
                                "strategy": "SEMANTIC",
                            })
                            idx += 1
                    else:
                        chunks.append({
                            "content": content,
                            "page": block["page"],
                            "chunk_index": idx,
                            "type": "text",
                            "strategy": "SEMANTIC",
                        })
                        idx += 1

            except Exception as e:
                logger.warning(f"Semantic chunking failed for block, using fixed: {e}")
                from langchain.text_splitter import RecursiveCharacterTextSplitter
                from langchain.schema import Document as LCDoc
                fallback = RecursiveCharacterTextSplitter(chunk_size=max_chunk_size, chunk_overlap=50)
                for doc in fallback.split_documents([LCDoc(page_content=text_content)]):
                    chunks.append({
                        "content": doc.page_content,
                        "page": block["page"],
                        "chunk_index": idx,
                        "type": "text",
                        "strategy": "FIXED_FALLBACK",
                    })
                    idx += 1

    return chunks


# ══════════════════════════════════════════════════════
# HIERARCHICAL — parent-child
# ══════════════════════════════════════════════════════

def _chunk_hierarchical(content_blocks: list[dict], chunk_size: int, chunk_overlap: int) -> list[dict]:
    """
    Crée 2 niveaux de chunks :
    - Parents (~chunk_size * 4 chars) — gros blocs pour le contexte riche
    - Enfants (~chunk_size chars) — petits blocs pour la recherche précise

    La recherche cible les enfants (précision).
    Le contexte envoyé au LLM inclut le parent (richesse).

    Chaque enfant a un parent_id qui pointe vers son parent.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document as LCDoc

    parent_size = chunk_size * 4      # ex: 2048 si chunk_size=512
    child_size = chunk_size            # ex: 512

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_size,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    idx = 0

    for block in content_blocks:
        if block["type"] == "table":
            chunks.append({
                "content": f"[TABLE]\n{block['content']}",
                "page": block["page"],
                "chunk_index": idx,
                "type": "table",
                "strategy": "HIERARCHICAL",
                "chunk_level": "standard",
                "parent_id": None,
            })
            idx += 1
        elif block["type"] == "text":
            text_content = block["content"]

            if len(text_content) <= child_size:
                chunks.append({
                    "content": text_content,
                    "page": block["page"],
                    "chunk_index": idx,
                    "type": "text",
                    "strategy": "HIERARCHICAL",
                    "chunk_level": "standard",
                    "parent_id": None,
                })
                idx += 1
                continue

            # Créer les parents
            parent_docs = parent_splitter.split_documents([LCDoc(page_content=text_content)])

            for parent_doc in parent_docs:
                parent_content = parent_doc.page_content
                parent_idx = idx

                # Ajouter le parent
                chunks.append({
                    "content": parent_content,
                    "page": block["page"],
                    "chunk_index": parent_idx,
                    "type": "text",
                    "strategy": "HIERARCHICAL",
                    "chunk_level": "parent",
                    "parent_id": None,
                })
                idx += 1

                # Créer les enfants de ce parent
                child_docs = child_splitter.split_documents([LCDoc(page_content=parent_content)])

                for child_doc in child_docs:
                    chunks.append({
                        "content": child_doc.page_content,
                        "page": block["page"],
                        "chunk_index": idx,
                        "type": "text",
                        "strategy": "HIERARCHICAL",
                        "chunk_level": "child",
                        "parent_id": parent_idx,    # pointe vers le parent
                    })
                    idx += 1

    return chunks


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _detect_section_title(text: str) -> str:
    """Détecte un titre de section dans les premières lignes."""
    for line in text.split("\n")[:5]:
        stripped = line.strip()
        if stripped and len(stripped) < 80 and (stripped.isupper() or stripped.endswith(":")):
            return stripped
    return ""
