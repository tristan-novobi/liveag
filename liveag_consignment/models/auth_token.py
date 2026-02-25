# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import secrets

from odoo import api, fields, models


class LiveAgAuthToken(models.Model):
	_name = "liveag.auth.token"
	_description = "LiveAg Auth Token"
	_order = "create_date desc"

	name = fields.Char(string="Name", help="Human readable label for the token", index=True)
	token = fields.Char(string="Access Token", required=True, index=True, help="Opaque bearer token string")
	user_id = fields.Many2one(
		comodel_name="res.users",
		string="User",
		required=True,
		ondelete="cascade",
		help="User this token is issued for",
	)
	expires_at = fields.Datetime(string="Expires At", required=True, help="Expiration datetime (UTC) for this token")
	active = fields.Boolean(string="Active", default=True, help="Inactive tokens are considered invalid")
	scope = fields.Char(string="Scope", help="Optional scopes for the token")
	user_agent = fields.Char(string="User Agent", help="Issuer user agent string")
	ip_address = fields.Char(string="IP Address", help="Issuer IP address")

	_token_unique = models.Constraint(
		'unique(token)',
		"Token must be unique.",
	)

	@api.model
	def generate(self, user, ttl_seconds=3600, scope=""):
		if not user:
			raise ValueError("User is required to generate token")
		token = secrets.token_urlsafe(40)
		expires = datetime.utcnow() + timedelta(seconds=int(ttl_seconds))
		record = self.sudo().create({
			"name": f"Token for {user.login}",
			"token": token,
			"user_id": user.id,
			"expires_at": fields.Datetime.to_string(expires),
			"scope": scope or "",
		})
		return record
