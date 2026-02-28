"""OAuth 2.0 PKCE authentication flow — core design from oauth-cli-kit's flow.py.

Flow: Generate PKCE → Start local callback server → Open browser for authorization
      → Intercept code → Exchange for tokens → Store securely.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable

import httpx

from ai_sub_auth.models import OAuthToken, ProviderConfig
from ai_sub_auth.token_store import TokenStore
from ai_sub_auth.exceptions import LoginRequiredError, TokenExchangeError, TokenExpiredError


# ── PKCE helpers ──────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE verifier + challenge (S256)."""
    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def _create_state() -> str:
    return _b64url(os.urandom(16))


def _decode_account_id(access_token: str, claim_path: str | None, claim_key: str | None) -> str | None:
    """Extract account_id from JWT payload."""
    if not claim_path or not claim_key:
        return None
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
        return str(payload.get(claim_path, {}).get(claim_key, "")) or None
    except Exception:
        return None


# ── Local callback server ──────────────────────────────────

SUCCESS_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Auth OK</title></head>"
    "<body><p>Authentication successful. You can close this tab and return to the terminal.</p></body></html>"
)


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _CallbackServer  # type: ignore[assignment]

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        if url.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            return

        qs = urllib.parse.parse_qs(url.query)
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]

        if state != self.server.expected_state or not code:
            self.send_response(400)
            self.end_headers()
            return

        if self.server.on_code:
            self.server.on_code(code)

        body = SUCCESS_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, /, *args: object) -> None:
        pass


class _CallbackServer(HTTPServer):
    def __init__(
        self,
        addr: tuple[str, int],
        state: str,
        on_code: Callable[[str], None] | None,
    ) -> None:
        super().__init__(addr, _CallbackHandler)
        self.expected_state = state
        self.on_code = on_code


def _start_callback_server(state: str, on_code: Callable[[str], None]):
    """Start local OAuth callback server on port 1455."""
    try:
        server = _CallbackServer(("127.0.0.1", 1455), state, on_code)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    except OSError:
        return None


# ── Token exchange & refresh ──────────────────────────────

async def _exchange_code(code: str, verifier: str, provider: ProviderConfig) -> OAuthToken:
    """Exchange authorization code for tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": provider.client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": provider.redirect_uri,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            provider.token_url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise TokenExchangeError(f"Token exchange failed: {resp.status_code} {resp.text}")

    payload = resp.json()
    if "error" in payload:
        raise TokenExchangeError(f"Token exchange error: {payload['error']}")
    access = payload["access_token"]
    refresh = payload["refresh_token"]
    expires_in = payload["expires_in"]
    account_id = _decode_account_id(access, provider.jwt_claim_path, provider.account_id_claim)

    return OAuthToken(
        access=access, refresh=refresh,
        expires=int(time.time() * 1000 + expires_in * 1000),
        account_id=account_id,
    )


def _refresh_token(refresh: str, provider: ProviderConfig) -> OAuthToken:
    """Refresh access token using refresh_token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": provider.client_id,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            provider.token_url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise TokenExpiredError(f"Token refresh failed: {resp.status_code} {resp.text}")

    payload = resp.json()
    if "error" in payload:
        raise TokenExchangeError(f"Token refresh error: {payload['error']}")
    access = payload["access_token"]
    new_refresh = payload["refresh_token"]
    expires_in = payload["expires_in"]
    account_id = _decode_account_id(access, provider.jwt_claim_path, provider.account_id_claim)

    return OAuthToken(
        access=access, refresh=new_refresh,
        expires=int(time.time() * 1000 + expires_in * 1000),
        account_id=account_id,
    )


# ── Public API ──────────────────────────────────────────

def oauth_login(
    provider: ProviderConfig,
    store: TokenStore | None = None,
    log: Callable[[str], None] = print,
) -> OAuthToken:
    """Interactive OAuth PKCE login — opens browser, waits for callback.

    This is the main entry point, equivalent to nanobot's `nanobot provider login`.
    """
    store = store or TokenStore(filename=provider.token_filename)

    async def _run() -> OAuthToken:
        verifier, challenge = _generate_pkce()
        state = _create_state()

        params = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": provider.redirect_uri,
            "scope": provider.scope,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        url = f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"

        loop = asyncio.get_running_loop()
        code_future: asyncio.Future[str] = loop.create_future()

        def on_code(code_val):
            loop.call_soon_threadsafe(code_future.set_result, code_val)

        server = _start_callback_server(state, on_code)

        log(f"Open this URL in your browser to authenticate:\n{url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass

        try:
            code = await asyncio.wait_for(code_future, timeout=120)
        except asyncio.TimeoutError:
            raise TokenExchangeError("OAuth login timed out (120s). Please try again.")
        finally:
            if server:
                server.shutdown()

        log("Exchanging authorization code for tokens...")
        token = await _exchange_code(code, verifier, provider)
        store.save(token)
        return token

    return asyncio.run(_run())


def get_or_refresh_token(
    provider: ProviderConfig,
    store: TokenStore | None = None,
    min_ttl: int = 60,
) -> OAuthToken:
    """Get a valid token — automatically refreshes if near expiry.

    Inspired by oauth-cli-kit's get_token(): file-locked concurrent-safe refresh.
    """
    store = store or TokenStore(filename=provider.token_filename)
    token = store.load()

    # Try importing from Codex CLI if no local token
    if not token:
        token = store.try_import_codex_cli()

    if not token:
        raise LoginRequiredError("No OAuth credentials found. Please run oauth_login() first.")

    if token.ttl_seconds > min_ttl:
        return token

    # Lock to prevent multiple processes from refreshing simultaneously
    with store.locked():
        token = store.load() or token
        if token.ttl_seconds > min_ttl:
            return token
        refreshed = _refresh_token(token.refresh, provider)
        store.save(refreshed)
        return refreshed
