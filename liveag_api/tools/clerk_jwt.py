from functools import wraps
from odoo import fields
from odoo.http import request
import logging
import time
import jwt
from jwt import PyJWKClient

from odoo.addons.liveag_api.tools.http_utils import json_response

_logger = logging.getLogger(__name__)

# Very small in-process cache; good enough for most Odoo deployments.
# If you're running multiple workers, each worker will have its own cache.
_JWKS_CACHE = {}  # jwks_url -> (PyJWKClient, expires_at_epoch)

# Clerk (or its CDN) may return 403 for requests with default Python User-Agent.
JWKS_HEADERS = {
    "User-Agent": "Odoo/19.0 (Clerk JWT verification)",
    "Accept": "application/json",
}

def _get_jwk_client(jwks_url: str, ttl_seconds: int = 3600) -> PyJWKClient:
    now = int(time.time())
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and cached[1] > now:
        return cached[0]
    client = PyJWKClient(jwks_url, headers=JWKS_HEADERS)
    _JWKS_CACHE[jwks_url] = (client, now + ttl_seconds)
    return client

def verify_clerk_jwt(token: str, *, jwks_url: str, issuer: str, audience: str | None = None) -> dict:
    """
    Verifies RS256 Clerk JWT using JWKS.

    Requires standard claims exp/iat/iss/sub.
    If audience is provided, verifies aud as well.
    Returns decoded claims dict if valid; raises on failure.
    """
    jwk_client = _get_jwk_client(jwks_url)
    signing_key = jwk_client.get_signing_key_from_jwt(token).key

    options = {
        "require": ["exp", "iat", "iss", "sub"],
        "verify_aud": audience is not None,
    }

    decoded = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=audience,
        options=options,
    )
    return decoded

def _extract_bearer_token():
    auth = request.httprequest.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

def authenticate_clerk_jwt(required_scope: str | None = None):
    """
    Validates Authorization: Bearer <Clerk JWT> via JWKS, then maps to an Odoo user.

    Returns (env_as_user, user, claims, None) on success
    Returns (None, None, None, error_dict) on failure
    """
    token_str = _extract_bearer_token()
    if not token_str:
        return None, None, None, {
            "error": "invalid_request",
            "error_description": "Missing Authorization: Bearer token",
        }

    # Pull config from ir.config_parameter (recommended)
    ICP = request.env["ir.config_parameter"].sudo()
    jwks_url = ICP.get_param("clerk.jwks_url")
    issuer   = ICP.get_param("clerk.issuer")
    audience = ICP.get_param("clerk.audience")  # optional, can be empty

    if not jwks_url or not issuer:
        _logger.error("Clerk JWT config missing (jwks_url/issuer)")
        return None, None, None, {
            "error": "server_error",
            "error_description": "Clerk JWT verification is not configured",
        }

    try:
        claims = verify_clerk_jwt(
            token_str,
            jwks_url=jwks_url,
            issuer=issuer,
            audience=audience or None,
        )
    except Exception:
        _logger.exception("Clerk JWT verification failed")
        return None, None, None, {
            "error": "invalid_token",
            "error_description": "JWT invalid or expired",
        }

    # Optional: scope check (depends on how you encode scopes in Clerk)
    if required_scope:
        # Common patterns: "scp" / "scope" as a string, or "permissions" as a list
        scope_str = claims.get("scope") or claims.get("scp") or ""
        scopes = scope_str.split() if isinstance(scope_str, str) else []
        if required_scope not in scopes:
            return None, None, None, {
                "error": "insufficient_scope",
                "error_description": f"Missing required scope: {required_scope}",
            }

    # Map Clerk user -> Odoo user
    # Recommended: store Clerk "sub" on res.users (e.g. clerk_user_id) OR in a mapping model.
    clerk_sub = claims.get("sub")
    email = claims.get("email")

    Users = request.env["res.users"].sudo()

    user = None
    if clerk_sub:
        # if you add a custom field clerk_user_id on res.users:
        user = Users.search([("clerk_user_id", "=", clerk_sub)], limit=1)

    if not user and email:
        # fallback: match by email
        user = Users.search([("login", "=", email)], limit=1) or Users.search([("email", "=", email)], limit=1)

    if not user:
        return None, None, None, {
            "error": "invalid_token",
            "error_description": "No matching Odoo user for this Clerk identity",
        }

    # Build an env that enforces ACL/record rules
    env_as_user = request.env(user=user.id)
    return env_as_user, user, claims, None
