"""
Ollama provider — fully local on the Jetson. Uses OpenAI-compatible endpoint.
"""

import httpx
from app.core.config import settings

DEFAULT_MODEL = "llama3.2:3b"  # Small enough for 8GB Jetson


async def complete(messages, model=None, temperature=0.7, max_tokens=2000, stream=False):
    from app.ai.client import LLMResponse, Provider

    model = model or DEFAULT_MODEL

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [m.model_dump() for m in messages],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            },
        )
        response.raise_for_status()
        data = response.json()

    return LLMResponse(
        content=data["choices"][0]["message"]["content"],
        provider=Provider.OLLAMA,
        model=model,
        input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
        output_tokens=data.get("usage", {}).get("completion_tokens", 0),
    )


async def ping(model: str = DEFAULT_MODEL) -> tuple[bool, str]:
    try:
        from app.ai.client import Message
        await complete(
            messages=[Message(role="user", content="ping")],
            model=model,
            max_tokens=5,
        )
        return True, model
    except Exception as e:
        return False, str(e)
