class NoURLAvailableError(Exception):
    pass


EXTERNAL = None


def get_url(hass, **kwargs):
    if EXTERNAL is None:
        raise NoURLAvailableError
    return EXTERNAL
