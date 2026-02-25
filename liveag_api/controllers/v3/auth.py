import json
import logging
from urllib.parse import quote

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.tools import html_escape

from odoo.addons.liveag_api.controllers.v3.webhooks import (
    _clerk_payload_user_data,
    _sync_clerk_user_to_odoo,
)
from odoo.addons.liveag_api.tools.clerk_jwt import verify_clerk_jwt
from odoo.addons.liveag_api.tools.http_utils import json_response, api_route

_logger = logging.getLogger(__name__)

PORTAL_GROUP_XMLID = "base.group_portal"
REP_REQUEST_CHANNEL_NAME = "rep-request"

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _post_rep_request_to_channel(env, partner):
    """Post a message to the rep-request Discuss channel linking the partner."""
    channel = env["discuss.channel"].sudo().search(
        [("name", "=", REP_REQUEST_CHANNEL_NAME)], limit=1
    )
    if not channel:
        _logger.warning("Discuss channel '%s' not found; skipping rep request notification", REP_REQUEST_CHANNEL_NAME)
        return
    partner_name = html_escape(partner.name or partner.email or "Contact")
    partner_url = f"/web#id={partner.id}&model=res.partner&view_type=form"
    redirect = quote(f"/web#model=discuss.channel&id={channel.id}", safe="")
    approve_url = f"/api/v3/rep-request/approve/{partner.id}?redirect={redirect}"
    body = Markup(
        '<p><a href="%s">%s</a> has requested access to ACTS. Please review the contact '
        'and assign them as a rep to allow access.</p>'
        '<p class="mb-0 mt-2">'
        '<a href="%s" class="btn btn-sm btn-success">Approve as Rep</a>'
        '</p>'
    ) % (partner_url, partner_name, approve_url)
    try:
        channel.message_post(
            body=body,
            message_type="comment",  # 'comment' = chat bubble; 'notification' = centered system message
            subtype_xmlid="mail.mt_comment",
            author_id=partner.id,  # Show requesting contact's name instead of "Public User"
        )
    except Exception as e:
        _logger.exception("Failed to post rep request to channel: %s", e)


class AuthController(http.Controller):
    @http.route("/api/v3/rep-request/approve/<int:partner_id>", type="http", auth="user", methods=["GET"])
    def rep_request_approve(self, partner_id, redirect=None, **kw):
        """Approve a partner as Rep from the rep-request Discuss channel.
        Adds Rep to contact_type_ids, which syncs group_consignment_rep to the portal user."""
        manager_group = request.env.ref("liveag_consignment.group_consignment_manager").sudo()
        if manager_group not in request.env.user.group_ids:
            return request.redirect("/web#error=unauthorized")
        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return request.redirect("/web#error=partner_not_found")
        rep_type = request.env["res.contact.type"].sudo().search([("name", "=", "Rep")], limit=1)
        if not rep_type:
            _logger.error("Rep contact type not found")
            return request.redirect("/web#error=config")
        if rep_type not in partner.contact_type_ids:
            partner.write({"contact_type_ids": [(4, rep_type.id)]})
        # Log approval in rep-request channel
        channel = request.env["discuss.channel"].sudo().search(
            [("name", "=", REP_REQUEST_CHANNEL_NAME)], limit=1
        )
        if channel:
            approver_name = html_escape(request.env.user.partner_id.name or "Unknown")
            partner_name = html_escape(partner.name or partner.email or "Contact")
            partner_url = f"/web#id={partner.id}&model=res.partner&view_type=form"
            try:
                channel.message_post(
                    body=Markup(
                        '<p>Approved <a href="%s">%s</a> as Rep.</p>'
                    ) % (partner_url, partner_name),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    author_id=request.env.user.partner_id.id,
                )
            except Exception as e:
                _logger.exception("Failed to log approval in rep-request channel: %s", e)
        redirect_url = (redirect and redirect.strip()) or "/web"
        if not redirect_url.startswith("/") or "//" in redirect_url:
            redirect_url = "/web"
        return request.redirect(redirect_url)

    @api_route("/api/v3/authentication/request-access", methods=["POST"])
    def request_access(self, **kw):
        # Verify Clerk JWT (same pattern as token_exchange)
        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return json_response(
                {"error": "invalid_request", "error_description": "Missing Bearer token"},
                status=400,
            )
        clerk_jwt = auth.split(" ", 1)[1].strip()

        ICP = request.env["ir.config_parameter"].sudo()
        issuer = ICP.get_param("clerk.issuer")
        jwks_url = ICP.get_param("clerk.jwks_url")
        audience = ICP.get_param("clerk.audience") or None

        if not issuer or not jwks_url:
            _logger.error("Clerk config missing: clerk.issuer / clerk.jwks_url")
            return json_response(
                {"error": "server_error", "error_description": "Clerk config not set"},
                status=500,
            )

        try:
            claims = verify_clerk_jwt(clerk_jwt, jwks_url=jwks_url, issuer=issuer, audience=audience)
        except Exception as e:
            err_str = str(e)
            _logger.warning("Clerk JWT invalid on request-access: %s", err_str)
            # If Clerk/JWKS returned 403 (e.g. forbidden URL), return 403 so status matches
            if "403" in err_str or "Forbidden" in err_str:
                return json_response(
                    {"error": "access_denied", "error_description": "Token verification service unavailable (forbidden)"},
                    status=403,
                )
            return json_response(
                {"error": "invalid_token", "error_description": "Token verification failed"},
                status=401,
            )

        # Use verified claims instead of raw request body
        clerk_id = claims.get("sub") or claims.get("user_id")
        email = _norm_email(claims.get("user_email"))
        first_name = (claims.get("user_first_name") or "").strip()
        last_name = (claims.get("user_last_name") or "").strip()

        if not clerk_id or not email:
            return json_response(
                {"error": "invalid_token", "error_description": "Missing required claims"},
                status=401,
            )

        user, _created = _sync_clerk_user_to_odoo(
            request.env, clerk_id, email, first_name, last_name
        )
        if user:
            _post_rep_request_to_channel(request.env, user.partner_id)
        return json_response({"message": "Access requested"}, status=200)

    @api_route("/api/v3/authentication/token/exchange", methods=["POST"])
    def token_exchange(self, **kw):
        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return json_response(
                {"error": "invalid_request", "error_description": "Missing Bearer token"},
                status=400,
            )
        clerk_jwt = auth.split(" ", 1)[1].strip()

        ICP = request.env["ir.config_parameter"].sudo()
        issuer = ICP.get_param("clerk.issuer")
        jwks_url = ICP.get_param("clerk.jwks_url")
        audience = ICP.get_param("clerk.audience") or None

        if not issuer or not jwks_url:
            _logger.error("Clerk config missing: clerk.issuer / clerk.jwks_url")
            return json_response(
                {"error": "server_error", "error_description": "Clerk config not set"},
                status=500,
            )

        try:
            claims = verify_clerk_jwt(clerk_jwt, jwks_url=jwks_url, issuer=issuer, audience=audience)
        except Exception as e:
            err_str = str(e)
            _logger.warning("Clerk JWT invalid: %s", err_str)
            # If Clerk/JWKS returned 403 (e.g. forbidden URL), return 403 so status matches
            if "403" in err_str or "Forbidden" in err_str:
                return json_response(
                    {"error": "access_denied", "error_description": "Token verification service unavailable (forbidden)"},
                    status=403,
                )
            return json_response(
                {"error": "invalid_token", "error_description": "Token verification failed"},
                status=401,
            )

        clerk_sub = claims.get("sub") or claims.get("user_id")
        email = _norm_email(claims.get("user_email"))
        first_name = (claims.get("user_first_name") or "").strip()
        last_name = (claims.get("user_last_name") or "").strip()

        if not clerk_sub or not email:
            return json_response(
                {"error": "invalid_token", "error_description": "Missing required claims"},
                status=401,
            )

        Users = request.env["res.users"].sudo()
        Partners = request.env["res.partner"].sudo()

        admin_group = request.env.ref("liveag_consignment.group_consignment_manager").sudo()
        rep_group = request.env.ref("liveag_consignment.group_consignment_rep").sudo()

        user = Users.search([("clerk_user_id", "=", clerk_sub)], limit=1)
        # If found user is portal-only, prefer admin/rep with same email (migrate clerk_user_id)
        if user and admin_group not in user.group_ids and rep_group not in user.group_ids:
            better = Users.search(
                ["|", ("login", "=", email), ("partner_id.email", "ilike", email)],
                order="id",
            )
            admin_or_rep = better.filtered(
                lambda u: admin_group in u.group_ids or rep_group in u.group_ids
            )[:1]
            if admin_or_rep:
                admin_or_rep.write({"clerk_user_id": clerk_sub})
                user.sudo().write({"clerk_user_id": False})
                user = admin_or_rep
        if not user:
            partner = Partners.search([("email", "ilike", email)], limit=1)
            if not partner:
                display_name = (" ".join([first_name, last_name]).strip() or email.split("@")[0])
                partner = Partners.create({"name": display_name, "email": email})

            candidates = Users.search(["|", ("partner_id", "=", partner.id), ("login", "=", email)])
            # Prefer admin/rep over portal when multiple users match same email/partner
            user = (
                candidates.filtered(lambda u: admin_group in u.group_ids)[:1]
                or candidates.filtered(lambda u: rep_group in u.group_ids)[:1]
                or candidates[:1]
            )
            if not user:
                portal_group = request.env.ref(PORTAL_GROUP_XMLID).sudo()
                display_name = partner.name or (" ".join([first_name, last_name]).strip()) or email
                user = Users.create({
                    "name": display_name,
                    "login": email,
                    "email": email,
                    "partner_id": partner.id,
                    "group_ids": [(4, portal_group.id)],
                })

            user.write({"clerk_user_id": clerk_sub})

        # Check if user has required role (admin or rep) to use the API
        has_admin = admin_group in user.group_ids
        has_rep = rep_group in user.group_ids

        if not has_admin and not has_rep:
            return json_response(
                {
                    "error": "access_denied",
                    "error_description": "User does not have required role (admin or rep) to access the API",
                },
                status=403,
            )

        ttl_seconds = 3600
        scope = "api"
        token_rec = request.env["liveag.auth.token"].generate(user, ttl_seconds=ttl_seconds, scope=scope)

        return json_response({
            "access_token": token_rec.token,
            "token_type": "Bearer",
            "expires_in": ttl_seconds,
            "scope": token_rec.scope or "",
        })