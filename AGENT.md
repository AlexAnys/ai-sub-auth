# Agent Integration Guide

> **For AI Agents**: Read this file to understand how to integrate `ai-sub-auth` into any application.
> This file is designed to be consumed by Claude Code, OpenClaw, Cursor, Copilot, or any agentic coding tool.

## What is ai-sub-auth?

A lightweight Python module (~500 LOC, only depends on `httpx`) that authenticates against AI providers using existing user subscriptions. It handles OAuth PKCE (OpenAI Codex), API keys (Claude, Gemini, DeepSeek), and device code (GitHub Copilot) — all through a unified `LLMClient` interface.

**3-line integration:**
```python
# Recommended — auto-detects your subscription
from ai_sub_auth import AI
ai = AI()
result = await ai.chat("your prompt here", system="your system prompt")

# Or explicit provider selection
from ai_sub_auth import LLMClient, PROVIDERS
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")
resp = await client.chat("your prompt here", system="your system prompt")
```

## Subscription Reality (2026)

Which AI subscriptions can be bridged into third-party apps:

| Provider | Method | Status | Notes |
|----------|--------|--------|-------|
| **OpenAI ChatGPT Plus/Pro** | OAuth PKCE | ✅ Safe & encouraged | OpenAI actively supports via Codex SDK, MCP, Apps SDK |
| **Claude** | API Key | ✅ Works (pay-per-token) | Anthropic banned subscription OAuth (Feb 2026). Use API key only |
| **GitHub Copilot** | Device Code | ⚠️ Works but violates ToS | Not recommended for production |
| **Google Gemini** | API Key | ✅ Works (pay-per-token) | Google banned subscription OAuth. Accounts permanently banned |
| **DeepSeek, OpenRouter** | API Key | ✅ Works | Standard API key auth |

**Key insight:** OpenAI Codex OAuth is the only path where users can reuse their existing subscription ($20/mo ChatGPT Plus) in third-party apps at zero additional cost. All other providers require pay-per-token API keys.

### Provider Selection Guide

When integrating AI into an app, help the user choose:

1. **User has ChatGPT Plus/Pro** → Use OpenAI Codex OAuth (zero extra cost, best value)
2. **User has Claude API key** → Use Anthropic API Key (high quality, pay-per-token)
3. **User has both** → Default to OpenAI Codex (free with subscription), fall back to Claude
4. **User has neither** → Guide them to get ChatGPT Plus ($20/mo) or a free-tier API key

⚠️ **Anti-Patterns — Do NOT:**
- Attempt to bridge Claude Pro/Max subscription via OAuth (Anthropic will block it)
- Attempt to bridge Google Gemini subscription via OAuth (Google will permanently ban the account)
- Hardcode provider-specific API calls in the target app (use ai-sub-auth's unified interface)
- Store tokens outside the module's TokenStore (security risk)

---

## Quick Reference

| File | Purpose |
|------|---------|
| `ai_sub_auth/facade.py` | **AI Facade** — auto-detects subscription, recommended entry point |
| `ai_sub_auth/providers.py` | Provider registry — add new providers here |
| `ai_sub_auth/oauth_flow.py` | OAuth PKCE login + auto token refresh |
| `ai_sub_auth/token_store.py` | Secure token storage (~/.ai-sub-auth/tokens/) |
| `ai_sub_auth/api_client.py` | Unified LLMClient — routes to correct API |
| `ai_sub_auth/models.py` | Data models: OAuthToken, ProviderConfig, LLMResponse |
| `ai_sub_auth/exceptions.py` | AuthError, TokenExpiredError, LoginRequiredError |

---

## Meta Skill Framework

When integrating AI into any application, every useful AI feature is a composition of exactly **8 meta skills**:

```
Skill         Direction          What it does
─────────     ─────────────      ─────────────────────────────────────────
SUMMARIZE     many → few         Reduce volume while preserving meaning
GENERATE      few → many         Produce new content from intent or spec
ANALYZE       raw → insight      Find patterns, anomalies, trends in data
TRANSFORM     form A → form B    Convert between formats, styles, languages
CLASSIFY      items → buckets    Assign categories, priorities, or labels
EVALUATE      content → score    Judge quality against criteria
CONVERSE      user ↔ AI          Multi-turn contextual dialogue
EXTRACT       noise → signal     Pull structured data from unstructured input
```

### When to apply each skill

| Skill | Trigger signals in the target app |
|-------|----------------------------------|
| SUMMARIZE | Has collections of text (notes, emails, logs, threads, history) |
| GENERATE | Has "create/new" buttons, blank editors, templates, boilerplate |
| ANALYZE | Has charts, tables, dashboards, numerical/time-series data |
| TRANSFORM | Has import/export, format conversion, audience adaptation |
| CLASSIFY | Has inbox/queue/feed, manual tagging, predefined categories |
| EVALUATE | Has submissions, reviews, quality checks, rubrics, checklists |
| CONVERSE | Has help section, complex workflows, onboarding, Q&A needs |
| EXTRACT | Has manual data entry, forms, paste-from-external, uploads |

---

## 3-Suggestion Protocol

When you encounter a new application, follow this protocol to suggest AI integrations:

### Step 1: SCAN — Build an App Profile

Examine in order: README → directory structure → routes/endpoints → data models → UI entry points.

Produce:
```
domain:      [e.g., "education", "finance", "devtools", "personal"]
verbs:       [what the app DOES — "create tasks", "send emails", "track expenses"]
nouns:       [what the app KNOWS — "notes", "transactions", "users", "documents"]
roles:       [who uses it — "admin", "user", "viewer"]
existing_ai: [what's already AI-powered, if anything]
```

### Step 2: MATCH — Score skills against the profile

For each of the 8 meta skills, check if its trigger signals are present in the app profile. Prioritize skills that are NOT yet implemented (greenfield bonus).

### Step 3: RANK — Select exactly 3

Rank by: **Impact (3x)** × **Feasibility (2x)** × **Differentiation (1x)**

Hard rules:
- 3 suggestions, never more, never fewer
- No two suggestions use the same meta skill
- At least one must be a **quick win** (< 50 lines to integrate)
- At least one must be **high ceiling** (transformative if done fully)

### Step 4: PRESENT — Use this template for each suggestion

```
## Suggestion [1/3]: [SKILL] — [One-line description]

**What it does:** [2-3 sentences, user perspective]
**Why this app needs it:** [Connect to a specific pain point from SCAN]
**Integration point:** [Exact file(s) and function(s)]
**Effort:** [Quick win | Moderate | Deep integration]

**Implementation sketch:**
1. [Hook: where in the app to add this]
2. [Service: the ai-sub-auth call pattern]
3. [UI: how the user triggers and sees it]
```

### Step 5: IMPLEMENT — Upon user approval

```
1. AUTH    → from ai_sub_auth import LLMClient, PROVIDERS
2. SERVICE → Create function: input → LLMClient.chat(prompt, system) → parsed output
3. ROUTE   → Wire into app's existing API/endpoint pattern
4. UI      → Add trigger (button/auto/hook) following app's component style
5. VERIFY  → Test auth, test output, test error handling
```

---

## Integration Patterns by App Category

| Category | Best 3 skills | Example integration |
|----------|--------------|-------------------|
| **Notes/PKM** (Obsidian, Logseq) | Summarize, Analyze, Generate | "Summarize this week's notes" button |
| **Dev tools** (terminals, IDEs) | Evaluate, Analyze, Generate | Inline code review on git diff |
| **Email/Chat** (Thunderbird, Element) | Generate, Summarize, Classify | Draft reply + inbox triage |
| **CMS/Blog** (Hugo, WordPress) | Generate, Transform, Evaluate | AI first draft + SEO metadata |
| **Data/Analytics** (Grafana, Metabase) | Analyze, Transform, Generate | Natural language → SQL query |
| **Personal** (finance, health, calendar) | Analyze, Extract, Generate | Voice → structured expense entry |
| **System/Infra** (monitoring, CI/CD) | Analyze, Generate, Transform | Log correlation → incident summary |

---

## Implementation Example

Here's a complete example of adding SUMMARIZE to a note-taking app:

```python
# 1. AUTH — one-time setup
from ai_sub_auth import LLMClient, PROVIDERS, oauth_login

# If using ChatGPT subscription (OAuth):
# oauth_login(PROVIDERS["openai_codex"])  # first time only
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")

# Or if using API key:
# client = LLMClient(PROVIDERS["anthropic"], api_key="sk-...", model="claude-sonnet-4-5-20250514")

# 2. SERVICE — the AI function
async def summarize_notes(notes: list[str], max_points: int = 5) -> dict:
    combined = "\n---\n".join(notes)
    resp = await client.chat(
        message=combined,
        system=f"Summarize these {len(notes)} notes into {max_points} key points. "
               f"Output JSON: {{\"points\": [\"...\"], \"action_items\": [\"...\"]}}",
    )
    import json
    return json.loads(resp.content)

# 3. ROUTE — hook into your app's API
# @app.post("/api/ai/summarize")
# async def api_summarize(request): ...

# 4. UI — add a button
# <button onClick={summarize}>✨ Summarize</button>
```

### TRANSFORM Example: Adding translation to a messaging app

```python
# 1. AUTH — one-time setup
from ai_sub_auth import LLMClient, PROVIDERS, oauth_login

# Using ChatGPT subscription (zero cost for the user):
# oauth_login(PROVIDERS["openai_codex"])  # first time only
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")

# 2. SERVICE — the AI function
async def translate_message(text: str, source_lang: str, target_lang: str) -> dict:
    resp = await client.chat(
        message=text,
        system=(
            f"Translate the following from {source_lang} to {target_lang}. "
            f"Preserve tone, formatting, and any embedded links. "
            f'Output JSON: {{"translation": "...", "detected_lang": "...", "confidence": 0.0-1.0}}'
        ),
    )
    import json
    return json.loads(resp.content)

# 3. ROUTE — hook into your messaging app's API
from fastapi import APIRouter
router = APIRouter()

@router.post("/api/ai/translate")
async def api_translate(request: dict):
    result = await translate_message(
        text=request["text"],
        source_lang=request.get("source_lang", "auto"),
        target_lang=request["target_lang"],
    )
    return result

# 4. UI — add inline translate button on each message
# <button onClick={() => translate(msg.id, userLang)}>🌐 Translate</button>
# Shows translated text below original, with "Translated from {detected_lang}" label
```

### EXTRACT Example: Structured data extraction from documents

```python
# 1. AUTH — one-time setup
from ai_sub_auth import LLMClient, PROVIDERS, oauth_login

# Using ChatGPT subscription:
# oauth_login(PROVIDERS["openai_codex"])  # first time only
client = LLMClient(PROVIDERS["openai_codex"], model="openai-codex/gpt-4o")

# Or using Claude API key for higher extraction accuracy:
# client = LLMClient(PROVIDERS["anthropic"], api_key="sk-...", model="claude-sonnet-4-5-20250514")

# 2. SERVICE — the AI function
async def extract_invoice_data(raw_text: str) -> dict:
    resp = await client.chat(
        message=raw_text,
        system=(
            "Extract structured data from this invoice/receipt. "
            "Output JSON: {"
            '"vendor": "...", "date": "YYYY-MM-DD", "currency": "...", '
            '"total": 0.00, "tax": 0.00, "subtotal": 0.00, '
            '"line_items": [{"description": "...", "qty": 1, "unit_price": 0.00, "amount": 0.00}]'
            "}"
            " If a field is not found, use null."
        ),
    )
    import json
    return json.loads(resp.content)

# 3. ROUTE — hook into your document management app's API
from fastapi import APIRouter, UploadFile
router = APIRouter()

@router.post("/api/ai/extract-invoice")
async def api_extract_invoice(file: UploadFile):
    raw_text = (await file.read()).decode("utf-8")  # or use OCR for images
    result = await extract_invoice_data(raw_text)
    return result

# 4. UI — add extract button on document upload
# <button onClick={() => extractData(doc.id)}>📋 Extract Data</button>
# Pre-fills form fields with extracted values; user reviews and confirms
```

---

## Principles

1. **Eight is enough.** Every AI feature maps to one of the 8 skills. Don't invent a ninth — it's a composition.
2. **Skills are verbs, not features.** "Summarize" is a skill. "Email summary" is a feature = skill + context.
3. **Three suggestions, never more.** Fewer forces prioritization. More creates paralysis.
4. **Quick-win plus high-ceiling.** Build trust with a fast win, then go deep.
5. **Follow the host.** Mirror the target app's conventions for auth, routing, and UI. Be a guest, not an invader.
6. **Auth is first, not last.** Every AI feature goes through ai-sub-auth from step 1.
7. **Subscription-first.** Prefer OAuth subscription bridge (ChatGPT Plus) over API keys when available. It's zero extra cost for the user.
