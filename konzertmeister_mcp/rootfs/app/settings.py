"""Tools and settings of one association (Verein) – shared by the app page and
the MCP server.

The app page stores the settings of every association as JSON (root-owned).
The MCP server of an association receives them in its environment
(KM_SETTINGS) and can therefore never change them itself.
"""

from __future__ import annotations

import json
import re

# Every tool of the server: name -> kind. Kinds decide the presets on the app
# page: read = only reads, create = adds something new, change = changes
# something that exists.
TOOLS: dict[str, str] = {
    "list_appointments": "read",
    "get_appointment_replies": "read",
    "get_appointment_attendance": "read",
    "list_appointment_templates": "read",
    "list_appointment_types": "read",
    "list_members": "read",
    "create_appointment": "create",
    "add_member": "create",
    "update_member": "change",
}
ALL_TOOLS = frozenset(TOOLS)
# Order on the app page
TOOL_ORDER = list(TOOLS)
# Default of a new association: read only, and no member list (the API cannot
# limit it to one group – it always returns every member of the association).
DEFAULT_TOOLS = frozenset(n for n, k in TOOLS.items() if k == "read") - {"list_members"}
WRITE_TOOLS = frozenset(n for n, k in TOOLS.items() if k != "read")

# Member data the AI may see besides the name (all off by default).
SHARE_KEYS = ("email", "phone", "address", "properties")

# Appointment types: the API requires type numbers and offers no list of them.
# Until the user lists the types of the association, these are asked for.
FALLBACK_TYPE_IDS = tuple(range(1, 11))

MAX_TEMPLATES = 50
MAX_TYPES = 30
MAX_GROUPS = 50
_MAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


def _clean_text(value, limit: int = 80) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isprintable())
    return " ".join(text.split())[:limit]


def valid_mail(value: str) -> bool:
    return bool(_MAIL.match(value or ""))


def parse_pairs(text: str, numeric: bool, limit: int) -> list[dict]:
    """Lines like "Probe Jugendkapelle = ABC123" -> [{"name": …, "id": …}].

    numeric: the id must be a whole number (appointment types)."""
    result: list[dict] = []
    seen = set()
    for line in str(text or "").splitlines():
        if "=" not in line:
            continue
        name, _, value = line.rpartition("=")
        name, value = _clean_text(name), _clean_text(value, 120)
        if not name or not value:
            continue
        if numeric:
            if not value.isdigit() or len(value) > 9:
                continue
            value = int(value)
        elif not re.fullmatch(r"[A-Za-z0-9_\-.:]{1,120}", value):
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        result.append({"name": name, "id": value})
        if len(result) >= limit:
            break
    return result


def pairs_text(pairs: list[dict]) -> str:
    return "\n".join(f'{p["name"]} = {p["id"]}' for p in pairs)


def default_settings() -> dict:
    return {
        "tools": sorted(DEFAULT_TOOLS),
        "groups": [],
        "include_without_group": True,
        "share": {key: False for key in SHARE_KEYS},
        "creator_mail": "",
        "templates": [],
        "types": [],
    }


def normalize(data) -> dict:
    """Settings as stored – anything unknown or broken falls back to the default."""
    result = default_settings()
    if not isinstance(data, dict):
        return result
    if isinstance(data.get("tools"), list):
        result["tools"] = sorted({str(t) for t in data["tools"]} & ALL_TOOLS)
    if isinstance(data.get("groups"), list):
        groups = []
        for g in data["groups"][:MAX_GROUPS]:
            if isinstance(g, int) or (isinstance(g, str) and g.isdigit()):
                groups.append(int(g))
        result["groups"] = sorted(set(groups))
    if isinstance(data.get("include_without_group"), bool):
        result["include_without_group"] = data["include_without_group"]
    share = data.get("share")
    if isinstance(share, dict):
        result["share"] = {key: share.get(key) is True for key in SHARE_KEYS}
    mail = _clean_text(data.get("creator_mail"), 254)
    result["creator_mail"] = mail if valid_mail(mail) else ""
    for key, numeric, limit in (("templates", False, MAX_TEMPLATES), ("types", True, MAX_TYPES)):
        if isinstance(data.get(key), list):
            text = "\n".join(
                f'{p.get("name")} = {p.get("id")}' for p in data[key] if isinstance(p, dict)
            )
            result[key] = parse_pairs(text, numeric, limit)
    return result


def type_ids(settings: dict) -> list[int]:
    """Type numbers asked for when the AI names none."""
    return [p["id"] for p in settings.get("types", [])] or list(FALLBACK_TYPE_IDS)


def dumps(settings: dict) -> str:
    return json.dumps(normalize(settings), sort_keys=True)
