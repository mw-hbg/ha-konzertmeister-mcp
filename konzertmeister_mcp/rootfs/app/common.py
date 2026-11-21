"""Paths, constants and small helpers shared by the parts of the launcher."""

from __future__ import annotations

import json
import logging
import os
import secrets
import stat
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("konzertmeister_mcp_app")

DATA = Path(os.environ.get("APP_DATA_DIR", "/data"))
OPTIONS_FILE = DATA / "options.json"
REGISTRY_FILE = DATA / "clubs.json"
CLUBS_DIR = DATA / "clubs"
REPORT_SECRET_FILE = DATA / "report_secret"
DISCOVERY_FILE = DATA / "discovery_uuid"

HA_CONFIG = Path(os.environ.get("HA_CONFIG_DIR", "/homeassistant"))
WEBHOOK_DOMAIN = "konzertmeister_mcp_webhook"
COMPONENT_SRC = Path(__file__).resolve().parent / "integration" / WEBHOOK_DOMAIN
COMPONENT_DST = HA_CONFIG / "custom_components" / WEBHOOK_DOMAIN

MCP_PORT = 8000          # first MCP server, loopback only (association n: 8000 + n - 1)
PUBLIC_PORT = 8100       # nginx
UI_PORT = 8099           # Home Assistant ingress
INGRESS_PROXY_IP = "172.30.32.2"
ALLOW_ANY_UI_CLIENT = os.environ.get("ALLOW_ANY_UI_CLIENT") == "1"  # tests only

MCP_USER = "km"          # users km1 … km10 (Dockerfile)
MAX_CLUBS = 10
LOAD_WARNING_FROM = 4    # from this many associations on, the page warns about the load
REPORT_MAX_AGE = 180     # integration reports newer than this: "Home Assistant is connected"

DEFAULT_OPTIONS = {
    "remote_access": "webhook",
    "public_url": "",
    "key_notification": True,
    "log_level": "info",
}


def app_version() -> str:
    return os.environ.get("APP_VERSION", "dev")


def load_options() -> dict:
    options = dict(DEFAULT_OPTIONS)
    try:
        options.update(json.loads(OPTIONS_FILE.read_text()))
    except FileNotFoundError:
        log.warning("No options.json found, using defaults")
    except json.JSONDecodeError as exc:
        log.error("options.json is invalid (%s), using defaults", exc)
    return options


def write_private(path: Path, content: str) -> None:
    """Write atomically, readable by the owner only (no window in which a
    secret sits on disk with default permissions)."""
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def read_private(path: Path, limit: int = 64 * 1024) -> str:
    """Read a regular file without following a symlink (folders of the MCP
    users may contain anything their server put there)."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd) as fh:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        return fh.read(limit)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_or_create(path: Path, make, rotate: bool = False) -> str:
    if not rotate and path.exists():
        value = path.read_text().strip()
        if len(value) >= 24:
            return value
    value = make()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private(path, value)
    return value


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def new_webhook_id() -> str:
    return "konzertmeister_mcp_" + secrets.token_urlsafe(32)


def report_secret() -> str:
    """Key of the status channel and the stand-in server – never one of the
    associations' secret paths (those end up in AI apps)."""
    return read_or_create(REPORT_SECRET_FILE, new_secret)


def normalize_public_url(value) -> tuple[str, str]:
    """(base URL, problem) – problem is "", "http" (works, but AI apps need
    HTTPS) or "invalid". Accepts "example.com" or a copied browser address."""
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return "", "invalid"
    if parts.scheme not in ("http", "https") or not host or " " in raw or parts.username:
        return "", "invalid"
    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc += f":{port}"
    return f"{parts.scheme}://{netloc}", ("http" if parts.scheme == "http" else "")


def mcp_identity(user: str) -> tuple[int, int] | None:
    """(uid, gid) of an MCP server user, or None where it does not exist (tests)."""
    import pwd

    try:
        entry = pwd.getpwnam(user)
    except KeyError:
        return None
    return entry.pw_uid, entry.pw_gid


def allow_passage(folder: Path) -> None:
    """Execute bit only: the MCP users may pass through, but not list the folder."""
    mode = folder.stat().st_mode & 0o777
    if not mode & 0o001:
        os.chmod(folder, mode | 0o001)


def hand_over(folder: Path, identity: tuple[int, int] | None) -> None:
    """Give a private folder (and everything in it) to an MCP user.

    fwalk works on file descriptors and never follows symlinks, so a link the
    server placed in its own folder cannot redirect root's chown."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if identity is None:
        return
    uid, gid = identity
    for _root, dirs, files, dirfd in os.fwalk(folder, follow_symlinks=False):
        for name in [*dirs, *files]:
            os.chown(name, uid, gid, dir_fd=dirfd, follow_symlinks=False)
    os.chown(folder, uid, gid, follow_symlinks=False)
    os.chmod(folder, 0o700)
