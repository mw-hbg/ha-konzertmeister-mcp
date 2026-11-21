# Konzertmeister MCP – Home Assistant app

[English](#english) · [Deutsch](#deutsch)

## English

Let AI assistants such as **Claude** work with the
[Konzertmeister](https://konzertmeister.app) of your music association: “Which rehearsals
are coming up for the youth band?”, “Who hasn't replied to the summer concert yet?”, “How
many were at last week's rehearsal?” – and, if you allow it, “Create next Friday's
rehearsal from our template.”

The app runs an [MCP](https://modelcontextprotocol.io) server inside your Home Assistant
and talks only to the **official Konzertmeister API**, with the API key of your
association. No passwords, no unofficial interfaces, no additional service in between.

> **Unofficial.** Not affiliated with or endorsed by KM Konzertmeister GmbH.
> “Konzertmeister” is used only to describe compatibility.

> **Experimental** until version 1.0. Version 0.1 is fully tested with a simulated
> Konzertmeister API; tests against the real API and in everyday use are still ahead
> (see *Known limits* in [DOCS.md](DOCS.md#known-limits)). Please report what you notice.

### Features

* **9 tools:** list appointments, replies (yes / no / maybe), attendance, templates and
  appointment types, member list, create an appointment from a template, add and change
  members.
* **Read only by default** – new associations start without the member list and without
  writing. Quick choice on the app page: *Read only*, *Read and create*, *Everything*.
* **Filters in the server**, the AI cannot get around them: names always; e-mail addresses,
  mobile phone numbers, addresses and custom member fields only if ticked; internal links,
  QR codes and payment data never.
* **Groups:** limit appointments, replies and attendance to some groups (e.g. only the
  youth band).
* **Several associations** (up to 10) – each with its own API key, connector URL,
  settings and on/off switch in Home Assistant.
* **No extra remote setup:** reachable through the address you already use for Home
  Assistant (Nabu Casa, Cloudflare Tunnel, reverse proxy …) via a webhook.
* **Connection test**, **repair notice** when Konzertmeister rejects a key, page in
  **English and German**.
* **Security first:** no access to the Home Assistant API, own AppArmor profile, every
  internet-facing server runs as its own unprivileged user.
* Pre-built images for `amd64` and `aarch64` (Raspberry Pi 4/5).

### Installation

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmw-hbg%2Fha-konzertmeister-mcp)

1. *Settings → Apps → Install app → ⋮ → Repositories*, add
   `https://github.com/mw-hbg/ha-konzertmeister-mcp`.
2. Install **Konzertmeister MCP** and start it.
3. **Restart Home Assistant once** (*Settings → System → ⋮ → Restart Home Assistant*).
   There is **no notification** for this first restart – only the app page shows
   **Restart Home Assistant once**.
4. Open **Konzertmeister** in the sidebar. A **leader of the association** creates the API
   key in the Konzertmeister web app: *association details → Edit → section “Public API”*.
   Paste it into **API key of the association** and click **Save key**.
5. Click **Connection test**, then add the **Connector URL for your AI assistant** in your
   AI app (Claude: *Settings → Connectors → Add custom connector*, no sign-in needed).

Requirements: Home Assistant OS or Supervised 2026.2 or newer, reachable from the internet
over HTTPS; the API key of your association; an AI app that supports remote MCP servers
via URL. Made for Claude; other MCP clients (e.g. Mistral Vibe, ChatGPT) should work
like any MCP client.

Full instructions: [DOCS.md](DOCS.md) (also in the app's *Documentation* tab).

### Your data and the association's data

* **What the AI reads goes to your AI provider** (e.g. Anthropic for Claude) and is handled
  under its privacy terms. Clarify with your board that this is allowed (GDPR) – especially
  for minors in youth groups.
* **The member list cannot be limited to groups** – Konzertmeister always returns every
  member of the association. That is why it is off by default.
* **Treat the connector URL like a password.** Anyone who knows it can use the tools of
  that association. If it leaks, click **New URL**.
* **The API key** belongs to the whole association. It is stored only inside the app (and
  in your Home Assistant backups), never shown again and never logged.

Found a vulnerability? Please report it privately – see [SECURITY.md](../SECURITY.md).

### Help and feedback

Problems or ideas: [open an issue](https://github.com/mw-hbg/ha-konzertmeister-mcp/issues).
Please add the result of the **Connection test** and the app log (*Log* tab) – but remove
any connector URL from it first. Never post the API key.

Released under the [MIT License](../LICENSE), free of charge and without warranty.
Changes: [CHANGELOG.md](CHANGELOG.md).

## Deutsch

Lass KI-Assistenten wie **Claude** mit dem [Konzertmeister](https://konzertmeister.app)
deines Musikvereins arbeiten: „Welche Proben stehen für die Jugendkapelle an?“, „Wer hat
sich zum Sommerkonzert noch nicht zurückgemeldet?“, „Wie viele waren letzte Woche in der
Probe?“ – und, wenn du es erlaubst: „Leg die Probe am nächsten Freitag aus unserer Vorlage
an.“

Die App betreibt einen [MCP](https://modelcontextprotocol.io)-Server in deinem Home
Assistant und spricht nur mit der **offiziellen Konzertmeister-API**, mit dem
API-Schlüssel deines Vereins. Keine Passwörter, keine inoffiziellen Schnittstellen, kein
Dienst dazwischen.

> **Inoffiziell.** Keine Verbindung zur KM Konzertmeister GmbH und nicht von ihr
> unterstützt. „Konzertmeister“ wird nur genannt, um die Kompatibilität zu beschreiben.

> **Experimentell** bis Version 1.0. Version 0.1 ist mit einer nachgebildeten
> Konzertmeister-API durchgetestet; Tests mit der echten API und im Alltag stehen noch aus
> (siehe *Bekannte Grenzen* in [DOCS.md](DOCS.md#bekannte-grenzen)). Bitte melde, was dir
> auffällt.

### Funktionen

* **9 Tools:** Termine auflisten, Rückmeldungen (Ja / Nein / Vielleicht), Anwesenheit,
  Vorlagen und Termintypen, Mitgliederliste, Termin aus einer Vorlage anlegen, Mitglieder
  hinzufügen und ändern.
* **Standardmäßig nur lesen** – neue Vereine starten ohne Mitgliederliste und ohne
  Schreiben. Schnellauswahl auf der App-Seite: *Nur lesen*, *Lesen und anlegen*, *Alles*.
* **Filter im Server**, die KI kann sie nicht umgehen: Namen immer; E-Mail-Adressen,
  Handynummern, Adressen und eigene Mitgliedsfelder nur, wenn angehakt; interne Links,
  QR-Codes und Zahlungsdaten nie.
* **Gruppen:** Termine, Rückmeldungen und Anwesenheit auf einzelne Gruppen beschränken
  (z. B. nur die Jugendkapelle).
* **Mehrere Vereine** (bis zu 10) – jeder mit eigenem API-Schlüssel, eigener
  Connector-URL, eigenen Einstellungen und Ein/Aus-Schalter in Home Assistant.
* **Kein zusätzlicher Fernzugriff nötig:** erreichbar über die Adresse, die du für Home
  Assistant schon nutzt (Nabu Casa, Cloudflare-Tunnel, Reverse Proxy …), per Webhook.
* **Verbindungstest**, **Reparatur-Hinweis**, wenn Konzertmeister einen Schlüssel ablehnt,
  Seite auf **Deutsch und Englisch**.
* **Sicherheit zuerst:** kein Zugriff auf die Home-Assistant-API, eigenes AppArmor-Profil,
  jeder aus dem Internet erreichbare Server läuft als eigener eingeschränkter Benutzer.
* Fertige Images für `amd64` und `aarch64` (Raspberry Pi 4/5).

### Installation

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmw-hbg%2Fha-konzertmeister-mcp)

1. *Einstellungen → Apps → App installieren → ⋮ → Repositories*, dort
   `https://github.com/mw-hbg/ha-konzertmeister-mcp` eintragen.
2. **Konzertmeister MCP** installieren und starten.
3. **Home Assistant einmal neu starten** (*Einstellungen → System → ⋮ → Home Assistant
   neu starten*). Für diesen ersten Neustart gibt es **keine Benachrichtigung** – nur die
   App-Seite zeigt **Home Assistant einmal neu starten**.
4. In der Seitenleiste **Konzertmeister** öffnen. Ein **Leiter des Vereins** legt den
   API-Schlüssel in der Konzertmeister-Web-App an: *Vereinsdetails → Bearbeiten → Abschnitt
   „Public API“*. Bei **API-Schlüssel des Vereins** einfügen und **Schlüssel speichern**
   klicken.
5. **Verbindungstest** drücken, dann die **Connector-URL für deinen KI-Assistenten** in
   deiner KI-App eintragen (Claude: *Einstellungen → Konnektoren → Benutzerdefinierten
   Konnektor hinzufügen*, keine Anmeldung nötig).

Voraussetzungen: Home Assistant OS oder Supervised ab 2026.2, per HTTPS aus dem Internet
erreichbar; der API-Schlüssel deines Vereins; eine KI-App, die Remote-MCP-Server per URL
unterstützt. Gemacht für Claude; andere MCP-Clients (z. B. Mistral Vibe, ChatGPT) sollten
wie jeder MCP-Client funktionieren.

Ausführliche Anleitung: [DOCS.md](DOCS.md#deutsch) (auch im Reiter *Dokumentation* der
App; der deutsche Teil steht dort nach dem englischen).

### Deine Daten und die des Vereins

* **Was die KI liest, geht an deinen KI-Anbieter** (bei Claude z. B. Anthropic) und wird
  nach dessen Datenschutzbedingungen verarbeitet. Kläre mit eurem Vorstand, dass das
  erlaubt ist (DSGVO) – besonders bei Minderjährigen in Jugendgruppen.
* **Die Mitgliederliste lässt sich nicht auf Gruppen beschränken** – Konzertmeister liefert
  immer alle Mitglieder des Vereins. Deshalb ist sie ab Werk aus.
* **Behandle die Connector-URL wie ein Passwort.** Wer sie kennt, kann die Tools dieses
  Vereins nutzen. Ist sie bekannt geworden: **Neue URL**.
* **Der API-Schlüssel** gehört dem ganzen Verein. Er liegt nur in der App (und in deinen
  Home-Assistant-Backups), wird nie wieder angezeigt und nie protokolliert.

Eine Sicherheitslücke gefunden? Bitte vertraulich melden – siehe
[SECURITY.md](../SECURITY.md).

### Hilfe und Rückmeldungen

Probleme oder Ideen: [Issue anlegen](https://github.com/mw-hbg/ha-konzertmeister-mcp/issues).
Bitte das Ergebnis des **Verbindungstests** und das App-Protokoll (Reiter *Protokoll*)
mitschicken – vorher jede Connector-URL daraus entfernen. Den API-Schlüssel nie
veröffentlichen.

Steht unter der [MIT-Lizenz](../LICENSE), kostenlos und ohne Gewähr.
Änderungen: [CHANGELOG.md](CHANGELOG.md).
