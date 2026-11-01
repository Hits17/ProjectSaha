"""
Provider-agnostic LLM client for Saha.

Routes calls to Anthropic, NVIDIA NIM, or Ollama based on:
1. Explicit provider override in the call
2. Function-level routing in provider_routing.py
3. Global LLM_PROVIDER env setting
4. Fallback to anthropic
"""

from enum import Enum
from typing import AsyncIterator, Optional
from pydantic import BaseModel
from app.core.config import settings


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    NVIDIA = "nvidia"
    OLLAMA = "ollama"


class Message(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResponse(BaseModel):
    content: str
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """The one client every service uses for AI calls."""

    async def complete(
        self,
        messages: list[Message],
        function_name: str,
        provider: Optional[Provider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> LLMResponse | AsyncIterator[str]:
        from app.ai import provider_routing
        from app.ai.providers import anthropic, nvidia, ollama

        resolved_provider = (
            provider
            or provider_routing.get_provider_for_function(function_name)
            or Provider(settings.LLM_PROVIDER)
        )

        if resolved_provider == Provider.ANTHROPIC:
            return await anthropic.complete(messages, model, temperature, max_tokens, stream)
        elif resolved_provider == Provider.NVIDIA:
            return await nvidia.complete(messages, model, temperature, max_tokens, stream)
        elif resolved_provider == Provider.OLLAMA:
            return await ollama.complete(messages, model, temperature, max_tokens, stream)
        else:
            raise ValueError(f"Unknown provider: {resolved_provider}")

    async def ping(self) -> dict:
        """Test the configured default provider. Used by /health."""
        from app.ai import provider_routing
        from app.ai.providers import anthropic, nvidia, ollama

        global_setting = settings.LLM_PROVIDER
        if global_setting == "auto":
            global_setting = "nvidia"

        try:
            provider = Provider(global_setting)
        except ValueError:
            provider = Provider.ANTHROPIC

        if provider == Provider.ANTHROPIC:
            ok, model = await anthropic.ping()
        elif provider == Provider.NVIDIA:
            ok, model = await nvidia.ping()
        else:
            ok, model = await ollama.ping()

        return {"active": provider.value, "status": "healthy" if ok else "unhealthy", "model": model}


llm = LLMClient()
