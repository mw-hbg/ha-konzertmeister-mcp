INSTALLED = None  # set by tests: list of slugs, or an Exception to raise


class _App:
    def __init__(self, slug):
        self.slug = slug


class _Apps:
    async def list(self):
        if isinstance(INSTALLED, Exception):
            raise INSTALLED
        return [_App(s) for s in INSTALLED]


class _Client:
    addons = _Apps()



def get_supervisor_client(hass):
    return _Client()
