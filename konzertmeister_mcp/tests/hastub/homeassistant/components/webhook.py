SUPPORTED_METHODS = ("GET", "HEAD", "POST", "PUT")
REGISTERED = {}


def async_register(hass, domain, name, webhook_id, handler, *, local_only=False, allowed_methods=None):
    # Same check as Home Assistant: unsupported methods raise
    bad = set(allowed_methods or []) - set(SUPPORTED_METHODS)
    if bad:
        raise ValueError(f"Unexpected method: {bad}")
    REGISTERED[webhook_id] = handler


def async_unregister(hass, webhook_id):
    REGISTERED.pop(webhook_id, None)
