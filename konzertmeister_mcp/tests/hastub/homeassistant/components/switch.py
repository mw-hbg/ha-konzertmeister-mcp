class SwitchEntity:
    """Just enough of Home Assistant's SwitchEntity for the tests."""

    hass = None
    written_states = None

    def async_write_ha_state(self):
        if self.written_states is None:
            self.written_states = []
        self.written_states.append("on" if self.is_on else "off")

    async def async_added_to_hass(self):
        pass
