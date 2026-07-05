"""
Chunking Factory — 3 strategies × 3 modes.

═══════════════════════════════════════════════════════════════
STRATEGIES (HOW a document is split):
  FIXED:        RecursiveCharacterTextSplitter
  SEMANTIC:     SemanticChunker — coupe par changement de sujet
  HIERARCHICAL: Parent-child — gros parents + petits enfants

MODES (WHICH strategy is used, set by space.chunk_mode):
  FIXED_ALL:     une seule stratégie (space.chunk_strategy) pour TOUS les docs
  PER_DOCUMENT:  chaque document utilise sa propre stratégie (doc.chunk_strategy)
  ADAPTIVE:      le système essaie toutes les stratégies et garde la meilleure
                 par document (score de qualité intrinsèque)
═══════════════════════════════════════════════════════════════

Usage:
    from app.services.providers.chunking_factory import chunk_document
    chunks = chunk_document(content_blocks, space, document=doc)
"""

import logging
from app.models.rag_space import ChunkStrategy

logger = logging.getLogger(__name__)

# Les stratégies que le mode ADAPTIVE va essayer puis comparer.
ADAPTIVE_CANDIDATES = ["FIXED", "HIERARCHICAL", "SEMANTIC"]


# ══════════════════════════════════════════════════════
# POINT D'ENTRÉE — dispatcher des 3 modes
# ══════════════════════════════════════════════════════

def chunk_document(content_blocks: list[dict], space, document=None) -> list[dict]:
    """
    Point d'entrée unique. Lit space.chunk_mode et route vers le bon mode.

    Args:
        content_blocks: list[{type, content, page}] (sortie de to_content_blocks())
        space:    RAGSpace — chunk_mode, chunk_strategy, chunk_size, chunk_overlap
        document: Document (optionnel) — utilisé en mode PER_DOCUMENT pour lire
                  document.chunk_strategy. En ADAPTIVE, on y écrira la stratégie
                  gagnante (document.chosen_strategy) si l'objet est fourni.

    Returns:
        list[dict] — content, page, chunk_index, type, strategy, (parent_id...)
    """
    mode = getattr(space, "chunk_mode", None) or "FIXED_ALL"

    logger.info(f"Chunking mode={mode}")

    if mode == "ADAPTIVE":
        return _adaptive_chunk(content_blocks, space, document)

    if mode == "PER_DOCUMENT":
        # La stratégie vient du document ; fallback sur celle du space.
        strategy = (
            getattr(document, "chunk_strategy", None)
            or space.chunk_strategy
            or "FIXED"
        )
        return chunk_with_strategy(content_blocks, strategy, space)

    # FIXED_ALL (défaut) — comportement historique
    strategy = space.chunk_strategy or "FIXED"
    return chunk_with_strategy(content_blocks, strategy, space)


# ══════════════════════════════════════════════════════
# SÉLECTION DE STRATÉGIE (ancien corps de chunk_document)
# ══════════════════════════════════════════════════════

def chunk_with_strategy(content_blocks: list[dict], strategy, space) -> list[dict]:
    """
    Applique UNE stratégie donnée. C'est l'ancien dispatcher, isolé ici pour
    être réutilisable par tous les modes (notamment ADAPTIVE qui l'appelle en boucle).
    """
    chunk_size = space.chunk_size or 512
    chunk_overlap = space.chunk_overlap or 50

    # Normalise (accepte enum ChunkStrategy ou string)
    strat = strategy.value if isinstance(strategy, ChunkStrategy) else str(strategy)

    logger.info(f"  strategy={strat}, size={chunk_size}, overlap={chunk_overlap}")

    if strat == "SEMANTIC":
        return _chunk_semantic(content_blocks, chunk_size)
    elif strat == "HIERARCHICAL":
        return _chunk_hierarchical(content_blocks, chunk_size, chunk_overlap)
    else:
        return _chunk_fixed(content_blocks, chunk_size, chunk_overlap)


# ══════════════════════════════════════════════════════
# ADAPTIVE — essaie toutes les stratégies, garde la meilleure
# ══════════════════════════════════════════════════════

def _adaptive_chunk(content_blocks: list[dict], space, document=None) -> list[dict]:
    """
    Pour CE document : essaie chaque stratégie candidate, score le résultat,
    et garde la stratégie avec le meilleur score.

    NOTE: coûteux — chunke le document N fois (une par stratégie). À utiliser
    quand la qualité prime sur la vitesse.

    Le score est pour l'instant TEMPORAIRE (voir _temp_quality_score).
    Il sera remplacé par les vraies métriques intrinsèques (Size Compliance,
    Block Integrity, etc.) à l'étape suivante.
    """
    target = space.chunk_size or 512
    best_strategy = None
    best_chunks = None
    best_score = float("-inf")

    for strategy in ADAPTIVE_CANDIDATES:
        try:
            candidate_chunks = chunk_with_strategy(content_blocks, strategy, space)
            if not candidate_chunks:
                continue
            score = _temp_quality_score(candidate_chunks, target)
            logger.info(f"  [adaptive] {strategy}: {len(candidate_chunks)} chunks, score={score:.3f}")

            if score > best_score:
                best_score = score
                best_strategy = strategy
                best_chunks = candidate_chunks
        except Exception as e:
            logger.warning(f"  [adaptive] {strategy} failed: {e}")
            continue

    # Sécurité : si tout échoue, fallback FIXED
    if best_chunks is None:
        logger.warning("  [adaptive] all candidates failed, falling back to FIXED")
        best_strategy = "FIXED"
        best_chunks = chunk_with_strategy(content_blocks, "FIXED", space)

    logger.info(f"  [adaptive] WINNER = {best_strategy} (score={best_score:.3f})")

    # Mémorise la stratégie gagnante sur le document (pour l'afficher à l'IT)
    if document is not None:
        try:
            document.chosen_strategy = best_strategy
        except Exception:
            pass  # le champ n'existe peut-être pas encore en base

    # Tag chaque chunk avec la stratégie gagnante
    for c in best_chunks:
        c["strategy"] = best_strategy

    return best_chunks


def _temp_quality_score(chunks: list[dict], target_size: int) -> float:
    """
    SCORE TEMPORAIRE — à remplacer par les vraies métriques intrinsèques.

    Pour l'instant : fraction de chunks dont la taille (en caractères) est
    proche de la cible (entre 0.5× et 1.5× target). Rapide, sans embeddings.
    Plus la fraction est haute, meilleur est le score.
    """
    if not chunks:
        return 0.0

    lo = target_size * 0.5
    hi = target_size * 1.5
    in_range = sum(1 for c in chunks if lo <= len(c["content"]) <= hi)
    return in_range / len(chunks)


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
        elif block["type"] == "image":
            chunks.append(_image_chunk(block, idx, "FIXED"))
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
    max_chunk_size = limite haute pour éviter les chunks géants.
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
        elif block["type"] == "image":
            chunks.append(_image_chunk(block, idx, "SEMANTIC"))
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
    2 niveaux de chunks :
    - Parents (~chunk_size * 4 chars) — contexte riche
    - Enfants (~chunk_size chars) — recherche précise
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document as LCDoc

    parent_size = chunk_size * 4
    child_size = chunk_size

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_size,
        chunk_overlap=chunk_overlap,
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
        elif block["type"] == "image":
            chunks.append(_image_chunk(block, idx, "HIERARCHICAL"))
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

            parent_docs = parent_splitter.split_documents([LCDoc(page_content=text_content)])

            for parent_doc in parent_docs:
                parent_content = parent_doc.page_content
                parent_idx = idx

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

                child_docs = child_splitter.split_documents([LCDoc(page_content=parent_content)])

                for child_doc in child_docs:
                    chunks.append({
                        "content": child_doc.page_content,
                        "page": block["page"],
                        "chunk_index": idx,
                        "type": "text",
                        "strategy": "HIERARCHICAL",
                        "chunk_level": "child",
                        "parent_id": parent_idx,
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


def _image_chunk(block: dict, idx: int, strategy: str) -> dict:
    """
    Batch 5: an image block becomes its own chunk (never split). The Gemini
    summary is the embeddable content; image_path is carried so the chat can
    render the image inline.
    """
    return {
        "content": block["content"],
        "page": block.get("page", 1),
        "chunk_index": idx,
        "type": "image_summary",
        "image_path": block.get("image_path", ""),
        "strategy": strategy,
    }