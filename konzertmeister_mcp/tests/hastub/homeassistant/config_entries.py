SOURCE_HASSIO = "hassio"


class ConfigEntry:
    def __init__(self, entry_id="test", data=None, source=SOURCE_HASSIO, unique_id=None, domain="konzertmeister_mcp_webhook"):
        self.entry_id = entry_id
        self.data = dict(data or {})
        self.source = source
        self.unique_id = unique_id
        self.domain = domain
        self.unloads = []
        self.update_listeners = []

    def async_on_unload(self, func):
        self.unloads.append(func)

    def add_update_listener(self, listener):
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)


class _Abort(Exception):
    def __init__(self, reason):
        self.reason = reason


class ConfigFlow:
    """Just enough of Home Assistant's ConfigFlow for the tests."""

    def __init_subclass__(cls, **kwargs):
        cls.domain = kwargs.get("domain")

    def __init__(self):
        self.hass = None
        self.unique_id = None
        self.reloaded = []

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _async_current_entries(self, include_ignore=True):
        return list(self.hass.config_entries.entries)

    def _abort_if_unique_id_configured(self, updates=None, reload_on_update=True):
        for entry in self.hass.config_entries.entries:
            if entry.unique_id == self.unique_id:
                if updates is not None and entry.data != updates:
                    # like Home Assistant: update listeners run on every change
                    self.hass.config_entries.async_update_entry(entry, data=updates)
                    if reload_on_update:
                        self.hass.config_entries.reloaded.append(entry.entry_id)
                raise _Abort("already_configured")

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, title, data):
        entry = ConfigEntry(f"e{len(self.hass.config_entries.entries) + 1}", data, unique_id=self.unique_id)
        self.hass.config_entries.entries.append(entry)
        return {"type": "create_entry", "title": title, "data": data}


async def run_flow_step(flow, step, *args):
    """Run a step like Home Assistant does (aborts raised inside become results)."""
    try:
        return await getattr(flow, step)(*args)
    except _Abort as err:
        return {"type": "abort", "reason": err.reason}


ConfigFlowResult = dict
