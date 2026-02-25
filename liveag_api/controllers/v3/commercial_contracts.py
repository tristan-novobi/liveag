from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError
import json

from odoo.addons.liveag_api.controllers._mixins.contracts_filters import (
    CONTRACT_FILTER_SPEC,
    ContractsFiltersMixin,
)

# Allowed sort_by values for GET /api/v3/contracts.
CONTRACT_SORT_FIELDS = [
    "id",
    "created_on",  # API alias for create_date
    "contract_id",
    "lot_number",
    "sold_date",
    "state",
    "status",
    "seller",
    "auction",
    "kind",
]
CONTRACT_SORT_FIELD_MAP = {
    "status": "state",
    "created_on": "create_date",
    "seller": "seller_name",
    "auction": "auction_name",
    "kind": "kind1_name",
    "contract_id": "id",
}
from odoo.addons.liveag_consignment.models.consignment_contract import DIRECTION_LIST
from odoo.addons.liveag_api.tools.liveag import (
    serialize_contract_preview,
    serialize_contract_detailed,
    serialize_contract_editable,
    serialize_contract_for_list,
)

# Allowed values for view= query param on GET contract(s). Default: preview.
CONTRACT_VIEW_VALUES = ("list", "preview", "detailed", "editable")
from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.api_decorators import (
    odoo_token_required,
    with_pagination,
    with_query_filters,
    with_sort,
)

import logging

_logger = logging.getLogger(__name__)

# Fields that must never be writable via the public API
_BLOCKED_WRITE_FIELDS = frozenset(
    {
        "id",
        "create_uid",
        "write_uid",
        "create_date",
        "write_date",
        "__last_update",
        "display_name",
    }
)


class ContractsV3Controller(http.Controller, ContractsFiltersMixin):

    @api_route("/api/v3/contracts", methods=["GET", "POST", "PUT"])
    @odoo_token_required("api")
    @with_pagination()
    @with_query_filters(CONTRACT_FILTER_SPEC)
    @with_sort(CONTRACT_SORT_FIELDS, default_field="created_on", default_order="desc")
    def handle_contracts_v3(self, **kw):
        env = request.api_env

        # ---------- GET ----------
        if request.httprequest.method == "GET":
            domain = []
            filters = getattr(request, "parsed_filters", None) or {}
            domain = self._apply_filters_to_domain(domain, filters)

            pag = request.pagination
            sort = getattr(request, "sort", None) or {
                "field": "created_on",
                "order": "desc",
            }
            # Map API sort names to Odoo fields (Many2one: Odoo uses related model's _order for name)
            order_field = CONTRACT_SORT_FIELD_MAP.get(sort["field"], sort["field"])
            order_clause = f"{order_field} {sort['order']}"
            Contract = env["consignment.contract"]

            try:
                if pag["use"]:
                    total_count = Contract.search_count(domain)
                    contracts = Contract.search(
                        domain,
                        limit=pag["limit"],
                        offset=pag["offset"],
                        order=order_clause,
                    )
                    total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
                else:
                    contracts = Contract.search(domain, order=order_clause)

                contract_list = [serialize_contract_for_list(c) for c in contracts]

                if pag["use"]:
                    return json_response(
                        {
                            "data": contract_list,
                            "pagination": {
                                "page": pag["page"],
                                "per_page": pag["per_page"],
                                "total_count": total_count,
                                "total_pages": total_pages,
                            },
                            "success": True,
                        },
                        status=200,
                    )

                return json_response(contract_list, status=200)

            except Exception as e:
                _logger.exception("Error getting contracts (v3)")
                return json_response(
                    {"error": "server_error", "error_description": str(e)}, status=500
                )

        # ---------- POST ----------
        if request.httprequest.method == "POST":
            user = request.api_user
            if not user.has_group(
                "liveag_consignment.group_consignment_manager"
            ) and not user.has_group("liveag_consignment.group_consignment_rep"):
                return json_response(
                    {
                        "error": "insufficient_scope",
                        "error_description": "Only Manager or Rep can create contracts",
                    },
                    status=403,
                )
            try:
                body = request.httprequest.get_data(as_text=True) or ""
                contract_data = json.loads(body) if body else {}

                if not contract_data:
                    return json_response(
                        {
                            "error": "invalid_request",
                            "error_description": "Contract data missing from request body",
                        },
                        status=400,
                    )

                contract_data.pop("rep_ids", None)  # reps managed separately elsewhere
                contract_data = {
                    k: v
                    for k, v in contract_data.items()
                    if k not in _BLOCKED_WRITE_FIELDS
                }

                new_contract = env["consignment.contract"].create(contract_data)

                return json_response({"id": new_contract.id}, status=201)

            except Exception as e:
                _logger.exception("Error creating contract (v3)")
                return json_response(
                    {"error": "server_error", "error_description": str(e)}, status=500
                )

        # ---------- PUT ----------
        if request.httprequest.method == "PUT":
            user = request.api_user
            if not user.has_group(
                "liveag_consignment.group_consignment_manager"
            ) and not user.has_group("liveag_consignment.group_consignment_rep"):
                return json_response(
                    {
                        "error": "insufficient_scope",
                        "error_description": "Only Manager or Rep can update contracts",
                    },
                    status=403,
                )
            try:
                contract_id = request.params.get("contract_id")
                if not contract_id:
                    return json_response(
                        {
                            "error": "invalid_request",
                            "error_description": "Missing contract_id",
                        },
                        status=400,
                    )

                try:
                    cid = int(contract_id)
                except (TypeError, ValueError):
                    return json_response(
                        {
                            "error": "invalid_request",
                            "error_description": "Invalid contract_id (must be an integer)",
                        },
                        status=400,
                    )

                contract = env["consignment.contract"].browse(cid)
                if not contract.exists():
                    return json_response(
                        {
                            "error": "not_found",
                            "error_description": "Contract not found",
                        },
                        status=404,
                    )

                # Prefer JSON body, fallback to ?vals=...
                vals = {}
                body = request.httprequest.get_data(as_text=True) or ""
                if body:
                    try:
                        vals = json.loads(body)
                    except Exception:
                        vals = {}

                if not vals:
                    vals_param = request.params.get("vals")
                    if vals_param:
                        try:
                            vals = json.loads(vals_param)
                        except Exception:
                            vals = {}

                if not isinstance(vals, dict) or not vals:
                    return json_response(
                        {
                            "error": "invalid_request",
                            "error_description": "Missing or invalid 'vals'.",
                        },
                        status=400,
                    )

                vals = {k: v for k, v in vals.items() if k not in _BLOCKED_WRITE_FIELDS}
                contract.write(vals)
                return json_response({"success": True}, status=200)

            except Exception as e:
                _logger.exception("Error updating contract (v3)")
                return json_response(
                    {"error": "server_error", "error_description": str(e)}, status=500
                )

        return json_response(
            {"error": "method_not_allowed", "error_description": "Method not allowed"},
            status=405,
        )

    # ---------- Contracts by ID ----------
    @api_route("/api/v3/contracts/<int:contract_id>", methods=["GET", "PUT"])
    @odoo_token_required("api")
    def handle_contracts_by_id(self, contract_id, **kw):
        # ---------- GET ----------
        if request.httprequest.method == "GET":
            view = (request.params.get("view") or "preview").strip().lower()
            if view not in CONTRACT_VIEW_VALUES:
                return json_response(
                    {
                        "error": "invalid_request",
                        "error_description": f"view must be one of: {', '.join(CONTRACT_VIEW_VALUES)}",
                    },
                    status=400,
                )

            try:
                env = request.api_env
                contract = env["consignment.contract"].search(
                    [("id", "=", contract_id)], limit=1
                )
                if not contract:
                    return json_response(
                        {
                            "error": "not_found",
                            "error_description": "Contract not found or access denied",
                        },
                        status=404,
                    )
                if view == "list":
                    data = serialize_contract_for_list(contract)
                elif view == "detailed":
                    data = serialize_contract_detailed(contract)
                elif view == "editable":
                    data = serialize_contract_editable(contract)
                else:
                    data = serialize_contract_preview(contract)
                return json_response({"data": data, "success": True}, status=200)
            except Exception as e:
                _logger.exception("Error getting contract by ID (v3)")
                return json_response(
                    {"error": "server_error", "error_description": str(e)}, status=500
                )

        # ---------- PUT ----------
        if request.httprequest.method == "PUT":
            try:
                env = request.api_env
                contract = env["consignment.contract"].search(
                    [("id", "=", contract_id)], limit=1
                )
                if not contract:
                    return json_response(
                        {
                            "error": "not_found",
                            "error_description": "Contract not found or access denied",
                        },
                        status=404,
                    )
                body = request.httprequest.get_data(as_text=True) or ""
                vals = {}
                if body:
                    try:
                        vals = json.loads(body)
                    except Exception:
                        vals = {}
                if not isinstance(vals, dict) or not vals:
                    return json_response(
                        {
                            "error": "invalid_request",
                            "error_description": "Missing or invalid 'vals'.",
                        },
                        status=400,
                    )
                # Transform rep_ids from API format (list of dicts) to Odoo One2many commands
                incoming_rep_data = vals.pop("rep_ids", None)
                if incoming_rep_data is not None and isinstance(
                    incoming_rep_data, list
                ):
                    rep_commands = [(5, 0, 0)]
                    for rep_data in incoming_rep_data:
                        if (
                            isinstance(rep_data, dict)
                            and rep_data.get("rep_id") is not None
                        ):
                            rep_commands.append(
                                (
                                    0,
                                    0,
                                    {
                                        "rep_id": rep_data["rep_id"],
                                        "percentage_commission": rep_data.get(
                                            "percentage_commission", 0
                                        ),
                                        "consigning_rep": rep_data.get(
                                            "consigning_rep", False
                                        ),
                                        "seller_id": contract.seller_id.id,
                                        "active": True,
                                    },
                                )
                            )
                    vals["rep_ids"] = rep_commands
                # Transform addendum_ids from API format (list of dicts) to Odoo One2many commands
                incoming_addendum_data = vals.pop("addendum_ids", None)
                if incoming_addendum_data is not None and isinstance(
                    incoming_addendum_data, list
                ):
                    existing_addendums = contract.addendum_ids
                    existing_addendum_ids = {a.id for a in existing_addendums}
                    addendums_to_delete = [
                        (2, a.id, False)
                        for a in existing_addendums
                        if a.id
                        not in {
                            ad.get("id")
                            for ad in incoming_addendum_data
                            if isinstance(ad, dict) and ad.get("id")
                        }
                    ]
                    addendums_to_update = [
                        (
                            1,
                            ad["id"],
                            {
                                "seller_id": ad["seller_id"],
                                "head_count": ad.get("head_count", 0),
                                "percentage": ad.get("percentage", 100),
                                "lien_holder_id": ad.get("lien_holder_id"),
                                "part_payment": ad.get("part_payment", 0),
                                "active": ad.get("active", True),
                            },
                        )
                        for ad in incoming_addendum_data
                        if isinstance(ad, dict)
                        and ad.get("id") in existing_addendum_ids
                    ]
                    addendums_to_add = [
                        (
                            0,
                            0,
                            {
                                "seller_id": ad["seller_id"],
                                "head_count": ad.get("head_count", 0),
                                "percentage": ad.get("percentage", 100),
                                "lien_holder_id": ad.get("lien_holder_id"),
                                "part_payment": ad.get("part_payment", 0),
                                "active": ad.get("active", True),
                            },
                        )
                        for ad in incoming_addendum_data
                        if isinstance(ad, dict) and not ad.get("id")
                    ]
                    vals["addendum_ids"] = (
                        addendums_to_delete + addendums_to_update + addendums_to_add
                    )
                # Transform option_contract_ids from API format (list of {id?, head1, head2}) to create/update
                incoming_option_data = vals.pop("option_contract_ids", None)
                if incoming_option_data is not None and isinstance(
                    incoming_option_data, list
                ):
                    existing_options = contract.option_contract_ids
                    existing_option_ids = {o.id for o in existing_options}
                    final_option_ids = []
                    for opt_data in incoming_option_data:
                        if not isinstance(opt_data, dict):
                            continue
                        opt_id = opt_data.get("id")
                        head1 = opt_data.get("head1")
                        head2 = opt_data.get("head2")
                        if opt_id and opt_id in existing_option_ids:
                            opt_contract = existing_options.filtered(
                                lambda o: o.id == opt_id
                            )[:1]
                            if opt_contract:
                                opt_contract.write({"head1": head1, "head2": head2})
                                final_option_ids.append(opt_id)
                        else:
                            default = {
                                "head1": head1,
                                "head2": head2,
                                "delivery_date_start": contract.delivery_date_start,
                                "delivery_date_end": contract.delivery_date_end,
                            }
                            new_opt = contract.copy(default)
                            new_opt.write(
                                {
                                    "option_on_contract": True,
                                    "auction_id": (
                                        contract.auction_id.id
                                        if contract.auction_id
                                        else False
                                    ),
                                }
                            )
                            final_option_ids.append(new_opt.id)
                    all_ids = [contract.id] + final_option_ids
                    vals["option_contract_ids"] = [(6, 0, final_option_ids)]
                    for opt_id in final_option_ids:
                        opt_contract = env["consignment.contract"].browse(opt_id)
                        if opt_contract.exists():
                            other_ids = [x for x in all_ids if x != opt_id]
                            opt_contract.write(
                                {"option_contract_ids": [(6, 0, other_ids)]}
                            )
                vals = {k: v for k, v in vals.items() if k not in _BLOCKED_WRITE_FIELDS}
                contract.write(vals)
                return json_response({"success": True}, status=200)
            except AccessError as e:
                _logger.warning("Access denied updating contract by ID (v3): %s", e)
                return json_response(
                    {
                        "error": "access_denied",
                        "error_description": str(e)
                        or "You do not have permission to update this contract.",
                    },
                    status=403,
                )
            except Exception as e:
                _logger.exception("Error updating contract by ID (v3)")
                return json_response(
                    {"error": "server_error", "error_description": str(e)}, status=500
                )

        return json_response(
            {"error": "method_not_allowed", "error_description": "Method not allowed"},
            status=405,
        )

    # ---------- Copy Contract ----------
    @api_route("/api/v3/contracts/<int:contract_id>/copy", methods=["POST"])
    @odoo_token_required("api")
    def handle_contract_copy(self, contract_id, **kw):
        user = request.api_user
        if not user.has_group(
            "liveag_consignment.group_consignment_manager"
        ) and not user.has_group("liveag_consignment.group_consignment_rep"):
            return json_response(
                {
                    "error": "insufficient_scope",
                    "error_description": "Only Manager or Rep can copy contracts",
                },
                status=403,
            )
        try:
            env = request.api_env
            contract = env["consignment.contract"].search(
                [("id", "=", contract_id)], limit=1
            )
            if not contract:
                return json_response(
                    {
                        "error": "not_found",
                        "error_description": "Contract not found or access denied",
                    },
                    status=404,
                )
            new_contract = contract.copy()
            return json_response({"id": new_contract.id}, status=201)
        except AccessError as e:
            _logger.warning("Access denied copying contract (v3): %s", e)
            return json_response(
                {
                    "error": "access_denied",
                    "error_description": str(e)
                    or "You do not have permission to copy this contract.",
                },
                status=403,
            )
        except (ValidationError, UserError) as e:
            _logger.warning("Business rule violation copying contract (v3): %s", e)
            return json_response(
                {
                    "error": "invalid_request",
                    "error_description": str(e),
                },
                status=400,
            )
        except Exception as e:
            _logger.exception("Error copying contract (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Metadata ----------
    # ---------- Statuses ----------
    @api_route("/api/v3/contracts/metadata/status", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_status(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            Contract = request.api_env["consignment.contract"]
            selection = Contract._fields["state"].selection
            statuses = [{"value": value, "label": label} for value, label in selection]
            return json_response({"data": statuses, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract statuses (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Sale Types ----------
    @api_route("/api/v3/contracts/metadata/sale_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_sale_types(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            sale_types = env["sale.type"].search(
                [("active", "=", True)], order="sequence, id"
            )
            sale_type_list = [{"value": st.id, "label": st.name} for st in sale_types]
            return json_response({"data": sale_type_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract sale types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Kinds ----------
    @api_route("/api/v3/contracts/metadata/kind", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_kind(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            kinds = env["kind.list"].search(
                [("active", "=", True)], order="sequence, id"
            )
            kind_list = [{"value": k.id, "label": k.name, "sex": k.sex} for k in kinds]
            return json_response({"data": kind_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract kinds (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Contract Types ----------
    @api_route("/api/v3/contracts/metadata/contract_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_contract_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            contract_types = env["contract.type"].search(
                [("active", "=", True)], order="sequence, id"
            )
            contract_type_list = [
                {"value": ct.id, "label": ct.name} for ct in contract_types
            ]
            return json_response(
                {"data": contract_type_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract contract types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Origins ----------
    @api_route("/api/v3/contracts/metadata/origin", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_origin(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            origins = env["origin.list"].search(
                [("active", "=", True)], order="sequence, id"
            )
            origin_list = [{"value": o.id, "label": o.name} for o in origins]
            return json_response({"data": origin_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract origins (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Frame Sizes ----------
    @api_route("/api/v3/contracts/metadata/frame_size", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_frame_size(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            frame_sizes = env["frame.size"].search(
                [("active", "=", True)], order="sequence, id"
            )
            frame_size_list = [{"value": fs.id, "label": fs.name} for fs in frame_sizes]
            return json_response({"data": frame_size_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract frame sizes (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Flesh Types ----------
    @api_route("/api/v3/contracts/metadata/flesh_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_flesh_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            flesh_types = env["flesh.type"].search(
                [("active", "=", True)], order="sequence, id"
            )
            flesh_type_list = [{"value": ft.id, "label": ft.name} for ft in flesh_types]
            return json_response({"data": flesh_type_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract flesh types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Weight Variances ----------
    @api_route("/api/v3/contracts/metadata/weight_variance", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_weight_variance(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            weight_variances = env["weight.variance"].search(
                [("active", "=", True)], order="sequence, id"
            )
            weight_variance_list = [
                {"value": wv.id, "label": wv.name} for wv in weight_variances
            ]
            return json_response(
                {"data": weight_variance_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract weight variances (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Horns ----------
    @api_route("/api/v3/contracts/metadata/horns", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_horns(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            horns = env["horns.list"].search(
                [("active", "=", True)], order="sequence, id"
            )
            horns_list = [{"value": h.id, "label": h.name} for h in horns]
            return json_response({"data": horns_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract horns (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Implanted Types ----------
    @api_route("/api/v3/contracts/metadata/implanted_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_implanted_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            implanted_types = env["implanted.list"].search(
                [("active", "=", True)], order="sequence, id"
            )
            implanted_type_list = [
                {"value": it.id, "label": it.name} for it in implanted_types
            ]
            return json_response(
                {"data": implanted_type_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract implanted types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Castrations ----------
    @api_route("/api/v3/contracts/metadata/castration_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_castration_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            castration_types = env["castration.list"].search(
                [("active", "=", True)], order="sequence, id"
            )
            castration_type_list = [
                {"value": ct.id, "label": ct.name} for ct in castration_types
            ]
            return json_response(
                {"data": castration_type_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract castration types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Bangs Vaccinated ----------
    @api_route("/api/v3/contracts/metadata/bangs_vaccination", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_bangs_vaccination(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            bangs_vaccinations = env["bangs.vaccinated"].search(
                [("active", "=", True)], order="sequence, id"
            )
            bangs_vaccination_list = [
                {"value": bv.id, "label": bv.name} for bv in bangs_vaccinations
            ]
            return json_response(
                {"data": bangs_vaccination_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract bangs vaccinations (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Special Sections ----------
    @api_route("/api/v3/contracts/metadata/special_section", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_special_section(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            special_sections = env["special.section"].search(
                [("active", "=", True)], order="sequence, id"
            )
            special_section_list = [
                {"value": ss.id, "label": ss.name} for ss in special_sections
            ]
            return json_response(
                {"data": special_section_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract special sections (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Genetic Merits ----------
    @api_route("/api/v3/contracts/metadata/genetic_merit", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_genetic_merit(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            genetic_merits = env["genetic.merit"].search(
                [("active", "=", True)], order="sequence, id"
            )
            genetic_merit_list = [
                {"value": gm.id, "label": gm.name} for gm in genetic_merits
            ]
            return json_response(
                {"data": genetic_merit_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract genetic merits (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Premium Genetics Programs ----------
    @api_route("/api/v3/contracts/metadata/premium_genetics_program", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_premium_genetics_program(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            premium_genetics_programs = env["premium.genetics.program"].search(
                [("active", "=", True)], order="sequence, id"
            )
            premium_genetics_program_list = [
                {"value": pgp.id, "label": pgp.name}
                for pgp in premium_genetics_programs
            ]
            return json_response(
                {"data": premium_genetics_program_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract premium genetics programs (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Value Added Nutrition Programs ----------
    @api_route("/api/v3/contracts/metadata/van_program", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_van_program(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            van_programs = env["van.program"].search(
                [("active", "=", True)], order="sequence, id"
            )
            van_program_list = [
                {"value": vp.id, "label": vp.name} for vp in van_programs
            ]
            return json_response(
                {"data": van_program_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract van programs (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Source Age Programs ----------
    @api_route("/api/v3/contracts/metadata/source_age_program", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_source_age_program(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            source_age_programs = env["third.party.age"].search(
                [("active", "=", True)], order="sequence, id"
            )
            source_age_program_list = [
                {"value": sa.id, "label": sa.name} for sa in source_age_programs
            ]
            return json_response(
                {"data": source_age_program_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract source age programs (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- VAC Programs ----------
    @api_route("/api/v3/contracts/metadata/vac_program", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_vac_program(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            vac_programs = env["vac.program"].search(
                [("active", "=", True)], order="sequence, id"
            )
            vac_program_list = [
                {"value": vp.id, "label": vp.name} for vp in vac_programs
            ]
            return json_response(
                {"data": vac_program_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract vac programs (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Location Types ----------
    @api_route("/api/v3/contracts/metadata/location_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_location_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            location_types = env["location.type"].search(
                [("active", "=", True)], order="sequence, id"
            )
            location_type_list = [
                {"value": lt.id, "label": lt.name} for lt in location_types
            ]
            return json_response(
                {"data": location_type_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract location types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Delivery Option Types ----------
    @api_route("/api/v3/contracts/metadata/delivery_option", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_delivery_option(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            delivery_options = env["whose.option"].search(
                [("active", "=", True)], order="sequence, id"
            )
            delivery_option_list = [
                {"value": do.id, "label": do.name} for do in delivery_options
            ]
            return json_response(
                {"data": delivery_option_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract delivery options (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Slide Types ----------
    @api_route("/api/v3/contracts/metadata/slide_type", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_slide_type(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            slide_types = env["slide.type"].search(
                [("active", "=", True)], order="sequence, id"
            )
            slide_type_list = [
                {
                    "value": st.id,
                    "label": st.label,
                    "sell_by_head": st.sell_by_head,
                    "above": st.above,
                    "under": st.under,
                    "both": st.both,
                    "description": st.description,
                }
                for st in slide_types
            ]
            return json_response({"data": slide_type_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract slide types (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Weight Stops ----------
    @api_route("/api/v3/contracts/metadata/weight_stop", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_weight_stop(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            weight_stops = env["weight.stop"].search(
                [("active", "=", True)], order="sequence, id"
            )
            weight_stop_list = [
                {"value": ws.id, "label": ws.name} for ws in weight_stops
            ]
            return json_response(
                {"data": weight_stop_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract weight stops (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Weight Stops ----------
    @api_route("/api/v3/contracts/metadata/gap_program", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_gap_program(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            env = request.api_env
            gap_programs = env["gap.program"].search(
                [("active", "=", True)], order="sequence, id"
            )
            gap_program_list = [
                {"value": gp.id, "label": gp.name} for gp in gap_programs
            ]
            return json_response(
                {"data": gap_program_list, "success": True}, status=200
            )
        except Exception as e:
            _logger.exception("Error getting contract gap programs (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )

    # ---------- Directions ----------
    @api_route("/api/v3/metadata/directions", methods=["GET"])
    @odoo_token_required("api")
    def handle_contracts_direction(self, **kw):
        if request.httprequest.method != "GET":
            return json_response(
                {
                    "error": "method_not_allowed",
                    "error_description": "Method not allowed",
                },
                status=405,
            )

        try:
            direction_list = [
                {"value": val, "label": label} for val, label in DIRECTION_LIST
            ]
            return json_response({"data": direction_list, "success": True}, status=200)
        except Exception as e:
            _logger.exception("Error getting contract directions (v3)")
            return json_response(
                {"error": "server_error", "error_description": str(e)}, status=500
            )
