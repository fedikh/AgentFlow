"""
Upload Sources — différentes façons d'ajouter du contenu au RAG.

Sources supportées :
    LOCAL    → fichier uploadé depuis l'ordinateur
    URL      → page web scrapée en temps réel

Sources futures (perspectives) :
    GDRIVE   → Google Drive (nécessite OAuth2)
    ONEDRIVE → Microsoft OneDrive (nécessite Azure AD)
    S3       → Amazon S3 bucket
    NOTION   → Notion pages
"""
import os
import tempfile
import logging

logger = logging.getLogger(__name__)


async def save_uploaded_file(file) -> tuple[str, str]:
    """Sauvegarde un UploadFile en fichier temporaire. Retourne (path, extension)."""
    ext = os.path.splitext(file.filename)[1].lower()
    content = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.write(content)
    tmp.close()
    logger.info(f"Local file saved: {file.filename} ({len(content)} bytes)")
    return tmp.name, ext


def cleanup_temp_file(path: str):
    """Supprime un fichier temporaire."""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def validate_url(url: str) -> str:
    """Valide et normalise une URL."""
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")
    if url.startswith("file://"):
        raise ValueError("Local file URLs not allowed")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def get_url_filename(url: str) -> str:
    """Génère un nom de fichier à partir d'une URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    name = (parsed.netloc + parsed.path).replace("/", "_").replace(".", "_").strip("_")
    return f"{name[:80]}.html"
