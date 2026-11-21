def is_hassio(hass):
    from homeassistant.components import hassio

    return hassio.INSTALLED is not None
