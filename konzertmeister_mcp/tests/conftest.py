"""Test setup: point the app at temporary folders and make the app code and a
minimal Home Assistant stub importable."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Tests live in the app folder: konzertmeister_mcp/tests
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "rootfs" / "app"

TMP = Path(tempfile.mkdtemp(prefix="konzertmeister-app-test-"))
os.environ["APP_DATA_DIR"] = str(TMP / "data")
os.environ["HA_CONFIG_DIR"] = str(TMP / "homeassistant")
os.environ["ALLOW_ANY_UI_CLIENT"] = "1"
(TMP / "data").mkdir()
(TMP / "homeassistant").mkdir()

sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).resolve().parent / "hastub"))
sys.path.insert(0, str(APP / "integration"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_data():
    """Every test starts with the layout of a fresh install (one association)."""
    data = TMP / "data"
    for name in ("clubs.json", "report_secret", "options.json"):
        (data / name).unlink(missing_ok=True)
    shutil.rmtree(data / "clubs", ignore_errors=True)
    yield
