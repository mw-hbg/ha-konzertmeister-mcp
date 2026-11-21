# Adding a language

[English](#english) · [Deutsch](#deutsch)

## English

The app is fully available in English and German. Another language only needs a few
files – no code changes. English is the reference: whatever a language does not
translate (yet) is shown in English.

Use the two-letter language code (`fr`, `nl`, `es`, …) in every file name. Replace `xx`
below with it.

| # | File | Shown in | How |
|---|---|---|---|
| 1 | `rootfs/app/i18n/xx.json` | App page, tool descriptions on the page | Copy `en.json`, translate the values, keep the keys and placeholders like `{n}` unchanged. Set `"language"` to the name of the language in that language (e.g. `"Français"`). |
| 2 | `translations/xx.yaml` | *Configuration* and *Network* sections of the app in Home Assistant | Copy `translations/en.yaml`, translate `name` and `description`. |
| 3 | `rootfs/app/integration/konzertmeister_mcp_webhook/translations/xx.json` | Repair notices (“restart required”, “API key rejected”), the switch and the notification after uninstalling (helper integration) | Copy `en.json` next to it and translate it. Also raise `version` in `manifest.json` of the integration (and `VERSION` in its `const.py`), so the app installs the new texts (Home Assistant then asks for one restart). |
| 4 | `DOCS.md` *(optional)* | *Documentation* tab of the app and the link on the app page | Home Assistant shows only `DOCS.md`, so all languages are in that one file. Copy the section `## English` to the end, rename the heading (e.g. `## Français`), translate it and rename its table markers to `<!-- tools:xx:start -->` / `<!-- tools:xx:end -->`. Add the language to the links at the top and set `"docs_section"` in `i18n/xx.json` to the heading's anchor (lower case, e.g. `"français"`). Without it the English section is linked. |
| 5 | `README.md` *(optional)* | App store in Home Assistant, GitHub | Same as `DOCS.md`: one more section `## <language>` at the end of the same file and a link at the top. |

Then, in the app folder (`konzertmeister_mcp`):

```sh
python scripts/update_docs.py   # fills the tool table in the documentation
pytest tests                    # checks that every text exists and placeholders match
```

How the language is chosen on the app page: the choice in the footer of the page (kept
in a cookie), otherwise the browser language, otherwise the Home Assistant language,
otherwise English. Repair notices always use the Home Assistant language.

Messages the app sends to the AI (e.g. “no API key saved”) and the tool descriptions the
AI reads stay in English on purpose – AI assistants understand them and answer in the
user's language anyway.

## Deutsch

Die App ist vollständig auf Englisch und Deutsch verfügbar. Eine weitere Sprache braucht
nur ein paar Dateien, keinen Code. Englisch ist die Vorlage: Was (noch) nicht übersetzt
ist, erscheint auf Englisch.

Die Dateien stehen in der Tabelle oben – `xx` durch den zweibuchstabigen Sprachcode
ersetzen (`fr`, `nl`, `es`, …):

1. `rootfs/app/i18n/xx.json` – App-Seite: `en.json` kopieren, Werte übersetzen, Schlüssel
   und Platzhalter wie `{n}` unverändert lassen, `"language"` auf den Namen der Sprache in
   dieser Sprache setzen.
2. `translations/xx.yaml` – Abschnitte *Konfiguration* und *Netzwerk* der App.
3. `rootfs/app/integration/konzertmeister_mcp_webhook/translations/xx.json` –
   Reparatur-Hinweise, Schalter und Benachrichtigung nach dem Deinstallieren; danach
   `version` in `manifest.json` (und `VERSION` in `const.py`) der Integration erhöhen.
4. *(optional)* `DOCS.md` – einen weiteren Abschnitt `## <Sprache>` am Ende derselben Datei
   mit eigenen Markern `<!-- tools:xx:start -->` / `<!-- tools:xx:end -->`, Link oben
   ergänzen und `"docs_section"` in `i18n/xx.json` setzen.
5. *(optional)* `README.md` – ebenso ein weiterer Abschnitt am Ende derselben Datei.

Danach im App-Ordner (`konzertmeister_mcp`) `python scripts/update_docs.py` und
`pytest tests` ausführen.

Meldungen an die KI und die Tool-Beschreibungen, die die KI liest, bleiben absichtlich auf
Englisch – KI-Assistenten verstehen sie und antworten trotzdem in der Sprache des
Benutzers.
