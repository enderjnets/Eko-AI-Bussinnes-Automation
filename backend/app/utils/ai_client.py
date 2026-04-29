import openai
import re
from app.config import get_settings

settings = get_settings()

# Pre-compiled regex for stripping MiniMax <think> tags
_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# Initialize primary client based on AI_PROVIDER
if settings.AI_PROVIDER == "minimax" and settings.MINIMAX_API_KEY:
    openai_client = openai.AsyncOpenAI(
        api_key=settings.MINIMAX_API_KEY,
        base_url=settings.MINIMAX_BASE_URL,
    )
    CHAT_MODEL = settings.MINIMAX_MODEL
    EMBEDDING_MODEL = settings.MINIMAX_EMBEDDING_MODEL
elif settings.AI_PROVIDER == "ollama":
    openai_client = openai.AsyncOpenAI(
        api_key="ollama",
        base_url=settings.OLLAMA_BASE_URL,
    )
    CHAT_MODEL = settings.OLLAMA_MODEL
    EMBEDDING_MODEL = settings.OLLAMA_EMBEDDING_MODEL
elif settings.AI_PROVIDER == "kimi" and settings.KIMI_API_KEY:
    openai_client = openai.AsyncOpenAI(
        api_key=settings.KIMI_API_KEY,
        base_url=settings.KIMI_BASE_URL,
        default_headers={
            "User-Agent": "claude-code/2.1.50",
        },
    )
    CHAT_MODEL = settings.KIMI_MODEL
    EMBEDDING_MODEL = settings.KIMI_EMBEDDING_MODEL
else:
    openai_client = openai.AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )
    CHAT_MODEL = settings.OPENAI_MODEL
    EMBEDDING_MODEL = settings.OPENAI_EMBEDDING_MODEL

# Initialize fallback client — use a different provider than primary
_fallback_client = None
_fallback_model = None
_fallback_provider = None

if settings.AI_PROVIDER == "kimi":
    # Primary is Kimi → fallback to OpenAI if available
    if settings.OPENAI_API_KEY:
        _fallback_client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        _fallback_model = settings.OPENAI_MODEL
        _fallback_provider = "openai"
elif settings.AI_PROVIDER in ("openai", "minimax", "ollama"):
    # Primary is OpenAI/Minimax/Ollama → fallback to Kimi if available
    if settings.KIMI_API_KEY:
        _fallback_client = openai.AsyncOpenAI(
            api_key=settings.KIMI_API_KEY,
            base_url=settings.KIMI_BASE_URL,
            default_headers={
                "User-Agent": "claude-code/2.1.50",
            },
        )
        _fallback_model = settings.KIMI_MODEL
        _fallback_provider = "kimi"


def _clean_content(content: str, provider: str) -> str:
    """Clean model-specific formatting from content."""
    if not content:
        return ""
    if provider == "minimax":
        import re
        content = _THINK_TAG_RE.sub("", content)
    return content


async def _try_completion(
    client: openai.AsyncOpenAI,
    model: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    provider: str,
) -> str:
    """Attempt a completion with a specific client."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        if provider == "kimi":
            # Deep-copy messages so fallback providers don't see the mutated version
            import copy
            kwargs["messages"] = copy.deepcopy(messages)
            kwargs["messages"][0]["content"] += "\n\nIMPORTANT: Your response must be ONLY valid JSON. No markdown, no explanations, no reasoning outside the JSON."
        else:
            kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)

    msg = response.choices[0].message
    content = msg.content or ""

    # Fallback to reasoning_content when content is empty (kimi-for-coding behavior)
    if not content and hasattr(msg, "reasoning_content"):
        content = msg.reasoning_content or ""

    content = _clean_content(content, provider)
    return content


async def generate_completion(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """Generate a completion using configured AI provider with Kimi fallback."""
    model = model or CHAT_MODEL

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Try primary provider first
    primary_provider = settings.AI_PROVIDER
    try:
        return await _try_completion(
            openai_client, model, messages, temperature, max_tokens, json_mode, primary_provider
        )
    except Exception as primary_err:
        # If fallback is available, try it
        if _fallback_client and _fallback_model:
            try:
                return await _try_completion(
                    _fallback_client, _fallback_model, messages, temperature, max_tokens, json_mode, _fallback_provider or "openai"
                )
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Both primary ({primary_provider}) and fallback (kimi) failed. "
                    f"Primary error: {primary_err}. Fallback error: {fallback_err}"
                )
        # No fallback available, re-raise original error
        raise


async def generate_embedding(text: str, model: str = None) -> list:
    """Generate an embedding for the given text."""
    model = model or EMBEDDING_MODEL

    # For local sentence-transformers (when using kimi or minimax provider)
    if settings.AI_PROVIDER in ("kimi", "minimax"):
        import asyncio
        from sentence_transformers import SentenceTransformer

        # Lazy-load model (cached after first call)
        if not hasattr(generate_embedding, "_model"):
            generate_embedding._model = SentenceTransformer("all-MiniLM-L6-v2")

        # Run CPU-bound encoding in a thread pool to avoid blocking the async loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, generate_embedding._model.encode, text
        )
        return embedding.tolist()

    # OpenAI embeddings
    response = await openai_client.embeddings.create(
        model=model,
        input=text,
    )
    return response.data[0].embedding
