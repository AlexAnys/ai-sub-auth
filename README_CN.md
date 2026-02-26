# ai-sub-auth

**复用你的 AI 订阅。一个模块，接入所有 Provider。**

[English](./README.md) | 中文

你已经在为 ChatGPT Plus、Claude Pro、GitHub Copilot 或 Gemini Advanced 每月支付 $20–200。为什么在开发自己的应用时还要再付一笔 API 费用？

`ai-sub-auth` 是一个轻量 Python 模块（约 500 行代码，仅依赖 `httpx`），让你用现有的 AI 订阅直接认证——不需要代理服务器，不需要中间件，零冗余。

## 痛点

| 问题 | 详情 |
|------|------|
| **重复付费** | AI 订阅 ($20/月) + API 费用 ($50–200/月)，用的是同样的模型 |
| **认证碎片化** | 每家 Provider 的认证方式都不一样（OAuth、API Key、设备码） |
| **代理开销** | 现有方案需要 24/7 运行一个独立的代理服务器 |
| **Token 管理** | 手动刷新 token、存储不安全、没有并发保护 |

## 解决方案

```
pip install httpx  # 唯一依赖
```

```python
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# 首次：用你的 ChatGPT Plus/Pro 订阅登录
oauth_login(PROVIDERS["openai_codex"])

# 之后：直接用
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")
resp = await client.chat("帮我总结这份会议记录")
print(resp.content)
```

就这样。Token 刷新、安全存储、PKCE——全部自动处理。

## 支持的 Provider

| Provider | 认证方式 | 使用的订阅 | 状态 |
|----------|----------|-----------|------|
| **OpenAI Codex** | OAuth PKCE | ChatGPT Plus/Pro | ✅ 可用 |
| **Claude** | API Key | 按量计费 | ✅ 可用 |
| **OpenAI** | API Key | 按量计费 | ✅ 可用 |
| **GitHub Copilot** | Device Code | Copilot 订阅 | ✅ 可用（通过 LiteLLM） |
| **Google Gemini** | API Key | 按量计费 | ✅ 可用 |
| **DeepSeek** | API Key | 按量计费 | ✅ 可用 |
| **OpenRouter** | API Key | 一个 key 用所有模型 | ✅ 可用 |

> **关于 Claude：** Anthropic 在 2026 年 1 月封禁了第三方工具使用 OAuth token。Claude 通过标准 API Key 接入，多一步去 console.anthropic.com 获取 key，但运行稳定。

## 快速开始

### 1. OpenAI Codex — 直接用你的 ChatGPT 订阅

```python
import asyncio
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# 首次：浏览器打开，登录，搞定
oauth_login(PROVIDERS["openai_codex"])

# 之后每次：全自动
async def main():
    client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-5.1-codex")
    resp = await client.chat("量子计算是什么？", system="简洁回答。")
    print(resp.content)

asyncio.run(main())
```

### 2. Claude — API Key

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["anthropic"], api_key="sk-ant-...", model="claude-sonnet-4-5-20250514")
    resp = await client.chat("用三句话解释 Transformer")
    print(resp.content)
    print(f"Token 用量: {resp.usage}")

asyncio.run(main())
```

### 3. Google Gemini

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["google_gemini"], api_key="AI...", model="gemini-2.0-flash")
    resp = await client.chat("用中文写一首关于编程的俳句")
    print(resp.content)

asyncio.run(main())
```

### 4. OpenRouter — 一个 Key 访问所有模型

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["openrouter"], api_key="sk-or-...", model="anthropic/claude-sonnet-4-5")
    resp = await client.chat("你好！")
    print(resp.content)

asyncio.run(main())
```

## 工作原理

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  你的应用     │────▶│  ai-sub-auth     │────▶│  Provider API   │
│              │     │                  │     │  (OpenAI 等)     │
│  3 行代码     │     │  ┌─ OAuth PKCE   │     │                 │
│  即可接入     │     │  ├─ Token 存储   │     │                 │
│              │     │  ├─ 自动刷新     │     │                 │
│              │     │  └─ Provider 注册 │     │                 │
└──────────────┘     └──────────────────┘     └─────────────────┘
```

**OAuth PKCE 流程（Codex）：**
1. 生成 PKCE verifier + challenge
2. 启动本地回调服务器 `localhost:1455`
3. 浏览器打开 → 用户用 ChatGPT 账号登录
4. 回调接收 authorization code
5. 用 code 换取 access + refresh token
6. Token 存储在 `~/.ai-sub-auth/tokens/`（权限 0600）
7. 到期前自动刷新（文件锁保证并发安全）

## 与其他方案对比

| 特性 | ai-sub-auth | CLIProxyAPI | ccproxy-api | ProxyPilot |
|------|------------|-------------|-------------|------------|
| 类型 | 库（import 即用） | 代理服务器 | 代理服务器 | 代理服务器 |
| 常驻进程 | 不需要 | 需要 | 需要 | 需要 |
| 语言 | Python | Go | Python | TypeScript |
| 代码量 | ~500 行 | 数千行 | 数千行 | 数千行 |
| 依赖 | 仅 httpx | 很多 | 很多 | 很多 |
| 集成方式 | `import` | HTTP 代理 | HTTP 代理 | HTTP 代理 |

## 添加自定义 Provider

```python
from ai_sub_auth import ProviderConfig, AuthMethod, LLMClient, PROVIDERS

my_provider = ProviderConfig(
    name="my_llm",
    display_name="我的 LLM 服务",
    auth_method=AuthMethod.API_KEY,
    env_key="MY_LLM_API_KEY",
    api_base="https://api.my-llm.com/v1",  # OpenAI 兼容接口
    keywords=("my-llm",),
)

# 注册
PROVIDERS["my_llm"] = my_provider

# 使用
client = LLMClient(my_provider, api_key="...", model="my-model-v1")
```

## 安全性

- Token 存储在 `~/.ai-sub-auth/tokens/`，文件权限 `0600`
- 文件锁防止并发刷新竞争
- PKCE（Proof Key for Code Exchange）防止授权码拦截
- Token 不会被记录或发送到 Provider API 以外的任何地方
- 自动导入已有的 Codex CLI token（`~/.codex/auth.json`），无需重复登录
- 跨平台：Unix（`fcntl`）和 Windows（`msvcrt`）文件锁

## 项目结构

```
ai_sub_auth/
├── __init__.py       # 公开 API
├── models.py         # OAuthToken, ProviderConfig, AuthMethod, LLMResponse
├── exceptions.py     # AuthError, TokenExpiredError, ProviderNotFoundError
├── providers.py      # Provider 注册表（Codex, Claude, Gemini 等）
├── oauth_flow.py     # OAuth PKCE 流程 + Token 刷新
├── token_store.py    # 安全的文件级 Token 存储
└── api_client.py     # 统一的 LLMClient
```

## 致谢

本项目通过研究和提炼以下项目的设计模式构建：

- **[nanobot](https://github.com/HKUDS/nanobot)** — Provider Registry 架构、多 Provider 路由
- **[oauth-cli-kit](https://github.com/pinhua33/oauth-cli-kit)** — OAuth PKCE 流程、Token 存储设计
- **[OpenClaw](https://github.com/openclaw/openclaw)** — Gateway 认证模式、策略驱动的 API 访问

## 许可证

MIT
