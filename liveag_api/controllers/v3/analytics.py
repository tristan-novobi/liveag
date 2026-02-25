from datetime import datetime
from calendar import monthrange

from odoo import http
from odoo.http import request

from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.api_decorators import odoo_token_required

import logging
_logger = logging.getLogger(__name__)

MANAGER_GROUP = "liveag_consignment.group_consignment_manager"
REP_GROUP = "liveag_consignment.group_consignment_rep"


def _get_analytics_scope(env, req):
    """
    Resolve analytics scope from role and optional partner_id.

    Returns:
        (scope_partner_id: int | None, error_response: Response | None)
        - scope_partner_id: None = company-wide (admin), int = filter by that partner (rep or admin viewing rep)
        - error_response: if not None, return it immediately
    """
    user = req.api_user
    is_admin = user.has_group(MANAGER_GROUP)
    is_rep = user.has_group(REP_GROUP)

    if not is_admin and not is_rep:
        return None, json_response(
            {"error": "access_denied", "error_description": "Analytics requires Administrator or Rep role"},
            status=403,
        )

    raw_partner_id = req.params.get("partner_id")
    partner_id = None
    if raw_partner_id is not None:
        try:
            partner_id = int(raw_partner_id)
        except (ValueError, TypeError):
            return None, json_response(
                {"error": "invalid_request", "error_description": "partner_id must be an integer"},
                status=400,
            )

    if partner_id is not None and not is_admin:
        return None, json_response(
            {"error": "access_denied", "error_description": "Only Administrator can specify partner_id"},
            status=403,
        )

    if is_rep:
        return user.partner_id.id, None

    if is_admin and partner_id is not None:
        partner = env["res.partner"].browse(partner_id)
        if not partner.exists():
            return None, json_response(
                {"error": "not_found", "error_description": f"Partner {partner_id} not found"},
                status=404,
            )
        return partner_id, None

    return None, None


def _build_contract_domain(scope_partner_id, user, date_from=None, date_to=None):
    """Build domain for consignment.contract from scope. Aligns with rule_consignment_rep semantics."""
    if scope_partner_id is None:
        domain = []
    elif user.partner_id.id == scope_partner_id:
        domain = ["|", ("rep_ids.rep_id", "=", scope_partner_id), ("create_uid", "=", user.id)]
    else:
        domain = [("rep_ids.rep_id", "=", scope_partner_id)]

    if date_from:
        domain.append(("create_date", ">=", datetime.combine(date_from, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")))
    if date_to:
        domain.append(("create_date", "<=", datetime.combine(date_to, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")))
    return domain


class AnalyticsV3Controller(http.Controller):

    @api_route("/api/v3/analytics/summary", methods=["GET"])
    @odoo_token_required("api")
    def handle_analytics_summary(self, **kw):
        if request.httprequest.method != "GET":
            return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

        try:
            env = request.api_env
            scope_partner_id, err = _get_analytics_scope(env, request)
            if err is not None:
                return err

            date_from = None
            date_to = None
            raw_from = request.params.get("date_from")
            raw_to = request.params.get("date_to")
            if raw_from:
                try:
                    date_from = datetime.strptime(str(raw_from).strip()[:10], "%Y-%m-%d").date()
                except ValueError:
                    return json_response(
                        {"error": "invalid_request", "error_description": "date_from must be YYYY-MM-DD"},
                        status=400,
                    )
            if raw_to:
                try:
                    date_to = datetime.strptime(str(raw_to).strip()[:10], "%Y-%m-%d").date()
                except ValueError:
                    return json_response(
                        {"error": "invalid_request", "error_description": "date_to must be YYYY-MM-DD"},
                        status=400,
                    )
            if date_from is None and date_to is None:
                today = datetime.now().date()
                date_from = today.replace(day=1)
                _, last_day = monthrange(today.year, today.month)
                date_to = today.replace(day=last_day)
                raw_from = date_from.isoformat()
                raw_to = date_to.isoformat()

            domain = _build_contract_domain(scope_partner_id, request.api_user, date_from, date_to)
            contracts = env["consignment.contract"].search(domain)

            total_contracts = len(contracts)
            if scope_partner_id is None:
                total_head = sum((c.head1 or 0) + (c.head2 or 0) for c in contracts)
            else:
                rep_lines = env["res.rep"].search([
                    ("contract_id", "in", contracts.ids),
                    ("rep_id", "=", scope_partner_id),
                    ("active", "=", True),
                ])
                total_head = sum(rep.rep_sold_head_count for rep in rep_lines)
            pending_approval_states = ("submitted", "changed")
            ready_to_proof_states = ("approved", "ready_for_sale")
            pending_approval_count = sum(1 for c in contracts if c.state in pending_approval_states)
            ready_to_proof_count = sum(1 for c in contracts if c.state in ready_to_proof_states)

            meta = {
                "scope": "rep" if scope_partner_id else "company",
                "partner_id": scope_partner_id,
                "date_range": {"from": raw_from, "to": raw_to},
            }

            data = {
                "total_contracts": total_contracts,
                "total_head": total_head,
                "pending_approval_count": pending_approval_count,
                "ready_to_proof_count": ready_to_proof_count,
            }

            return json_response({"data": data, "meta": meta, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting analytics summary (v3)")
            return json_response({"error": "server_error", "error_description": str(e)}, status=500)