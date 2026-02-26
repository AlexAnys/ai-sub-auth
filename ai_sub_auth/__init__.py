"""ai-sub-auth — Reuse your AI subscriptions. One module, every provider.

Built on patterns from nanobot (HKUDS/nanobot) Provider Registry
and oauth-cli-kit's OAuth PKCE flow.

Supports: OpenAI Codex (OAuth), Claude (API Key), GitHub Copilot (Device Code),
Google Gemini (API Key), DeepSeek, OpenRouter, and custom providers.
"""

from ai_sub_auth.models import OAuthToken, ProviderConfig, AuthMethod, LLMResponse
from ai_sub_auth.exceptions import AuthError, TokenExpiredError, ProviderNotFoundError
from ai_sub_auth.token_store import TokenStore
from ai_sub_auth.oauth_flow import oauth_login, get_or_refresh_token
from ai_sub_auth.providers import PROVIDERS, get_provider, find_provider_by_model
from ai_sub_auth.api_client import LLMClient
from ai_sub_auth.skills import META_SKILLS, AppProfile, Suggestion, Skill, suggest_for_app

__version__ = "0.1.0"

__all__ = [
    "OAuthToken", "ProviderConfig", "AuthMethod", "LLMResponse",
    "AuthError", "TokenExpiredError", "ProviderNotFoundError",
    "TokenStore",
    "oauth_login", "get_or_refresh_token",
    "PROVIDERS", "get_provider", "find_provider_by_model",
    "LLMClient",
    "META_SKILLS", "AppProfile", "Suggestion", "Skill", "suggest_for_app",
]
