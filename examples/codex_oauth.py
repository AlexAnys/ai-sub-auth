"""Example: Use your ChatGPT Plus/Pro subscription via OpenAI Codex OAuth."""

import asyncio
from ai_sub_auth import LLMClient, oauth_login, get_or_refresh_token, PROVIDERS

provider = PROVIDERS["openai_codex"]


def login():
    """One-time interactive login — opens browser."""
    token = oauth_login(provider)
    print(f"Logged in! account={token.account_id}, expires in {token.ttl_seconds:.0f}s")


async def chat():
    """Use Codex after login — tokens auto-refresh."""
    client = LLMClient(provider, model="openai-codex/gpt-5.1-codex")
    resp = await client.chat(
        "What are the key differences between TCP and UDP?",
        system="Answer concisely in bullet points.",
    )
    print(resp.content)


if __name__ == "__main__":
    # Uncomment to login first time:
    # login()

    asyncio.run(chat())
