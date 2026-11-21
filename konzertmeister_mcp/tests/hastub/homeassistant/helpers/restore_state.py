class _State:
    def __init__(self, state):
        self.state = state


# Tests set this to the state Home Assistant "remembers" (None = no state).
LAST_STATE = {"value": None}


class RestoreEntity:
    async def async_added_to_hass(self):
        pass

    async def async_get_last_state(self):
        value = LAST_STATE["value"]
        return None if value is None else _State(value)
