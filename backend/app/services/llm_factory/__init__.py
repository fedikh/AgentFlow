"""
LLM Factory package — everything LLM-related in one place.

Public API:
    from app.services.llm_factory import generate_answer, get_llm, describe_image

  generate_answer(db, space, question, context, sources_info)
      → the configurable replacement for the old hardcoded Groq generate_answer.

  get_llm(family, model, api_key, ...)
      → low-level: build a LangChain chat client for any provider.

  resolve_llm_config(db, space)
      → which provider/key/model to use for a space (space → company → local).

  describe_image(image_path, family, model, api_key)
      → vision: turn an image into a text summary (for image-RAG).

Embeddings live in a separate embedding factory (to be added later).
"""
from app.services.llm_factory.factory import get_llm
from app.services.llm_factory.resolver import resolve_llm_config
from app.services.llm_factory.generate import generate_answer, DEFAULT_SYSTEM_PROMPT
from app.services.llm_factory.vision import describe_image

__all__ = [
    "get_llm",
    "resolve_llm_config",
    "generate_answer",
    "describe_image",
    "DEFAULT_SYSTEM_PROMPT",
]