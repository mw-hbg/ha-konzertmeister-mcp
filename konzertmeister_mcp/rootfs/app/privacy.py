"""What the AI gets to see.

Konzertmeister answers with a lot of data (contact details, internal links,
payment plans of the association …). These functions reduce every answer to
what the tools need and to what the user released on the app page:

* names are always shown,
* e-mail, phone, address and custom member fields only when released,
* appointments only of the groups chosen on the app page.

The filters run in the MCP server – the AI cannot ask its way around them.
"""

from __future__ import annotations

from typing import Any

DESCRIPTION_LIMIT = 1500


def _text(value: Any, limit: int = 300) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _drop_empty(data: dict) -> dict:
    return {k: v for k, v in data.items() if v not in (None, "", [], {})}


def group_of(appointment: dict) -> dict | None:
    group = appointment.get("group")
    return group if isinstance(group, dict) and group.get("id") is not None else None


def group_allowed(appointment: dict, settings: dict) -> bool:
    groups = settings.get("groups") or []
    if not groups:
        return True
    group = group_of(appointment)
    if group is None:
        return bool(settings.get("include_without_group", True))
    try:
        return int(group["id"]) in groups
    except (TypeError, ValueError):
        return False


def _location(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    return _drop_empty(
        {
            "name": _text(value.get("name")),
            "address": _text(value.get("formattedAddress")),
            "latitude": value.get("latitude"),
            "longitude": value.get("longitude"),
        }
    ) or None


def type_name(type_id: Any, settings: dict) -> str | None:
    for pair in settings.get("types", []):
        if pair.get("id") == type_id:
            return pair.get("name")
    return None


def appointment_view(a: dict, settings: dict) -> dict:
    """An appointment without internal links, QR codes and organisation details."""
    group = group_of(a)
    meeting = a.get("meetingPoint") if isinstance(a.get("meetingPoint"), dict) else {}
    room = a.get("room") if isinstance(a.get("room"), dict) else {}
    tags = [t.get("tag") for t in a.get("tags") or [] if isinstance(t, dict) and t.get("tag")]
    published = a.get("published")
    view = {
        "id": a.get("id"),
        "name": _text(a.get("name")),
        "start": a.get("start"),
        "end": a.get("end"),
        "time_undefined": a.get("timeUndefined") or None,
        "type_id": a.get("typId"),
        "type": type_name(a.get("typId"), settings),
        "cancelled": a.get("active") is False or None,
        "cancel_reason": _text(a.get("cancelDescription")) if a.get("active") is False else None,
        "description": _text(a.get("description"), DESCRIPTION_LIMIT),
        "group": _text(group.get("name")) if group else None,
        "group_id": group.get("id") if group else None,
        "location": _location(a.get("location")),
        "meeting_point": _drop_empty(
            {
                "time": meeting.get("meetingDateTime"),
                "location": _location(meeting.get("meetingLocation")),
                "description": _text(meeting.get("description")),
            }
        ) or None,
        "room": _text(room.get("name")),
        "tags": tags,
        "reply_deadline": a.get("statusDeadline"),
        "published": published,
        "public_link": _text(a.get("publicSharingUrl")) if published else None,
        "external_link": _text(a.get("externalAppointmentLink")),
    }
    return _drop_empty(view)


def _person(first: Any, last: Any) -> str:
    return " ".join(p for p in (_text(first, 80), _text(last, 80)) if p) or "?"


def reply_view(r: dict, share: dict) -> dict:
    view = {
        "name": _person(r.get("kmUserFirstName"), r.get("kmUserLastName")),
        "reply": {"POSITIVE": "yes", "NEGATIVE": "no", "MAYBE": "maybe"}.get(str(r.get("reply")), "no answer"),
        "comment": _text(r.get("replyComment"), 500),
        "replied_at": r.get("repliedAt"),
        "guest": r.get("externalInvite") or None,
    }
    if share.get("email"):
        view["email"] = _text(r.get("kmUserEmail"), 254)
    return _drop_empty(view)


def attendance_view(r: dict, share: dict) -> dict:
    view = {
        "name": _person(r.get("kmUserFirstName"), r.get("kmUserLastName")),
        "attended": bool(r.get("attending")),
        "comment": _text(r.get("comment"), 500),
    }
    if share.get("email"):
        view["email"] = _text(r.get("kmUserEmail"), 254)
    return _drop_empty(view) | {"attended": view["attended"]}  # False is a real answer


def _property_value(p: dict) -> Any:
    option = p.get("valueSelectOption")
    if isinstance(option, dict) and option.get("name"):
        return option["name"]
    for key in ("valueString", "valueNumber", "valueDate", "valueBoolean"):
        if p.get(key) is not None:
            return p[key]
    return None


def member_view(m: dict, share: dict) -> dict:
    view: dict[str, Any] = {"name": _person(m.get("firstname"), m.get("lastname"))}
    if share.get("email"):
        view["email"] = _text(m.get("mail"), 254)
    if share.get("phone"):
        view["mobile_phone"] = _text(m.get("mobilePhone"), 40)
    if share.get("address") and isinstance(m.get("address"), dict):
        addr = m["address"]
        view["address"] = _drop_empty(
            {
                "street": _text(addr.get("streetline1")),
                "street2": _text(addr.get("streetline2")),
                "postal_code": _text(addr.get("postalCode"), 20),
                "city": _text(addr.get("city")),
                "country": _text(addr.get("countryIso3"), 3),
            }
        ) or None
    if share.get("properties"):
        fields = {}
        for p in m.get("properties") or []:
            if not isinstance(p, dict) or p.get("memberPropertyActive") is False:
                continue
            name = _text(p.get("memberPropertyName"), 80)
            value = _property_value(p)
            if name and value is not None:
                fields[name] = value
        view["fields"] = fields or None
    return _drop_empty(view)


def reply_summary(views: list[dict]) -> dict:
    summary = {"yes": 0, "no": 0, "maybe": 0, "no answer": 0}
    for v in views:
        summary[v["reply"]] = summary.get(v["reply"], 0) + 1
    return summary
