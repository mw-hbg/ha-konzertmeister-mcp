"""Remote access through the helper integration, connection test and the
stand-in answers while a server is not running.

The app has NO access to the Home Assistant API. It only
* copies the helper integration into custom_components (and removes it in
  direct mode),
* announces the integration's settings through the Supervisor's discovery
  service – Home Assistant then sets up (and on uninstall removes) the config
  entry itself,
* receives a status report from the integration over the internal network
  (secret path + key) and answers with the state of every association.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import threading
import time
import urllib.error
import urllib.request

from common import (
    COMPONENT_DST,
    COMPONENT_SRC,
    DISCOVERY_FILE,
    HA_CONFIG,
    MAX_CLUBS,
    PUBLIC_PORT,
    REPORT_MAX_AGE,
    WEBHOOK_DOMAIN,
    app_version,
    new_webhook_id,
    normalize_public_url,
    read_or_create,
    write_private,
)

log = logging.getLogger("konzertmeister_mcp_app")


def supervisor_api(method: str, path: str, data: dict | None = None):
    """Call the Supervisor (only /discovery is used). Returns the data or None."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(
        f"http://supervisor{path}",
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            body = json.loads(raw) if raw else {}
    except Exception as exc:  # noqa: BLE001
        log.debug("Supervisor %s %s failed: %s", method, path, exc)
        return None
    return body.get("data", {}) if isinstance(body, dict) else {}


def app_slug() -> str:
    """Slug of this app as the Supervisor knows it (hostname "abcd1234-konzertmeister-mcp")."""
    return socket.gethostname().replace("-", "_")


def _own_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return socket.gethostname()


class RemoteAccess:
    """States: disabled (direct mode), setting_up, restart_needed, active, error."""

    def __init__(self, services) -> None:
        self.services = services
        self.enabled = services.options.get("remote_access", "webhook") == "webhook"
        self.state = "setting_up" if self.enabled else "disabled"
        self.detail = ""
        self._wake = threading.Event()
        self._announced = ""
        self._started = time.time()
        self.first_install = False
        self.report: dict = {}
        self.cleaned_up = False

    # files -------------------------------------------------------------------
    @staticmethod
    def bundled_version() -> str:
        try:
            return str(json.loads((COMPONENT_SRC / "manifest.json").read_text()).get("version"))
        except (OSError, ValueError):
            return ""

    def install_component(self) -> bool:
        """Copy the integration into custom_components. True if files changed."""
        try:
            installed = json.loads((COMPONENT_DST / "manifest.json").read_text()).get("version")
        except (OSError, ValueError):
            installed = None
        if installed == self.bundled_version():
            return False
        COMPONENT_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(COMPONENT_DST, ignore_errors=True)
        shutil.copytree(COMPONENT_SRC, COMPONENT_DST, ignore=shutil.ignore_patterns("__pycache__"))
        log.info("Installed Home Assistant integration %s %s", WEBHOOK_DOMAIN, self.bundled_version())
        return True

    # discovery -----------------------------------------------------------------
    def discovery_config(self) -> dict:
        host = f"http://{_own_ip()}:{PUBLIC_PORT}"
        return {
            "clubs": [
                {
                    "id": club.id,
                    "name": club.shown_name(),
                    "webhook_id": club.webhook_id,
                    "target_url": f"{host}/{club.secret}/mcp",
                }
                for club in self.services.clubs.values()
            ],
            "report_url": f"{host}/{self.services.report_secret}/ha",
            "app_slug": app_slug(),
        }

    def _announce(self) -> bool:
        config = self.discovery_config()
        fingerprint = json.dumps(config, sort_keys=True)
        if fingerprint == self._announced:
            return True
        result = supervisor_api("POST", "/discovery", {"service": WEBHOOK_DOMAIN, "config": config})
        if result is None:
            return False
        if result.get("uuid"):
            write_private(DISCOVERY_FILE, str(result["uuid"]))
        self._announced = fingerprint
        log.info("Remote access: settings announced to Home Assistant")
        return True

    def _withdraw(self) -> None:
        try:
            uuid = DISCOVERY_FILE.read_text().strip()
        except OSError:
            return
        if uuid and supervisor_api("DELETE", f"/discovery/{uuid}") is not None:
            DISCOVERY_FILE.unlink(missing_ok=True)

    # report of the integration -------------------------------------------------
    def receive_report(self, report: dict) -> dict:
        def text(key: str, limit: int = 300) -> str:
            value = report.get(key)
            return str(value)[:limit] if isinstance(value, (str, int, float)) else ""

        external, _ = normalize_public_url(text("external_url"))
        self.report = {
            "time": time.time(),
            "external_url": external,
            "language": text("language", 20),
            "version": text("integration_version", 20),
            "restart_needed": bool(report.get("restart_needed")),
        }
        self.update_state()
        switches = report.get("clubs")
        if isinstance(switches, dict):
            for club_id, info in list(switches.items())[:MAX_CLUBS]:
                club = self.services.clubs.get(str(club_id))
                if club is not None and isinstance(info, dict) and isinstance(info.get("mcp_enabled"), bool):
                    club.set_switched_off(not info["mcp_enabled"])
        return {
            "clubs": {
                club.id: {
                    "name": club.display_name(),
                    "status": club.key_status(),
                    "mcp_enabled": not club.switched_off,
                }
                for club in self.services.clubs.values()
            },
            "notify": bool(self.services.options.get("key_notification", True)),
            "app_version": app_version(),
        }

    def update_state(self) -> None:
        if not self.enabled or self.state == "error":
            return
        fresh = self.report and time.time() - self.report.get("time", 0) < REPORT_MAX_AGE
        if fresh:
            if self.report.get("restart_needed") or self.report.get("version") != self.bundled_version():
                self.state = "restart_needed"
            else:
                if self.state != "active":
                    log.info("Remote access active")
                self.state, self.detail = "active", ""
        elif self.first_install or time.time() - self._started > 300:
            self.state = "restart_needed"
        else:
            self.state = "setting_up"

    # loop ----------------------------------------------------------------------
    def _cleanup(self) -> None:
        """Direct mode: remove the helper integration if an earlier start installed it."""
        self._withdraw()
        if not COMPONENT_DST.exists():
            return
        log.info("Remote access is set to direct – removing the helper integration")
        shutil.rmtree(COMPONENT_DST, ignore_errors=True)
        self.cleaned_up = True

    def run(self) -> None:
        if not self.enabled:
            try:
                self._cleanup()
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not remove the helper integration: %s", exc)
            return
        if not HA_CONFIG.is_dir():
            self.state, self.detail = "error", "@no_config_access"
            log.error("Remote access: the Home Assistant configuration folder is not available")
            return
        try:
            if self.install_component():
                self.first_install = True
        except OSError as exc:
            self.state, self.detail = "error", str(exc)
            log.error("Remote access: could not install integration: %s", exc)
            return
        while not self.services.stopping:
            try:
                announced = self._announce()
                self.update_state()
            except Exception as exc:  # noqa: BLE001
                announced = False
                log.warning("Remote access: %s", exc)
            self._wake.wait(30 if not announced or self.state != "active" else 300)
            self._wake.clear()

    def rotate(self, club) -> None:
        club.webhook_id = read_or_create(club.webhook_id_file, new_webhook_id, rotate=True)
        self._wake.set()

    def nudge(self) -> None:
        self._wake.set()

    def base_url(self) -> str:
        configured, _ = normalize_public_url(self.services.options.get("public_url"))
        return configured or self.report.get("external_url", "")

    def connector_url(self, club, base: str) -> str:
        if self.enabled:
            return f"{base or 'https://<your-home-assistant>'}/api/webhook/{club.webhook_id}"
        public, _ = normalize_public_url(self.services.options.get("public_url"))
        return f"{public or 'https://<your-domain>'}/{club.secret}/mcp"


# --------------------------------------------------------------------------
# Connection test
# --------------------------------------------------------------------------
def mcp_request(url: str, payload: dict, host_header: str | None = None, timeout: int = 20):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        # A real client name: Cloudflare and similar services block "Python-urllib".
        "User-Agent": f"Mozilla/5.0 (compatible; KonzertmeisterMCP/{app_version()}; "
        "+https://github.com/mw-hbg/ha-konzertmeister-mcp)",
    }
    if host_header:
        headers["Host"] = host_header
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    lines = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
    return json.loads(lines[0] if lines else raw)


def blocked_by_proxy(exc: urllib.error.HTTPError) -> bool:
    """True if a 403/429/503 came from Cloudflare (or a similar proxy), not from HA."""
    if exc.code not in (403, 429, 503):
        return False
    headers = {k.lower(): v.lower() for k, v in (exc.headers or {}).items()}
    if "cf-ray" in headers or "cf-mitigated" in headers or "cloudflare" in headers.get("server", ""):
        return True
    try:
        body = exc.read(2048).decode(errors="ignore").lower()
    except Exception:  # noqa: BLE001
        body = ""
    return "cloudflare" in body


def run_connection_test(club, remote: RemoteAccess) -> dict:
    """Server, Konzertmeister (key, groups, types) and the public connector URL."""
    result: dict = {"time": time.strftime("%H:%M:%S"), "checks": []}

    def add(key: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        result["checks"].append({"key": key, "ok": ok, "detail": detail, "warn": warn})

    # 1. Konzertmeister accepts the key
    probe = club.refresh_info()
    if probe["ok"]:
        add("test_km", True, f"@km_ok|{probe.get('count', 0)}")
    else:
        add("test_km", False, {"no_key": "@no_key", "auth": "@key_rejected", "forbidden": "@key_rejected"}.get(probe["kind"], probe.get("detail", "")))

    # 2. MCP server answers locally
    try:
        data = mcp_request(
            f"http://127.0.0.1:{club.port}/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            host_header=f"127.0.0.1:{club.port}",
        )
        add("test_server", True, f"@tools|{len(data['result']['tools'])}")
    except Exception as exc:  # noqa: BLE001
        add("test_server", False, "@server_off" if club.shown_state() in ("off", "no_key") else type(exc).__name__)

    # 3. The connector URL works from the internet (round trip like the AI app)
    if remote.enabled:
        base = remote.base_url()
        url = f"{base}/api/webhook/{club.webhook_id}" if base else ""
    else:
        public, _ = normalize_public_url(remote.services.options.get("public_url"))
        url = f"{public}/{club.secret}/mcp" if public else ""
    if not url:
        add("test_public", False, "@no_public")
    else:
        try:
            data = mcp_request(
                url,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "konzertmeister-mcp-app-selftest", "version": "1"},
                    },
                },
            )
            add("test_public", "result" in data, data.get("result", {}).get("serverInfo", {}).get("name", ""))
        except urllib.error.HTTPError as exc:
            if blocked_by_proxy(exc):
                add("test_public", True, f"@blocked_proxy|{exc.code}", warn=True)
            elif exc.code in (401, 403):
                add("test_public", False, f"@http_forbidden|{exc.code}")
            else:
                add("test_public", False, f"HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            add("test_public", False, type(exc).__name__)
    result["ok"] = all(c["ok"] for c in result["checks"])
    result["warn"] = any(c.get("warn") for c in result["checks"])
    return result


# --------------------------------------------------------------------------
# Stand-in answers (no key, key rejected, starting, switched off)
# --------------------------------------------------------------------------
NOT_READY_TEXT = {
    "no_key": (
        "Konzertmeister is not connected: no API key is stored for this association in the Home "
        "Assistant app 'Konzertmeister MCP'. Ask the user to open 'Konzertmeister' in the Home "
        "Assistant sidebar and enter the association's API key (a leader of the association creates "
        "it in the Konzertmeister web app), then try again."
    ),
    "failed": (
        "Konzertmeister rejected the API key of this association (wrong or revoked). Ask the user to "
        "open 'Konzertmeister' in the Home Assistant sidebar and enter a new API key."
    ),
    "starting": "The Konzertmeister MCP server is starting. Try again in a minute.",
    "off": (
        "The Konzertmeister MCP server of this association is switched off in Home Assistant. Ask the "
        "user to turn on its switch ('Konzertmeister MCP … Server') in Home Assistant, then try again."
    ),
}


def not_ready_answer(message, reason: str) -> dict | None:
    """MCP answer of the stand-in for one JSON-RPC message (None = no answer)."""
    if not isinstance(message, dict) or "id" not in message:
        return None  # notification
    text = NOT_READY_TEXT[reason]
    method = message.get("method")
    if method == "initialize":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        result = {
            "protocolVersion": str(params.get("protocolVersion") or "2025-06-18"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "Konzertmeister (not ready)", "version": app_version()},
            "instructions": text,
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "konzertmeister_connection_status",
                    "description": "Explains why the Konzertmeister tools are not available right now. " + text,
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        }
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": text}], "isError": True}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": text}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}
