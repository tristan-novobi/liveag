import logging
from odoo import http
from odoo.http import request

from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.roles import user_division_roles, sanitize_groups_for_debug
from odoo.addons.liveag_api.tools.api_decorators import odoo_token_required

_logger = logging.getLogger(__name__)

ALLOW_ACTS_ACCESS_GROUPS = [
  "liveag_consignment.group_consignment_manager",
  # "liveag_consignment.group_consignment_buyer", 
  # "liveag_consignment.group_consignment_seller", 
  "liveag_consignment.group_consignment_rep"
  ]
class LiveAgAPI(http.Controller):

	@api_route("/api/v3/me", methods=["GET"])
	@odoo_token_required("api")
	def me(self, **kw):
			user = request.api_user
			has_acts_access = any(user.has_group(group) for group in ALLOW_ACTS_ACCESS_GROUPS)

			payload = {
					"id": user.id,
					"email": user.email,
					"name": user.name,
					"roles": user_division_roles(user),
					"has_acts_access": has_acts_access,
			}

			# Optional debug mode: /api/v3/me?debug=1
			if request.params.get("debug") in ("1", "true", "yes"):
					payload["role_groups"] = sanitize_groups_for_debug(user)
					# Optional: include Clerk claims for troubleshooting
					claims = getattr(request, "api_claims", None) or {}
					payload["clerk"] = {
							"sub": claims.get("sub"),
							"iss": claims.get("iss"),
							"aud": claims.get("aud"),
					}

			return json_response(payload)

	@api_route("/api/v3/audit-test/partner", methods=["POST"])
	@odoo_token_required("api")
	def audit_test_partner(self, **kw):
			env = request.api_env
			user = request.api_user

			payload = {}
			try:
					ctype = (request.httprequest.headers.get("Content-Type") or "").lower()
					if "application/json" in ctype:
							payload = request.get_json_data() or {}
			except Exception:
					payload = {}

			name = payload.get("name") or request.params.get("name")
			email = payload.get("email") or request.params.get("email")

			partner = env["res.partner"].create({
					"name": name or f"AUDIT TEST – {user.name}",
					"email": email or f"audit-test+{user.id}@example.com",
					"comment": "Created via API audit test",
			})

			return json_response(
					{
							"partner_id": partner.id,
							"partner_name": partner.name,
							"create_uid": partner.create_uid.id,
							"create_user": partner.create_uid.name,
							"write_uid": partner.write_uid.id,
							"write_user": partner.write_uid.name,
					},
					status=201,
			)