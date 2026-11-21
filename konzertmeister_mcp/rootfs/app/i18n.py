"""Translations of the app page and the tool descriptions.

Every language is one file ``i18n/<code>.json`` (e.g. ``de.json``). English
(``en.json``) is the reference: it contains every key, and any key missing in
another language falls back to English. To add a language, copy ``en.json``,
translate the values and keep the keys – nothing else in the code has to change.
See TRANSLATING.md in the app folder.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("konzertmeister_mcp_app")

I18N_DIR = Path(__file__).resolve().parent / "i18n"
DEFAULT = "en"

def _load() -> dict[str, dict]:
    languages: dict[str, dict] = {}
    for path in sorted(I18N_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Translation %s is invalid and was skipped: %s", path.name, exc)
            continue
        languages[path.stem.lower()] = data
    if DEFAULT not in languages:
        raise RuntimeError(f"{I18N_DIR / (DEFAULT + '.json')} is missing")
    base = languages[DEFAULT]
    merged = {}
    for code, data in languages.items():
        merged[code] = {
            "language": data.get("language", code),
            "ui": {**base["ui"], **data.get("ui", {})},
            "tools": {**base.get("tools", {}), **data.get("tools", {})},
        }
    return merged


LANGUAGES = _load()


def supported(code: str | None) -> str | None:
    """Map 'de', 'de-CH', 'de_DE' … to a language we have, or None."""
    if not code:
        return None
    code = code.strip().lower().replace("_", "-")
    if code in LANGUAGES:
        return code
    primary = code.split("-", 1)[0]
    return primary if primary in LANGUAGES else None


def from_accept_language(header: str | None) -> str | None:
    """Best supported language from an Accept-Language header (honours q=)."""
    choices = []
    for pos, part in enumerate((header or "").split(",")):
        piece = part.strip()
        if not piece:
            continue
        code, _, params = piece.partition(";")
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        if q > 0:
            choices.append((-q, pos, code.strip()))
    for _, _, code in sorted(choices):
        if (lang := supported(code)) is not None:
            return lang
    return None


def pick(*candidates: str | None) -> str:
    """First supported language of the candidates, else English."""
    for candidate in candidates:
        if (lang := supported(candidate)) is not None:
            return lang
    return DEFAULT


def ui(lang: str) -> dict:
    return LANGUAGES.get(lang, LANGUAGES[DEFAULT])["ui"]


def tool(lang: str, name: str) -> str:
    return LANGUAGES.get(lang, LANGUAGES[DEFAULT])["tools"].get(name, name)


def names() -> dict[str, str]:
    """{code: native language name} of every available language."""
    return {code: data["language"] for code, data in LANGUAGES.items()}
