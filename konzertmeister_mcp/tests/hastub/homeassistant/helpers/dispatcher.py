"""Just enough of Home Assistant's dispatcher for the tests."""

LISTENERS: dict[str, list] = {}


def async_dispatcher_connect(hass, signal, target):
    LISTENERS.setdefault(signal, []).append(target)

    def remove():
        if target in LISTENERS.get(signal, []):
            LISTENERS[signal].remove(target)

    return remove


def async_dispatcher_send(hass, signal, *args):
    for target in list(LISTENERS.get(signal, [])):
        target(*args)
