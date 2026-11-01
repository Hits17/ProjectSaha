"""
NVIDIA NIM provider — uses OpenAI-compatible endpoint.
Free tier: 40 requests/minute, no credit card required.
Sign up at https://build.nvidia.com to get an nvapi-* key.
"""

import httpx
from app.core.config import settings

DEFAULT_MODEL = settings.NVIDIA_CHAT_MODEL
_BASE_URL = "https://integrate.api.nvidia.com/v1"


async def complete(messages, model=None, temperature=0.7, max_tokens=2000, stream=False):
    from app.ai.client import LLMResponse, Provider

    model = model or DEFAULT_MODEL

    payload = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    # DiffusionGemma is a "thinking" model: without enable_thinking it returns
    # empty content on the OpenAI-compatible endpoint. The reasoning goes to a
    # separate field; the answer still lands in message.content.
    if "diffusiongemma" in model:
        payload["chat_template_kwargs"] = {"enable_thinking": True}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return LLMResponse(
        content=data["choices"][0]["message"]["content"],
        provider=Provider.NVIDIA,
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
