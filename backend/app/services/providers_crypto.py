"""
Crypto utility — encrypt/decrypt API keys at rest.

Uses Fernet (AES-128 symmetric). The key comes from settings.FERNET_KEY
(a 32-byte url-safe base64 string). Generate one once with:

    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())

Put it in your .env:
    FERNET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx=

NEVER commit this key. If it changes, previously stored keys can't be decrypted.
"""
from cryptography.fernet import Fernet
from app.config import settings


def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        raise RuntimeError("FERNET_KEY is not set in settings/.env")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_key(plaintext: str) -> str:
    """Encrypt an API key. Returns a token string safe to store in the DB."""
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(token: str) -> str:
    """Decrypt a stored API key back to plaintext (server-side only)."""
    if not token:
        return ""
    return _fernet().decrypt(token.encode()).decode()


def mask_key(plaintext: str) -> str:
    """Return a masked preview like 'sk-•••4f2' for safe display in the UI."""
    if not plaintext:
        return ""
    if len(plaintext) <= 6:
        return "•••"
    prefix = plaintext[:3]
    suffix = plaintext[-3:]
    return f"{prefix}•••{suffix}"