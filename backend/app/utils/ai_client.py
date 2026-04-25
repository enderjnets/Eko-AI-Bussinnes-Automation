import openai
from app.config import get_settings

settings = get_settings()

# Determine provider and configure client
if settings.AI_PROVIDER == "kimi" and settings.KIMI_API_KEY:
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


async def generate_completion(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """Generate a completion using configured AI provider."""
    model = model or CHAT_MODEL
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    
    response = await openai_client.chat.completions.create(**kwargs)
    
    # Kimi returns reasoning_content separately; use content for the actual output
    msg = response.choices[0].message
    content = msg.content or ""
    
    # Fallback to reasoning_content when content is empty (kimi-for-coding behavior)
    if not content and hasattr(msg, "reasoning_content"):
        content = msg.reasoning_content or ""
    
    return content


async def generate_embedding(text: str, model: str = None) -> list:
    """Generate an embedding for the given text."""
    model = model or EMBEDDING_MODEL
    
    # For local sentence-transformers (when using kimi provider)
    if settings.AI_PROVIDER == "kimi" and settings.KIMI_API_KEY:
        from sentence_transformers import SentenceTransformer
        
        # Lazy-load model (cached after first call)
        if not hasattr(generate_embedding, "_model"):
            generate_embedding._model = SentenceTransformer("all-MiniLM-L6-v2")
        
        embedding = generate_embedding._model.encode(text)
        return embedding.tolist()
    
    # OpenAI embeddings
    response = await openai_client.embeddings.create(
        model=model,
        input=text,
    )
    return response.data[0].embedding
