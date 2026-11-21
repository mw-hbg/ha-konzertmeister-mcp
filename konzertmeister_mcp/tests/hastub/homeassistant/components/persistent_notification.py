CREATED = []


def async_create(hass, message, title=None, notification_id=None):
    CREATED.append({"message": message, "title": title, "notification_id": notification_id})
