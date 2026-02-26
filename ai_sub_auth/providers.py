"""Provider registry — inspired by nanobot's providers/registry.py.

All provider configs are managed here. Adding a new provider = appending one ProviderConfig.

Note (2026-02):
- OpenAI Codex OAuth: Works with ChatGPT Plus/Pro subscription
- Claude OAuth: Blocked by Anthropic (Jan 2026) for third-party tools → use API key
- GitHub Copilot: Device code flow via LiteLLM
- Google Gemini: API key (OAuth 2.0 support planned)
"""

from __future__ import annotations

from ai_sub_auth.models import AuthMethod, ProviderConfig
from ai_sub_auth.exceptions import ProviderNotFoundError


# ── Provider Configs ──────────────────────────────────────

OPENAI_CODEX = ProviderConfig(
    name="openai_codex",
    display_name="OpenAI Codex",
    auth_method=AuthMethod.OAUTH_PKCE,
    api_base="https://chatgpt.com/backend-api/codex/responses",
    # OAuth config (from oauth-cli-kit/providers/openai_codex.py)
    client_id="app_EMoamEEZ73f0CkXaXp7hrann",
    authorize_url="https://auth.openai.com/oauth/authorize",
    token_url="https://auth.openai.com/oauth/token",
    redirect_uri="http://localhost:1455/auth/callback",
    scope="openid profile email offline_access",
    jwt_claim_path="https://api.openai.com/auth",
    account_id_claim="chatgpt_account_id",
    token_filename="codex.json",
    keywords=("codex", "openai-codex"),
)

ANTHROPIC_API = ProviderConfig(
    name="anthropic",
    display_name="Claude (API Key)",
    auth_method=AuthMethod.API_KEY,
    env_key="ANTHROPIC_API_KEY",
    api_base="https://api.anthropic.com",
    keywords=("claude", "anthropic"),
)

OPENAI_API = ProviderConfig(
    name="openai",
    display_name="OpenAI (API Key)",
    auth_method=AuthMethod.API_KEY,
    env_key="OPENAI_API_KEY",
    api_base="https://api.openai.com/v1",
    keywords=("gpt", "openai"),
)

GITHUB_COPILOT = ProviderConfig(
    name="github_copilot",
    display_name="GitHub Copilot",
    auth_method=AuthMethod.DEVICE_CODE,
    keywords=("copilot", "github-copilot"),
)

GOOGLE_GEMINI = ProviderConfig(
    name="google_gemini",
    display_name="Google Gemini",
    auth_method=AuthMethod.API_KEY,
    env_key="GEMINI_API_KEY",
    api_base="https://generativelanguage.googleapis.com/v1beta",
    keywords=("gemini", "google"),
)

DEEPSEEK = ProviderConfig(
    name="deepseek",
    display_name="DeepSeek",
    auth_method=AuthMethod.API_KEY,
    env_key="DEEPSEEK_API_KEY",
    api_base="https://api.deepseek.com",
    keywords=("deepseek",),
)

OPENROUTER = ProviderConfig(
    name="openrouter",
    display_name="OpenRouter",
    auth_method=AuthMethod.API_KEY,
    env_key="OPENROUTER_API_KEY",
    api_base="https://openrouter.ai/api/v1",
    keywords=("openrouter",),
)


# ── Registry ──────────────────────────────────────────

PROVIDERS: dict[str, ProviderConfig] = {
    p.name: p for p in [
        OPENAI_CODEX, ANTHROPIC_API, OPENAI_API,
        GITHUB_COPILOT, GOOGLE_GEMINI, DEEPSEEK, OPENROUTER,
    ]
}


def get_provider(name: str) -> ProviderConfig:
    """Look up provider by name. Raises ProviderNotFoundError if not found."""
    key = name.replace("-", "_")
    provider = PROVIDERS.get(key)
    if not provider:
        available = ", ".join(PROVIDERS.keys())
        raise ProviderNotFoundError(f"Unknown provider: {name}. Available: {available}")
    return provider


def find_provider_by_model(model: str) -> ProviderConfig | None:
    """Auto-match provider by model name keywords (nanobot's find_by_model pattern).

    Priority: explicit prefix ("openai-codex/gpt-4o") > keyword match ("claude-...").
    """
    model_lower = model.lower()

    # Explicit prefix: "openai-codex/gpt-4o" → openai_codex
    if "/" in model_lower:
        prefix = model_lower.split("/", 1)[0].replace("-", "_")
        if prefix in PROVIDERS:
            return PROVIDERS[prefix]

    # Keyword match
    for p in PROVIDERS.values():
        if any(kw in model_lower for kw in p.keywords):
            return p
    return None
