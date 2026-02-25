"""
Webhook endpoints. Clerk webhook syncs user creation/sign-in to Odoo (res.users + res.partner).
"""
import base64
import hmac
import hashlib
import json
import logging
import time
from odoo import http
from odoo.http import request

from odoo.addons.liveag_api.tools.http_utils import json_response, api_route

_logger = logging.getLogger(__name__)

PORTAL_GROUP_XMLID = "base.group_portal"
WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _verify_clerk_webhook(payload_body: str, svix_id: str, svix_timestamp: str, svix_signature: str, signing_secret: str) -> bool:
    """
    Verify Clerk/Svix webhook signature.
    See https://docs.svix.com/receiving/verifying-payloads/how-manual
    """
    if not all([svix_id, svix_timestamp, svix_signature, signing_secret]):
        return False
    signing_secret = signing_secret.strip()
    if not signing_secret.startswith("whsec_"):
        return False
    # Reject old webhooks (replay protection)
    try:
        ts = int(svix_timestamp)
        if abs(time.time() - ts) > WEBHOOK_TOLERANCE_SECONDS:
            return False
    except (ValueError, TypeError):
        return False
    # Decode secret (part after whsec_ is base64)
    try:
        secret_b64 = signing_secret.split("whsec_", 1)[1]
        secret_bytes = base64.b64decode(secret_b64)
    except Exception:
        return False
    signed_content = f"{svix_id}.{svix_timestamp}.{payload_body}"
    expected_sig = base64.b64encode(
        hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii")
    # svix-signature format: "v1,<sig> v1,<sig> ..."
    for part in svix_signature.split():
        if part.startswith("v1,"):
            sig = part[3:]
            if hmac.compare_digest(sig, expected_sig):
                return True
    return False


def _sync_clerk_user_to_odoo(env, clerk_id: str, email: str, first_name: str = "", last_name: str = ""):
    """
    Ensure an Odoo user exists for this Clerk user. Idempotent.
    1. Find user by clerk_user_id; if found, return.
    2. Find user by login (email); if found, set clerk_user_id and return.
    3. Find contact (res.partner) by email; if found, create portal user for that contact.
    4. Else create new partner + portal user.
    Returns (res.users record, created: bool for new user).
    """
    email = _norm_email(email)
    if not clerk_id or not email:
        return None, False

    Users = env["res.users"].sudo()
    Partners = env["res.partner"].sudo()

    user = Users.search([("clerk_user_id", "=", clerk_id)], limit=1)
    if user:
        return user, False

    user = Users.search([("login", "=", email)], limit=1)
    if user:
        user.write({"clerk_user_id": clerk_id})
        return user, False

    partner = Partners.search([("email", "ilike", email)], limit=1)
    if not partner:
        display_name = (" ".join([first_name, last_name]).strip() or email.split("@")[0])
        partner = Partners.create({"name": display_name, "email": email})

    user = Users.search(["|", ("partner_id", "=", partner.id), ("login", "=", email)], limit=1)
    if not user:
        portal_group = env.ref(PORTAL_GROUP_XMLID).sudo()
        display_name = partner.name or (" ".join([first_name, last_name]).strip()) or email
        user = Users.create({
            "name": display_name,
            "login": email,
            "email": email,
            "partner_id": partner.id,
            "group_ids": [(4, portal_group.id)],
        })

    user.write({"clerk_user_id": clerk_id})
    return user, True


def _clerk_payload_user_data(payload: dict) -> tuple:
    """
    Extract (clerk_id, email, first_name, last_name) from Clerk webhook payload.
    Handles user.created (data is the user object) and session.created (data.user or data.user_id).
    Note: user.created may have empty email_addresses for some sign-up flows; token exchange
    will create the user on first login when the JWT includes email.
    """
    data = payload.get("data") or payload
    user_obj = data.get("user") or data
    clerk_id = user_obj.get("id") or data.get("user_id")
    first_name = (user_obj.get("first_name") or "").strip()
    last_name = (user_obj.get("last_name") or "").strip()

    email = None
    email_addresses = user_obj.get("email_addresses") or []
    primary_id = user_obj.get("primary_email_address_id")
    if primary_id and email_addresses:
        for e in email_addresses:
            if e.get("id") == primary_id:
                email = _norm_email(e.get("email_address"))
                break
    if not email and email_addresses:
        email = _norm_email(email_addresses[0].get("email_address"))
    if not email and user_obj.get("primary_email_address"):
        # Some payloads nest the primary email object
        pea = user_obj["primary_email_address"]
        if isinstance(pea, dict):
            email = _norm_email(pea.get("email_address"))

    if not clerk_id:
        clerk_id = data.get("user_id") or user_obj.get("clerk_id")
    if not email:
        email = _norm_email(user_obj.get("email"))
    return clerk_id, email, first_name, last_name


class WebhooksController(http.Controller):

    @api_route("/api/v3/webhooks/auction_created", methods=["POST"])
    def auction_created(self, **kw):
        return json_response({"message": "Auction created"}, status=200)

    @api_route("/api/v3/webhooks/auction_updated", methods=["POST"])
    def auction_updated(self, **kw):
        return json_response({"message": "Auction updated"}, status=200)

    @api_route("/api/v3/webhooks/auction_deleted", methods=["POST"])
    def auction_deleted(self, **kw):
        return json_response({"message": "Auction deleted"}, status=200)

    @api_route("/api/v3/webhooks/clerk_user_created", methods=["POST"])
    def clerk_user_created(self, **kw):
        body = request.httprequest.get_data(as_text=True) or ""
        signing_secret = (
            request.env["ir.config_parameter"].sudo().get_param("clerk.webhook_signing_secret") or ""
        ).strip()
        if signing_secret:
            svix_id = request.httprequest.headers.get("svix-id", "")
            svix_ts = request.httprequest.headers.get("svix-timestamp", "")
            svix_sig = request.httprequest.headers.get("svix-signature", "")
            if not _verify_clerk_webhook(body, svix_id, svix_ts, svix_sig, signing_secret):
                _logger.warning("Clerk webhook signature verification failed")
                return json_response(
                    {"error": "Webhook signature verification failed"},
                    status=400,
                )
        else:
            _logger.warning("clerk.webhook_signing_secret not set; webhook received without verification")

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            _logger.warning("Clerk webhook invalid JSON: %s", e)
            return json_response({"error": "Invalid JSON payload"}, status=400)

        clerk_id, email, first_name, last_name = _clerk_payload_user_data(payload)
        if not clerk_id:
            _logger.warning("Clerk webhook missing user id in payload")
            return json_response({"message": "No user id"}, status=200)

        if not email:
            _logger.info(
                "Clerk webhook user %s has no email in payload; skipping sync (token exchange will create on first login)",
                clerk_id,
            )
            return json_response({"message": "User has no email; will sync on first login"}, status=200)

        user, created = _sync_clerk_user_to_odoo(
            request.env, clerk_id, email, first_name, last_name
        )
        if user:
            return json_response(
                {"message": "Clerk user created" if created else "Clerk user already synced"},
                status=200,
            )
        return json_response({"message": "Sync skipped (missing required data)"}, status=200)
