"""Secure token storage — inspired by oauth-cli-kit's FileTokenStorage.

Features: load/save/auto-refresh tokens, file locking for concurrency, 0o600 permissions.
Cross-platform: fcntl on Unix, msvcrt on Windows.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ai_sub_auth.models import OAuthToken


DEFAULT_DATA_DIR = Path.home() / ".ai-sub-auth" / "tokens"


class TokenStore:
    """File-based token storage with concurrency-safe locking."""

    def __init__(self, filename: str = "token.json", data_dir: Path | None = None):
        self._dir = data_dir or DEFAULT_DATA_DIR
        self._path = self._dir / filename

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> OAuthToken | None:
        """Load token from disk. Returns None if not found or corrupted."""
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text("utf-8"))
            return OAuthToken(
                access=data["access"],
                refresh=data["refresh"],
                expires=int(data["expires"]),
                account_id=data.get("account_id"),
            )
        except Exception:
            return None

    def save(self, token: OAuthToken) -> None:
        """Persist token to disk with 0600 permissions."""
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {"access": token.access, "refresh": token.refresh, "expires": token.expires}
        if token.account_id:
            payload["account_id"] = token.account_id
        self._path.write_text(json.dumps(payload, indent=2), "utf-8")
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass  # Windows or permission issue — non-fatal

    def locked(self):
        """File lock context manager to prevent concurrent token refreshes."""
        return _FileLock(self._path.with_suffix(".lock"))

    def try_import_codex_cli(self) -> OAuthToken | None:
        """Import existing tokens from Codex CLI (~/.codex/auth.json).

        This allows reusing tokens if the user has already logged in
        via the official Codex CLI — same pattern as oauth-cli-kit.
        """
        import time
        codex_path = Path.home() / ".codex" / "auth.json"
        if not codex_path.exists():
            return None
        try:
            data = json.loads(codex_path.read_text("utf-8"))
            tokens = data.get("tokens", {})
            access = tokens.get("access_token")
            refresh = tokens.get("refresh_token")
            account_id = tokens.get("account_id")
            if not access or not refresh:
                return None
            mtime = codex_path.stat().st_mtime
            expires = int(mtime * 1000 + 3600 * 1000)
            token = OAuthToken(access=str(access), refresh=str(refresh),
                               expires=expires, account_id=str(account_id) if account_id else None)
            self.save(token)
            return token
        except Exception:
            return None


class _FileLock:
    """Simple file lock — from oauth-cli-kit/storage.py.

    Uses fcntl on Unix, msvcrt on Windows.
    """

    def __init__(self, path: Path):
        self._path = path
        self._fp = None

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._path, "a+")
        try:
            import fcntl
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX)
        except ImportError:
            # Windows fallback
            try:
                import msvcrt
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_LOCK, 1)
            except Exception:
                pass
        except Exception:
            pass
        return self

    def __exit__(self, *_):
        try:
            import fcntl
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        except Exception:
            pass
        if self._fp:
            self._fp.close()
