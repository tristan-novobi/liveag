from odoo import fields
from odoo.http import request

from odoo.addons.liveag_api.tools.http_utils import json_response

def _extract_bearer_token():
    auth = request.httprequest.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

def authenticate_liveag_token(required_scope: str | None = None):
    """
    Validates Authorization: Bearer <token> against liveag.auth.token.

    Returns (env_as_user, token_rec, None) on success.
    Returns (None, None, error_dict) on failure.

    env_as_user runs as token_rec.user_id so Odoo ACL/record rules apply.
    """
    token_str = _extract_bearer_token()
    if not token_str:
        return None, None, {
            "error": "invalid_request",
            "error_description": "Missing Authorization: Bearer token",
        }

    Token = request.env["liveag.auth.token"].sudo()
    token_rec = Token.search([
        ("token", "=", token_str),
        ("active", "=", True),
        ("expires_at", ">", fields.Datetime.now()),
    ], limit=1)

    if not token_rec:
        return None, None, {
            "error": "invalid_token",
            "error_description": "Token invalid or expired",
        }

    if required_scope:
        scopes = (token_rec.scope or "").split()
        if required_scope not in scopes:
            return None, None, {
                "error": "insufficient_scope",
                "error_description": f"Missing required scope: {required_scope}",
            }

    env_as_user = request.env(user=token_rec.user_id.id)
    return env_as_user, token_rec, None