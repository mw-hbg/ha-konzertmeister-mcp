"""App page behind Home Assistant ingress, the status channel of the helper
integration and the stand-in MCP endpoint (both reached only through nginx)."""

from __future__ import annotations

import html
import json
import logging
import secrets
import socket

import anyio
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

import i18n
import settings as km_settings
from common import ALLOW_ANY_UI_CLIENT, INGRESS_PROXY_IP, LOAD_WARNING_FROM, MAX_CLUBS, PUBLIC_PORT, app_version, normalize_public_url
from remote import NOT_READY_TEXT, app_slug, not_ready_answer, run_connection_test
from clubs import ClubError
from web_assets import CSS, JS, PRESET_JS, STATUS_POLL_JS

log = logging.getLogger("konzertmeister_mcp_app")

SERVICES = None  # set by the launcher
REMOTE = None
CSRF_TOKEN = secrets.token_urlsafe(24)
FLASH: dict = {}
DOCS_BASE = "https://github.com/mw-hbg/ha-konzertmeister-mcp/blob/main/konzertmeister_mcp"
LANG_COOKIE = "konzertmeister_mcp_lang"
KM_API_HELP = "https://konzertmeister.app/de/help/konzertmeister-api"


def setup(services, remote) -> None:
    global SERVICES, REMOTE
    SERVICES, REMOTE = services, remote


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def e(value) -> str:
    return html.escape(str(value), quote=True)


def _lang(request: Request) -> str:
    """Language chosen on the page > browser > Home Assistant > English."""
    ha = REMOTE.report.get("language", "") if REMOTE is not None else ""
    return i18n.pick(request.cookies.get(LANG_COOKIE), i18n.from_accept_language(request.headers.get("accept-language")), ha)


def detail_text(t: dict, detail: str) -> str:
    """Details starting with an at sign are translated (key or key|value)."""
    if not detail.startswith("@"):
        return e(detail)
    key, _, value = detail[1:].partition("|")
    return e(t.get("detail_" + key, key).replace("{value}", value))


def _guard(request: Request, allow_local: bool = False) -> Response | None:
    """Only Home Assistant's ingress proxy may use the page. 127.0.0.1 only for
    status.json (health check) – the MCP servers run in the same container
    and must never read the page (CSRF token, connector URLs)."""
    client = request.client.host if request.client else ""
    if ALLOW_ANY_UI_CLIENT or client == INGRESS_PROXY_IP or (allow_local and client == "127.0.0.1"):
        return None
    return Response("Forbidden", status_code=403)


def _redirect(request: Request, anchor: str = "") -> RedirectResponse:
    base = request.headers.get("x-ingress-path", "")
    return RedirectResponse(f"{base}/{anchor}", status_code=303)


async def _form(request: Request):
    form = await request.form()
    if not secrets.compare_digest(str(form.get("csrf", "")), CSRF_TOKEN):
        FLASH.update(kind="err", key="err_csrf")
        return None
    return form


async def _club_form(request: Request):
    form = await _form(request)
    if form is None:
        return None
    try:
        return form, SERVICES.club(form.get("club"))
    except ClubError as exc:
        FLASH.update(kind="err", key=exc.key)
        return None


def _csrf() -> str:
    return f'<input type="hidden" name="csrf" value="{CSRF_TOKEN}">'


def _club_field(club) -> str:
    return f'<input type="hidden" name="club" value="{e(club.id)}">'


def _confirm(text: str) -> str:
    return f'data-confirm="{e(text)}" onsubmit="return confirm(this.dataset.confirm)"'


def _secret_field(fid: str, value: str, t: dict) -> str:
    mask = "•" * 24
    if "://" in value:
        scheme, rest = value.split("://", 1)
        mask = f"{scheme}://{rest.split('/', 1)[0]}/{'•' * 20}"
    return (
        f'<div class="row"><code id="{fid}" data-value="{e(value)}" data-mask="{e(mask)}" data-hidden="1">{e(mask)}</code>'
        f'<button type="button" class="secondary" data-show="{e(t["show"])}" data-hide="{e(t["hide"])}" '
        f"onclick=\"toggle('{fid}',this)\">{t['show']}</button>"
        f'<button type="button" class="secondary" data-done="{e(t["copied"])}" '
        f"onclick=\"copyVal('{fid}',this)\">{t['copy']}</button></div>"
    )


def _test_html(t: dict, result: dict) -> str:
    if not result:
        return ""
    rows = "".join(
        f'<tr><td>{"⚠️" if c.get("warn") else "✅" if c["ok"] else "❌"}</td><td>{t[c["key"]]}</td>'
        f'<td class="muted">{detail_text(t, c["detail"])}</td></tr>'
        for c in result["checks"]
    )
    if not result["ok"]:
        summary, cls = t["test_failed"], "err"
    elif result.get("warn"):
        summary, cls = t["test_warn"], "warn"
    else:
        summary, cls = t["test_ok"], "ok"
    return f'<p class="{cls}">{summary} <span class="muted">({e(result["time"])})</span></p><table>{rows}</table>'


def _check(name: str, value: str, label: str, checked: bool, extra: str = "") -> str:
    return (
        f'<label class="check"><input type="checkbox" name="{name}" value="{e(value)}"{" checked" if checked else ""}{extra}> '
        f"{label}</label>"
    )


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------
def _settings_form(lang: str, t: dict, club) -> str:
    s = club.settings()
    info = club.info()
    csrf, vf = _csrf(), _club_field(club)
    parts = [f'<form method="post" action="clubs/settings" onsubmit="return busy(this)">{csrf}{vf}']

    # 1. what the AI may do
    tools = "".join(
        _check(
            "tool",
            name,
            f'{e(i18n.tool(lang, name))} <span class="badge {kind}">{t["kind_" + kind]}</span> <code style="display:inline;border:0;padding:0" class="muted">{name}</code>',
            name in s["tools"],
            f' data-kind="{kind}"',
        )
        for name, kind in km_settings.TOOLS.items()
    )
    parts.append(
        f'<details><summary>{t["sec_tools"]}</summary><p class="muted">{t["tools_intro"]}</p>'
        f'<div class="row"><span class="muted">{t["preset"]}</span>'
        f'<button type="button" class="secondary" onclick="preset(this,[\'read\'])">{t["preset_read"]}</button>'
        f'<button type="button" class="secondary" onclick="preset(this,[\'read\',\'create\'])">{t["preset_create"]}</button>'
        f'<button type="button" class="secondary" onclick="preset(this,[\'read\',\'create\',\'change\'])">{t["preset_all"]}</button></div>'
        f'<div class="tools-list">{tools}</div><p class="muted">{t["confirm_note"]}</p></details>'
    )

    # 2. groups
    known = info.get("groups", [])
    chosen = set(s["groups"])
    group_boxes = "".join(_check("group", str(g["id"]), e(g["name"]), g["id"] in chosen) for g in known)
    # groups chosen earlier but not seen lately stay selectable
    group_boxes += "".join(
        _check("group", str(gid), e(t["group_n"].format(n=gid)), True) for gid in sorted(chosen - {g["id"] for g in known})
    )
    parts.append(
        f'<details><summary>{t["sec_groups"]}</summary><p class="muted">{t["groups_intro"]}</p>'
        + (f"<div>{group_boxes}</div>" if group_boxes else f'<p class="muted">{t["groups_none"]}</p>')
        + _check("nogroup", "1", t["include_without_group"], s["include_without_group"])
        + f'<p class="warn">{t["groups_members_note"]}</p>'
        f'<button type="submit" class="secondary" formaction="clubs/refresh" formnovalidate>{t["groups_reload"]}</button></details>'
    )

    # 3. member data
    shares = "".join(_check("share", key, t["share_" + key], s["share"][key]) for key in km_settings.SHARE_KEYS)
    parts.append(
        f'<details><summary>{t["sec_members"]}</summary><p class="muted">{t["members_intro"]}</p>{shares}'
        f'<p class="warn">{t["gdpr_note"]}</p></details>'
    )

    # 4. creating appointments
    found_types = info.get("types", [])
    parts.append(
        f'<details><summary>{t["sec_create"]}</summary>'
        f'<label>{t["creator_mail"]}</label><input name="creator_mail" type="email" value="{e(s["creator_mail"])}" placeholder="name@example.com">'
        f'<p class="muted">{t["creator_mail_hint"]}</p>'
        f'<label>{t["templates"]}</label><textarea name="templates" placeholder="{e(t["templates_placeholder"])}">{e(km_settings.pairs_text(s["templates"]))}</textarea>'
        f'<p class="muted">{t["templates_hint"]}</p></details>'
        f'<details><summary>{t["sec_types"]}</summary>'
        f'<textarea name="types" placeholder="{e(t["types_placeholder"])}">{e(km_settings.pairs_text(s["types"]))}</textarea>'
        f'<p class="muted">{t["types_hint"]}</p>'
        + (f'<p class="muted">{t["types_found"]} <b>{e(", ".join(str(n) for n in found_types))}</b></p>' if found_types else "")
        + "</details>"
    )
    parts.append(f'<button type="submit" data-busy="{t["restart_busy"]}">{t["save_settings"]}</button></form>')
    return "".join(parts)


async def _club_card(lang: str, t: dict, club, base: str) -> str:
    csrf, vf = _csrf(), _club_field(club)
    km_name = club.km_name()
    parts = [f'<div class="card" id="v{e(club.id)}">']
    if SERVICES.named:
        title = club.display_name() if (club.custom_name or km_name) else t["club_n"].format(n=club.id)
        parts.append(
            f'<div class="row"><h2 style="margin:0">{e(title)}</h2>'
            f'<details class="rename"><summary title="{e(t["rename"])}" aria-label="{e(t["rename"])}">✏️</summary>'
            f'<form method="post" action="clubs/rename">{csrf}{vf}<label>{t["rename"]}</label>'
            f'<input name="name" maxlength="40" value="{e(club.custom_name)}" placeholder="{e(km_name or t["club_n"].format(n=club.id))}">'
            f'<p class="muted">{t["rename_hint"]}</p><button type="submit">{t["save_name"]}</button></form></details></div>'
        )
        if club.custom_name and km_name:
            parts.append(f'<p class="muted" style="margin:4px 0 0">{t["km_name"]}: {e(km_name)}</p>')
    else:
        parts.append(f'<h2>{t["club"]}</h2>')

    # API key
    state = await anyio.to_thread.run_sync(club.shown_state)
    key_form = (
        f'<form method="post" action="clubs/key" onsubmit="return busy(this)">{csrf}{vf}'
        f'<label>{t["api_key"]}</label><input name="key" type="password" autocomplete="off" spellcheck="false" required>'
        f'<button type="submit" data-busy="{t["key_busy"]}">{{button}}</button></form>'
    )
    if not club.has_key():
        parts.append(f'<p class="muted">{t["no_key"]}</p><p class="muted">{t["key_how"].format(url=KM_API_HELP)}</p>')
        parts.append(key_form.replace("{button}", t["key_save"]))
    else:
        if state == "failed":
            parts.append(f'<p class="err">{t["key_rejected"]}</p>' + key_form.replace("{button}", t["key_replace"]))
        else:
            parts.append(f'<p>{t["key_stored"]}' + (f" <b>{e(km_name)}</b>" if km_name else "") + "</p>")
            parts.append(f'<details><summary>{t["key_replace"]}</summary>{key_form.replace("{button}", t["key_replace"])}</details>')

    # status
    s = club.settings()
    shared = [t["share_" + k] for k in km_settings.SHARE_KEYS if s["share"][k]]
    groups = {g["id"]: g["name"] for g in club.info().get("groups", [])}
    group_text = ", ".join(groups.get(g, str(g)) for g in s["groups"]) if s["groups"] else t["groups_all"]
    writes = [n for n in s["tools"] if n in km_settings.WRITE_TOOLS]
    cls = {"ready": "ok", "failed": "err", "pending": "warn", "off": "warn", "no_key": "muted"}.get(state, "muted")
    parts.append(
        f'<table><tr><td class="muted">{t["state"]}</td><td class="{cls}">{t["state_" + state]}</td></tr>'
        f'<tr><td class="muted">{t["tools"]}</td><td>{len(s["tools"])} / {len(km_settings.TOOLS)}'
        + (f' <span class="badge create">{t["writes_on"]}</span>' if writes else f' <span class="badge read">{t["read_only"]}</span>')
        + f'</td></tr><tr><td class="muted">{t["groups"]}</td><td>{e(group_text)}</td></tr>'
        f'<tr><td class="muted">{t["member_data"]}</td><td>{e(", ".join(shared) or t["names_only"])}</td></tr></table>'
    )
    if "create_appointment" in s["tools"] and not (s["creator_mail"] and s["templates"]):
        parts.append(f'<p class="warn">{t["create_incomplete"]}</p>')
    parts.append(_settings_form(lang, t, club))

    # connector URL, test and the rest
    parts.append(f'<label>{t["connector_url"]}</label>{_secret_field("url" + club.id, REMOTE.connector_url(club, base), t)}')
    if REMOTE.enabled and not base:
        parts.append(f'<p class="muted">{t["no_base_url"]}</p>')
    parts.append(_test_html(t, club.test_result))
    remove_text = t["remove_confirm"].format(name=club.display_name())
    parts.append(
        '<div class="row">'
        f'<form method="post" action="clubs/test" onsubmit="return busy(this)">{csrf}{vf}'
        f'<button type="submit" class="secondary" data-busy="{t["test_busy"]}">{t["test_run"]}</button></form>'
        f'<form method="post" action="clubs/rotate" {_confirm(t["rotate_confirm"])}>{csrf}{vf}'
        f'<button type="submit" class="secondary">{t["rotate"]}</button></form>'
        + (
            f'<form method="post" action="clubs/delete-key" {_confirm(t["delete_key_confirm"])}>{csrf}{vf}'
            f'<button type="submit" class="secondary">{t["delete_key"]}</button></form>'
            if club.has_key() else ""
        )
        + (
            f'<form method="post" action="clubs/remove" {_confirm(remove_text)}>{csrf}{vf}'
            f'<button type="submit" class="secondary danger">{t["remove_club"]}</button></form>'
            if SERVICES.named else ""
        )
        + "</div></div>"
    )
    return "".join(parts)


def page_status() -> str:
    """Status as the page shows it – compared with status.json by STATUS_POLL_JS."""
    states = [f"{v.id}:{v.shown_state()}" for v in SERVICES.clubs.values()]
    return "|".join([*states, REMOTE.state])


async def index(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    lang = _lang(request)
    t = i18n.ui(lang)
    parts = [f"<h1>{t['title']}</h1>"]
    if FLASH:
        detail = FLASH.get("detail", "")
        msg = t.get(FLASH.get("key", ""), FLASH.get("key", "")) + (f" <span class='muted'>({e(detail)})</span>" if detail else "")
        parts.append(f'<div class="flash {FLASH.get("kind", "ok")}">{msg}</div>')
        FLASH.clear()
    if REMOTE.enabled and REMOTE.state == "restart_needed":
        parts.append(f'<div class="banner"><b>{t["restart_banner_title"]}</b><p>{t["restart_hint"]}</p></div>')
    clubs = list(SERVICES.clubs.values())
    if len(clubs) >= LOAD_WARNING_FROM:
        parts.append(f'<div class="banner">{t["load_warning"]}</div>')

    base = await anyio.to_thread.run_sync(REMOTE.base_url) if REMOTE.enabled else ""
    for club in clubs:
        parts.append(await _club_card(lang, t, club, base))

    csrf = _csrf()
    parts.append(f'<div class="card"><h2>{t["add_club"]}</h2>')
    if len(clubs) >= MAX_CLUBS:
        parts.append(f'<p class="muted">{t["max_clubs"].format(n=MAX_CLUBS)}</p>')
    else:
        parts.append(f'<p class="muted">{t["add_club_hint"]}</p>')
        if len(clubs) + 1 >= LOAD_WARNING_FROM:
            parts.append(f'<p class="warn">{t["load_warning"]}</p>')
        parts.append(f'<form method="post" action="clubs/add">{csrf}<button type="submit">{t["add_club"]}</button></form>')
    parts.append("</div>")

    # connection
    direct_public, url_problem = normalize_public_url(SERVICES.options.get("public_url"))
    parts.append(f'<div class="card"><h2>{t["connection"]}</h2>')
    if url_problem:
        parts.append(f'<p class="warn">{t["public_url_" + url_problem]}</p>')
    if REMOTE.enabled:
        rcls = {"active": "ok", "error": "err", "restart_needed": "warn"}.get(REMOTE.state, "muted")
        parts.append(
            f'<table><tr><td class="muted">{t["remote"]}</td><td class="{rcls}">{t["remote_" + REMOTE.state]}'
            + (f' <span class="muted">({detail_text(t, REMOTE.detail)})</span>' if REMOTE.state == "error" and REMOTE.detail else "")
            + f'</td></tr></table><p class="warn">{t["secret_warning"]}</p><p>{t["steps"]}</p>'
        )
    else:
        if REMOTE.cleaned_up:
            parts.append(f'<p class="ok">{t["cleaned_up"]}</p>')
        parts.append(
            ("" if direct_public else f'<p class="muted">{t["no_public_url"]}</p>')
            + f'<p class="warn">{t["secret_warning"]}</p><p>{t["steps"]}</p>'
            f'<label>{t["internal_url"]}</label><div class="row"><code>http://{e(socket.gethostname())}:{PUBLIC_PORT}</code></div>'
            f'<p class="muted">{t["internal_hint"]}</p>'
        )
    parts.append(
        f'<div class="row links"><a class="btn secondary" href="/config/app/{e(app_slug())}/config" target="_top">{t["open_config"]}</a></div>'
        f'<p class="muted">{t["admins_note"]}</p></div>'
    )

    links = " · ".join(
        f"<b>{e(name)}</b>" if code == lang else f'<a href="lang?l={code}">{e(name)}</a>' for code, name in i18n.names().items()
    )
    parts.append(
        f'<p class="muted footer">Konzertmeister MCP {e(app_version())}'
        f' · <a href="{DOCS_BASE}/DOCS.md#{t["docs_section"]}" target="_blank" rel="noopener">{t["docs"]}</a>'
        + (f" · {links}" if len(i18n.names()) > 1 else "")
        + "</p>"
    )
    shown = await anyio.to_thread.run_sync(page_status)
    waiting = any(v.shown_state() == "pending" for v in clubs) or REMOTE.state == "setting_up"
    page = (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{t['title']}</title><style>{CSS}</style></head>"
        f"<body><main>{''.join(parts)}</main><script>{JS}{PRESET_JS}</script>"
        + (f"<script>const SHOWN={json.dumps(shown)};{STATUS_POLL_JS}</script>" if waiting else "")
        + "</body></html>"
    )
    return HTMLResponse(page)


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------
def _settings_from_form(form, club) -> tuple[dict | None, str]:
    """(new settings, error key)."""
    s = club.settings()
    mail = " ".join(str(form.get("creator_mail", "")).split())
    if mail and not km_settings.valid_mail(mail):
        return None, "err_creator_mail"
    data = {
        "tools": [str(n) for n in form.getlist("tool")],
        "groups": [str(g) for g in form.getlist("group") if str(g).isdigit()],
        "include_without_group": form.get("nogroup") == "1",
        "share": {key: key in form.getlist("share") for key in km_settings.SHARE_KEYS},
        "creator_mail": mail,
        "templates": km_settings.parse_pairs(str(form.get("templates", "")), False, km_settings.MAX_TEMPLATES),
        "types": km_settings.parse_pairs(str(form.get("types", "")), True, km_settings.MAX_TYPES),
    }
    s.update(data)
    return km_settings.normalize(s), ""


async def save_settings(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    anchor = ""
    if (got := await _club_form(request)) is not None:
        form, club = got
        anchor = f"#v{club.id}"
        new, error = _settings_from_form(form, club)
        if new is None:
            FLASH.update(kind="err", key=error)
        else:
            await anyio.to_thread.run_sync(club.save_settings, new)
            log.info("[%s] Settings saved (%d tools)", club.display_name(), len(new["tools"]))
            FLASH.update(kind="ok", key="ok_settings")
    return _redirect(request, anchor)


async def refresh_info(request: Request) -> Response:
    """'Load groups again' – also keeps the settings typed so far."""
    if (denied := _guard(request)) is not None:
        return denied
    anchor = ""
    if (got := await _club_form(request)) is not None:
        form, club = got
        anchor = f"#v{club.id}"
        new, _error = _settings_from_form(form, club)
        if new is not None:
            await anyio.to_thread.run_sync(club.save_settings, new)
        result = await anyio.to_thread.run_sync(club.refresh_info)
        if result["ok"]:
            FLASH.update(kind="ok", key="ok_refreshed")
        else:
            FLASH.update(kind="err", key={"no_key": "err_no_key", "auth": "err_key_rejected"}.get(result["kind"], "err_key_check"), detail=result.get("detail", ""))
    return _redirect(request, anchor)


async def set_key(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    anchor = ""
    if (got := await _club_form(request)) is not None:
        form, club = got
        anchor = f"#v{club.id}"
        try:
            await anyio.to_thread.run_sync(club.set_key, str(form.get("key", "")))
            REMOTE.nudge()  # the name in Home Assistant may have changed
            FLASH.update(kind="ok", key="ok_key")
        except ClubError as exc:
            FLASH.update(kind="err", key=exc.key, detail=exc.detail)
    return _redirect(request, anchor)


async def delete_key(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if (got := await _club_form(request)) is not None:
        await anyio.to_thread.run_sync(got[1].delete_key)
        FLASH.update(kind="ok", key="ok_key_deleted")
    return _redirect(request)


async def do_test(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    anchor = ""
    if (got := await _club_form(request)) is not None:
        club = got[1]
        anchor = f"#v{club.id}"
        club.test_result.clear()
        club.test_result.update(await anyio.to_thread.run_sync(run_connection_test, club, REMOTE))
    return _redirect(request, anchor)


async def do_rotate(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if (got := await _club_form(request)) is not None:
        club = got[1]
        await anyio.to_thread.run_sync(SERVICES.rotate_secret, club)
        REMOTE.rotate(club)
        FLASH.update(kind="ok", key="ok_rotate")
    return _redirect(request)


async def add_club(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if await _form(request) is not None:
        try:
            await anyio.to_thread.run_sync(SERVICES.add_club)
            REMOTE.nudge()
            FLASH.update(kind="ok", key="ok_club_added")
        except ClubError as exc:
            FLASH.update(kind="err", key=exc.key)
    return _redirect(request)


async def remove_club(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if (got := await _club_form(request)) is not None:
        if len(SERVICES.clubs) <= 1:
            FLASH.update(kind="err", key="err_last_club")
        else:
            await anyio.to_thread.run_sync(SERVICES.remove_club, got[1])
            REMOTE.nudge()
            FLASH.update(kind="ok", key="ok_club_removed")
    return _redirect(request)


async def rename_club(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if (got := await _club_form(request)) is not None:
        form, club = got
        await anyio.to_thread.run_sync(SERVICES.rename_club, club, str(form.get("name", "")))
        REMOTE.nudge()
        FLASH.update(kind="ok", key="ok_renamed")
    return _redirect(request)


async def set_language(request: Request) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    response = _redirect(request)
    lang = i18n.supported(request.query_params.get("l"))
    if lang:
        base = request.headers.get("x-ingress-path", "") or "/"
        response.set_cookie(LANG_COOKIE, lang, max_age=365 * 86400, path=base, httponly=True, samesite="strict")
    return response


# --------------------------------------------------------------------------
# Channels used through nginx only
# --------------------------------------------------------------------------
def _report_key_ok(request: Request) -> bool:
    """nginx adds the key – only it knows it, so neither an MCP server inside
    the container nor anything else can fake a report or a stand-in answer."""
    key = request.headers.get("x-report-key", "")
    return bool(SERVICES is not None and SERVICES.report_secret) and secrets.compare_digest(key.encode(), SERVICES.report_secret.encode())


async def report(request: Request) -> Response:
    if REMOTE is None or not REMOTE.enabled or not _report_key_ok(request):
        return Response("Forbidden", status_code=403)
    body = await request.body()
    if len(body) > 4096:
        return Response("Too large", status_code=413)
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return Response("Bad request", status_code=400)
    if not isinstance(data, dict):
        return Response("Bad request", status_code=400)
    return JSONResponse(await anyio.to_thread.run_sync(REMOTE.receive_report, data))


async def mcp_unavailable(request: Request) -> Response:
    if not _report_key_ok(request):
        return Response("Forbidden", status_code=403)
    if request.method != "POST":
        return Response(status_code=405, headers={"Allow": "POST"})
    club = SERVICES.clubs.get(str(request.path_params.get("club", "")))
    try:
        data = json.loads(await request.body() or b"{}")
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    status_now = await anyio.to_thread.run_sync(club.key_status) if club else "no_key"
    reason = status_now if status_now in NOT_READY_TEXT else "starting"
    if isinstance(data, list):
        answers = [a for a in (not_ready_answer(m, reason) for m in data[:50]) if a is not None]
        return JSONResponse(answers) if answers else Response(status_code=202)
    answer = not_ready_answer(data, reason)
    return JSONResponse(answer) if answer is not None else Response(status_code=202)


async def status(request: Request) -> Response:
    if (denied := _guard(request, allow_local=True)) is not None:
        return denied
    return JSONResponse(
        {
            "state": await anyio.to_thread.run_sync(page_status),
            "remote": REMOTE.state,
            "clubs": [{"id": v.id, "has_key": v.has_key(), "switched_off": v.switched_off} for v in SERVICES.clubs.values()],
        }
    )


SECURITY_HEADERS = {
    # The page shows secrets (connector URLs): never cache it, never leak it via
    # the Referer header, only Home Assistant may frame it.
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": "frame-ancestors 'self'; base-uri 'none'; form-action 'self'; object-src 'none'",
}


class SecurityHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                for key, value in SECURITY_HEADERS.items():
                    if key.lower().encode() not in present:
                        headers.append((key.lower().encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/status.json", status),
        Route("/lang", set_language),
        Route("/report", report, methods=["POST"]),
        Route("/mcp-unavailable/{club}", mcp_unavailable, methods=["GET", "POST"]),
        Route("/clubs/add", add_club, methods=["POST"]),
        Route("/clubs/remove", remove_club, methods=["POST"]),
        Route("/clubs/rename", rename_club, methods=["POST"]),
        Route("/clubs/key", set_key, methods=["POST"]),
        Route("/clubs/delete-key", delete_key, methods=["POST"]),
        Route("/clubs/settings", save_settings, methods=["POST"]),
        Route("/clubs/refresh", refresh_info, methods=["POST"]),
        Route("/clubs/test", do_test, methods=["POST"]),
        Route("/clubs/rotate", do_rotate, methods=["POST"]),
    ],
    middleware=[Middleware(SecurityHeaders)],
)
