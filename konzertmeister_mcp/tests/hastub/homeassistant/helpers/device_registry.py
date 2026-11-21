from enum import Enum


class DeviceEntryType(Enum):
    SERVICE = "service"


def DeviceInfo(**kwargs):  # noqa: N802 - TypedDict / dataclass in Home Assistant
    return dict(kwargs)


class _Device:
    def __init__(self, device_id, identifiers, config_entry_id, name=None):
        self.id = device_id
        self.name = name
        self.identifiers = set(identifiers)
        self.config_entries = {config_entry_id}


class _Registry:
    """Devices by config entry; tests add devices and check removals."""

    def __init__(self):
        self.devices = {}
        self.removed = []
        self.counter = 0

    def add(self, config_entry_id, identifiers, name=None):
        self.counter += 1
        device = _Device(f"d{self.counter}", identifiers, config_entry_id, name)
        self.devices[device.id] = device
        return device

    def async_get_device(self, identifiers):
        return next((d for d in self.devices.values() if d.identifiers & set(identifiers)), None)

    def async_update_device(self, device_id, *, remove_config_entry_id=None, name=None, **_kwargs):
        device = self.devices[device_id]
        if name is not None:
            device.name = name
        if remove_config_entry_id:
            device.config_entries.discard(remove_config_entry_id)
            self.removed.append(device_id)
            if not device.config_entries:
                self.devices.pop(device_id)
        return device


REGISTRY = _Registry()


def async_get(hass):
    return REGISTRY


def async_entries_for_config_entry(registry, config_entry_id):
    return [d for d in registry.devices.values() if config_entry_id in d.config_entries]
