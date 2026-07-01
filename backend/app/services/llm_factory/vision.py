"""
Vision — describe an image with a multimodal LLM, for the image-RAG pipeline.

Used to turn an extracted image into a TEXT summary that gets embedded and
made searchable (the original image is kept separately and shown on retrieval).

Supports OPENAI (gpt-4o family) and GOOGLE (gemini) — both handle images via
LangChain's multimodal message format. We pass the image as base64.

resolve the provider/key the same way as text (resolver), but vision needs a
provider that actually supports images, so we let the caller pass family/model.
"""
import base64
import logging

logger = logging.getLogger(__name__)


VISION_PROMPT = (
    "Describe this image in detail for search and retrieval. "
    "State what it shows, any visible text, numbers, labels, chart type, "
    "and the key information a reader would want. Be factual and concise."
)


def _b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def describe_image(
    image_path: str,
    family: str,
    model: str,
    api_key: str,
    prompt: str = VISION_PROMPT,
    base_url: str = "",
) -> str:
    """
    Return a text description of the image using a vision-capable LLM.

    family ∈ {OPENAI, GOOGLE}.  (Groq/local text models can't see images.)
    """
    fam = (family or "OPENAI").upper()
    b64 = _b64(image_path)

    if fam == "OPENAI":
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(model=model or "gpt-4o-mini", api_key=api_key,
                         max_tokens=500,
                         **({"base_url": base_url} if base_url else {}))
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ])
        return llm.invoke([message]).content

    if fam == "GOOGLE":
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(model=model or "gemini-2.5-flash",
                                     google_api_key=api_key, max_output_tokens=500)
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": f"data:image/png;base64,{b64}"},
        ])
        return llm.invoke([message]).content

    raise ValueError(f"Vision not supported for family: {family} (use OPENAI or GOOGLE)")