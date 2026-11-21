# Konzertmeister MCP – Home Assistant app
FROM python:3.12-slim

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=amd64

ENV APP_VERSION=${BUILD_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY constraints.txt /tmp/constraints.txt

# Every package in an exactly pinned version (constraints.txt).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends nginx ca-certificates; \
    pip install -c /tmp/constraints.txt mcp httpx uvicorn starlette python-multipart tzdata; \
    rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled /root/.cache /tmp/constraints.txt; \
    python -c "import mcp.server.fastmcp, httpx, zoneinfo; zoneinfo.ZoneInfo('Europe/Berlin')"

# Unprivileged users for the internet-facing MCP servers – one per association
# (km1 … km10, each with a group of its own), so no association can read another
# one's API key. No login shell, no write access to the Home Assistant
# configuration folder.
RUN for n in 1 2 3 4 5 6 7 8 9 10; do \
        useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "km$n"; \
    done

COPY rootfs/ /

LABEL \
    io.hass.name="Konzertmeister MCP" \
    io.hass.description="MCP server for Konzertmeister" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/mw-hbg/ha-konzertmeister-mcp" \
    org.opencontainers.image.licenses="MIT"

# Health check: the Supervisor restarts the app when the web UI stops answering
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/status.json', timeout=4)" || exit 1

WORKDIR /app
CMD ["python3", "-u", "/app/launcher.py"]
