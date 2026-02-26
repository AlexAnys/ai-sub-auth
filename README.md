# ai-sub-auth

**Reuse your AI subscriptions. One module, every provider.**

English | [中文](./README_CN.md)

You're already paying $20–200/month for ChatGPT Plus, Claude Pro, GitHub Copilot, or Gemini Advanced. Why pay again for API access when building your own apps?

`ai-sub-auth` is a lightweight Python module (~500 lines, only depends on `httpx`) that authenticates against AI providers using your existing subscriptions — no proxy servers, no middleware, no bloat.

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

```python
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# One-time: login with your ChatGPT Plus/Pro subscription
oauth_login(PROVIDERS["openai_codex"])

# Forever after: just use it
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")
resp = await client.chat("Summarize this meeting transcript")
print(resp.content)
```

That's it. Token refresh, secure storage, PKCE — all handled automatically.

## Supported Providers

| Provider | Auth Method | Subscription Used | Status |
|----------|-------------|-------------------|--------|
| **OpenAI Codex** | OAuth PKCE | ChatGPT Plus/Pro | ✅ Working |
| **Claude** | API Key | Pay-per-token | ✅ Working |
| **OpenAI** | API Key | Pay-per-token | ✅ Working |
| **GitHub Copilot** | Device Code | Copilot subscription | ✅ Working (via LiteLLM) |
| **Google Gemini** | API Key | Pay-per-token | ✅ Working |
| **DeepSeek** | API Key | Pay-per-token | ✅ Working |
| **OpenRouter** | API Key | One key, all models | ✅ Working |

> **Note on Claude:** Anthropic blocked third-party OAuth token usage in January 2026. Claude is supported via standard API keys. This adds one extra step (getting a key from console.anthropic.com) but works reliably.

## Quick Start

### 1. OpenAI Codex — Use Your ChatGPT Subscription

```python
import asyncio
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# First time: browser opens, you log in, done
oauth_login(PROVIDERS["openai_codex"])

# Every time after: automatic
async def main():
    client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-5.1-codex")
    resp = await client.chat("What is quantum computing?", system="Be concise.")
    print(resp.content)

asyncio.run(main())
```

### 2. Claude — API Key

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["anthropic"], api_key="sk-ant-...", model="claude-sonnet-4-5-20250514")
    resp = await client.chat("Explain transformers in 3 sentences")
    print(resp.content)
    print(f"Tokens: {resp.usage}")

asyncio.run(main())
```

### 3. Google Gemini

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["google_gemini"], api_key="AI...", model="gemini-2.0-flash")
    resp = await client.chat("Write a haiku about Python")
    print(resp.content)

asyncio.run(main())
```

### 4. OpenRouter — One Key, Every Model

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
├── models.py         # OAuthToken, ProviderConfig, AuthMethod, LLMResponse
├── exceptions.py     # AuthError, TokenExpiredError, ProviderNotFoundError
├── providers.py      # Provider registry (Codex, Claude, Gemini, etc.)
├── oauth_flow.py     # OAuth PKCE flow + token refresh
├── token_store.py    # Secure file-based token storage
└── api_client.py     # Unified LLMClient
```

## Credits

Built by studying and distilling patterns from:

- **[nanobot](https://github.com/HKUDS/nanobot)** — Provider Registry architecture, multi-provider routing
- **[oauth-cli-kit](https://github.com/pinhua33/oauth-cli-kit)** — OAuth PKCE flow, token storage design
- **[OpenClaw](https://github.com/openclaw/openclaw)** — Gateway auth patterns, policy-driven API access

## License

MIT
