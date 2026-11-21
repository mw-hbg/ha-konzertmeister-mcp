"""Associations (Vereine): their files, settings and MCP servers, plus nginx.

Every association has
* /data/clubs/<id>/            root-owned: secret path, webhook id, settings, info
* /data/clubs/<id>/private/    owned by its own user km<slot>: API key and the
                                 server's state – no association can read another
                                 association's key.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import httpx

import settings as km_settings
from common import (
    DATA,
    MAX_CLUBS,
    MCP_PORT,
    MCP_USER,
    PUBLIC_PORT,
    REGISTRY_FILE,
    UI_PORT,
    CLUBS_DIR,
    allow_passage,
    hand_over,
    load_options,
    mcp_identity,
    new_secret,
    new_webhook_id,
    read_json,
    read_or_create,
    read_private,
    report_secret,
    write_private,
)
from km_api import BASE_URL, KEY_HEADER, PATH_APPOINTMENTS, USER_AGENT

log = logging.getLogger("konzertmeister_mcp_app")
APP_DIR = Path(__file__).resolve().parent
NGINX_CONF = Path("/tmp/konzertmeister-mcp-nginx.conf")


class ClubError(Exception):
    def __init__(self, key: str, detail: str = "") -> None:
        super().__init__(key)
        self.key = key
        self.detail = detail


# --------------------------------------------------------------------------
# Talking to Konzertmeister from the app page (key check, groups, types)
# --------------------------------------------------------------------------
def probe_api(key: str, type_ids: list[int], base_url: str = BASE_URL, transport=None) -> dict:
    """Ask Konzertmeister for the upcoming appointments with this key.

    Returns {"ok": True, "name", "groups", "types", "count"} or
    {"ok": False, "kind": auth|forbidden|network|other, "detail"}."""
    body = {
        "typeIds": type_ids,
        "activationStatusList": ["ACTIVE"],
        "publishedStatus": "ALL",
        "sortMode": "STARTDATE",
        "dateMode": "UPCOMING",
        "page": 0,
    }
    try:
        with httpx.Client(
            base_url=base_url,
            headers={KEY_HEADER: key, "User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(20.0, connect=10.0),
            transport=transport,
            follow_redirects=False,
        ) as client:
            response = client.post(PATH_APPOINTMENTS, json=body)
    except httpx.HTTPError as exc:
        return {"ok": False, "kind": "network", "detail": type(exc).__name__}
    if response.status_code == 401:
        return {"ok": False, "kind": "auth", "detail": "HTTP 401"}
    if response.status_code == 403:
        return {"ok": False, "kind": "forbidden", "detail": "HTTP 403"}
    if response.status_code >= 300:
        return {"ok": False, "kind": "other", "detail": f"HTTP {response.status_code}"}
    try:
        data = response.json()
    except ValueError:
        data = []
    appointments = [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []
    return {"ok": True, **summarize(appointments)}


def summarize(appointments: list[dict]) -> dict:
    """Name of the association, groups and type numbers seen in appointments."""
    names: Counter = Counter()
    groups: dict[int, str] = {}
    types: set[int] = set()
    for a in appointments:
        org = a.get("org") if isinstance(a.get("org"), dict) else {}
        top = org.get("name") if org.get("parentId") in (None, 0) else org.get("parentName")
        if top:
            names[str(top)[:60]] += 1
        group = a.get("group")
        if isinstance(group, dict) and isinstance(group.get("id"), int):
            groups[group["id"]] = str(group.get("name") or group["id"])[:60]
        if isinstance(a.get("typId"), int):
            types.add(a["typId"])
    return {
        "name": names.most_common(1)[0][0] if names else "",
        "groups": [{"id": gid, "name": name} for gid, name in sorted(groups.items(), key=lambda g: g[1].lower())],
        "types": sorted(types),
        "count": len(appointments),
    }


# --------------------------------------------------------------------------
# One association
# --------------------------------------------------------------------------
class Club:
    def __init__(self, record: dict, services: "Services") -> None:
        self.services = services
        self.id = str(record["id"])
        if not self.id.isdigit():
            raise ValueError("bad id")
        self.slot = int(record["slot"])
        if not 1 <= self.slot <= MAX_CLUBS:
            raise ValueError("bad slot")
        self.custom_name = str(record.get("custom_name", ""))[:40]
        self.base = CLUBS_DIR / self.id
        self.private = self.base / "private"
        self.key_file = self.private / "api_key"
        self.key_invalid_file = self.private / "key_invalid"
        self.secret_file = self.base / "secret_path"
        self.webhook_id_file = self.base / "webhook_id"
        self.settings_file = self.base / "settings.json"
        self.info_file = self.base / "info.json"
        self.switched_off_file = self.base / "mcp_switched_off"
        self.port = MCP_PORT + self.slot - 1
        self.user = f"{MCP_USER}{self.slot}"
        self.proxy_conf = Path(f"/tmp/konzertmeister-mcp-proxy-{self.id}.conf")
        CLUBS_DIR.mkdir(mode=0o711, parents=True, exist_ok=True)
        self.base.mkdir(mode=0o711, exist_ok=True)
        os.chmod(self.base, 0o711)
        self.secret = read_or_create(self.secret_file, new_secret)
        self.webhook_id = read_or_create(self.webhook_id_file, new_webhook_id)
        if services.options.get("remote_access", "webhook") != "webhook":
            self.switched_off_file.unlink(missing_ok=True)  # the switch exists only in webhook mode
        self.switched_off = self.switched_off_file.exists()
        self.mcp: subprocess.Popen | None = None
        self.removed = False
        self.test_result: dict = {}
        self._failures = 0

    # names -----------------------------------------------------------------
    def km_name(self) -> str:
        return str(self.info().get("name") or "")

    def display_name(self) -> str:
        """Own name > name from Konzertmeister > number."""
        return self.custom_name or self.km_name() or self.id

    def shown_name(self) -> str:
        """Name in Home Assistant – only once there are several associations."""
        return self.display_name() if self.services.named else ""

    def record(self) -> dict:
        return {"id": self.id, "slot": self.slot, "custom_name": self.custom_name}

    # files -----------------------------------------------------------------
    def has_key(self) -> bool:
        try:
            return bool(read_private(self.key_file, 4096).strip())
        except OSError:
            return False

    def read_key(self) -> str:
        return read_private(self.key_file, 4096).strip()

    def info(self) -> dict:
        return read_json(self.info_file)

    def settings(self) -> dict:
        return km_settings.normalize(read_json(self.settings_file)) if self.settings_file.exists() else km_settings.default_settings()

    def save_settings(self, data: dict) -> None:
        write_private(self.settings_file, km_settings.dumps(data))
        self.restart_mcp()

    def save_info(self, summary: dict) -> None:
        """Remember name, groups and types seen at Konzertmeister (merged with earlier ones)."""
        old = self.info()
        groups = {g["id"]: g["name"] for g in old.get("groups", []) if isinstance(g, dict) and isinstance(g.get("id"), int)}
        groups.update({g["id"]: g["name"] for g in summary.get("groups", [])})
        types = sorted({*[t for t in old.get("types", []) if isinstance(t, int)], *summary.get("types", [])})
        info = {
            "name": summary.get("name") or old.get("name", ""),
            "groups": [{"id": k, "name": v} for k, v in sorted(groups.items(), key=lambda g: str(g[1]).lower())][:km_settings.MAX_GROUPS],
            "types": types[: km_settings.MAX_TYPES],
            "checked": int(time.time()),
        }
        write_private(self.info_file, json.dumps(info))

    def set_key(self, key: str) -> dict:
        """Check a new API key with Konzertmeister and store it. Raises ClubError."""
        key = "".join(key.split())
        if not 16 <= len(key) <= 512 or not key.isprintable():
            raise ClubError("err_key_format")
        result = probe_api(key, km_settings.type_ids(self.settings()))
        if not result["ok"]:
            if result["kind"] in ("auth", "forbidden"):
                raise ClubError("err_key_rejected", result["detail"])
            raise ClubError("err_key_check", result["detail"])
        self.stop_mcp()
        self.private.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Written by root into the user's folder: never through a planted
        # symlink (write_private opens with O_NOFOLLOW), then handed over.
        self.key_file.unlink(missing_ok=True)
        write_private(self.key_file, key)
        self.key_invalid_file.unlink(missing_ok=True)
        hand_over(self.private, mcp_identity(self.user))
        self.save_info(result)
        self._failures = 0
        self.start_mcp()
        log.info("[%s] New API key stored", self.display_name())
        return result

    def delete_key(self) -> None:
        self.stop_mcp()
        self.key_file.unlink(missing_ok=True)
        self.key_invalid_file.unlink(missing_ok=True)
        self.test_result.clear()
        log.info("[%s] API key deleted", self.display_name())

    def refresh_info(self) -> dict:
        """Load name, groups and types again (button on the page, connection test)."""
        if not self.has_key():
            return {"ok": False, "kind": "no_key", "detail": ""}
        result = probe_api(self.read_key(), km_settings.type_ids(self.settings()))
        if result["ok"]:
            self.save_info(result)
            self.key_invalid_file.unlink(missing_ok=True)
        elif result["kind"] == "auth":
            self.key_invalid_file.touch()
        return result

    def delete_files(self) -> None:
        if self.base.parent == CLUBS_DIR and self.base.name == self.id:
            shutil.rmtree(self.base, ignore_errors=True)

    # MCP server ------------------------------------------------------------
    def environment(self) -> dict:
        env = {
            key: value
            for key, value in os.environ.items()
            # The server is reachable from the internet and acts for an AI: no
            # Supervisor token, no other credentials in its environment.
            if not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "KEY"))
        }
        env.update(
            {
                "KM_SETTINGS": km_settings.dumps(self.settings()),
                "KM_KEY_FILE": str(self.key_file),
                "KM_STATE_DIR": str(self.private),
                "KM_PORT": str(self.port),
                "KM_LOG_LEVEL": str(self.services.options.get("log_level", "info")).lower(),
                "HOME": str(self.private),
                "PYTHONPATH": str(APP_DIR),
            }
        )
        return env

    def start_mcp(self) -> None:
        with self.services.lock:
            if (self.mcp and self.mcp.poll() is None) or self.removed or self.services.stopping:
                return
            if self.switched_off:
                log.info("[%s] The MCP server is switched off in Home Assistant", self.display_name())
                return
            if not self.has_key():
                log.info("[%s] No API key yet – enter it on the app page", self.display_name())
                return
            identity = mcp_identity(self.user)
            allow_passage(DATA)
            hand_over(self.private, identity)
            drop = {}
            if identity is not None:
                drop = {"user": identity[0], "group": identity[1], "extra_groups": [], "umask": 0o077}
            else:
                log.warning("User %r missing – the MCP server runs with full rights", self.user)
            self.mcp = subprocess.Popen(
                [sys.executable, str(APP_DIR / "mcp_server.py")], env=self.environment(), cwd=str(self.private), **drop
            )
            log.info("[%s] MCP server started (%d tools)", self.display_name(), len(self.settings()["tools"]))

    def stop_mcp(self) -> None:
        with self.services.lock:
            proc, self.mcp = self.mcp, None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def restart_mcp(self) -> None:
        self.stop_mcp()
        self._failures = 0
        self.start_mcp()

    def set_switched_off(self, off: bool) -> None:
        with self.services.lock:
            if off == self.switched_off:
                return
            self.switched_off = off
            if off:
                self.switched_off_file.touch()
            else:
                self.switched_off_file.unlink(missing_ok=True)
        log.info("[%s] MCP server switched %s in Home Assistant", self.display_name(), "off" if off else "on")
        if off:
            self.stop_mcp()
        else:
            self._failures = 0
            self.start_mcp()

    def mcp_state(self) -> str:
        """'stopped', 'pending', 'ready' or 'failed' (key rejected)."""
        if not self.mcp or self.mcp.poll() is not None:
            return "stopped"
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/readyz", timeout=2) as resp:
                return json.loads(resp.read()).get("status", "ready")
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read()).get("status", "failed")
            except Exception:  # noqa: BLE001
                return "failed"
        except Exception:  # noqa: BLE001 - not listening yet
            return "pending"

    def key_status(self) -> str:
        """For the helper integration and the stand-in server:
        'ok', 'failed' (key rejected), 'no_key', 'starting', 'off'."""
        if self.switched_off:
            return "off"
        if not self.has_key():
            return "no_key"
        if self.key_invalid_file.exists():
            return "failed"
        state = self.mcp_state()
        if state == "ready":
            return "ok"
        if state == "failed":
            return "failed"
        return "starting"

    def shown_state(self) -> str:
        """State on the page: off, no_key, failed, ready, pending, stopped."""
        status = self.key_status()
        if status in ("off", "no_key", "failed"):
            return status
        return self.mcp_state()

    def supervise_tick(self) -> float:
        with self.services.lock:
            if self.mcp and self.mcp.poll() is not None:
                self._failures += 1
                delay = min(60, 5 * self._failures)
                log.error("[%s] MCP server exited (%s), restarting in %ss", self.display_name(), self.mcp.returncode, delay)
                self.mcp = None
                return delay
        return 0


# --------------------------------------------------------------------------
# nginx
# --------------------------------------------------------------------------
NGINX_TEMPLATE = """
worker_processes 1;
pid /tmp/konzertmeister-mcp-nginx.pid;
# Only critical errors: nginx error lines contain the request path, i.e. the secret.
error_log stderr crit;
events {{ worker_connections 256; }}
http {{
    access_log off;            # the secret path must never end up in a log
    server_tokens off;
    client_max_body_size 1m;
    client_body_temp_path /tmp/nginx-body;
    proxy_temp_path /tmp/nginx-proxy;
    fastcgi_temp_path /tmp/nginx-fastcgi;
    uwsgi_temp_path /tmp/nginx-uwsgi;
    scgi_temp_path /tmp/nginx-scgi;
    server {{
        listen {public_port} default_server;
{locations}{report_location}
        location / {{
            return 404;
        }}
    }}
}}
"""

# One block per association: its own secret path and its own server. While
# the server is not running (no key, starting, switched off) a small stand-in
# in the app answers proper MCP messages that tell the AI why.
NGINX_CLUB = """
        location = /{secret}/mcp {{
            include {proxy_conf};
        }}
        location = /{secret}/mcp/ {{
            include {proxy_conf};
        }}
        location @unavailable_{club} {{
            # (a named location may not have a path in proxy_pass)
            rewrite ^ /mcp-unavailable/{club} break;
            proxy_pass http://127.0.0.1:{ui_port};
            proxy_set_header X-Report-Key "{report_secret}";
            proxy_set_header Host 127.0.0.1;
            proxy_set_header Origin "";
        }}
"""

NGINX_PROXY = """
proxy_pass http://127.0.0.1:{mcp_port}/mcp;
proxy_http_version 1.1;
# The MCP SDK only accepts loopback Host headers (DNS rebinding protection);
# the request has already passed the secret-path check at this point.
proxy_set_header Host 127.0.0.1:{mcp_port};
proxy_set_header Origin "";
proxy_set_header Connection "";
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 120s;
proxy_send_timeout 120s;
error_page 502 503 504 = @unavailable_{club};
"""


# --------------------------------------------------------------------------
# All associations
# --------------------------------------------------------------------------
class Services:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.nginx: subprocess.Popen | None = None
        self.stopping = False
        self.options = load_options()
        self.report_secret = report_secret()
        registry = read_json(REGISTRY_FILE)
        if not isinstance(registry.get("clubs"), list):
            # First start: one (still empty) association
            registry = {"clubs": [{"id": "1", "slot": 1, "custom_name": ""}], "next_id": 2}
            write_private(REGISTRY_FILE, json.dumps(registry))
        self.next_id = int(registry.get("next_id", 2))
        self.clubs: dict[str, Club] = {}
        for record in registry["clubs"][:MAX_CLUBS]:
            try:
                club = Club(record, self)
            except (KeyError, ValueError, TypeError) as exc:
                log.error("Ignoring a broken association entry: %s", exc)
                continue
            self.clubs[club.id] = club

    def save_registry(self) -> None:
        write_private(
            REGISTRY_FILE,
            json.dumps({"clubs": [v.record() for v in self.clubs.values()], "next_id": self.next_id}),
        )

    @property
    def named(self) -> bool:
        """Names are only shown (and editable) from the second association on."""
        return len(self.clubs) > 1

    def club(self, club_id) -> Club:
        club = self.clubs.get(str(club_id or ""))
        if club is None:
            raise ClubError("err_no_club")
        return club

    def add_club(self) -> Club:
        with self.lock:
            if len(self.clubs) >= MAX_CLUBS:
                raise ClubError("err_max_clubs")
            used = {v.slot for v in self.clubs.values()}
            slot = min(s for s in range(1, MAX_CLUBS + 1) if s not in used)
            club = Club({"id": str(self.next_id), "slot": slot, "custom_name": ""}, self)
            self.next_id += 1
            self.clubs[club.id] = club
            self.save_registry()
            self.reload_nginx()
        log.info("Association %s added", club.id)
        return club

    def remove_club(self, club: Club) -> None:
        with self.lock:
            club.removed = True  # a timer running now must not start it again
        club.stop_mcp()
        with self.lock:
            self.clubs.pop(club.id, None)
            club.delete_files()
            self.save_registry()
            self.reload_nginx()
        log.info("Association %s removed (API key deleted)", club.id)

    def rename_club(self, club: Club, name: str) -> None:
        with self.lock:
            club.custom_name = " ".join(str(name or "").split())[:40]
            self.save_registry()

    def rotate_secret(self, club: Club) -> None:
        with self.lock:
            club.secret = read_or_create(club.secret_file, new_secret, rotate=True)
            self.reload_nginx()

    # nginx -------------------------------------------------------------------
    def _report_location(self) -> str:
        """Status channel of the helper integration: only from Home Assistant's
        internal network, and nginx adds the key."""
        if self.options.get("remote_access", "webhook") != "webhook":
            return ""
        return (
            f"        location = /{self.report_secret}/ha {{\n"
            "            allow 172.30.32.0/23;\n"
            "            deny all;\n"
            "            limit_except POST { deny all; }\n"
            f"            proxy_pass http://127.0.0.1:{UI_PORT}/report;\n"
            f'            proxy_set_header X-Report-Key "{self.report_secret}";\n'
            "            proxy_set_header Host 127.0.0.1;\n"
            "            client_max_body_size 4k;\n"
            "        }\n"
        )

    def write_nginx_conf(self) -> None:
        blocks = []
        for club in self.clubs.values():
            write_private(club.proxy_conf, NGINX_PROXY.format(mcp_port=club.port, club=club.id))
            blocks.append(
                NGINX_CLUB.format(
                    secret=club.secret,
                    club=club.id,
                    proxy_conf=club.proxy_conf,
                    ui_port=UI_PORT,
                    report_secret=self.report_secret,
                )
            )
        write_private(
            NGINX_CONF,
            NGINX_TEMPLATE.format(public_port=PUBLIC_PORT, locations="".join(blocks), report_location=self._report_location()),
        )

    def start_nginx(self) -> None:
        self.write_nginx_conf()
        self.nginx = subprocess.Popen(["nginx", "-c", str(NGINX_CONF), "-g", "daemon off;"])
        log.info("nginx listening on port %s", PUBLIC_PORT)

    def reload_nginx(self) -> None:
        self.write_nginx_conf()
        if self.nginx and self.nginx.poll() is None:
            subprocess.run(["nginx", "-c", str(NGINX_CONF), "-s", "reload"], check=False)

    # all servers ---------------------------------------------------------------
    def start_all(self) -> None:
        for club in list(self.clubs.values()):
            club.start_mcp()

    def supervise(self) -> None:
        while not self.stopping:
            time.sleep(5)
            with self.lock:
                if self.stopping:
                    return
                if self.nginx and self.nginx.poll() is not None:
                    log.error("nginx exited (%s), restarting", self.nginx.returncode)
                    self.start_nginx()
            for club in list(self.clubs.values()):
                delay = club.supervise_tick()
                if delay and not self.stopping:
                    threading.Timer(delay, club.start_mcp).start()

    def shutdown(self) -> None:
        self.stopping = True
        for club in list(self.clubs.values()):
            club.stop_mcp()
        if self.nginx and self.nginx.poll() is None:
            self.nginx.terminate()
