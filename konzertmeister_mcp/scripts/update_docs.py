"""Regenerate the tool tables in DOCS.md from the code.

DOCS.md holds every language in one file (Home Assistant shows only DOCS.md):
a section "## English", "## Deutsch", … each with its own table between
<!-- tools:<lang>:start --> and <!-- tools:<lang>:end -->.

Run after a tool or translation change (in the app folder):
    python scripts/update_docs.py
The tests fail if a table is out of date.
"""

import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "rootfs" / "app"))

import settings as km_settings  # noqa: E402
import i18n  # noqa: E402

DOCS = APP / "DOCS.md"
HEAD = {
    "en": "| Tool | What it does | Kind | Needs |",
    "de": "| Tool | Was es tut | Art | Voraussetzung |",
}
NEEDS = {
    "en": {"list_members": "off by default", "create_appointment": "off by default; templates + creator e-mail", "add_member": "off by default", "update_member": "off by default"},
    "de": {"list_members": "ab Werk aus", "create_appointment": "ab Werk aus; Vorlagen + Ersteller-E-Mail", "add_member": "ab Werk aus", "update_member": "ab Werk aus"},
}


def markers(lang: str) -> tuple[str, str]:
    return f"<!-- tools:{lang}:start -->", f"<!-- tools:{lang}:end -->"


def table(lang: str) -> str:
    t = i18n.ui(lang)
    rows = [HEAD.get(lang, HEAD["en"]), "|---|---|---|---|"]
    for name, kind in km_settings.TOOLS.items():
        desc = i18n.tool(lang, name).replace("|", "\\|")
        need = NEEDS.get(lang, NEEDS["en"]).get(name, "–")
        rows.append(f'| `{name}` | {desc} | {t["kind_" + kind]} | {need} |')
    return "\n".join(rows)


def render(text: str) -> str:
    languages = [lang for lang in i18n.LANGUAGES if markers(lang)[0] in text]
    if "en" not in languages:
        raise SystemExit("DOCS.md: markers <!-- tools:en:start --> / <!-- tools:en:end --> missing")
    for lang in languages:
        start, end = markers(lang)
        pattern = re.compile(re.escape(start) + ".*?" + re.escape(end), re.S)
        if not pattern.search(text):
            raise SystemExit(f"DOCS.md: {end} missing")
        block = f"{start}\n{table(lang)}\n{end}"
        text = pattern.sub(lambda _m, block=block: block, text)
    return text


def main() -> None:
    old = DOCS.read_text(encoding="utf-8")
    new = render(old)
    if new != old:
        DOCS.write_text(new, encoding="utf-8")
        print("updated", DOCS)


if __name__ == "__main__":
    main()
