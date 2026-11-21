# Konzertmeister MCP – Home Assistant app

[English](#english) · [Deutsch](#deutsch)

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmw-hbg%2Fha-konzertmeister-mcp)
[![Test](https://github.com/mw-hbg/ha-konzertmeister-mcp/actions/workflows/build.yaml/badge.svg)](https://github.com/mw-hbg/ha-konzertmeister-mcp/actions/workflows/build.yaml)
[![Release](https://img.shields.io/github/v/release/mw-hbg/ha-konzertmeister-mcp?label=release)](https://github.com/mw-hbg/ha-konzertmeister-mcp/releases)
![Stage: experimental](https://img.shields.io/badge/stage-experimental-orange)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-mwhbg-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/mwhbg)

## English

Let AI assistants such as **Claude** work with the
[Konzertmeister](https://konzertmeister.app) of your music association – upcoming
rehearsals and concerts, who replied yes or no, who was really there – and, if you allow
it, create appointments from your Konzertmeister templates. The app runs an
[MCP](https://modelcontextprotocol.io) server inside your Home Assistant and uses only the
**official Konzertmeister API** with the API key of your association – no passwords, no
unofficial interfaces, no additional service in between.

* 9 tools: appointments, replies, attendance, templates, appointment types, member list,
  create appointments from templates, add and change members.
* **Read only by default** (and without the member list). You decide per association what
  the AI may do – the server enforces it, not the AI.
* **Personal data stays off** until you share it: e-mail, mobile phone, address and custom
  member fields are separate checkboxes. Appointments, replies and attendance can be
  limited to some groups (e.g. only the youth band).
* Several associations (up to 10) – each with its own API key, connector URL, settings
  and an on/off switch in Home Assistant.
* Security first: no access to the Home Assistant API, AppArmor profile, every
  internet-facing server runs as its own unprivileged user.
* English and German; more languages can be added without code.

> **Unofficial** – not affiliated with or endorsed by KM Konzertmeister GmbH.
> **Experimental** until version 1.0: version 0.1 is fully tested with a simulated
> Konzertmeister API; tests against the real API and in everyday use are still ahead.

**Installation:** click the button above or add
`https://github.com/mw-hbg/ha-konzertmeister-mcp` under *Settings → Apps → Install app →
⋮ → Repositories*, then install **Konzertmeister MCP**. You need the API key of your
association, which only a leader of the association can create in Konzertmeister. Step
by step: [app README](konzertmeister_mcp/README.md) · full documentation:
[DOCS.md](konzertmeister_mcp/DOCS.md) (also in the app's *Documentation* tab).

### Support

Everything I build is free and stays free. If this project is useful to you, you're welcome to buy me a coffee – entirely voluntary, nothing in return, just a thank-you that keeps me motivated. ☕ Note: payments to a private person are not tax-deductible donations.

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy_me_a_coffee-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/mwhbg)

**Help:** [issues](https://github.com/mw-hbg/ha-konzertmeister-mcp/issues) · security
problems please privately, see [SECURITY.md](SECURITY.md) ·
[changelog](konzertmeister_mcp/CHANGELOG.md) · more projects:
[github.com/mw-hbg](https://github.com/mw-hbg)

## Deutsch

KI-Assistenten wie **Claude** arbeiten mit dem
[Konzertmeister](https://konzertmeister.app) deines Musikvereins – kommende Proben und
Konzerte, wer zu- oder abgesagt hat, wer wirklich da war – und legen, wenn du es
erlaubst, Termine aus euren Konzertmeister-Vorlagen an. Die App betreibt einen
[MCP](https://modelcontextprotocol.io)-Server in deinem Home Assistant und nutzt nur die
**offizielle Konzertmeister-API** mit dem API-Schlüssel deines Vereins – keine
Passwörter, keine inoffiziellen Schnittstellen, kein Dienst dazwischen.

* 9 Tools: Termine, Rückmeldungen, Anwesenheit, Vorlagen, Termintypen, Mitgliederliste,
  Termine aus Vorlagen anlegen, Mitglieder hinzufügen und ändern.
* **Standardmäßig nur lesen** (und ohne Mitgliederliste). Du bestimmst pro Verein, was die
  KI darf – der Server setzt es durch, nicht die KI.
* **Persönliche Daten bleiben aus**, bis du sie freigibst: E-Mail, Handynummer, Adresse
  und eigene Mitgliedsfelder sind eigene Häkchen. Termine, Rückmeldungen und Anwesenheit
  lassen sich auf einzelne Gruppen beschränken (z. B. nur die Jugendkapelle).
* Mehrere Vereine (bis zu 10) – jeder mit eigenem API-Schlüssel, eigener Connector-URL,
  eigenen Einstellungen und einem Ein/Aus-Schalter in Home Assistant.
* Sicherheit zuerst: kein Zugriff auf die Home-Assistant-API, AppArmor-Profil, jeder aus
  dem Internet erreichbare Server läuft als eigener eingeschränkter Benutzer.
* Deutsch und Englisch; weitere Sprachen ohne Code ergänzbar.

> **Inoffiziell** – keine Verbindung zur KM Konzertmeister GmbH und nicht von ihr
> unterstützt. **Experimentell** bis Version 1.0: Version 0.1 ist mit einer nachgebildeten
> Konzertmeister-API durchgetestet; Tests mit der echten API und im Alltag stehen noch aus.

**Installation:** Knopf oben anklicken oder unter *Einstellungen → Apps → App
installieren → ⋮ → Repositories* `https://github.com/mw-hbg/ha-konzertmeister-mcp`
eintragen, dann **Konzertmeister MCP** installieren. Du brauchst den API-Schlüssel deines
Vereins, den nur ein Leiter des Vereins in Konzertmeister anlegen kann. Schritt für
Schritt: [App-README](konzertmeister_mcp/README.md#deutsch) · ausführliche Anleitung:
[DOCS.md](konzertmeister_mcp/DOCS.md#deutsch) (auch im Reiter *Dokumentation* der App).

### Unterstützen

Alles, was ich baue, ist kostenlos und bleibt es auch. Wenn dir dieses Projekt nützt, kannst du mir gern einen Kaffee ausgeben – völlig freiwillig und ohne Gegenleistung, einfach als Dankeschön, das motiviert. ☕ Hinweis: Zahlungen an eine Privatperson sind keine steuerlich absetzbaren Spenden.

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Kaffee_ausgeben-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/mwhbg)

**Hilfe:** [Issues](https://github.com/mw-hbg/ha-konzertmeister-mcp/issues) ·
Sicherheitsprobleme bitte vertraulich, siehe [SECURITY.md](SECURITY.md) ·
[Changelog](konzertmeister_mcp/CHANGELOG.md) · weitere Projekte:
[github.com/mw-hbg](https://github.com/mw-hbg)

## License / Lizenz

[MIT](LICENSE). Free of charge and without warranty / kostenlos und ohne Gewähr.
Bundled software / enthaltene Software: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
"Konzertmeister" is a trademark of KM Konzertmeister GmbH, used here only to describe
compatibility / „Konzertmeister“ ist eine Marke der KM Konzertmeister GmbH und wird hier
nur zur Beschreibung der Kompatibilität genannt.
