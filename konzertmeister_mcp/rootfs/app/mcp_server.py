"""MCP server for one Konzertmeister association.

Started by the launcher – once per association, each as its own unprivileged
user – and reachable only on 127.0.0.1 (nginx in front of it checks the
secret path). It gets:

* KM_SETTINGS  the association's settings from the app page (JSON, read only
               for this process: it lives in the environment, not in a file
               the server could change),
* KM_KEY_FILE  the file with the association's API key,
* KM_STATE_DIR its own folder (marker "key_invalid" for the app page),
* KM_PORT      the loopback port.

Only the tools released on the app page are registered at all. Every answer
passes the filters in privacy.py (groups, released member data).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

import privacy
import settings as km_settings
from km_api import ApiError, Konzertmeister

log = logging.getLogger("konzertmeister_mcp_app")

CACHE_SECONDS = 60
PAGE_SIZE_HINT = "Results come in pages; ask for page=1, 2 … if a page is full."

INSTRUCTIONS = """\
Konzertmeister is the planning app of a music association (rehearsals, concerts, \
replies of the members, attendance). These tools give read access to the appointments \
of the association and – only if the user allowed it in Home Assistant – write access.

Rules:
* Before calling a tool that creates or changes something (create_appointment, \
add_member, update_member), show the user exactly what you are about to do and wait \
for an explicit confirmation. Konzertmeister may notify the members immediately.
* Only the data released in Home Assistant is visible: member contact details and \
appointments of other groups may be hidden on purpose. Do not try to work around it.
* Times are in the association's time zone unless they carry an offset.
"""


# --------------------------------------------------------------------------
# Configuration from the launcher
# --------------------------------------------------------------------------
def load_settings() -> dict:
    try:
        return km_settings.normalize(json.loads(os.environ.get("KM_SETTINGS", "{}")))
    except ValueError:
        log.error("KM_SETTINGS is invalid – using the defaults")
        return km_settings.default_settings()


def read_key(path: str) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd) as fh:
        return fh.read(4096).strip()


def local_zone() -> dt.tzinfo:
    try:
        return ZoneInfo(os.environ.get("TZ") or "Europe/Berlin")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Europe/Berlin")


def parse_when(value: str, zone: dt.tzinfo, end_of_day: bool = False) -> dt.datetime:
    """'2026-12-01', '2026-12-01 18:30', '2026-12-01T18:30:00+01:00' -> aware datetime."""
    text = str(value or "").strip().replace(" ", "T", 1)
    if not text:
        raise ToolError("A date is missing.")
    try:
        if len(text) == 10:
            day = dt.date.fromisoformat(text)
            moment = dt.datetime.combine(day, dt.time(23, 59, 59) if end_of_day else dt.time(0, 0))
        else:
            moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ToolError(f"'{value}' is not a date. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM.") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone)
    return moment


def iso(moment: dt.datetime) -> str:
    return moment.isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# State shared by the tools
# --------------------------------------------------------------------------
class State:
    def __init__(self, settings: dict, api: Konzertmeister, state_dir: Path) -> None:
        self.settings = settings
        self.api = api
        self.state_dir = state_dir
        self.zone = local_zone()
        self._cache: dict[str, tuple[float, Any]] = {}
        # Appointments the AI has seen, with "allowed by the group filter".
        self.known: dict[int, bool] = {}

    @property
    def share(self) -> dict:
        return self.settings.get("share", {})

    def _marker(self, ok: bool) -> None:
        marker = self.state_dir / "key_invalid"
        try:
            if ok:
                marker.unlink(missing_ok=True)
            else:
                marker.touch()
        except OSError:
            pass

    async def call(self, coro_fn, *args, cache_key: str | None = None):
        if cache_key and (hit := self._cache.get(cache_key)) and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
        try:
            result = await coro_fn(*args)
        except ApiError as exc:
            if exc.kind == "auth":
                self._marker(False)
            raise ToolError(error_text(exc)) from None
        self._marker(True)
        if cache_key:
            if len(self._cache) > 200:
                self._cache.clear()
            self._cache[cache_key] = (time.monotonic(), result)
        return result

    def forget_cache(self) -> None:
        self._cache.clear()


def error_text(exc: ApiError) -> str:
    texts = {
        "auth": (
            "Konzertmeister rejected the API key of this association (wrong or revoked). Ask the user "
            "to open 'Konzertmeister MCP' in the Home Assistant sidebar and enter a new API key."
        ),
        "forbidden": "Konzertmeister does not allow this with the association's API key.",
        "not_found": "Konzertmeister does not know this entry (wrong id?).",
        "rate_limit": "Konzertmeister received too many requests. Wait a minute and try again.",
        "bad_request": "Konzertmeister rejected the request as invalid.",
        "server": "Konzertmeister had a problem answering. Try again later.",
        "network": "Konzertmeister could not be reached from Home Assistant. Try again later.",
    }
    text = texts.get(exc.kind, "Konzertmeister request failed.")
    if exc.detail and exc.kind in ("bad_request", "forbidden", "not_found"):
        text += f" Details: {exc.detail}"
    return text


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
class MemberProperty(BaseModel):
    property_id: Annotated[str, Field(description="External id of the member field in Konzertmeister")]
    value: Annotated[bool | float | str, Field(description="Text, number, true/false or a date YYYY-MM-DD")]


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
CREATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
CHANGE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)


def build_server(state: State, port: int = 8000) -> FastMCP:
    s = state.settings
    enabled = set(s.get("tools", []))
    mcp = FastMCP(
        name="Konzertmeister",
        instructions=INSTRUCTIONS,
        host="127.0.0.1",
        port=port,
        stateless_http=True,
        json_response=True,
        log_level="DEBUG" if os.environ.get("KM_LOG_LEVEL") == "debug" else "WARNING",
    )

    def tool(name: str, annotations: ToolAnnotations):
        def register(fn):
            if name in enabled:
                mcp.tool(name=name, annotations=annotations)(fn)
            return fn
        return register

    async def check_appointment(appointment_id: int) -> None:
        if not s.get("groups"):
            return
        allowed = state.known.get(int(appointment_id))
        if allowed is None:
            raise ToolError(
                "Unknown appointment for the group filter of this association. Find it with "
                "list_appointments first, then use its id."
            )
        if not allowed:
            raise ToolError("This appointment belongs to a group that is not shared with you.")

    # reading ---------------------------------------------------------------
    @tool("list_appointments", READ)
    async def list_appointments(
        start_date: Annotated[str | None, Field(description="First day (YYYY-MM-DD). Empty = upcoming appointments from now on.")] = None,
        end_date: Annotated[str | None, Field(description="Last day (YYYY-MM-DD), optional.")] = None,
        type_ids: Annotated[list[int] | None, Field(description="Appointment type numbers (see list_appointment_types). Empty = all configured types.")] = None,
        include_cancelled: Annotated[bool, Field(description="Also list cancelled appointments.")] = False,
        published: Annotated[str, Field(description="all, published or unpublished.")] = "all",
        tags: Annotated[list[str] | None, Field(description="Only appointments with these tags.")] = None,
        sort_by: Annotated[str, Field(description="start or deadline (reply deadline).")] = "start",
        page: Annotated[int, Field(ge=0, le=100, description="Page, starting at 0.")] = 0,
    ) -> dict:
        """List appointments (rehearsals, concerts …) of the association with time, place, group, type and reply deadline.
        Use the returned id for get_appointment_replies and get_appointment_attendance."""
        body: dict[str, Any] = {
            "typeIds": [int(t) for t in (type_ids or km_settings.type_ids(s))][:30],
            "activationStatusList": ["ACTIVE", "CANCELLED"] if include_cancelled else ["ACTIVE"],
            "publishedStatus": {"published": "PUBLISHED", "unpublished": "UNPUBLISHED"}.get(published, "ALL"),
            "sortMode": "DEADLINE" if sort_by == "deadline" else "STARTDATE",
            "page": int(page),
        }
        if tags:
            body["tags"] = [str(t)[:60] for t in tags][:20]
        start = end = None
        if start_date:
            start = parse_when(start_date, state.zone)
            body["dateMode"] = "FROM_DATE"
            body["filterStart"] = iso(start)
        else:
            body["dateMode"] = "UPCOMING"
        if end_date:
            end = parse_when(end_date, state.zone, end_of_day=True)
            body["filterEnd"] = iso(end)
        raw = await state.call(state.api.appointments, body, cache_key="app:" + json.dumps(body, sort_keys=True))
        shown, hidden = [], 0
        for appointment in raw:
            allowed = privacy.group_allowed(appointment, s)
            if appointment.get("id") is not None:
                state.known[int(appointment["id"])] = allowed
            if allowed:
                shown.append(privacy.appointment_view(appointment, s))
            else:
                hidden += 1
        result: dict[str, Any] = {"appointments": shown, "page": page, "received": len(raw)}
        if hidden:
            result["note"] = f"{hidden} appointment(s) of other groups are not shared with you."
        if raw:
            result["paging"] = PAGE_SIZE_HINT
        return result

    @tool("get_appointment_replies", READ)
    async def get_appointment_replies(
        appointment_id: Annotated[int, Field(description="id from list_appointments")],
    ) -> dict:
        """Who replied yes, no or maybe to an appointment (with comments), and who has not answered yet."""
        await check_appointment(appointment_id)
        raw = await state.call(state.api.replies, appointment_id, cache_key=f"rep:{appointment_id}")
        views = [privacy.reply_view(r, state.share) for r in raw]
        return {"summary": privacy.reply_summary(views), "replies": views}

    @tool("get_appointment_attendance", READ)
    async def get_appointment_attendance(
        appointment_id: Annotated[int, Field(description="id from list_appointments")],
    ) -> dict:
        """Who actually attended an appointment (attendance recorded in Konzertmeister)."""
        await check_appointment(appointment_id)
        raw = await state.call(state.api.attendance, appointment_id, cache_key=f"att:{appointment_id}")
        views = [privacy.attendance_view(r, state.share) for r in raw]
        return {"attended": sum(1 for v in views if v["attended"]), "total": len(views), "people": views}

    @tool("list_appointment_templates", READ)
    async def list_appointment_templates() -> dict:
        """Appointment templates that create_appointment can use (set up on the Home Assistant app page)."""
        templates = [{"name": p["name"]} for p in s.get("templates", [])]
        result: dict[str, Any] = {"templates": templates}
        if not templates:
            result["note"] = "No templates are set up. The user can add them on the app page in Home Assistant."
        return result

    @tool("list_appointment_types", READ)
    async def list_appointment_types() -> dict:
        """Names and numbers of the appointment types (for type_ids of list_appointments)."""
        types = s.get("types", [])
        if types:
            return {"types": types}
        return {
            "types": [],
            "note": "The user has not named the types yet; list_appointments asks for the numbers "
            f"{list(km_settings.FALLBACK_TYPE_IDS)} and returns type_id with every appointment.",
        }

    @tool("list_members", READ)
    async def list_members(
        search: Annotated[str | None, Field(description="Only members whose name contains this text.")] = None,
    ) -> dict:
        """Members of the association (all groups). Contact details only if the user released them."""
        raw = await state.call(state.api.members, cache_key="members")
        views = [privacy.member_view(m, state.share) for m in raw]
        if search:
            needle = search.strip().lower()
            views = [v for v in views if needle in v["name"].lower()]
        released = [k for k in km_settings.SHARE_KEYS if state.share.get(k)]
        return {"members": views, "count": len(views), "released_details": released or ["names only"]}

    # writing ---------------------------------------------------------------
    @tool("create_appointment", CREATE)
    async def create_appointment(
        template: Annotated[str, Field(description="Name of a template from list_appointment_templates")],
        start: Annotated[str, Field(description="Start, e.g. 2026-12-01T18:30 (local time) or with offset")],
        name: Annotated[str | None, Field(description="Own name instead of the template's")] = None,
        description: Annotated[str | None, Field(description="Own description instead of the template's")] = None,
    ) -> dict:
        """Create an appointment from a template (place, group, duration and deadlines come from the template).
        Confirm with the user first – members may be notified immediately."""
        templates = s.get("templates", [])
        match = next((p for p in templates if p["name"].lower() == template.strip().lower()), None)
        if match is None:
            raise ToolError(
                "Unknown template. Use one of: " + (", ".join(p["name"] for p in templates) or "(none set up)")
            )
        creator = s.get("creator_mail", "")
        if not creator:
            raise ToolError(
                "No creator e-mail is set for this association. Ask the user to enter it on the app page "
                "in Home Assistant (the Konzertmeister account that appears as creator)."
            )
        moment = parse_when(start, state.zone)
        if moment < dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1):
            raise ToolError("The start lies in the past.")
        body: dict[str, Any] = {
            "appointmentTemplateExtId": match["id"],
            "creatorMail": creator,
            "startZoned": iso(moment),
        }
        if name:
            body["name"] = name.strip()[:200]
        if description:
            body["description"] = description.strip()[:5000]
        created = await state.call(state.api.create_appointment, body)
        state.forget_cache()
        if created.get("id") is not None:
            state.known[int(created["id"])] = privacy.group_allowed(created, s)
        return {"created": privacy.appointment_view(created, s) if created else {"start": iso(moment)}}

    def member_body(email: str, first_name, last_name, mobile_phone, properties) -> dict:
        email = (email or "").strip()
        if not km_settings.valid_mail(email):
            raise ToolError("A valid e-mail address is required.")
        body: dict[str, Any] = {"mail": email}
        for key, value in (("firstname", first_name), ("lastname", last_name), ("mobilePhone", mobile_phone)):
            if value:
                body[key] = str(value).strip()[:100]
        if properties:
            items = []
            for item in properties[:30]:
                prop = {"propertyExtId": str(item.property_id)[:120]}
                value = item.value
                if isinstance(value, bool):
                    prop["valueBoolean"] = value
                elif isinstance(value, (int, float)):
                    prop["valueNumber"] = value
                elif isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
                    prop["valueDate"] = value
                else:
                    prop["valueString"] = str(value)[:500]
                items.append(prop)
            body["properties"] = items
        return body

    @tool("add_member", CREATE)
    async def add_member(
        email: Annotated[str, Field(description="E-mail address of the new member (required)")],
        first_name: str | None = None,
        last_name: str | None = None,
        mobile_phone: str | None = None,
        properties: Annotated[list[MemberProperty] | None, Field(description="Custom member fields, optional")] = None,
    ) -> dict:
        """Add a member to the association (Konzertmeister invites them by e-mail). Confirm with the user first."""
        body = member_body(email, first_name, last_name, mobile_phone, properties)
        await state.call(state.api.add_member, body)
        state.forget_cache()
        return {"added": privacy.member_view({"firstname": first_name, "lastname": last_name}, {}), "ok": True}

    @tool("update_member", CHANGE)
    async def update_member(
        email: Annotated[str, Field(description="E-mail address that identifies the member")],
        first_name: str | None = None,
        last_name: str | None = None,
        mobile_phone: str | None = None,
        properties: Annotated[list[MemberProperty] | None, Field(description="Custom member fields to set")] = None,
    ) -> dict:
        """Change name, mobile phone or custom fields of a member. Only given values change. Confirm with the user first."""
        body = member_body(email, first_name, last_name, mobile_phone, properties)
        if len(body) == 1:
            raise ToolError("Nothing to change – give at least one new value.")
        await state.call(state.api.update_member, body)
        state.forget_cache()
        return {"updated": sorted(k for k in body if k != "mail"), "ok": True}

    # health check for the launcher -------------------------------------------
    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(_request: Request) -> JSONResponse:
        if (state.state_dir / "key_invalid").exists():
            return JSONResponse({"status": "failed"}, status_code=503)
        return JSONResponse({"status": "ready", "tools": len(enabled)})

    return mcp


def lock_down(state_dir: str) -> bool:
    """Landlock (where the kernel offers it): only its own folder and /tmp."""
    import sandbox

    # Python's own folders stay readable wherever Python is installed (modules
    # are imported lazily, e.g. by uvicorn at start).
    code = tuple(p for p in {sys.prefix, sys.base_prefix, *sys.path} if p and os.path.isdir(p))
    try:
        return sandbox.restrict([state_dir, "/tmp"], read_dirs=sandbox.READ_PATHS + code)
    except OSError as exc:
        log.error("Landlock could not be applied: %s", exc)
        return False


def main() -> None:
    debug = os.environ.get("KM_LOG_LEVEL") == "debug"
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    for noisy in ("httpx", "mcp", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.DEBUG if debug else logging.WARNING)
    state_dir = Path(os.environ["KM_STATE_DIR"])
    key = read_key(os.environ["KM_KEY_FILE"])
    port = int(os.environ.get("KM_PORT", "8000"))
    settings = load_settings()
    state = State(settings, Konzertmeister(key), state_dir)
    del key
    server = build_server(state, port)
    lock_down(str(state_dir))
    log.info("Konzertmeister MCP server ready (%d tools)", len(settings["tools"]))
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
