"""
Answer generation — the configurable replacement for the old hardcoded
generate_answer() that always used Groq.

Now it:
  - resolves the right provider + key for the space (resolver)
  - builds the right client (factory)
  - uses the space's own system_prompt if set, else a sensible default

Drop-in: call generate_answer(db, space, question, context, sources_info)
instead of the old generate_answer(question, context, sources_info).
"""
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_factory.factory import get_llm
from app.services.llm_factory.resolver import resolve_llm_config

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """You are a professional AI assistant for an enterprise organization.
Answer questions using ONLY the provided context. Format your answers clearly.
Use **bold** for important terms.
If the context doesn't contain relevant information, say so clearly.
Always cite your sources at the end."""


def _build_system_prompt(space, context: str, sources_info: str,
                         history: str = "") -> str:
    """Use the space's custom prompt if present, else the default. `history`
    is the chat layer's memory block (conversation summary + recent
    messages) — the LLM keeps continuity without receiving the whole
    transcript."""
    base = getattr(space, "system_prompt", None) or DEFAULT_SYSTEM_PROMPT
    memory = (f"\n\nCONVERSATION SO FAR (for continuity — answer only the "
              f"CURRENT question):\n{history}" if history else "")
    return f"""{base}{memory}

CONTEXT:
{context}

SOURCES AVAILABLE:
{sources_info}"""


def generate_answer(db, space, question: str, context: str, sources_info: str,
                    history: str = "") -> str:
    """
    Generate an answer using the space's configured LLM provider.
    Falls back to GROQ free model if no paid provider/key is set.
    """
    config = resolve_llm_config(db, space)
    logger.info(f"[GENERATE] provider={config['family']} model={config['model']}")

    llm = get_llm(**config)

    system_prompt = _build_system_prompt(space, context, sources_info, history)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=question)]

    response = llm.invoke(messages)
    return response.content