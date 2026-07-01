"""
Live model fetcher — asks each provider's API for its available models.

The admin only stores name + family + key. When the IT opens the model
picker, the backend calls the provider's /models endpoint LIVE and returns
every model the API reports (no filtering, no hardcoded list).

Endpoints per family:
  OPENAI     GET https://api.openai.com/v1/models          (Bearer key)
  GROQ       GET https://api.groq.com/openai/v1/models      (Bearer key, OpenAI-compatible)
  ANTHROPIC  GET https://api.anthropic.com/v1/models        (x-api-key + anthropic-version)
  GOOGLE     GET https://generativelanguage.googleapis.com/v1beta/models?key=...

Each returns a normalized list: [{"id": "...", "label": "..."}].
Raises HTTPException(400) with a clear message if the call fails
(bad key, network, etc.) so the IT sees why.
"""
import requests
from fastapi import HTTPException

TIMEOUT = 15


def _openai_like(base: str, api_key: str) -> list:
    """OpenAI and Groq share the same /models shape."""
    r = requests.get(
        f"{base}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=TIMEOUT,
    )
    if r.status_code == 401:
        raise HTTPException(400, "Invalid API key for this provider.")
    r.raise_for_status()
    data = r.json().get("data", [])
    models = []
    for m in data:
        mid = m.get("id")
        if mid:
            models.append({"id": mid, "label": mid})
    return models


def _fetch_openai(api_key: str, base_url: str = "") -> list:
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    return _openai_like(base, api_key)


def _fetch_groq(api_key: str, base_url: str = "") -> list:
    base = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
    return _openai_like(base, api_key)


def _fetch_anthropic(api_key: str, base_url: str = "") -> list:
    base = (base_url or "https://api.anthropic.com/v1").rstrip("/")
    r = requests.get(
        f"{base}/models",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=TIMEOUT,
    )
    if r.status_code == 401:
        raise HTTPException(400, "Invalid API key for Anthropic.")
    r.raise_for_status()
    data = r.json().get("data", [])
    models = []
    for m in data:
        mid = m.get("id")
        if mid:
            label = m.get("display_name") or mid
            models.append({"id": mid, "label": label})
    return models


def _fetch_google(api_key: str, base_url: str = "") -> list:
    base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    r = requests.get(f"{base}/models", params={"key": api_key}, timeout=TIMEOUT)
    if r.status_code in (400, 401, 403):
        raise HTTPException(400, "Invalid API key for Google Gemini.")
    r.raise_for_status()
    data = r.json().get("models", [])
    models = []
    for m in data:
        name = m.get("name", "")  # e.g. "models/gemini-2.5-flash"
        mid = name.split("/", 1)[1] if "/" in name else name
        if mid:
            label = m.get("displayName") or mid
            models.append({"id": mid, "label": label})
    return models


_FETCHERS = {
    "OPENAI": _fetch_openai,
    "GROQ": _fetch_groq,
    "ANTHROPIC": _fetch_anthropic,
    "GOOGLE": _fetch_google,
}


def fetch_models(family: str, api_key: str, base_url: str = "") -> list:
    """
    Return the live list of models for a provider family.
    Raises HTTPException(400) on any failure with a readable message.
    """
    fam = (family or "").upper()
    fetcher = _FETCHERS.get(fam)
    if not fetcher:
        raise HTTPException(400, f"Live model listing not supported for {family}.")
    if not api_key:
        raise HTTPException(400, "This provider has no API key set.")
    try:
        return fetcher(api_key, base_url)
    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        raise HTTPException(400, "The provider took too long to respond. Try again.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(400, f"Could not reach the provider: {str(e)[:120]}")