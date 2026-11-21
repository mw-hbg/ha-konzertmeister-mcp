"""Remove this helper integration once its app has been uninstalled.

When the app is uninstalled, the Supervisor withdraws its discovery
announcement and Home Assistant removes the config entry by itself (then
async_remove_entry runs). The files in custom_components stay, though, and if
Home Assistant was off during the uninstall the entry stays too. So the
integration also checks every 10 minutes whether the app is still installed
(asked from the Supervisor). Only when the Supervisor answers and the app is
missing from the list of installed apps in two checks in a row, it

* removes its config entry (the webhook stops existing immediately),
* deletes its own folder custom_components/konzertmeister_mcp_webhook,
* shows a notification that nothing else needs to be done.

If the Supervisor cannot be asked (not a Supervisor installation, an error, an
older app version that does not tell its slug), nothing is removed.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, ISSUE_RESTART

_LOGGER = logging.getLogger(__name__)

CHECK_INTERVAL = timedelta(minutes=10)
CONFIRMATIONS = 2
_INTEGRATION_DIR = Path(__file__).resolve().parent


async def async_installed_apps(hass: HomeAssistant) -> set[str] | None:
    """Slugs of all installed apps, or None if the Supervisor cannot be asked."""
    try:
        from homeassistant.components.hassio import get_supervisor_client
        from homeassistant.helpers.hassio import is_hassio
    except ImportError:
        return None
    try:
        if not is_hassio(hass):
            return None
        client = get_supervisor_client(hass)
        # Home Assistant's Supervisor client still uses the old technical name here.
        apps_client = getattr(client, "apps", None) or client.addons
        apps = await apps_client.list()
    except Exception as err:  # noqa: BLE001 - never remove anything on errors
        _LOGGER.debug("Could not ask the Supervisor for installed apps: %s", err)
        return None
    return {str(getattr(app, "slug", "")) for app in apps}


def _removal_text(language: str | None) -> tuple[str, str]:
    """Notification text in the Home Assistant language (English fallback)."""
    texts = {}
    for code in ("en", (language or "en").split("-")[0].lower()):
        try:
            data = json.loads((_INTEGRATION_DIR / "translations" / f"{code}.json").read_text(encoding="utf-8"))
            texts.update(data.get("removal", {}))
        except (OSError, ValueError):
            pass
    return (
        texts.get("title", "Konzertmeister MCP"),
        texts.get("message", "The Konzertmeister MCP app was uninstalled. Its helper integration removed itself."),
    )


def _delete_files() -> None:
    # Safety net: only ever delete our own folder inside custom_components.
    if _INTEGRATION_DIR.name == DOMAIN and _INTEGRATION_DIR.parent.name == "custom_components":
        shutil.rmtree(_INTEGRATION_DIR, ignore_errors=True)


async def async_delete_files(hass: HomeAssistant) -> None:
    """Delete the integration's files and tell the user (entry already removed)."""
    from homeassistant.components import persistent_notification

    title, message = await hass.async_add_executor_job(_removal_text, hass.config.language)
    _LOGGER.warning("The Konzertmeister MCP app is no longer installed – removing its helper integration")
    ir.async_delete_issue(hass, DOMAIN, ISSUE_RESTART)
    await hass.async_add_executor_job(_delete_files)
    persistent_notification.async_create(hass, message, title=title, notification_id=f"{DOMAIN}_removed")


async def async_app_gone(hass: HomeAssistant, app_slug: str | None) -> bool:
    """True only if the Supervisor answered and the app is not installed."""
    if not app_slug:
        return False
    installed = await async_installed_apps(hass)
    return installed is not None and app_slug not in installed


async def async_remove_everything(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Removing the entry runs async_remove_entry, which deletes the files.
    await hass.config_entries.async_remove(entry.entry_id)


def async_watch_app(hass: HomeAssistant, entry: ConfigEntry, app_slug: str | None) -> None:
    """Start the periodic check (does nothing if the app did not tell its slug)."""
    if not app_slug:
        return
    missing = 0

    async def _check(_now=None) -> None:
        nonlocal missing
        installed = await async_installed_apps(hass)
        if installed is None or app_slug in installed:
            missing = 0
            return
        missing += 1
        if missing >= CONFIRMATIONS:
            await async_remove_everything(hass, entry)

    entry.async_on_unload(async_track_time_interval(hass, _check, CHECK_INTERVAL))
    hass.async_create_task(_check())
