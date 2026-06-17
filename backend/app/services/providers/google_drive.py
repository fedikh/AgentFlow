"""
Google Drive Integration — downloads files from Drive to the server.
Called by the frontend after user picks a file from Google Picker.
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

# Supported file types and their extensions
MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "text/html": ".html",
    "application/json": ".json",
    "application/xml": ".xml",
    "text/xml": ".xml",
}

# Google Docs export types (Docs/Sheets/Slides are not files, they need export)
GOOGLE_EXPORT = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


def download_from_drive(file_id: str, access_token: str, save_dir: str) -> dict:
    """
    Download a file from Google Drive.

    Args:
        file_id: Google Drive file ID
        access_token: user's OAuth access token
        save_dir: directory to save the file

    Returns:
        {"file_path": "...", "file_name": "...", "file_size": ..., "mime_type": "..."}
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 1: Get file metadata
    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType,size"
    meta_res = httpx.get(meta_url, headers=headers, timeout=15)

    if meta_res.status_code != 200:
        raise Exception(f"Failed to get file info: {meta_res.text}")

    meta = meta_res.json()
    file_name = meta.get("name", "unknown")
    mime_type = meta.get("mimeType", "")
    file_size = int(meta.get("size", 0))

    logger.info(f"[GDRIVE] File: {file_name} ({mime_type}, {file_size} bytes)")

    # Step 2: Determine download method
    if mime_type in GOOGLE_EXPORT:
        # Google Docs/Sheets/Slides → export
        export_mime, ext = GOOGLE_EXPORT[mime_type]
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}"
        file_name = os.path.splitext(file_name)[0] + ext
        logger.info(f"[GDRIVE] Exporting as {export_mime}")
    elif mime_type in MIME_TO_EXT:
        # Regular file → direct download
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    else:
        raise Exception(f"Unsupported file type: {mime_type} ({file_name})")

    # Step 3: Download
    dl_res = httpx.get(download_url, headers=headers, timeout=60, follow_redirects=True)

    if dl_res.status_code != 200:
        raise Exception(f"Download failed: {dl_res.status_code}")

    content = dl_res.content

    if not content:
        raise Exception("Downloaded file is empty")

    # Step 4: Save to disk
    os.makedirs(save_dir, exist_ok=True)
    ext = MIME_TO_EXT.get(mime_type, os.path.splitext(file_name)[1])
    if not ext:
        ext = ".pdf"

    # Ensure filename has correct extension
    if not file_name.lower().endswith(ext):
        file_name = os.path.splitext(file_name)[0] + ext

    file_path = os.path.join(save_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"[GDRIVE] Saved: {file_path} ({len(content)} bytes)")

    return {
        "file_path": file_path,
        "file_name": file_name,
        "file_size": len(content),
        "mime_type": mime_type,
    }