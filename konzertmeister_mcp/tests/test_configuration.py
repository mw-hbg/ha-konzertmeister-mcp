"""App configuration, translations and security-relevant files stay consistent."""

import json
import re
from pathlib import Path

import yaml

import common
import i18n
import settings as km_settings

APP_DIR = Path(__file__).resolve().parent.parent
CODE = APP_DIR / "rootfs" / "app"
CONFIG = yaml.safe_load((APP_DIR / "config.yaml").read_text())


def test_options_match_defaults_schema_and_translations():
    assert CONFIG["options"] == common.DEFAULT_OPTIONS
    assert set(CONFIG["schema"]) == set(CONFIG["options"])
    for lang in ("en", "de"):
        texts = yaml.safe_load((APP_DIR / "translations" / f"{lang}.yaml").read_text())
        assert set(texts["configuration"]) == set(CONFIG["options"]), lang
        assert set(texts["network"]) == set(CONFIG["ports"]), lang


def test_no_wide_access():
    for key in ("homeassistant_api", "hassio_api", "auth_api", "host_network", "privileged", "full_access", "docker_api"):
        assert not CONFIG.get(key), key
    assert CONFIG["map"] == [{"type": "homeassistant_config", "read_only": False, "path": "/homeassistant"}]
    assert CONFIG["discovery"] == [common.WEBHOOK_DOMAIN]
    assert CONFIG["stage"] == "experimental"


def test_apparmor_limits_the_config_folder_to_the_helper_integration():
    profile = (APP_DIR / "apparmor.txt").read_text()
    assert "profile konzertmeister_mcp " in profile
    rules = [line.strip() for line in profile.splitlines() if line.strip().startswith("/homeassistant")]
    assert rules == [
        "/homeassistant/ r,",
        "/homeassistant/custom_components/ rw,",
        "/homeassistant/custom_components/konzertmeister_mcp_webhook/ rw,",
        "/homeassistant/custom_components/konzertmeister_mcp_webhook/** rwl,",
    ]
    assert "deny ptrace," in profile


def test_every_used_text_exists_in_every_language():
    used = set()
    for name in ("web.py", "remote.py", "clubs.py"):
        source = (CODE / name).read_text()
        used |= set(re.findall(r'\bt\["([a-z_]+)"\]', source))
        used |= {f"detail_{k}" for k in re.findall(r'"@([a-z_]+)', source)}
        used |= set(re.findall(r'ClubError\("([a-z_]+)"', source))
        used |= set(re.findall(r'key="([a-z_]+)"', source))
        used |= set(re.findall(r'"((?:err|ok)_[a-z_]+)"', source))
    used |= {f"state_{s}" for s in ("ready", "pending", "stopped", "no_key", "failed", "off")}
    used |= {f"remote_{s}" for s in ("setting_up", "restart_needed", "active", "error", "disabled")}
    used |= {f"kind_{k}" for k in ("read", "create", "change")}
    used |= {f"share_{k}" for k in km_settings.SHARE_KEYS}
    used |= {f"public_url_{k}" for k in ("http", "invalid")}
    used |= {"test_km", "test_server", "test_public", "copy"}
    for lang in ("en", "de"):
        data = json.loads((CODE / "i18n" / f"{lang}.json").read_text())
        missing = used - set(data["ui"])
        assert not missing, (lang, sorted(missing))
        assert set(data["tools"]) == set(km_settings.ALL_TOOLS), lang


def test_translations_have_the_same_keys_and_placeholders():
    en = json.loads((CODE / "i18n" / "en.json").read_text())
    de = json.loads((CODE / "i18n" / "de.json").read_text())
    assert set(en["ui"]) == set(de["ui"])
    for key, text in en["ui"].items():
        assert set(re.findall(r"\{\w+\}", text)) == set(re.findall(r"\{\w+\}", de["ui"][key])), key
    assert i18n.pick("de-CH") == "de" and i18n.pick("fr", None) == "en"


def test_tools_and_defaults():
    assert km_settings.DEFAULT_TOOLS == {
        "list_appointments", "get_appointment_replies", "get_appointment_attendance",
        "list_appointment_templates", "list_appointment_types",
    }
    assert km_settings.WRITE_TOOLS == {"create_appointment", "add_member", "update_member"}
    defaults = km_settings.default_settings()
    assert not any(defaults["share"].values()) and defaults["groups"] == []
    import mcp_server

    source = (CODE / "mcp_server.py").read_text()
    for name in km_settings.ALL_TOOLS:
        assert f'@tool("{name}",' in source, name
    assert "explicit confirmation" in " ".join(mcp_server.INSTRUCTIONS.split())


def test_dockerfile_creates_one_user_per_slot_and_pins_packages():
    dockerfile = (APP_DIR / "Dockerfile").read_text()
    assert "for n in 1 2 3 4 5 6 7 8 9 10" in dockerfile and '"km$n"' in dockerfile
    assert common.MAX_CLUBS == 10
    pins = (APP_DIR / "constraints.txt").read_text()
    for package in ("mcp", "httpx", "uvicorn", "starlette", "python-multipart", "tzdata"):
        assert re.search(rf"^{package}==\S+$", pins, re.M), package


def test_integration_version_matches():
    manifest = json.loads((CODE / "integration" / common.WEBHOOK_DOMAIN / "manifest.json").read_text())
    from konzertmeister_mcp_webhook.const import VERSION

    assert manifest["version"] == VERSION


def test_tool_tables_in_docs_are_up_to_date():
    import importlib.util

    spec = importlib.util.spec_from_file_location("update_docs", APP_DIR / "scripts" / "update_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = (APP_DIR / "DOCS.md").read_text(encoding="utf-8")
    assert module.render(text) == text, "run: python scripts/update_docs.py"
