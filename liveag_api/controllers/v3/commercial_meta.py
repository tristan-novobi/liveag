from odoo import http
from odoo.http import request
import json

from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.api_decorators import (
    odoo_token_required,
)

import logging
_logger = logging.getLogger(__name__)


class CommercialMetaController(http.Controller):
# ---------- Metadata ----------
	# ---------- Countries ----------
	@api_route("/api/v3/metadata/countries", methods=["GET"])
	@odoo_token_required("api")
	def handle_countries(self, **kw):
		if request.httprequest.method != "GET":
			return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

		try:
			env = request.api_env
			countries = env["res.country"].search(
				[("code", "in", ["US", "CA", "MX"])], order="name, id"
			)
			# US first, then rest alphabetical by name
			us = countries.filtered(lambda c: c.code == "US")
			others = (countries - us).sorted(key=lambda c: c.name)
			ordered = us + others
			base_url = request.httprequest.url_root.rstrip("/")
			country_list = [
				{
					"value": c.id,
					"label": c.name,
					"code": c.code,
					"flag": f"{base_url}{c.image_url}" if c.image_url else None,
				}
				for c in ordered
			]
			return json_response({"data": country_list, "success": True}, status=200)
		except Exception as e:
			_logger.exception("Error getting countries (v3)")
			return json_response({"error": "server_error", "error_description": str(e)}, status=500)

	# ---------- Regions ----------
	@api_route("/api/v3/metadata/regions", methods=["GET"])
	@odoo_token_required("api")
	def handle_regions(self, **kw):
		if request.httprequest.method != "GET":
			return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

		try:
			env = request.api_env
			regions = env["res.region"].search([("active", "=", True)], order="sequence, id")
			region_list = [{"value": r.id, "label": r.name} for r in regions]
			return json_response({"data": region_list, "success": True}, status=200)
		except Exception as e:
			_logger.exception("Error getting regions (v3)")
			return json_response({"error": "server_error", "error_description": str(e)}, status=500)

	# ---------- States ----------
	@api_route("/api/v3/metadata/states", methods=["GET"])
	@odoo_token_required("api")
	def handle_states(self, **kw):
		if request.httprequest.method != "GET":
			return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

		try:
			env = request.api_env
			domain = []
			country_code = (request.httprequest.args.get("country") or "US").strip().upper() or "US"
			country = env["res.country"].search([("code", "=", country_code)], limit=1)
			if not country:
				country = env["res.country"].search([("code", "=", "US")], limit=1)
			if country:
				domain.append(("country_id", "=", country.id))
			states = env["res.country.state"].search(domain, order="code, id")
			state_list = [{"value": s.id, "label": s.name, "abbr": s.code, "region": {"value": s.region_id.id, "label": s.region_id.name} if s.region_id else None} for s in states]
			return json_response({"data": state_list, "success": True}, status=200)
		except Exception as e:
			_logger.exception("Error getting states (v3)")
			return json_response({"error": "server_error", "error_description": str(e)}, status=500)