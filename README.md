# ai-sub-auth

**Reuse your AI subscriptions. One module, every provider. Code + knowledge reference for AI agents.**

English | [中文](./README_CN.md)

You're already paying $20/month for ChatGPT Plus. Why pay again for API access when building your own apps?

`ai-sub-auth` is a lightweight Python module (~600 lines, only depends on `httpx`) that bridges your existing AI subscriptions into any application — no proxy servers, no middleware, no bloat. It serves two purposes:

1. **For developers** — Drop-in AI subscription auth with auto-detection, OAuth PKCE, token management, and a unified API across 7 providers.
2. **For AI agents** — A code + knowledge reference (with [`AGENT.md`](./AGENT.md) and a **Meta Skill Framework**) that teaches agents how to integrate AI capabilities into any application.

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [Subscription Reality (2026)](#subscription-reality-2026)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Comparison with Alternatives](#comparison-with-alternatives)
- [Adding a Custom Provider](#adding-a-custom-provider)
- [Security](#security)
- [Project Structure](#project-structure)
- [Agent Skills — AI Integration Framework](#agent-skills--ai-integration-framework)
- [Credits](#credits)
- [License](#license)

## The Problem

| Pain Point | Details |
|------------|---------|
| **Double payment** | AI subscriptions ($20/mo) + API fees ($50–200/mo) for the same models |
| **Fragmented auth** | Each provider uses different auth flows (OAuth, API keys, device codes) |
| **Proxy overhead** | Existing solutions require running a separate proxy server 24/7 |
| **Token management** | Manual token refresh, insecure storage, no concurrency safety |

## The Solution

```
pip install httpx  # only dependency
```

### Recommended: AI Facade (auto-detects your subscription)

```python
from ai_sub_auth import AI

ai = AI()           # auto-detects ChatGPT Plus OAuth token or API key env vars
ai.connect()        # OAuth login or API key verification

# Async
result = await ai.chat("Summarize this meeting transcript", system="Be concise.")

# Sync (safe in any context — FastAPI, Jupyter, scripts)
result = ai.chat_sync("Summarize this meeting transcript")

# Multi-turn conversation
result = await ai.chat(messages=[
    {"role": "user", "content": "What is quantum computing?"},
    {"role": "assistant", "content": "Quantum computing uses..."},
    {"role": "user", "content": "How does it differ from classical?"},
])
```

### Direct LLMClient (explicit provider control)

```python
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# One-time: login with your ChatGPT Plus/Pro subscription
oauth_login(PROVIDERS["openai_codex"])

# Forever after: just use it
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")
resp = await client.chat("Summarize this meeting transcript")
print(resp.content)
```

Token refresh, secure storage, PKCE — all handled automatically.

## Subscription Reality (2026)

Not all AI subscriptions can be bridged into third-party apps. Here's what actually works:

| Provider | Method | Can Bridge Subscription? | Notes |
|----------|--------|--------------------------|-------|
| **OpenAI ChatGPT Plus/Pro** | OAuth PKCE | ✅ Yes — zero extra cost | OpenAI actively supports this via Codex SDK |
| **Claude** | API Key | ❌ API key only (pay-per-token) | Anthropic banned subscription OAuth (Feb 2026) |
| **OpenAI** | API Key | ❌ API key only (pay-per-token) | Separate from ChatGPT subscription |
| **GitHub Copilot** | Device Code | ⚠️ Works but violates ToS | Not recommended for production |
| **Google Gemini** | API Key | ❌ API key only (pay-per-token) | Google permanently bans accounts for OAuth abuse |
| **DeepSeek** | API Key | ❌ API key only (pay-per-token) | Standard API key auth |
| **OpenRouter** | API Key | ❌ API key only (pay-per-token) | One key, all models |

**Key insight:** OpenAI Codex OAuth is the only path where users can reuse their existing subscription ($20/mo ChatGPT Plus) in third-party apps at zero additional cost. All other providers require separate API keys with pay-per-token billing.

> **Anti-patterns:** Do NOT attempt to bridge Claude Pro/Max or Google Gemini subscriptions via OAuth. Anthropic will block it; Google will permanently ban the user's account.

## Quick Start

### 1. AI Facade — Auto-detect (Recommended)

```python
from ai_sub_auth import AI

# Auto-detects: existing OAuth token → env var API keys
ai = AI()
ai.connect()

# Sync usage (simplest)
result = ai.chat_sync("What is quantum computing?", system="Be concise.")
print(result.content)

# Check subscription status
print(ai.status)  # SubscriptionStatus(connected=True, provider_name='OpenAI Codex', ...)
```

### 2. OpenAI Codex — Use Your ChatGPT Subscription

```python
import asyncio
from ai_sub_auth import AI

ai = AI(provider="openai_codex")
ai.connect()  # First time: browser opens for OAuth login. After: automatic.

async def main():
    resp = await ai.chat("What is quantum computing?", system="Be concise.")
    print(resp.content)

asyncio.run(main())
```

### 3. Claude — API Key

```python
from ai_sub_auth import AI

ai = AI(api_key="sk-ant-...")  # auto-detects Anthropic from key prefix
result = ai.chat_sync("Explain transformers in 3 sentences")
print(result.content)
print(f"Tokens: {result.usage}")
```

### 4. Google Gemini

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["google_gemini"], api_key="AI...", model="gemini-2.0-flash")
    resp = await client.chat("Write a haiku about Python")
    print(resp.content)

asyncio.run(main())
```

### 5. OpenRouter — One Key, Every Model

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["openrouter"], api_key="sk-or-...", model="anthropic/claude-sonnet-4-5")
    resp = await client.chat("Hello!")
    print(resp.content)

asyncio.run(main())
```

## How It Works

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Your App    │────▶│  ai-sub-auth     │────▶│  Provider API   │
│              │     │                  │     │  (OpenAI, etc.) │
│  3 lines of  │     │  ┌─ OAuth PKCE   │     │                 │
│  code        │     │  ├─ Token Store  │     │                 │
│              │     │  ├─ Auto Refresh │     │                 │
│              │     │  └─ Provider Reg │     │                 │
└──────────────┘     └──────────────────┘     └─────────────────┘
```

**OAuth PKCE flow (Codex):**
1. Generate PKCE verifier + challenge
2. Start local callback server on `localhost:1455`
3. Open browser → user logs in with ChatGPT account
4. Callback receives authorization code
5. Exchange code for access + refresh tokens
6. Store tokens at `~/.ai-sub-auth/tokens/` with 0600 permissions
7. Auto-refresh before expiry (with file locking for concurrency)

## Comparison with Alternatives

| Feature | ai-sub-auth | CLIProxyAPI | ccproxy-api | ProxyPilot |
|---------|------------|-------------|-------------|------------|
| Type | Library (import) | Proxy server | Proxy server | Proxy server |
| Running process | None | Required | Required | Required |
| Language | Python | Go | Python | TypeScript |
| Size | ~500 LOC | 1000s LOC | 1000s LOC | 1000s LOC |
| Dependencies | httpx only | Many | Many | Many |
| Integration | `import` | HTTP proxy | HTTP proxy | HTTP proxy |

## Adding a Custom Provider

```python
from ai_sub_auth import ProviderConfig, AuthMethod, LLMClient, PROVIDERS

my_provider = ProviderConfig(
    name="my_llm",
    display_name="My LLM Service",
    auth_method=AuthMethod.API_KEY,
    env_key="MY_LLM_API_KEY",
    api_base="https://api.my-llm.com/v1",  # OpenAI-compatible endpoint
    keywords=("my-llm",),
)

# Register it
PROVIDERS["my_llm"] = my_provider

# Use it
client = LLMClient(my_provider, api_key="...", model="my-model-v1")
```

## Security

- Tokens stored at `~/.ai-sub-auth/tokens/` with `0600` file permissions
- File-level locking prevents concurrent refresh races
- PKCE (Proof Key for Code Exchange) prevents authorization code interception
- No tokens are logged or transmitted anywhere except the provider's API
- Auto-imports existing Codex CLI tokens from `~/.codex/auth.json` (no re-login needed)
- Cross-platform: Unix (`fcntl`) and Windows (`msvcrt`) file locking

## Project Structure

```
ai_sub_auth/
├── __init__.py       # Public API
├── facade.py         # AI Facade — auto-detect, connect, chat (recommended entry point)
├── models.py         # OAuthToken, ProviderConfig, AuthMethod, LLMResponse
├── exceptions.py     # AuthError, TokenExpiredError, ProviderNotFoundError
├── providers.py      # Provider registry (Codex, Claude, Gemini, etc.)
├── oauth_flow.py     # OAuth PKCE flow + token refresh
├── token_store.py    # Secure file-based token storage
├── api_client.py     # Unified LLMClient
└── skills.py         # Meta Skill Framework (8 skills + 3-Suggestion Protocol)
```

## Agent Skills — AI Integration Framework

> **For AI Agents**: See [`AGENT.md`](./AGENT.md) for the full integration guide.

This module includes a **Meta Skill Framework** that helps AI agents (Claude Code, OpenClaw, Cursor, etc.) automatically discover how to integrate AI features into any application.

### 8 Meta Skills

Every useful AI feature is a composition of exactly 8 universal skills:

```
SUMMARIZE    many → few         Reduce volume, preserve meaning
GENERATE     few → many         Produce new content from intent
ANALYZE      raw → insight      Find patterns in data
TRANSFORM    form A → form B    Convert between formats/styles
CLASSIFY     items → buckets    Assign categories or priorities
EVALUATE     content → score    Judge quality against criteria
CONVERSE     user ↔ AI          Multi-turn contextual dialogue
EXTRACT      noise → signal     Pull structure from chaos
```

### 3-Suggestion Protocol

When an agent encounters any app, it follows: **SCAN → MATCH → RANK → PRESENT → IMPLEMENT**

```python
from ai_sub_auth import AppProfile, suggest_for_app

profile = AppProfile(
    domain="note-taking",
    verbs=["create notes", "search", "tag", "link"],
    nouns=["notes", "tags", "folders", "backlinks"],
    roles=["user"],
    existing_ai=[],
)

suggestions = suggest_for_app(profile)
for s in suggestions:
    print(f"{s.skill.name}: {s.reason} [{s.effort}]")
```

This produces exactly 3 diverse, ranked suggestions — at least one quick win, at least one high-ceiling opportunity. See [`AGENT.md`](./AGENT.md) for the complete protocol and implementation patterns.

## Credits

Built by studying and distilling patterns from:

- **[nanobot](https://github.com/HKUDS/nanobot)** — Provider Registry architecture, multi-provider routing
- **[oauth-cli-kit](https://github.com/pinhua33/oauth-cli-kit)** — OAuth PKCE flow, token storage design
- **[OpenClaw](https://github.com/openclaw/openclaw)** — Gateway auth patterns, policy-driven API access

## License

MIT
