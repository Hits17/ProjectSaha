"""
Anthropic Claude provider.
Used for legal assistant and any time quality matters more than dev cost.
"""

from anthropic import AsyncAnthropic
from app.core.config import settings

DEFAULT_MODEL = "claude-sonnet-4-6"

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def complete(messages, model=None, temperature=0.7, max_tokens=2000, stream=False):
    from app.ai.client import LLMResponse, Provider

    model = model or DEFAULT_MODEL
    client = _get_client()

    system_msg = None
    user_messages = []
    for msg in messages:
        if msg.role == "system":
            system_msg = msg.content
        else:
            user_messages.append({"role": msg.role, "content": msg.content})

    response = await client.messages.create(
        model=model,
        system=system_msg or "",
        messages=user_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return LLMResponse(
        content=response.content[0].text,
        provider=Provider.ANTHROPIC,
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
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
