"""AI Facade — the simplest possible integration API.

    from ai_sub_auth import AI
    ai = AI()              # auto-detect provider
    ai.connect()           # OAuth login or verify API key
    result = await ai.chat("Hello!")
    result = ai.chat_sync("Hello!")
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import AsyncIterator

from ai_sub_auth.api_client import LLMClient
from ai_sub_auth.exceptions import AuthError
from ai_sub_auth.models import AuthMethod, LLMResponse
from ai_sub_auth.oauth_flow import oauth_login
from ai_sub_auth.providers import PROVIDERS, get_provider
from ai_sub_auth.token_store import TokenStore


@dataclass
class SubscriptionStatus:
    """Current subscription/connection status."""
    connected: bool
    provider_name: str
    auth_method: AuthMethod
    account_id: str | None = None
    token_expires_in: float | None = None
    needs_reauth: bool = False


# Default models per provider
_DEFAULT_MODELS: dict[str, str] = {
    "openai_codex": "codex/gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google_gemini": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "openrouter": "openrouter/auto",
}

# Auto-detection order: OAuth token first, then API keys
_DETECT_ORDER: list[str] = [
    "openai_codex", "anthropic", "openai", "google_gemini", "deepseek", "openrouter",
]


def _auto_detect_provider() -> ProviderConfig:
    """Auto-detect the best available provider."""
    # Check for existing Codex OAuth token
    codex = PROVIDERS["openai_codex"]
    store = TokenStore(filename=codex.token_filename)
    if store.load() or store.try_import_codex_cli():
        return codex

    # Check API key env vars
    for name in _DETECT_ORDER[1:]:
        p = PROVIDERS[name]
        if p.env_key and os.environ.get(p.env_key):
            return p

    raise AuthError(
        "No AI provider detected. Options:\n"
        "  1. Run ai.connect() with provider='openai_codex' for ChatGPT Plus OAuth\n"
        "  2. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or another provider env var"
    )


class AI:
    """The simplest way to use AI subscriptions."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
    ):
        if provider:
            self._provider = get_provider(provider)
        elif api_key:
            if api_key.startswith("sk-ant-"):
                self._provider = PROVIDERS["anthropic"]
            else:
                self._provider = PROVIDERS["openai"]
        else:
            self._provider = _auto_detect_provider()

        self._api_key = api_key
        self._model = model or _DEFAULT_MODELS.get(self._provider.name)
        self._user_id = user_id
        self._client: LLMClient | None = None
        self._connected = False

    def connect(self, log=print) -> None:
        """Connect to the AI provider. OAuth login or API key verification."""
        if self._connected and self._client:
            return

        if self._provider.auth_method == AuthMethod.OAUTH_PKCE:
            store = TokenStore(filename=self._provider.token_filename)
            token = store.load()
            if not token:
                token = store.try_import_codex_cli()
            if token and not token.is_expired:
                log(f"Connected to {self._provider.display_name} (existing token)")
            else:
                log(f"Logging in to {self._provider.display_name} via OAuth...")
                token = oauth_login(self._provider, store=store, log=log)
            self._client = LLMClient(self._provider, model=self._model)
            self._connected = True

        elif self._provider.auth_method == AuthMethod.API_KEY:
            key = self._api_key or os.environ.get(self._provider.env_key, "")
            if not key:
                raise AuthError(
                    f"API key required for {self._provider.display_name}. "
                    f"Set {self._provider.env_key} or pass api_key=."
                )
            self._client = LLMClient(self._provider, api_key=key, model=self._model)
            self._connected = True
            log(f"Connected to {self._provider.display_name} (API key)")

        else:
            raise AuthError(f"Auth method {self._provider.auth_method} not yet supported in facade.")

    def _ensure_connected(self) -> LLMClient:
        if not self._client:
            self.connect()
        assert self._client is not None
        return self._client

    async def chat(
        self,
        message: str = "",
        *,
        system: str = "",
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat message (async). Supports single message or multi-turn."""
        client = self._ensure_connected()
        return await client.chat(
            message=message, system=system,
            model=model or self._model, max_tokens=max_tokens,
            temperature=temperature, messages=messages,
        )

    def chat_sync(
        self,
        message: str = "",
        *,
        system: str = "",
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat message (sync). Safe to call from any context."""
        coro = self.chat(
            message, system=system, model=model, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        # If there's already a running event loop, use a thread
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            result: LLMResponse | None = None
            exc: BaseException | None = None

            def _run():
                nonlocal result, exc
                try:
                    result = asyncio.run(coro)
                except BaseException as e:
                    exc = e

            t = threading.Thread(target=_run)
            t.start()
            t.join()
            if exc:
                raise exc
            assert result is not None
            return result
        else:
            return asyncio.run(coro)

    async def stream(
        self,
        message: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream a chat response. Yields text chunks."""
        # For now, yield the full response as a single chunk.
        # Codex SSE streaming can be enhanced later.
        resp = await self.chat(
            message, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        if resp.content:
            yield resp.content

    @property
    def status(self) -> SubscriptionStatus:
        """Current subscription status."""
        connected = self._connected and self._client is not None
        account_id = None
        expires_in = None
        needs_reauth = False

        if connected and self._provider.auth_method == AuthMethod.OAUTH_PKCE:
            try:
                store = TokenStore(filename=self._provider.token_filename)
                token = store.load()
                if token:
                    account_id = token.account_id
                    expires_in = token.ttl_seconds
                    needs_reauth = token.is_expired
            except Exception:
                needs_reauth = True

        return SubscriptionStatus(
            connected=connected,
            provider_name=self._provider.display_name,
            auth_method=self._provider.auth_method,
            account_id=account_id,
            token_expires_in=expires_in,
            needs_reauth=needs_reauth,
        )

    def get_login_url(self) -> str | None:
        """Get OAuth authorization URL without opening browser. None for API key providers."""
        if self._provider.auth_method != AuthMethod.OAUTH_PKCE:
            return None

        import urllib.parse
        from ai_sub_auth.oauth_flow import _generate_pkce, _create_state

        _, challenge = _generate_pkce()
        state = _create_state()
        params = {
            "response_type": "code",
            "client_id": self._provider.client_id,
            "redirect_uri": self._provider.redirect_uri,
            "scope": self._provider.scope,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return f"{self._provider.authorize_url}?{urllib.parse.urlencode(params)}"
