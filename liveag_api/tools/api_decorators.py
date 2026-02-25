import logging
from datetime import date
from functools import wraps
from odoo.http import request
from odoo.addons.liveag_api.tools.http_utils import json_response
from odoo.addons.liveag_api.tools.clerk_jwt import authenticate_clerk_jwt
from odoo.addons.liveag_api.tools.liveag_auth import authenticate_liveag_token

_logger = logging.getLogger(__name__)

def clerk_required(scope: str | None = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            env_as_user, user, claims, err = authenticate_clerk_jwt(scope)
            if err:
                return json_response(err, status=401)

            # Attach for downstream use
            request.api_env = env_as_user
            request.api_user = user
            request.api_claims = claims
            request.update_env(user=user.id)

            _logger.info(
                "API request (Clerk JWT): method=%s path=%s uid=%s login=%s",
                request.httprequest.method,
                request.httprequest.path,
                user.id,
                user.login or "(none)",
            )

            return fn(*args, **kwargs)
        return wrapper
    return decorator

def odoo_token_required(scope: str | None = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            env_as_user, token_rec, err = authenticate_liveag_token(scope)
            if err:
                return json_response(err, status=401)

            request.api_env = env_as_user
            request.api_user = token_rec.user_id.sudo()
            request.api_token = token_rec
            request.update_env(user=request.api_user.id)

            _logger.info(
                "API request: method=%s path=%s token=%s... uid=%s login=%s",
                request.httprequest.method,
                request.httprequest.path,
                (token_rec.token or "")[:16] + "..." if token_rec.token else "(none)",
                request.api_user.id,
                request.api_user.login or "(none)",
            )

            return fn(*args, **kwargs)
        return wrapper
    return decorator

def with_pagination(default_per_page=25, max_per_page=100):
    """
    Adds request.pagination = {
        "use": bool,
        "page": int,
        "per_page": int,
        "limit": int,
        "offset": int,
    }
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            page = request.params.get("page")
            per_page = request.params.get("per_page")
            use = page is not None or per_page is not None

            try:
                page_i = int(page) if page is not None else 1
                per_page_i = int(per_page) if per_page is not None else default_per_page

                if page_i < 1:
                    return json_response(
                        {"error": "invalid_request", "error_description": "page must be >= 1"},
                        status=400,
                    )
                if per_page_i < 1 or per_page_i > max_per_page:
                    return json_response(
                        {"error": "invalid_request", "error_description": f"per_page must be between 1 and {max_per_page}"},
                        status=400,
                    )

            except (ValueError, TypeError):
                return json_response(
                    {"error": "invalid_request", "error_description": "Invalid page or per_page parameter"},
                    status=400,
                )

            request.pagination = {
                "use": use,
                "page": page_i,
                "per_page": per_page_i,
                "limit": per_page_i,
                "offset": (page_i - 1) * per_page_i,
            }

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def with_query_filters(spec, attr="parsed_filters"):
    """
    Parse and validate query params according to spec; set request.<attr> with
    normalized dict. Spec is a list of (param_name, type) where type is one of:
    "search" (string), "ids" (comma-separated ints), "strings" (comma-separated),
    "date" (ISO YYYY-MM-DD). Only keys that were present and valid are set.
    On validation failure returns 400. Reusable for any list endpoint.
    Spec entries may be 2-tuples (param_name, type) or 3-tuples (param_name, type, domain_info).
    The decorator uses only the first two elements; domain_info is for the mixin.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            result = {}
            for entry in spec:
                param_name, param_type = entry[0], entry[1]
                raw = request.params.get(param_name)
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    continue
                raw = raw.strip() if isinstance(raw, str) else raw

                if param_type == "search":
                    if raw:
                        result[param_name] = raw
                    continue

                if param_type == "ids":
                    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
                    if not parts:
                        continue
                    try:
                        ids = [int(p) for p in parts]
                    except ValueError:
                        return json_response(
                            {
                                "error": "invalid_request",
                                "error_description": f"Parameter '{param_name}' must be comma-separated integers",
                            },
                            status=400,
                        )
                    result[param_name] = ids
                    continue

                if param_type == "strings":
                    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
                    if not parts:
                        continue
                    result[param_name] = parts
                    continue

                if param_type == "date":
                    try:
                        d = date.fromisoformat(str(raw).strip())
                    except ValueError:
                        return json_response(
                            {
                                "error": "invalid_request",
                                "error_description": f"Parameter '{param_name}' must be a date (YYYY-MM-DD)",
                            },
                            status=400,
                        )
                    result[param_name] = d
                    continue

            setattr(request, attr, result)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def with_sort(allowed_fields, default_field=None, default_order="desc", sort_param="sort_by", order_param="order_by"):
    """
    Parse sort_by and order query params; set request.sort = {
        "field": str,
        "order": "asc" | "desc",
        "order_clause": str,  # e.g. "create_date desc" for use in search()
    }
    Allowed_fields: list of field names that may be used for sorting.
    Invalid sort_by returns 400. order_param accepts "asc", "desc" (case-insensitive).
    """
    default_order = (default_order or "desc").lower()
    if default_order not in ("asc", "desc"):
        default_order = "desc"

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            raw_sort = request.params.get(sort_param)
            raw_order = request.params.get(order_param)
            field = (raw_sort and raw_sort.strip()) or default_field
            order = (raw_order and raw_order.strip().lower()) or default_order
            if order not in ("asc", "desc"):
                order = default_order

            if field is not None and field not in allowed_fields:
                return json_response(
                    {
                        "error": "invalid_request",
                        "error_description": f"sort_by must be one of: {', '.join(allowed_fields)}",
                    },
                    status=400,
                )
            if field is None:
                field = allowed_fields[0] if allowed_fields else "id"
            order_clause = f"{field} {order}"
            request.sort = {
                "field": field,
                "order": order,
                "order_clause": order_clause,
            }
            return fn(*args, **kwargs)
        return wrapper
    return decorator