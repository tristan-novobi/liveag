# -*- coding: utf-8 -*-
import secrets
from datetime import datetime, timedelta
from typing import Optional

from odoo.http import request
from odoo import fields


def _parse_authorization_header() -> Optional[str]:
	auth_header = request.httprequest.headers.get("Authorization") or ""
	if not auth_header:
		return None
	parts = auth_header.split(" ", 1)
	if len(parts) != 2:
		return None
	scheme, token = parts[0], parts[1]
	if scheme.lower() != "bearer":
		return None
	return token.strip() or None


def get_user_from_bearer_token() -> Optional[int]:
	token_str = _parse_authorization_header()
	if not token_str:
		return None
	Token = request.env["liveag.auth.token"].sudo()
	token = Token.search([("token", "=", token_str), ("active", "=", True)], limit=1)
	if not token:
		return None
	now = fields.Datetime.now()
	if token.expires_at and token.expires_at < now:
		return None
	return token.user_id.id if token.user_id else None


def create_token_for_user(login: str, password: str, ttl_seconds: int = 3600, scope: str = ""):
	User = request.env["res.users"].sudo()
	user = User.search([("login", "=", login)], limit=1)
	if not user:
		return None, "invalid_grant"
	try:
		user.env.user = user.sudo()
		user._check_credentials(password, {"interactive": True})
	except Exception:
		return None, "invalid_grant"
	Token = request.env["liveag.auth.token"]
	record = Token.generate(user=user, ttl_seconds=ttl_seconds, scope=scope or "")
	return record, None
