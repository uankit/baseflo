"""User-sign-in OAuth providers (Google for v1).

Separate from connector-data OAuth (which lives at
`app/api/v1/routes/oauth.py` and authorizes data-plane access for connectors
like Shopify and Google Sheets).
"""

from app.auth.oauth.google import GoogleAuthResult, GoogleOAuthService

__all__ = ["GoogleAuthResult", "GoogleOAuthService"]
