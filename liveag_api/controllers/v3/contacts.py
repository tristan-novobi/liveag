from odoo import http
from odoo.http import request
import json

from odoo.addons.liveag_api.controllers._mixins.auction_filters import (
    AUCTION_FILTER_SPEC,
    AuctionsFiltersMixin,
)
from odoo.addons.liveag_api.tools.liveag import (
	serialize_contact_basic_info,
	serialize_contact_seller,
	serialize_contact_rep,
	serialize_payment_address,
	serialize_lienholder,
)
from odoo.addons.liveag_api.tools.http_utils import json_response, api_route
from odoo.addons.liveag_api.tools.api_decorators import (
    odoo_token_required,
    with_pagination,
    with_query_filters,
)
from odoo.addons.liveag_api.tools.roles import user_has_role

import logging
_logger = logging.getLogger(__name__)


class ContactsV3Controller(http.Controller):
  @api_route("/api/v3/contacts", methods=["GET"])
  @odoo_token_required("api")
  @with_pagination()
  def handle_contacts_v3(self, **kw):
      env = request.api_env

      # ---------- GET ----------
      if request.httprequest.method == "GET":
          domain = []

          pag = request.pagination
          Contact = env["res.partner"]

          try:
              if pag["use"]:
                  total_count = Contact.search_count(domain)
                  contacts = Contact.search(
                      domain,
                      limit=pag["limit"],
                      offset=pag["offset"],
                      order="name asc, id desc",
                  )
                  total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
              else:
                  contacts = Contact.search(domain, order="name asc, id desc")

              contact_list = [serialize_contact_basic_info(c) for c in contacts]

              if pag["use"]:
                  return json_response(
                      {
                          "data": contact_list,
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

              return json_response(contact_list, status=200)

          except Exception as e:
              _logger.exception("Error getting contacts (v3)")
              return json_response({"error": "server_error", "error_description": str(e)}, status=500)

      # ---------- POST ----------
      if request.httprequest.method == "POST":
          user = request.api_user
          if not user.has_group("liveag_consignment.group_consignment_manager"):
              return json_response(
                  {"error": "insufficient_scope", "error_description": "Only Manager can create contacts"},
                  status=403,
              )
          try:
              body = request.httprequest.get_data(as_text=True) or ""
              contact_data = json.loads(body) if body else {}

              if not contact_data:
                  return json_response(
                      {"error": "invalid_request", "error_description": "Contact data missing from request body"},
                      status=400,
                  )

              new_contact = env["res.partner"].create(contact_data)
              return json_response(serialize_contact_basic_info(new_contact), status=201)

          except Exception as e:
              _logger.exception("Error creating contact (v3)")
              return json_response({"error": "server_error", "error_description": str(e)}, status=500)

      return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

  @api_route("/api/v3/contacts/sellers", methods=["GET"])
  @odoo_token_required("api")
  @with_pagination()
  def handle_sellers_v3(self, **kw):
      env = request.api_env
      if request.httprequest.method == "GET":
          # Resolve seller contact type by name (no dependency on XML ID)
          seller_type = env["res.contact.type"].search([("name", "=", "Seller")], limit=1)
          domain = [("contact_type_ids", "in", seller_type.ids)] if seller_type else []

          # Reps see only sellers that have them in rep_ids; admins see all sellers
          user = request.api_user
          is_admin = user_has_role(user, "commercial", "admin")
          is_rep = user_has_role(user, "commercial", "rep")
          if is_rep and not is_admin and user.partner_id:
              domain.append(("rep_ids.rep_id", "=", user.partner_id.id))

          pag = request.pagination
          total_count = env["res.partner"].search_count(domain) if pag["use"] else None
          sellers = env["res.partner"].search(
              domain,
              limit=pag["limit"] if pag["use"] else None,
              offset=pag["offset"] if pag["use"] else None,
              order="name asc, id desc",
            )
          
          seller_list = []
          for seller in sellers:
            seller_info = serialize_contact_basic_info(seller)
            seller_info.update(serialize_contact_seller(seller))
            seller_list.append(seller_info)
            
          if pag["use"]:
              total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
              return json_response({
                  "data": seller_list,
                  "pagination": {
                      "page": pag["page"],
                      "per_page": pag["per_page"],
                      "total_count": total_count,
                      "total_pages": total_pages,
                  },
                  "success": True,
              }, status=200)
          return json_response({"data": seller_list, "success": True}, status=200)

      return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)
  
  # ---------- Seller by ID ----------
  @api_route("/api/v3/contacts/sellers/<int:seller_id>", methods=["GET"])
  @odoo_token_required("api")
  def handle_sellers_by_id_v3(self, seller_id, **kw):
      env = request.api_env
      if request.httprequest.method == "GET":
          # Resolve seller contact type by name (no dependency on XML ID)
          seller_type = env["res.contact.type"].search([("name", "=", "Seller")], limit=1)
          domain = [("id", "=", seller_id), ("contact_type_ids", "in", seller_type.ids)] if seller_type else []

          # Reps see only sellers that have them in rep_ids; admins see all sellers
          user = request.api_user
          is_admin = user_has_role(user, "commercial", "admin")
          is_rep = user_has_role(user, "commercial", "rep")
          if is_rep and not is_admin and user.partner_id:
              domain.append(("rep_ids.rep_id", "=", user.partner_id.id))

          seller = env["res.partner"].search(domain, limit=1)
          if not seller:
              return json_response({"error": "not_found", "error_description": "Seller not found"}, status=404)
          
          seller_info = serialize_contact_basic_info(seller)
          seller_info.update(serialize_contact_seller(seller))
          return json_response({"data": seller_info, "success": True}, status=200)

      return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

  # ---------- Seller Payment Info ----------
  @api_route("/api/v3/contacts/sellers/<int:seller_id>/payment_options", methods=["GET"])
  @odoo_token_required("api")
  def handle_sellers_payment_options_v3(self, seller_id, **kw):
      if request.httprequest.method != "GET":
          return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

      env = request.api_env
      seller_type = env["res.contact.type"].search([("name", "=", "Seller")], limit=1)
      domain = [("id", "=", seller_id), ("contact_type_ids", "in", seller_type.ids)] if seller_type else []

      user = request.api_user
      is_admin = user_has_role(user, "commercial", "admin")
      is_rep = user_has_role(user, "commercial", "rep")
      if is_rep and not is_admin and user.partner_id:
          domain.append(("rep_ids.rep_id", "=", user.partner_id.id))

      seller = env["res.partner"].search(domain, limit=1)
      if not seller:
          return json_response({"error": "not_found", "error_description": "Seller not found"}, status=404)

      # Payment options = seller's child contacts with type "Payment Address" (addendum pattern).
      # If none exist, return seller's own basic contact as single option so UI always has a choice.
      # To create a real payment-address child, use server action "Create payment address for selected contacts" or ensure_payment_address().
      payment_addresses = seller.child_ids.filtered(lambda p: p.type == "payment")
      default_id = seller.default_payment_info_id.id if seller.default_payment_info_id else None

      if not payment_addresses:
          data = [serialize_payment_address(seller, is_default=True)]
      else:
          data = [
              serialize_payment_address(addr, is_default=(addr.id == default_id))
              for addr in payment_addresses
          ]
      return json_response({"data": data, "success": True}, status=200)

  # ---------- Seller Lienholder Options ----------
  @api_route("/api/v3/contacts/sellers/<int:seller_id>/lien_holders", methods=["GET"])
  @odoo_token_required("api")
  def handle_sellers_lienholders_v3(self, seller_id, **kw):
      if request.httprequest.method != "GET":
          return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

      env = request.api_env
      seller_type = env["res.contact.type"].search([("name", "=", "Seller")], limit=1)
      domain = [("id", "=", seller_id), ("contact_type_ids", "in", seller_type.ids)] if seller_type else []

      user = request.api_user
      is_admin = user_has_role(user, "commercial", "admin")
      is_rep = user_has_role(user, "commercial", "rep")
      if is_rep and not is_admin and user.partner_id:
          domain.append(("rep_ids.rep_id", "=", user.partner_id.id))

      seller = env["res.partner"].search(domain, limit=1)
      if not seller:
          return json_response({"error": "not_found", "error_description": "Seller not found"}, status=404)

      lienholders = seller.lien_holder_ids
      default_id = seller.default_lien_holder_id.id if seller.default_lien_holder_id else None

      if not lienholders:
          data = [serialize_lienholder(seller, is_default=True)]
      else:
          data = [
              serialize_lienholder(lienholder, is_default=(lienholder.id == default_id))
              for lienholder in lienholders
          ]
      return json_response({"data": data, "success": True}, status=200)

  @api_route("/api/v3/contacts/reps", methods=["GET"])
  @odoo_token_required("api")
  @with_pagination()
  def handle_reps_v3(self, **kw):
      env = request.api_env
      if request.httprequest.method == "GET":
          # Resolve rep contact type by name (no dependency on XML ID)
          rep_type = env["res.contact.type"].search([("name", "=", "Rep")], limit=1)
          domain = [("contact_type_ids", "in", rep_type.ids)] if rep_type else []

          # Admins and reps both get full list of reps (record rule allows reps to see Rep-type partners)
          pag = request.pagination
          total_count = env["res.partner"].search_count(domain) if pag["use"] else None
          reps = env["res.partner"].search(
              domain,
              limit=pag["limit"] if pag["use"] else None,
              offset=pag["offset"] if pag["use"] else None,
              order="name asc, id desc",
            )
          
          rep_list = []
          for rep in reps:
            rep_info = serialize_contact_basic_info(rep)
            rep_info.update(serialize_contact_rep(rep))
            rep_list.append(rep_info)
            
          if pag["use"]:
              total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
              return json_response({
                  "data": rep_list,
                  "pagination": {
                      "page": pag["page"],
                      "per_page": pag["per_page"],
                      "total_count": total_count,
                      "total_pages": total_pages,
                  },
                  "success": True,
              }, status=200)
          return json_response({"data": rep_list, "success": True}, status=200)

      return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)

  # ---------- Lien Holders ----------
  @api_route("/api/v3/contacts/lien_holders", methods=["GET"])
  @odoo_token_required("api")
  @with_pagination()
  def handle_lien_holders_v3(self, **kw):
      env = request.api_env
      if request.httprequest.method == "GET":
          # Resolve seller contact type by name (no dependency on XML ID)
          lien_holder_type = env["res.contact.type"].search([("name", "=", "Lien Holder")], limit=1)
          domain = [("contact_type_ids", "in", lien_holder_type.ids)] if lien_holder_type else []

          # Reps see only sellers that have them in rep_ids; admins see all sellers
          user = request.api_user
          is_admin = user_has_role(user, "commercial", "admin")
          is_rep = user_has_role(user, "commercial", "rep")
          if is_rep and not is_admin and user.partner_id:
              domain.append(("rep_ids.rep_id", "=", user.partner_id.id))

          pag = request.pagination
          total_count = env["res.partner"].search_count(domain) if pag["use"] else None
          lien_holders = env["res.partner"].search(
              domain,
              limit=pag["limit"] if pag["use"] else None,
              offset=pag["offset"] if pag["use"] else None,
              order="name asc, id desc",
            )
          
          lien_holder_list = []
          for lien_holder in lien_holders:
            lien_holder_info = serialize_lienholder(lien_holder)
            lien_holder_list.append(lien_holder_info)
            
          if pag["use"]:
              total_pages = (total_count + pag["per_page"] - 1) // pag["per_page"]
              return json_response({
                  "data": lien_holder_list,
                  "pagination": {
                      "page": pag["page"],
                      "per_page": pag["per_page"],
                      "total_count": total_count,
                      "total_pages": total_pages,
                  },
                  "success": True,
              }, status=200)
          return json_response({"data": lien_holder_list, "success": True}, status=200)

      return json_response({"error": "method_not_allowed", "error_description": "Method not allowed"}, status=405)