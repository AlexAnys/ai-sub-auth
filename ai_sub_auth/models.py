"""Data models — inspired by oauth-cli-kit's OAuthToken + nanobot's ProviderSpec."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuthMethod(Enum):
    """Supported authentication methods."""
    API_KEY = "api_key"         # Standard API key (Anthropic, OpenAI, DeepSeek...)
    OAUTH_PKCE = "oauth_pkce"   # OAuth 2.0 + PKCE (OpenAI Codex)
    DEVICE_CODE = "device"      # Device Code Flow (GitHub Copilot)


@dataclass(frozen=True)
class ProviderConfig:
    """Provider configuration — distilled from nanobot's ProviderSpec
    and oauth-cli-kit's OAuthProviderConfig into a single dataclass.

    Covers both API key and OAuth modes in one structure.
    """
    # Identity
    name: str
    display_name: str
    auth_method: AuthMethod

    # API key mode
    env_key: str = ""               # Environment variable name, e.g. "ANTHROPIC_API_KEY"
    api_base: str = ""              # API endpoint base URL

    # OAuth PKCE mode
    client_id: str = ""
    authorize_url: str = ""
    token_url: str = ""
    redirect_uri: str = "http://localhost:1455/auth/callback"
    scope: str = ""
    jwt_claim_path: str | None = None
    account_id_claim: str | None = None

    # Token storage filename
    token_filename: str = ""

    # Model name keywords for auto-matching (nanobot pattern)
    keywords: tuple[str, ...] = ()


@dataclass
class OAuthToken:
    """OAuth token — compatible with oauth-cli-kit's OAuthToken format."""
    access: str
    refresh: str
    expires: int                    # Millisecond timestamp
    account_id: str | None = None

    @property
    def is_expired(self) -> bool:
        return int(time.time() * 1000) >= self.expires

    @property
    def ttl_seconds(self) -> float:
        return max(0, (self.expires - int(time.time() * 1000)) / 1000)


@dataclass
class LLMResponse:
    """Unified LLM response across all providers."""
    content: str | None = None
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None
