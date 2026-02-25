# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from odoo.http import request


# Division -> (group xmlid -> role key)
DIVISION_GROUP_ROLE_MAP: Dict[str, Dict[str, str]] = {
    "commercial": {
        "liveag_consignment.group_consignment_buyer": "buyer",
        "liveag_consignment.group_consignment_seller": "seller",
        "liveag_consignment.group_consignment_rep": "rep",
        "liveag_consignment.group_consignment_manager": "admin",
    },

    # Future divisions can be added later:
    # "equipment": {
    #     "liveag_equipment.group_equipment_buyer": "buyer",
    #     "liveag_equipment.group_equipment_seller": "seller",
    #     "liveag_equipment.group_equipment_rep": "rep",
    #     "liveag_equipment.group_equipment_manager": "admin",
    # },
}


def _safe_ref(xmlid: str):
    """env.ref that returns None if the xmlid doesn't exist."""
    try:
        return request.env.ref(xmlid).sudo()
    except Exception:
        return None


def user_division_roles(user) -> Dict[str, List[str]]:
    """
    Returns roles grouped by division:
      { "commercial": ["admin", "buyer", "rep", "seller"], "equipment": [] }
    Only includes roles derived from DIVISION_GROUP_ROLE_MAP.
    """
    user = user.sudo()
    user_groups = user.group_ids  # recordset

    out: Dict[str, List[str]] = {}
    for division, mapping in DIVISION_GROUP_ROLE_MAP.items():
        roles: List[str] = []
        for xmlid, role_key in mapping.items():
            grp = _safe_ref(xmlid)
            if grp and grp in user_groups:
                roles.append(role_key)

        # Ensure deterministic ordering (optional, but nice)
        roles = sorted(set(roles))
        out[division] = roles

    return out


def user_has_role(user, division: str, role: str) -> bool:
    """
    Convenience helper for server-side checks.
    """
    roles = user_division_roles(user).get(division, [])
    return role in roles


def sanitize_groups_for_debug(user) -> Dict[str, List[Dict[str, str]]]:
    """
    Optional: returns only your "division groups" with display names
    for debug/inspection in UI without exposing all Odoo technical groups.
    """
    user = user.sudo()
    user_groups = user.group_ids

    out: Dict[str, List[Dict[str, str]]] = {}
    for division, mapping in DIVISION_GROUP_ROLE_MAP.items():
        groups = []
        for xmlid, role_key in mapping.items():
            grp = _safe_ref(xmlid)
            if grp and grp in user_groups:
                groups.append({
                    "xmlid": xmlid,
                    "name": grp.name,
                    "role": role_key,
                })
        out[division] = groups

    return out