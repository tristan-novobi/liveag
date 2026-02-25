import json
from datetime import date, datetime
from odoo import http
from odoo.http import request

def api_route(route, **kw):
    """Wrapper around http.route with API defaults: cors='*', csrf=False, type='http', auth='public'."""
    kw.setdefault('type', 'http')
    kw.setdefault('auth', 'public')
    kw.setdefault('cors', '*')
    kw.setdefault('csrf', False)
    return http.route(route, **kw)

# Base CORS policy (methods/headers allowed for your API)
BASE_CORS_HEADERS = {
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
}

def cors_headers():
    """
    Central CORS policy.
    For now permissive. Tighten by reflecting allowed origins.
    """
    origin = request.httprequest.headers.get("Origin")
    headers = dict(BASE_CORS_HEADERS)

    # --- Quick unblock (dev/local) ---
    headers["Access-Control-Allow-Origin"] = "*"

    # --- Recommended production tightening (uncomment and set allowed origins) ---
    # allowed = {
    #     "https://0a33dac2-5914-4fcd-aa6c-3e32aaa1dfb4.lovableproject.com",
    #     "https://your-prod-frontend.com",
    # }
    # if origin in allowed:
    #     headers["Access-Control-Allow-Origin"] = origin
    #     headers["Vary"] = "Origin"
    # else:
    #     # If not allowed, omit ACAO so browser blocks
    #     headers["Access-Control-Allow-Origin"] = "null"

    return headers

def preflight_response(status: int = 204):
    """
    Return an OPTIONS response with proper CORS headers.
    """
    return request.make_response("", headers=cors_headers(), status=status)

def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def _to_header_list(h):
    """
    Accept dict or list[tuple] and return list[tuple].
    """
    if not h:
        return []
    if isinstance(h, dict):
        return list(h.items())
    return list(h)

def json_response(payload, status=200, headers=None):
    base = {"Content-Type": "application/json"}
    # CORS headers are added by Odoo from the route's cors=; do not add them here.

    extra = _to_header_list(headers)
    final_headers = list(base.items())

    # Allow caller-provided headers to override defaults
    if extra:
        base_dict = dict(final_headers)
        base_dict.update(dict(extra))
        final_headers = list(base_dict.items())

    return request.make_response(
        json.dumps(payload, default=_json_default),
        headers=final_headers,
        status=status,
    )