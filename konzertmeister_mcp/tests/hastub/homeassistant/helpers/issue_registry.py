import enum

ISSUES = {}


class IssueSeverity(enum.Enum):
    WARNING = "warning"


def async_create_issue(hass, domain, issue_id, **kwargs):
    ISSUES[(domain, issue_id)] = kwargs


def async_delete_issue(hass, domain, issue_id):
    ISSUES.pop((domain, issue_id), None)
