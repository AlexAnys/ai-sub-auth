"""Unified LLM API client — inspired by nanobot's provider abstraction layer.

Automatically selects auth method based on provider type:
- API Key: Standard Bearer token / x-api-key header
- OAuth PKCE: Auto-retrieve and refresh OAuth tokens
- Device Code: Delegates to LiteLLM (GitHub Copilot)
"""

from __future__ import annotations

import json
import os
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
        message: str,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat request, auto-routed to the correct provider API."""
        model = model or self.model

        dispatch = {
            "openai_codex": self._chat_codex,
            "anthropic": self._chat_anthropic,
            "google_gemini": self._chat_gemini,
        }
        handler = dispatch.get(self.provider.name, self._chat_openai_compat)
        return await handler(message, system, model, max_tokens, temperature)

    # ── OpenAI Codex (Responses API, SSE) ──

    async def _chat_codex(self, message, system, model, max_tokens, temperature) -> LLMResponse:
        """Codex Responses API — from nanobot/providers/openai_codex_provider.py."""
        headers = self._get_auth_headers()
        headers.update({
            "OpenAI-Beta": "responses=experimental",
            "originator": "ai-sub-auth",
            "User-Agent": "ai-sub-auth",
            "accept": "text/event-stream",
            "content-type": "application/json",
        })

        bare_model = model.split("/", 1)[-1] if model and "/" in model else (model or "gpt-5.1-codex")
        body = {
            "model": bare_model,
            "store": False,
            "stream": True,
            "instructions": system,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": message}]}],
            "text": {"verbosity": "medium"},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", self.provider.api_base, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise AuthError(f"Codex API error {resp.status_code}: {text.decode()}")
                return await self._consume_codex_sse(resp)

    async def _consume_codex_sse(self, response) -> LLMResponse:
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
            except Exception:
                continue
            if event.get("type") == "response.output_text.delta":
                content += event.get("delta", "")
        return LLMResponse(content=content)

    # ── Anthropic Messages API ──

    async def _chat_anthropic(self, message, system, model, max_tokens, temperature) -> LLMResponse:
        headers = self._get_auth_headers()
        headers["content-type"] = "application/json"
        body: dict[str, Any] = {
            "model": model or "claude-sonnet-4-5-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": message}],
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

    async def _chat_gemini(self, message, system, model, max_tokens, temperature) -> LLMResponse:
        model = model or "gemini-2.0-flash"
        url = f"{self.provider.api_base}/models/{model}:generateContent?key={self.api_key}"

        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body, headers={"content-type": "application/json"})

        if resp.status_code != 200:
            raise AuthError(f"Gemini API error {resp.status_code}: {resp.text}")

        data = resp.json()
        candidates = data.get("candidates", [{}])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=text,
            finish_reason=candidates[0].get("finishReason", "STOP") if candidates else "STOP",
            usage={"input": usage.get("promptTokenCount", 0), "output": usage.get("candidatesTokenCount", 0)},
            raw=data,
        )

    # ── OpenAI-Compatible API (OpenAI, DeepSeek, OpenRouter...) ──

    async def _chat_openai_compat(self, message, system, model, max_tokens, temperature) -> LLMResponse:
        headers = self._get_auth_headers()
        headers["content-type"] = "application/json"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        body = {
            "model": model or "gpt-4o",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
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
