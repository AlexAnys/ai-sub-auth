"""Unified LLM API client — inspired by nanobot's provider abstraction layer.

Automatically selects auth method based on provider type:
- API Key: Standard Bearer token / x-api-key header
- OAuth PKCE: Auto-retrieve and refresh OAuth tokens
- Device Code: Delegates to LiteLLM (GitHub Copilot)
"""

from __future__ import annotations

import json
import os
import warnings
from typing import Any

import httpx

from ai_sub_auth.models import AuthMethod, LLMResponse, ProviderConfig
from ai_sub_auth.oauth_flow import get_or_refresh_token
from ai_sub_auth.exceptions import AuthError


class LLMClient:
    """Unified LLM client that routes to the correct API based on provider.

    Usage:
        client = LLMClient(provider, api_key="sk-...")   # API key mode
        client = LLMClient(provider)                      # OAuth mode (auto-reads token)
        resp = await client.chat("Hello")
    """

    def __init__(
        self,
        provider: ProviderConfig,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.provider = provider
        self.api_key = api_key or os.environ.get(provider.env_key, "")
        self.model = model

        if provider.auth_method == AuthMethod.API_KEY and not self.api_key:
            raise AuthError(
                f"API key required for {provider.display_name}. "
                f"Pass api_key= or set {provider.env_key}."
            )

    def _get_auth_headers(self) -> dict[str, str]:
        """Build auth headers based on provider type."""
        if self.provider.auth_method == AuthMethod.OAUTH_PKCE:
            token = get_or_refresh_token(self.provider)
            headers = {"Authorization": f"Bearer {token.access}"}
            if token.account_id:
                headers["chatgpt-account-id"] = token.account_id
            return headers

        if self.provider.auth_method == AuthMethod.API_KEY:
            if self.provider.name == "anthropic":
                return {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                }
            if self.provider.name == "google_gemini":
                return {}  # Gemini uses query param for API key
            return {"Authorization": f"Bearer {self.api_key}"}

        return {}

    async def chat(
        self,
        message: str = "",
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        """Send a chat request, auto-routed to the correct provider API.

        Args:
            message: Single user message string (simple mode).
            messages: Multi-turn conversation as list of {"role": ..., "content": ...}.
                      If provided, takes precedence over `message`.
        """
        model = model or self.model
        if not model:
            raise AuthError("Model is required — pass model to LLMClient() or chat()")

        dispatch = {
            "openai_codex": self._chat_codex,
            "anthropic": self._chat_anthropic,
            "google_gemini": self._chat_gemini,
        }
        handler = dispatch.get(self.provider.name, self._chat_openai_compat)
        return await handler(message, system, model, max_tokens, temperature, messages)

    # ── OpenAI Codex (Responses API, SSE) ──

    async def _chat_codex(
        self, message: str, system: str, model: str, max_tokens: int, temperature: float,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        """Codex Responses API — from nanobot/providers/openai_codex_provider.py."""
        headers = self._get_auth_headers()
        headers.update({
            "OpenAI-Beta": "responses=experimental",
            "originator": "ai-sub-auth",
            "User-Agent": "ai-sub-auth",
            "accept": "text/event-stream",
            "content-type": "application/json",
        })

        bare_model = model.split("/", 1)[-1] if "/" in model else model
        if messages:
            input_items = [
                {"role": m["role"], "content": [{"type": "input_text", "text": m["content"]}]}
                for m in messages
            ]
        else:
            input_items = [{"role": "user", "content": [{"type": "input_text", "text": message}]}]
        body = {
            "model": bare_model,
            "store": False,
            "stream": True,
            "instructions": system,
            "input": input_items,
            "text": {"verbosity": "medium"},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", self.provider.api_base, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise AuthError(f"Codex API error {resp.status_code}: {text.decode()}")
                return await self._consume_codex_sse(resp)

    async def _consume_codex_sse(self, response: httpx.Response) -> LLMResponse:
        """Parse Codex SSE stream."""
        content = ""
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                warnings.warn(f"Skipping malformed SSE JSON: {data[:100]}")
                continue
            if event.get("type") == "response.output_text.delta":
                content += event.get("delta", "")
        return LLMResponse(content=content)

    # ── Anthropic Messages API ──

    async def _chat_anthropic(
        self, message: str, system: str, model: str, max_tokens: int, temperature: float,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        headers = self._get_auth_headers()
        headers["content-type"] = "application/json"
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages if messages else [{"role": "user", "content": message}],
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.provider.api_base}/v1/messages", headers=headers, json=body)

        if resp.status_code != 200:
            raise AuthError(f"Anthropic API error {resp.status_code}: {resp.text}")

        data = resp.json()
        text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(
            content=text,
            finish_reason=data.get("stop_reason", "stop"),
            usage={"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)},
            raw=data,
        )

    # ── Google Gemini API ──

    async def _chat_gemini(
        self, message: str, system: str, model: str, max_tokens: int, temperature: float,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        url = f"{self.provider.api_base}/models/{model}:generateContent?key={self.api_key}"

        if messages:
            # Gemini uses "model" instead of "assistant" for role
            contents = [
                {"role": "model" if m["role"] == "assistant" else m["role"],
                 "parts": [{"text": m["content"]}]}
                for m in messages
            ]
        else:
            contents = [{"role": "user", "parts": [{"text": message}]}]

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body, headers={"content-type": "application/json"})

        if resp.status_code != 200:
            raise AuthError(f"Gemini API error {resp.status_code}: {resp.text}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates or "content" not in candidates[0]:
            raise AuthError(
                f"Gemini returned no candidates: {data.get('promptFeedback', 'unknown reason')}"
            )
        parts = candidates[0]["content"].get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=text,
            finish_reason=candidates[0].get("finishReason", "STOP"),
            usage={"input": usage.get("promptTokenCount", 0), "output": usage.get("candidatesTokenCount", 0)},
            raw=data,
        )

    # ── OpenAI-Compatible API (OpenAI, DeepSeek, OpenRouter...) ──

    async def _chat_openai_compat(
        self, message: str, system: str, model: str, max_tokens: int, temperature: float,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        headers = self._get_auth_headers()
        headers["content-type"] = "application/json"
        if messages:
            chat_messages = list(messages)
            if system and not any(m["role"] == "system" for m in chat_messages):
                chat_messages.insert(0, {"role": "system", "content": system})
        else:
            chat_messages = []
            if system:
                chat_messages.append({"role": "system", "content": system})
            chat_messages.append({"role": "user", "content": message})

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }

        base = self.provider.api_base.rstrip("/")
        url = f"{base}/chat/completions"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=body)

        if resp.status_code != 200:
            raise AuthError(f"API error {resp.status_code}: {resp.text}")

        data = resp.json()
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            raw=data,
        )
