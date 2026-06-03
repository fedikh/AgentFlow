"""
Ingestion Pipeline — orchestre les 9 étapes avant le chunking.

Usage dans rag_service.py:
    from app.services.providers.ingestion_pipeline import run_ingestion
    result = run_ingestion(file_path)
    # result = {
    #     "blocks": [...],           # blocs nettoyés et structurés
    #     "merged_text": "...",       # texte fusionné (pour chunking)
    #     "tables": [...],            # tableaux séparés (jamais coupés)
    #     "metadata": {...},          # auteur, date, titre, pages
    #     "language": "fr",           # langue détectée
    #     "quality_score": 0.85,      # score de qualité
    #     "warnings": [...],          # avertissements pour l'IT
    # }

pip install langdetect chardet
"""

import os
import re
import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════

def run_ingestion(file_path: str, source_type: str = "local", source_url: str = None) -> dict:
    """
    Exécute les 9 étapes du pipeline d'ingestion.

    Args:
        file_path: chemin vers le fichier temporaire
        source_type: "local" ou "url"
        source_url: URL d'origine (si scraping)

    Returns:
        dict avec blocks, merged_text, tables, metadata, language, quality_score, warnings
    """
    warnings = []
    ext = os.path.splitext(file_path)[1].lower()

    # ── Étape 1: Validation ──
    logger.info("Step 1/9: Validation")
    validation = _validate_file(file_path, ext)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    warnings.extend(validation.get("warnings", []))

    # ── Étape 2: Extraction ──
    logger.info("Step 2/9: Extraction")
    from app.services.providers.processing_factory import extract_document
    raw_blocks = extract_document(file_path)
    if not raw_blocks:
        raise ValueError("No content found in document")

    # ── Étape 3: Nettoyage ──
    logger.info("Step 3/9: Cleaning")
    cleaned_blocks = _clean_blocks(raw_blocks)

    # ── Étape 4: Détection de langue ──
    logger.info("Step 4/9: Language detection")
    language = _detect_language(cleaned_blocks)

    # ── Étape 5: Détection de structure ──
    logger.info("Step 5/9: Structure detection")
    structured_blocks = _detect_structure(cleaned_blocks)

    # ── Étape 6: Extraction de métadonnées ──
    logger.info("Step 6/9: Metadata extraction")
    metadata = _extract_metadata(file_path, ext, raw_blocks, language)
    if source_url:
        metadata["source_url"] = source_url

    # ── Étape 7: Déduplication ──
    logger.info("Step 7/9: Deduplication")
    deduped_blocks, dup_count = _deduplicate(structured_blocks)
    if dup_count > 0:
        warnings.append(f"{dup_count} duplicate block(s) removed")

    # ── Étape 8: Évaluation de qualité ──
    logger.info("Step 8/9: Quality assessment")
    quality = _assess_quality(deduped_blocks, raw_blocks)
    warnings.extend(quality.get("warnings", []))

    # ── Étape 9: Fusion du texte ──
    logger.info("Step 9/9: Merging text")
    merged_text, tables = _merge_text_and_tables(deduped_blocks)

    logger.info(f"Ingestion complete: {len(deduped_blocks)} blocks, {len(tables)} tables, "
                f"language={language}, quality={quality['score']:.2f}")

    return {
        "blocks": deduped_blocks,
        "merged_text": merged_text,
        "tables": tables,
        "metadata": metadata,
        "language": language,
        "quality_score": quality["score"],
        "quality_details": quality,
        "warnings": warnings,
        "stats": {
            "total_blocks": len(deduped_blocks),
            "text_blocks": len([b for b in deduped_blocks if b["type"] == "text"]),
            "table_blocks": len(tables),
            "total_chars": len(merged_text) + sum(len(t["content"]) for t in tables),
            "duplicates_removed": dup_count,
        },
    }


# ══════════════════════════════════════════════════════
# ÉTAPE 1: VALIDATION
# ══════════════════════════════════════════════════════

def _validate_file(file_path: str, ext: str) -> dict:
    """
    Vérifie que le fichier est valide avant de l'extraire.

    Checks:
    - Le fichier existe
    - Le fichier n'est pas vide (> 0 bytes)
    - Le fichier n'est pas trop gros (< 50 MB)
    - L'extension est supportée
    """
    warnings = []

    if not os.path.exists(file_path):
        return {"valid": False, "error": "File not found"}

    file_size = os.path.getsize(file_path)

    if file_size == 0:
        return {"valid": False, "error": "File is empty (0 bytes)"}

    if file_size > 50 * 1024 * 1024:  # 50 MB
        return {"valid": False, "error": f"File too large ({file_size // (1024*1024)} MB). Maximum is 50 MB"}

    if file_size > 10 * 1024 * 1024:  # > 10 MB
        warnings.append(f"Large file ({file_size // (1024*1024)} MB) — extraction may take longer")

    from app.services.providers.processing_factory import SUPPORTED_FORMATS
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        return {"valid": False, "error": f"Format '{ext}' not supported. Accepted: {supported}"}

    return {"valid": True, "warnings": warnings}


# ══════════════════════════════════════════════════════
# ÉTAPE 3: NETTOYAGE
# ══════════════════════════════════════════════════════

def _clean_blocks(blocks: list[dict]) -> list[dict]:
    """
    Nettoie chaque bloc de texte extrait.

    Actions:
    - Supprimer les retours chariot Windows (\\r)
    - Normaliser les espaces multiples
    - Supprimer les lignes vides consécutives
    - Corriger les caractères Unicode cassés
    - Supprimer les headers/footers répétés
    - Supprimer les blocs trop courts (< 20 chars)
    """
    if not blocks:
        return []

    # Détecter les headers/footers répétés (texte identique sur >= 3 pages)
    repeated = _detect_repeated_lines(blocks)

    cleaned = []
    for block in blocks:
        content = block["content"]

        # Corriger les caractères Unicode cassés
        content = _fix_unicode(content)

        # Supprimer \\r
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Normaliser les espaces multiples (mais garder les sauts de ligne)
        content = re.sub(r"[ \t]+", " ", content)

        # Supprimer les lignes vides consécutives (garder max 1)
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Supprimer les headers/footers répétés
        for repeated_line in repeated:
            content = content.replace(repeated_line, "")

        # Supprimer les numéros de page isolés
        content = re.sub(r"^\s*Page\s+\d+\s*(of|sur|de|/)?\s*\d*\s*$", "", content, flags=re.MULTILINE | re.IGNORECASE)
        content = re.sub(r"^\s*-\s*\d+\s*-\s*$", "", content, flags=re.MULTILINE)

        content = content.strip()

        # Garder seulement les blocs avec du contenu significatif
        if content and len(content) > 20:
            cleaned.append({
                "type": block["type"],
                "content": content,
                "page": block.get("page", 1),
            })

    return cleaned


def _detect_repeated_lines(blocks: list[dict]) -> list[str]:
    """Détecte les lignes qui se répètent sur plusieurs pages (headers/footers)."""
    from collections import Counter

    all_lines = []
    for block in blocks:
        if block["type"] != "text":
            continue
        for line in block["content"].split("\n"):
            stripped = line.strip()
            if stripped and 5 < len(stripped) < 100:
                all_lines.append(stripped)

    counts = Counter(all_lines)
    # Si une ligne apparaît sur 3+ pages, c'est probablement un header/footer
    repeated = [line for line, count in counts.items() if count >= 3]
    return repeated


def _fix_unicode(text: str) -> str:
    """Corrige les caractères Unicode cassés courants."""
    replacements = {
        "\u00e2\u0080\u0099": "'",
        "\u00e2\u0080\u009c": '"',
        "\u00e2\u0080\u009d": '"',
        "\u00e2\u0080\u0093": "—",
        "\u00e2\u0080\u0094": "–",
        "\u00c3\u00a9": "é",
        "\u00c3\u00a8": "è",
        "\u00c3\u00a0": "à",
        "\u00c3\u00a7": "ç",
        "\u00c3\u00aa": "ê",
        "\u00c3\u00ae": "î",
        "\u00c3\u00b4": "ô",
        "\u00c3\u00b9": "ù",
        "\u00c3\u00a2": "â",
        "\u00c3\u00ab": "ë",
        "\u00c3\u00af": "ï",
        "\u00c3\u00bc": "ü",
        "\u00c3\u00b6": "ö",
        "\u00c3\u00a4": "ä",
        "\x00": "",
        "\ufeff": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


# ══════════════════════════════════════════════════════
# ÉTAPE 4: DÉTECTION DE LANGUE
# ══════════════════════════════════════════════════════

def _detect_language(blocks: list[dict]) -> str:
    """
    Détecte la langue principale du document.

    Utilise langdetect sur un échantillon de texte (les 3 premiers blocs texte).
    Retourne le code ISO 639-1 (fr, en, ar, de, es...).
    """
    # Assembler un échantillon de texte
    sample = ""
    for block in blocks:
        if block["type"] == "text":
            sample += block["content"][:500] + " "
        if len(sample) > 1000:
            break

    if not sample.strip():
        return "unknown"

    try:
        from langdetect import detect
        lang = detect(sample)
        return lang
    except Exception:
        # langdetect pas installé ou échec → deviner
        # Heuristique simple basée sur les caractères
        if re.search(r"[\u0600-\u06FF]", sample):
            return "ar"
        elif re.search(r"[àâéèêëïîôùûüç]", sample, re.IGNORECASE):
            return "fr"
        else:
            return "en"


# ══════════════════════════════════════════════════════
# ÉTAPE 5: DÉTECTION DE STRUCTURE
# ══════════════════════════════════════════════════════

def _detect_structure(blocks: list[dict]) -> list[dict]:
    """
    Analyse la structure du texte et ajoute des préfixes de section.

    Détection des titres :
    - Lignes courtes (< 80 chars) en MAJUSCULES
    - Lignes courtes se terminant par ":"
    - Lignes commençant par "Article", "Chapitre", "Section"
    - Lignes commençant par un numéro (1., 1.1, I., II.)
    """
    structured = []

    for block in blocks:
        if block["type"] == "table":
            structured.append(block)
            continue

        content = block["content"]
        lines = content.split("\n")
        current_section = ""
        current_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue

            # Détecter si c'est un titre
            is_title = False

            # Ligne courte en majuscules
            if len(stripped) < 80 and stripped.isupper() and len(stripped) > 3:
                is_title = True

            # Ligne se terminant par ":"
            elif len(stripped) < 80 and stripped.endswith(":") and not stripped.startswith("-"):
                is_title = True

            # "Article X", "Chapitre X", "Section X"
            elif re.match(r"^(article|chapitre|section|titre|partie)\s+\d", stripped, re.IGNORECASE):
                is_title = True

            # Numérotation hiérarchique "1.", "1.1", "1.1.1"
            elif re.match(r"^\d+(\.\d+)*\.\s+[A-Z]", stripped):
                is_title = True

            if is_title:
                # Sauvegarder le bloc précédent
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text and len(text) > 20:
                        prefix = f"[Section: {current_section}]\n" if current_section else ""
                        structured.append({
                            "type": "text",
                            "content": f"{prefix}{text}",
                            "page": block["page"],
                        })
                    current_lines = []
                current_section = stripped.rstrip(":")
            else:
                current_lines.append(stripped)

        # Dernier bloc
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text and len(text) > 20:
                prefix = f"[Section: {current_section}]\n" if current_section else ""
                structured.append({
                    "type": "text",
                    "content": f"{prefix}{text}",
                    "page": block["page"],
                })

    return structured


# ══════════════════════════════════════════════════════
# ÉTAPE 6: EXTRACTION DE MÉTADONNÉES
# ══════════════════════════════════════════════════════

def _extract_metadata(file_path: str, ext: str, blocks: list[dict], language: str) -> dict:
    """
    Extrait les métadonnées du document.

    PDF : auteur, titre, sujet, date de création (depuis les metadata PDF)
    DOCX : auteur, titre, sujet (depuis core_properties)
    Autres : nom du fichier, taille, nombre de pages estimé
    """
    metadata = {
        "file_name": os.path.basename(file_path),
        "file_size": os.path.getsize(file_path),
        "file_type": ext.replace(".", ""),
        "language": language,
        "total_pages": max((b.get("page", 1) for b in blocks), default=1),
        "author": None,
        "title": None,
        "subject": None,
        "creation_date": None,
    }

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                info = pdf.metadata or {}
                metadata["author"] = info.get("Author")
                metadata["title"] = info.get("Title")
                metadata["subject"] = info.get("Subject")
                metadata["creation_date"] = info.get("CreationDate")
                metadata["total_pages"] = len(pdf.pages)
        except Exception:
            pass

    elif ext in [".docx", ".doc"]:
        try:
            from docx import Document
            doc = Document(file_path)
            props = doc.core_properties
            metadata["author"] = props.author
            metadata["title"] = props.title
            metadata["subject"] = props.subject
            if props.created:
                metadata["creation_date"] = str(props.created)
        except Exception:
            pass

    return metadata


# ══════════════════════════════════════════════════════
# ÉTAPE 7: DÉDUPLICATION
# ══════════════════════════════════════════════════════

def _deduplicate(blocks: list[dict]) -> tuple[list[dict], int]:
    """
    Supprime les blocs dont le contenu est identique.

    Utilise un hash MD5 de chaque bloc pour détecter les doublons.
    Garde la première occurrence, supprime les suivantes.

    Retourne (blocs_dédupliqués, nombre_de_doublons_supprimés)
    """
    seen_hashes = set()
    deduped = []
    dup_count = 0

    for block in blocks:
        content_hash = hashlib.md5(block["content"].encode()).hexdigest()

        if content_hash in seen_hashes:
            dup_count += 1
            continue

        seen_hashes.add(content_hash)
        deduped.append(block)

    return deduped, dup_count


# ══════════════════════════════════════════════════════
# ÉTAPE 8: ÉVALUATION DE QUALITÉ
# ══════════════════════════════════════════════════════

def _assess_quality(cleaned_blocks: list[dict], raw_blocks: list[dict]) -> dict:
    """
    Évalue la qualité de l'extraction.

    Score de 0 à 1 basé sur :
    - Ratio blocs gardés / blocs bruts (beaucoup de suppression = bruit)
    - Longueur moyenne des blocs (blocs très courts = mauvaise extraction)
    - Présence de texte lisible (pas juste des symboles)
    - Ratio texte / tableaux

    Retourne un score global + des warnings pour l'IT.
    """
    warnings = []

    if not cleaned_blocks:
        return {"score": 0.0, "warnings": ["No content extracted from document"]}

    total_chars = sum(len(b["content"]) for b in cleaned_blocks)
    text_blocks = [b for b in cleaned_blocks if b["type"] == "text"]
    table_blocks = [b for b in cleaned_blocks if b["type"] == "table"]

    # Score 1: Ratio blocs gardés (1.0 = tout gardé, 0.0 = tout supprimé)
    if raw_blocks:
        retention_ratio = len(cleaned_blocks) / len(raw_blocks)
    else:
        retention_ratio = 0.0

    # Score 2: Longueur moyenne des blocs (> 100 chars = bien)
    if text_blocks:
        avg_length = sum(len(b["content"]) for b in text_blocks) / len(text_blocks)
        length_score = min(avg_length / 200, 1.0)
    else:
        length_score = 0.0

    # Score 3: Lisibilité (ratio lettres / total caractères)
    if total_chars > 0:
        letter_count = sum(1 for c in "".join(b["content"] for b in cleaned_blocks) if c.isalpha())
        readability = letter_count / total_chars
    else:
        readability = 0.0

    # Score 4: Contenu suffisant (> 500 chars = bien)
    content_score = min(total_chars / 1000, 1.0)

    # Score final
    score = (retention_ratio * 0.2) + (length_score * 0.3) + (readability * 0.3) + (content_score * 0.2)
    score = round(min(max(score, 0.0), 1.0), 2)

    # Warnings
    if total_chars < 100:
        warnings.append("Very little text extracted — document may be scanned (needs OCR)")

    if readability < 0.5:
        warnings.append("Low readability — text may contain encoding errors")

    if len(text_blocks) == 0 and len(table_blocks) > 0:
        warnings.append("Only tables found — no text paragraphs extracted")

    if retention_ratio < 0.5:
        warnings.append("More than 50% of content was removed during cleaning")

    return {
        "score": score,
        "retention_ratio": round(retention_ratio, 2),
        "avg_block_length": round(avg_length, 0) if text_blocks else 0,
        "readability": round(readability, 2),
        "total_chars": total_chars,
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════
# ÉTAPE 9: FUSION TEXTE + SÉPARATION TABLEAUX
# ══════════════════════════════════════════════════════

def _merge_text_and_tables(blocks: list[dict]) -> tuple[str, list[dict]]:
    """
    Fusionne tous les blocs texte en un seul texte continu.
    Les tableaux sont gardés séparés (jamais découpés par le chunker).

    POURQUOI fusionner : Le chunker (RecursiveCharacterTextSplitter) doit
    voir le document ENTIER pour couper aux bons endroits (fins de phrases,
    fins de paragraphes). Si on lui donne des petits blocs par page, il coupe
    au milieu des phrases.

    Retourne:
        merged_text: tout le texte en un seul string
        tables: liste de blocs table séparés
    """
    text_parts = []
    tables = []

    for block in blocks:
        if block["type"] == "table":
            tables.append({
                "content": f"[TABLE]\n{block['content']}",
                "page": block.get("page", 1),
                "type": "table",
            })
        elif block["type"] == "text":
            text_parts.append(block["content"])

    # Fusionner avec double saut de ligne entre les blocs
    merged_text = "\n\n".join(text_parts)

    return merged_text, tables