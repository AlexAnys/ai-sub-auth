"""Example: Switch between providers dynamically."""

import asyncio
from ai_sub_auth import LLMClient, get_provider, find_provider_by_model


async def ask(model: str, question: str, api_key: str = ""):
    """Auto-detect provider from model name and ask a question."""
    provider = find_provider_by_model(model)
    if not provider:
        print(f"No provider found for model: {model}")
        return

    print(f"Using {provider.display_name} for {model}")
    client = LLMClient(provider, api_key=api_key, model=model)
    resp = await client.chat(question)
    print(f"  → {resp.content}\n")


async def main():
    question = "What is 2 + 2? Answer in one word."

    # Auto-routes to correct provider based on model name
    await ask("openai-codex/codex-mini-latest", question)                 # → OpenAI Codex (OAuth)
    await ask("claude-sonnet-4-5-20250514", question, "sk-ant-...")      # → Anthropic (API Key)
    await ask("gpt-4o", question, "sk-...")                              # → OpenAI (API Key)
    await ask("gemini-2.0-flash", question, "AI...")                     # → Google Gemini
    await ask("deepseek-chat", question, "sk-...")                       # → DeepSeek


if __name__ == "__main__":
    asyncio.run(main())
