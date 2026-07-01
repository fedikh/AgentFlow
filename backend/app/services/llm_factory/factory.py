"""
LLM Factory — returns a ready-to-use LangChain chat client for any provider.

All providers expose the SAME interface: `.invoke(messages)` where messages is
a list of SystemMessage / HumanMessage. So the rest of the app never needs to
know which provider is behind it — it just calls .invoke().

Supported families: GROQ (free), OPENAI, ANTHROPIC, GOOGLE (Gemini),
LOCAL/OLLAMA. Add a new one by adding a branch here.

The factory does NOT decide which key to use — that's resolver.py's job.
The factory just takes a resolved (provider, model, key) and builds the client.
"""
import logging

logger = logging.getLogger(__name__)


def get_llm(
    family: str,
    model: str,
    api_key: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    base_url: str = "",
):
    """
    Build a LangChain chat model for the given provider family.

    family ∈ {GROQ, OPENAI, ANTHROPIC, GOOGLE, OLLAMA, LOCAL, CUSTOM}
    Returns an object with .invoke(messages) -> response (response.content = text).
    """
    fam = (family or "GROQ").upper()

    if fam == "GROQ":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model or "llama-3.3-70b-versatile",
            temperature=temperature,
            max_tokens=max_tokens,
            groq_api_key=api_key,
        )

    if fam == "OPENAI":
        from langchain_openai import ChatOpenAI
        kwargs = dict(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    if fam == "ANTHROPIC":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-haiku-4-5",
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    if fam == "GOOGLE":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.5-flash",
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=api_key,
        )

    if fam in ("OLLAMA", "LOCAL"):
        # Local model via Ollama — no API key needed.
        from langchain_ollama import ChatOllama
        kwargs = dict(model=model or "llama3", temperature=temperature)
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOllama(**kwargs)

    if fam == "CUSTOM":
        # Custom OpenAI-compatible endpoint (vLLM, LM Studio, etc.)
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "default",
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key or "not-needed",
            base_url=base_url,
        )

    raise ValueError(f"Unknown LLM family: {family}")