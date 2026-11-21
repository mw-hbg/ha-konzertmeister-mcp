"""Repair flow: restart Home Assistant after the app updated this integration."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


class RestartRequiredFlow(RepairsFlow):
    """Confirm and restart Home Assistant (like HACS does after updates)."""

    async def async_step_init(self, user_input=None) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            await self.hass.services.async_call("homeassistant", "restart")
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow:
    return RestartRequiredFlow()
