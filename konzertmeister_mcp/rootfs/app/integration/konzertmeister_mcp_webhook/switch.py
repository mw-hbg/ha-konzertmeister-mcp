"""One switch per association: "Konzertmeister MCP <name> Server".

Off means: the association's webhook answers every MCP request itself with
"switched off" (nothing reaches the app), and the app stops that association's
server until the switch is turned on again. The state survives
restarts of Home Assistant and of the app.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import device_identifier, device_name
from .const import DOMAIN, SIGNAL_NEW_CLUBS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    clubs = hass.data[DOMAIN][entry.entry_id]["clubs"]
    async_add_entities([McpServerSwitch(hass, entry, club_id) for club_id in clubs])

    def _added(club_ids: list[str]) -> None:
        """Associations added in the app while the entry stays loaded."""
        async_add_entities([McpServerSwitch(hass, entry, club_id) for club_id in club_ids])

    entry.async_on_unload(async_dispatcher_connect(hass, f"{SIGNAL_NEW_CLUBS}_{entry.entry_id}", _added))


class McpServerSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "mcp_server"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, club_id: str) -> None:
        self.hass = hass
        self._entry = entry
        self._club_id = club_id
        name = self._club.get("name") or ""
        self._attr_unique_id = f"{entry.entry_id}_{club_id}_mcp_server"
        self._attr_device_info = DeviceInfo(
            identifiers={device_identifier(entry, club_id)},
            name=device_name(name),
            manufacturer="mw-hbg",
            model="Konzertmeister association",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _runtime(self) -> dict:
        return self.hass.data[DOMAIN][self._entry.entry_id]

    @property
    def _club(self) -> dict:
        # Removed in the app: Home Assistant removes this entity with its device.
        return self._runtime["clubs"].get(self._club_id) or {"enabled": False}

    @property
    def is_on(self) -> bool:
        return bool(self._club["enabled"])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        # On by default; only an explicit "off" is restored.
        self._club["enabled"] = not (last is not None and last.state == "off")

    async def _set(self, enabled: bool) -> None:
        self._club["enabled"] = enabled
        self.async_write_ha_state()
        # Tell the app right away (it stops or starts this association's server).
        await self._runtime["report"]()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
