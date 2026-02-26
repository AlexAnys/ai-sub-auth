"""Example: Integrate ai-sub-auth into your application."""

import asyncio
from ai_sub_auth import LLMClient, get_provider


class MyApp:
    """A simple app that uses ai-sub-auth for LLM access."""

    def __init__(self, provider_name: str = "anthropic", api_key: str = "", model: str = ""):
        provider = get_provider(provider_name)
        self.client = LLMClient(provider, api_key=api_key, model=model)

    async def summarize(self, text: str) -> str:
        resp = await self.client.chat(text, system="Summarize the following text concisely.")
        return resp.content or ""

    async def translate(self, text: str, target_lang: str = "English") -> str:
        resp = await self.client.chat(text, system=f"Translate to {target_lang}. Output only the translation.")
        return resp.content or ""


async def main():
    app = MyApp(
        provider_name="anthropic",
        api_key="your-api-key-here",
        model="claude-sonnet-4-5-20250514",
    )

    summary = await app.summarize("Python is a programming language created by Guido van Rossum...")
    print(f"Summary: {summary}")

    translation = await app.translate("Hello, how are you?", "Chinese")
    print(f"Translation: {translation}")


if __name__ == "__main__":
    asyncio.run(main())
