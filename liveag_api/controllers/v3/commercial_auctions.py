from odoo import http
from odoo.http import request
import json

from odoo.addons.liveag_api.controllers._mixins.auction_filters import (
    AUCTION_FILTER_SPEC,
    AuctionsFiltersMixin,
)
from odoo.addons.liveag_api.tools.liveag import serialize_auction_preview
from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.api_decorators import (
    odoo_token_required,
    with_pagination,
    with_query_filters,
)

import logging
_logger = logging.getLogger(__name__)


class AuctionsV3Controller(http.Controller, AuctionsFiltersMixin):

    @api_route("/api/v3/auctions", methods=["GET", "POST"])
    @odoo_token_required("api")
    @with_pagination()
    @with_query_filters(AUCTION_FILTER_SPEC)
    def handle_auctions_v3(self, **kw):
        env = request.api_env

        # ---------- GET ----------
        if request.httprequest.method == "GET":
            domain = []
            filters = getattr(request, "parsed_filters", None) or {}
            if not filters.get("sale_type_ids"):
                video_sale = env["sale.type"].search([("name", "=", "Video Sale")], limit=1)
                if video_sale:
                    filters = dict(filters)
                    filters["sale_type_ids"] = [video_sale.id]
            domain = self._apply_filters_to_domain(domain, filters)

            pag = request.pagination
            Auction = env["sale.auction"]

            try:
                if pag["use"]:
                    total_count = Auction.search_count(domain)
                    auctions = Auction.search(
                        domain,
                        limit=pag["limit"],
                        offset=pag["offset"],
                        order="sale_date_begin desc, id desc",
                    )
                    total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
                else:
                    auctions = Auction.search(domain, order="sale_date_begin desc, id desc")

                auction_list = [serialize_auction_preview(a) for a in auctions]

                if pag["use"]:
                    return json_response(
                        {
                            "data": auction_list,
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

                return json_response(auction_list, status=200)

            except Exception as e:
                _logger.exception("Error getting auctions (v3)")
                return json_response({"error": "server_error", "error_description": str(e)}, status=500)

        # ---------- POST ----------
        if request.httprequest.method == "POST":
            user = request.api_user
            if not user.has_group("liveag_consignment.group_consignment_manager"):
                return json_response(
                    {"error": "insufficient_scope", "error_description": "Only Manager can create auctions"},
                    status=403,
                )
            try:
                body = request.httprequest.get_data(as_text=True) or ""
                auction_data = json.loads(body) if body else {}

                if not auction_data:
                    return json_response(
                        {"error": "invalid_request", "error_description": "Auction data missing from request body"},
                        status=400,
                    )

                new_auction = env["sale.auction"].create(auction_data)
                return json_response(serialize_auction_preview(new_auction), status=201)

            except Exception as e:
                _logger.exception("Error creating auction (v3)")
                return json_response({"error": "server_error", "error_description": str(e)}, status=500)

        return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)
