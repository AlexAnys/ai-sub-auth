# ai-sub-auth

**复用你的 AI 订阅。一个模块，接入所有 Provider。AI Agent 的代码 + 知识参考。**

[English](./README.md) | 中文

你已经在为 ChatGPT Plus 每月支付 $20。为什么在开发自己的应用时还要再付一笔 API 费用？

`ai-sub-auth` 是一个轻量 Python 模块（约 600 行代码，仅依赖 `httpx`），能将你现有的 AI 订阅桥接到任何应用中——不需要代理服务器，不需要中间件，零冗余。它有两个用途：

1. **给开发者** — 开箱即用的 AI 订阅认证，支持自动检测、OAuth PKCE、Token 管理，以及跨 7 个 Provider 的统一 API。
2. **给 AI Agent** — 一套代码 + 知识参考（包含 [`AGENT.md`](./AGENT.md) 和 **Meta Skill 框架**），教会 Agent 如何将 AI 能力集成到任意应用中。

## 目录

- [痛点](#痛点)
- [解决方案](#解决方案)
- [订阅现实 (2026)](#订阅现实-2026)
- [快速开始](#快速开始)
- [工作原理](#工作原理)
- [与其他方案对比](#与其他方案对比)
- [添加自定义 Provider](#添加自定义-provider)
- [安全性](#安全性)
- [项目结构](#项目结构)
- [Agent Skills — AI 集成框架](#agent-skills--ai-集成框架)
- [致谢](#致谢)
- [许可证](#许可证)

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

### 推荐：AI Facade（自动检测你的订阅）

```python
from ai_sub_auth import AI

ai = AI()           # 自动检测：ChatGPT Plus OAuth token → 环境变量中的 API key
ai.connect()        # OAuth 登录或 API key 验证

# 异步
result = await ai.chat("帮我总结这份会议记录", system="简洁回答。")

# 同步（适用于任何场景——FastAPI、Jupyter、脚本）
result = ai.chat_sync("帮我总结这份会议记录")

# 多轮对话
result = await ai.chat(messages=[
    {"role": "user", "content": "量子计算是什么？"},
    {"role": "assistant", "content": "量子计算利用..."},
    {"role": "user", "content": "它和经典计算有什么区别？"},
])
```

### 直接使用 LLMClient（显式 Provider 控制）

```python
from ai_sub_auth import LLMClient, oauth_login, PROVIDERS

# 首次：用你的 ChatGPT Plus/Pro 订阅登录
oauth_login(PROVIDERS["openai_codex"])

# 之后：直接用
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")
resp = await client.chat("帮我总结这份会议记录")
print(resp.content)
```

Token 刷新、安全存储、PKCE——全部自动处理。

## 订阅现实 (2026)

并非所有 AI 订阅都能桥接到第三方应用。以下是实际情况：

| Provider | 认证方式 | 能否桥接订阅？ | 说明 |
|----------|----------|---------------|------|
| **OpenAI ChatGPT Plus/Pro** | OAuth PKCE | ✅ 可以——零额外成本 | OpenAI 通过 Codex SDK 积极支持 |
| **Claude** | API Key | ❌ 仅 API key（按量计费） | Anthropic 于 2026 年 2 月封禁了订阅 OAuth |
| **OpenAI** | API Key | ❌ 仅 API key（按量计费） | 与 ChatGPT 订阅独立 |
| **GitHub Copilot** | Device Code | ⚠️ 可用但违反 ToS | 不推荐在生产环境使用 |
| **Google Gemini** | API Key | ❌ 仅 API key（按量计费） | Google 会永久封禁滥用 OAuth 的账号 |
| **DeepSeek** | API Key | ❌ 仅 API key（按量计费） | 标准 API key 认证 |
| **OpenRouter** | API Key | ❌ 仅 API key（按量计费） | 一个 key 用所有模型 |

**核心洞察：** OpenAI Codex OAuth 是唯一能让用户在第三方应用中复用现有订阅（$20/月 ChatGPT Plus）且零额外成本的路径。其他 Provider 都需要独立的 API key，按量计费。

> **反面模式：** 不要尝试通过 OAuth 桥接 Claude Pro/Max 或 Google Gemini 订阅。Anthropic 会直接封禁；Google 会永久封禁用户账号。

## 快速开始

### 1. AI Facade — 自动检测（推荐）

```python
from ai_sub_auth import AI

# 自动检测：已有 OAuth token → 环境变量中的 API key
ai = AI()
ai.connect()

# 同步用法（最简单）
result = ai.chat_sync("量子计算是什么？", system="简洁回答。")
print(result.content)

# 查看订阅状态
print(ai.status)  # SubscriptionStatus(connected=True, provider_name='OpenAI Codex', ...)
```

### 2. OpenAI Codex — 直接用你的 ChatGPT 订阅

```python
import asyncio
from ai_sub_auth import AI

ai = AI(provider="openai_codex")
ai.connect()  # 首次：浏览器打开进行 OAuth 登录。之后：全自动。

async def main():
    resp = await ai.chat("量子计算是什么？", system="简洁回答。")
    print(resp.content)

asyncio.run(main())
```

### 3. Claude — API Key

```python
from ai_sub_auth import AI

ai = AI(api_key="sk-ant-...")  # 从 key 前缀自动识别 Anthropic
result = ai.chat_sync("用三句话解释 Transformer")
print(result.content)
print(f"Token 用量: {result.usage}")
```

### 4. Google Gemini

```python
import asyncio
from ai_sub_auth import LLMClient, PROVIDERS

async def main():
    client = LLMClient(PROVIDERS["google_gemini"], api_key="AI...", model="gemini-2.0-flash")
    resp = await client.chat("用中文写一首关于编程的俳句")
    print(resp.content)

asyncio.run(main())
```

### 5. OpenRouter — 一个 Key 访问所有模型

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
├── facade.py         # AI Facade — 自动检测、连接、对话（推荐入口）
├── models.py         # OAuthToken, ProviderConfig, AuthMethod, LLMResponse
├── exceptions.py     # AuthError, TokenExpiredError, ProviderNotFoundError
├── providers.py      # Provider 注册表（Codex, Claude, Gemini 等）
├── oauth_flow.py     # OAuth PKCE 流程 + Token 刷新
├── token_store.py    # 安全的文件级 Token 存储
├── api_client.py     # 统一的 LLMClient
└── skills.py         # Meta Skill 框架（8 技能 + 3-Suggestion 协议）
```

## Agent Skills — AI 集成框架

> **给 AI Agent**: 完整集成指南见 [`AGENT.md`](./AGENT.md)

本模块包含一个 **Meta Skill 框架**，帮助 AI Agent（Claude Code、OpenClaw、Cursor 等）自动发现如何将 AI 功能集成到任意应用中。

### 8 个 Meta Skill

任何有用的 AI 功能都是这 8 个基础能力的组合：

```
SUMMARIZE    多 → 少            压缩内容，保留核心含义
GENERATE     少 → 多            从意图或规范生成新内容
ANALYZE      原始 → 洞察        发现数据中的模式、异常、趋势
TRANSFORM    形式A → 形式B      在格式、风格、语言之间转换
CLASSIFY     条目 → 分类        分配类别、优先级或标签
EVALUATE     内容 → 评分        根据标准判断质量
CONVERSE     用户 ↔ AI          多轮上下文对话
EXTRACT      噪声 → 信号        从非结构化输入提取结构化数据
```

### 3-Suggestion 协议

当 Agent 遇到任何应用时，遵循：**扫描 → 匹配 → 排序 → 呈现 → 实施**

```python
from ai_sub_auth import AppProfile, suggest_for_app

profile = AppProfile(
    domain="笔记应用",
    verbs=["创建笔记", "搜索", "打标签", "双链"],
    nouns=["笔记", "标签", "文件夹", "反向链接"],
    roles=["用户"],
    existing_ai=[],
)

suggestions = suggest_for_app(profile)
for s in suggestions:
    print(f"{s.skill.name}: {s.reason} [{s.effort}]")
```

输出恰好 3 条多样化、排序后的建议——至少一个快速见效的，至少一个有高上限的。完整协议和实现模式见 [`AGENT.md`](./AGENT.md)。

## 致谢

本项目通过研究和提炼以下项目的设计模式构建：

- **[nanobot](https://github.com/HKUDS/nanobot)** — Provider Registry 架构、多 Provider 路由
- **[oauth-cli-kit](https://github.com/pinhua33/oauth-cli-kit)** — OAuth PKCE 流程、Token 存储设计
- **[OpenClaw](https://github.com/openclaw/openclaw)** — Gateway 认证模式、策略驱动的 API 访问

## 许可证

MIT
