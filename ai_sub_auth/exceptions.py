"""Exception hierarchy for ai-sub-auth."""


class AuthError(Exception):
    """Base authentication error."""
    pass


class TokenExpiredError(AuthError):
    """Token has expired and could not be refreshed."""
    pass


class ProviderNotFoundError(AuthError):
    """Requested provider is not registered."""
    pass


class LoginRequiredError(AuthError):
    """No credentials found — interactive login is required."""
    pass


class TokenExchangeError(AuthError):
    """Failed to exchange authorization code for tokens."""
    pass
