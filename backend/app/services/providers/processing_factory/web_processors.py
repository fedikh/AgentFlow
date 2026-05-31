"""
Web Processors — extraction de contenu web.

Formats : HTML (fichier local), URL (scraping web)
Utilise BeautifulSoup pour nettoyer le HTML et extraire le contenu.

pip install beautifulsoup4 requests
"""
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# HTML — fichier local
# ══════════════════════════════════════════════════════

def extract_html(file_path: str) -> list[dict]:
    """
    Lit un fichier HTML local et extrait le contenu.
    Utilisation : page_intranet.html, documentation_sauvegardee.html

    Ce qui est supprimé : <script>, <style>, <nav>, <footer>, <aside>, <iframe>
    Ce qui est gardé : <p>, <h1-h6>, <li>, <table>, <article>
    Les tableaux <table> sont convertis en Markdown.
    """
    from bs4 import BeautifulSoup
    import chardet

    with open(file_path, "rb") as f:
        raw = f.read()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8") or "utf-8"

    html = raw.decode(encoding, errors="replace")
    return _parse_html(html, source=file_path)


# ══════════════════════════════════════════════════════
# URL — scraping de page web
# ══════════════════════════════════════════════════════

def extract_url(url: str) -> list[dict]:
    """
    Télécharge et extrait le contenu d'une URL.
    Utilisation : https://docs.company.com/api, https://intranet/rh/conges

    Le User-Agent imite un navigateur Chrome pour éviter les blocages.
    Timeout de 15 secondes.
    La source URL est ajoutée comme métadonnée [Source: url].
    """
    import requests

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch URL '{url}': {str(e)}")

    return _parse_html(response.text, source=url)


# ══════════════════════════════════════════════════════
# PARSING HTML (partagé entre HTML local et URL)
# ══════════════════════════════════════════════════════

def _parse_html(html: str, source: str = "") -> list[dict]:
    """
    Parse le HTML et extrait le contenu propre.

    Étapes :
    1. Supprimer les éléments non-contenu (script, style, nav...)
    2. Extraire les tableaux → Markdown
    3. Extraire le texte par sections (h1/h2 → titre, p → paragraphe)
    4. Éliminer les doublons
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # ── Supprimer le bruit ──
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript", "meta", "link", "svg"]):
        tag.decompose()

    content_blocks = []
    source_prefix = f"[Source: {source}]\n" if source else ""

    # ── Extraire les tableaux ──
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)

        if len(rows) >= 2:
            headers = rows[0]
            num_cols = len(headers)
            md_lines = ["| " + " | ".join(headers) + " |"]
            md_lines.append("| " + " | ".join(["---"] * num_cols) + " |")
            for row in rows[1:]:
                padded = row + [""] * (num_cols - len(row))
                md_lines.append("| " + " | ".join(padded[:num_cols]) + " |")
            table_md = "\n".join(md_lines)
            if len(table_md) > 20:
                content_blocks.append({
                    "type": "table",
                    "content": f"{source_prefix}{table_md}",
                    "page": 1,
                })

        table.decompose()

    # ── Extraire le texte par sections ──
    title_tag = soup.find("title")
    current_section = title_tag.get_text(strip=True) if title_tag else ""
    current_lines = []
    seen_texts = set()

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "article", "blockquote", "pre"]):
        text = element.get_text(strip=True)
        if not text or len(text) < 10:
            continue

        # Éviter les doublons
        if text in seen_texts:
            continue
        seen_texts.add(text)

        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            if current_lines:
                block = "\n".join(current_lines).strip()
                if block and len(block) > 20:
                    prefix = f"{source_prefix}[Section: {current_section}]\n" if current_section else source_prefix
                    content_blocks.append({"type": "text", "content": f"{prefix}{block}", "page": 1})
                current_lines = []
            current_section = text
        else:
            current_lines.append(text)

    # Dernier bloc
    if current_lines:
        block = "\n".join(current_lines).strip()
        if block and len(block) > 20:
            prefix = f"{source_prefix}[Section: {current_section}]\n" if current_section else source_prefix
            content_blocks.append({"type": "text", "content": f"{prefix}{block}", "page": 1})

    # Fallback
    if not content_blocks:
        full_text = soup.get_text(separator="\n", strip=True)
        if full_text and len(full_text) > 50:
            content_blocks.append({"type": "text", "content": f"{source_prefix}{full_text}", "page": 1})

    return content_blocks
