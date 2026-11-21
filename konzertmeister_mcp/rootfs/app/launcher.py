"""Konzertmeister MCP – Home Assistant app launcher.

Runs inside the app container:
* one MCP server per association (mcp_server.py, loopback only, each as its
  own unprivileged user),
* nginx in front of them – only requests with an association's secret path
  get through, everything else is a 404,
* the app page behind Home Assistant ingress (web.py),
* remote access through the helper integration (remote.py).

Modules: common (paths, helpers) · clubs (associations, servers, nginx) ·
remote (Home Assistant, connection test) · web (page) · settings (tools and
settings of an association) · mcp_server · km_api · privacy.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

import uvicorn

import web
from common import DATA, UI_PORT, load_options
from remote import RemoteAccess
from clubs import Services

log = logging.getLogger("konzertmeister_mcp_app")


def main() -> None:
    options = load_options()
    level = getattr(logging, str(options.get("log_level", "info")).upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.DEBUG if level == logging.DEBUG else logging.WARNING)
    DATA.mkdir(parents=True, exist_ok=True)

    services = Services()
    services.start_nginx()
    services.start_all()
    threading.Thread(target=services.supervise, name="supervisor", daemon=True).start()
    remote = RemoteAccess(services)
    threading.Thread(target=remote.run, name="remote-access", daemon=True).start()
    web.setup(services, remote)

    def _stop(*_args):
        services.shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    try:
        uvicorn.run(web.app, host="0.0.0.0", port=UI_PORT, log_level="warning", access_log=False, proxy_headers=False)
    finally:
        services.shutdown()


if __name__ == "__main__":
    main()
