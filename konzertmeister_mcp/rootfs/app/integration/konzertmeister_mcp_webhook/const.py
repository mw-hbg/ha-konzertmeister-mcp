"""Constants for the Konzertmeister MCP remote-access webhook."""

DOMAIN = "konzertmeister_mcp_webhook"
# Must equal "version" in manifest.json (checked by the tests). Raise both
# with every change – the app only replaces the files on a different version.
VERSION = "0.1.0"
PLATFORMS = ["switch"]
TITLE = "Konzertmeister MCP (remote access)"

ISSUE_RESTART = "restart_required"
ISSUE_KEY = "api_key"  # one issue per association: api_key_<id>
MAX_CLUBS = 10
# Dispatcher signal (+ "_<entry id>"): associations added without a reload
SIGNAL_NEW_CLUBS = "konzertmeister_mcp_webhook_new_clubs"
