# Konzertmeister MCP

[English](#english) · [Deutsch](#deutsch)

## English

This app runs an [MCP](https://modelcontextprotocol.io) server for
[Konzertmeister](https://konzertmeister.app) – the planning app of many music
associations (rehearsals, concerts, replies of the members, attendance) – inside Home
Assistant. AI assistants that support remote MCP servers can then read the appointments
of your association and, if you allow it, create appointments from templates and add or
change members.

> **Unofficial.** This project is not affiliated with or endorsed by KM Konzertmeister
> GmbH. It uses only the **official Konzertmeister API**
> ([documentation](https://konzertmeister.app/de/help/konzertmeister-api)) with the API key
> of your association – no passwords, no unofficial interfaces.

> **Experimental** until version 1.0. Version 0.1 is fully tested with a simulated
> Konzertmeister API; tests against the real API (with a **Pro** association) and in
> everyday use are still ahead. Whether the API also works with the free Basic plan
> is not documented by Konzertmeister. See [Known limits](#known-limits).

### How it works

```
AI assistant ──HTTPS──► your Home Assistant address ──► /api/webhook/<secret id> ──► app ──► rest.konzertmeister.app
                        (Nabu Casa, Cloudflare Tunnel,   (helper integration)            (API key of the association)
                         reverse proxy …)
```

* By default the app is reached through the address you already use to access Home
  Assistant from outside – **no extra hostname, tunnel or port forwarding**. A small
  helper integration **Konzertmeister MCP (remote access)** (`konzertmeister_mcp_webhook`),
  installed by the app, provides a Home Assistant webhook with a long random id and
  forwards requests to the app.
* Alternatively (`remote_access: direct`) you route your own HTTPS hostname to the app's
  port 8100.
* Every association has its own MCP server. It listens on `127.0.0.1` only; an nginx in
  front of it only forwards requests that carry the long random **secret path** of that
  association – everything else gets a `404`.
* The server talks only to `https://rest.konzertmeister.app` with the API key of the
  association (header `X-KM-ORG-API-KEY`). Answers are cached for 60 seconds.
* The app page (sidebar → **Konzertmeister**) is only reachable through Home Assistant and
  only for administrators.

### Setup

Requires Home Assistant **2026.2** or newer (OS or Supervised) on `amd64` or `aarch64`.

#### 1. Install and start

*Settings → Apps → Install app → ⋮ → Repositories*, add
`https://github.com/mw-hbg/ha-konzertmeister-mcp`. Then install **Konzertmeister MCP**,
start it and open **Konzertmeister** in the sidebar (or **Open Web UI** on the app page).

#### 2. Get the API key of your association

The API key belongs to the **whole association**, not to a person. Only a **leader of the
association** can create it, in the Konzertmeister web app: *association details → Edit →
section “Public API”*.

* The key is **shown only once** – paste it right away into **API key of the
  association** on the app page and click **Save key**.
* Creating a key again **overwrites the old one** – everything that used the old key (also
  this app) stops working until it gets the new one.
* A leader of a sub-group (e.g. the youth band) usually cannot create the key – ask the
  board or a leader of the whole association.

When saving, the app checks the key with Konzertmeister and refuses a key that
Konzertmeister rejects. Afterwards the card shows the name of the association. The key is
stored only in the app's private folder, is **never shown again and never logged**.
**Replace key** and **Delete key** are in the same card.

#### 3. Restart Home Assistant once

On first start the app copies its helper integration into Home Assistant. The app page
then shows **Restart Home Assistant once**: restart via *Settings → System → ⋮ → Restart
Home Assistant*. Home Assistant itself shows **no notification** for this first restart –
the app has no access to its API, and the helper integration only runs after the restart.
After the restart Home Assistant sets the integration up by itself (the app announces its
settings through the Supervisor's discovery service), and about a minute later *Remote
access via Home Assistant* shows **active**. When a later app update brings a new version
of the helper integration, Home Assistant shows a **repair notice** (*Settings → Repairs*)
with a button to restart.

Requirement: Home Assistant must already be reachable from the internet over **HTTPS**
(Nabu Casa, Cloudflare Tunnel, reverse proxy, …). The app learns your external address
from the helper integration. If it cannot work it out, enter it as **Public address** in
the app configuration.

<details>
<summary>Alternative: own hostname (<code>remote_access: direct</code>)</summary>

Set **Remote access** = `direct` on the *Configuration* tab, then route a public **HTTPS**
hostname to port 8100 of the app – the target address is shown on the app page (e.g. with
`additional_hosts` in the Cloudflared app):

```yaml
additional_hosts:
  - hostname: konzertmeister.example.com
    service: http://abcd1234-konzertmeister-mcp:8100
```

Enter that hostname as **Public address**. Never forward port 8100 on your router without
HTTPS. All associations share the port; each has its own secret path.

Best set `direct` before the first start. If you switch later, the app removes its helper
integration from Home Assistant by itself on the next start. Switching back to `webhook`
installs it again and asks for one restart. The connector URLs change when you switch, and
the on/off switches in Home Assistant only exist in webhook mode.
</details>

#### 4. Connect your AI assistant

Click **Connection test** first (see [Connection test](#connection-test)). Then copy the
**Connector URL for your AI assistant** from the card (**Show** / **Copy**). It looks like
`https://home.example.com/api/webhook/konzertmeister_mcp_<secret>` (or
`https://konzertmeister.example.com/<secret>/mcp` in direct mode).

* **Claude** (claude.ai, desktop, mobile): *Settings → Connectors → Add custom connector*,
  paste the URL, no authentication.
* **Other MCP clients** (e.g. Mistral Vibe, ChatGPT with developer mode, Cursor, VS Code):
  add a remote MCP server using the *Streamable HTTP* transport and the URL, without
  authentication. They should work like any MCP client.

The connector URL is the **only secret** – there is no separate sign-in. Treat it like a
password; **New URL** creates a new one (the old one stops working right away).

### What the AI may do

Under **What the AI may do** in the card you tick the tools the AI gets – only ticked tools
exist for the AI. Quick choice: **Read only**, **Read and create**, **Everything**. New
associations start with reading only and **without the member list**. **Save settings**
restarts the server of that association (a few seconds).

Before creating or changing anything, the AI is told to show you what it is about to send
and to wait for your explicit yes – Konzertmeister may notify the members immediately. The
AI still acts with the rights of the API key, so only allow what you need. All tools:
[table at the end](#all-tools).

### What the AI sees

The filters run **in the server** – the AI cannot get around them, whatever it asks for.

* **Names** of members are always shared.
* Under **Member data**: **E-mail addresses**, **Mobile phone numbers**, **Addresses** and
  **Custom member fields** only if ticked – in the member list **and** in replies and
  attendance. All off by default.
* **Never** passed on: internal links, QR codes, payment data and other organisation
  details from Konzertmeister.
* Appointments that are not published have no public link.

> **Data protection:** everything the AI reads goes to the provider of your AI assistant
> (e.g. Anthropic for Claude) and is handled under its privacy terms. Only share what you
> really need and what your association allows (GDPR) – in particular for **minors** in
> youth groups. Clarify it with your board before you start.

### Groups

Under **Groups** you can limit **appointments, replies and attendance** to some groups
(e.g. only the youth band). Nothing ticked = all groups. **Also appointments without a
group (for the whole association)** is on by default.

* The app learns the groups from the upcoming appointments when you save the key, and again
  with **Load groups again** (also reloads the name and the appointment types).
* Replies and attendance are only given for appointments the AI has listed before and that
  are in an allowed group.
* **Limit:** the **member list cannot be limited to groups** – Konzertmeister always returns
  every member of the association. That is why `list_members` is off by default. If you
  only want to share one group, leave it off.

### Creating appointments

The Konzertmeister API can create appointments **only from templates**: place, group,
duration and deadlines come from the template; the AI can set the name, the description and
the start. Under **Creating appointments**:

* **Creator e-mail** – the e-mail address of the Konzertmeister account that appears as
  creator of new appointments (required by Konzertmeister).
* **Templates** – one per line: `name = template id`, e.g. `Rehearsal youth band = 1a2b3c`.
  The name is what the AI uses; the id is the id of the template in Konzertmeister (see the
  Konzertmeister help or ask your Konzertmeister admin – where exactly it is shown is not
  documented yet, see [Known limits](#known-limits)).

If `create_appointment` is ticked but the creator e-mail or the templates are missing, the
card says so. `list_appointment_templates` shows the AI only the names of your templates.

### Appointment types

To list appointments, Konzertmeister needs the **numbers** of the appointment types, but
offers no list of them. Under **Appointment types** enter one per line: `name = number`,
e.g. `Rehearsal = 1`. The section shows the **numbers seen in upcoming appointments** as a
hint. Without entries the numbers 1–10 are asked for.

### Members

* `add_member` – adds a member; the **e-mail address is required**, Konzertmeister then
  invites the person by e-mail.
* `update_member` – changes a member, identified by e-mail; only the values the AI gives
  are changed.

Both are off by default and, like every writing tool, the AI is told to ask you first.

### Several associations

One app can serve up to **10 associations** – e.g. the main band and a partner
association. **Add association** creates a new card. Every association has:

* its own API key and its **own connector URL**,
* its own settings, connection test, **New URL** and **Remove association**,
* its own device and switch in Home Assistant and its own repair notice,
* its own MCP server, running as its own unprivileged user (`km1` … `km10`): no association
  can read another one's key.

**Name:** only from the second association on – a single association needs none. Then by
default the name from Konzertmeister; ✏️ next to it sets your own (**Name of this
association**, only shown on the page and in Home Assistant).

**Load:** every association runs its own server. From four associations on the page warns
that this needs noticeably more memory and CPU – keep an eye on small devices.

The last association cannot be removed – delete its key instead. Every Home Assistant
administrator can open the app page and therefore sees and manages **all** associations,
including their connector URLs.

### Switching the server off

In webhook mode the helper integration adds a device per association with the switch
**Konzertmeister MCP <name> Server** (with a single association: *Konzertmeister MCP
Server*, `switch.konzertmeister_mcp_server`). Turn it off and no AI app can reach that
association any more: Home Assistant answers every MCP request itself with “switched off”,
and the app stops that server. Key, settings and connector URL stay; turn it on again and
everything works within seconds. The state survives restarts. The switch is a normal
entity – use it in automations, dashboards or with voice assistants.

### What the AI gets instead of an error

While there is no key, Konzertmeister rejects the key, the server is starting or it is
switched off, the AI gets a short, clear message (e.g. that a key must be entered on the
app page) instead of a connection error. These messages are in English on purpose – AI
assistants understand them and answer in your language.

### Notifications

Shown by the helper integration as **repair notices** (*Settings → Repairs*), in the Home
Assistant language:

* **Restart required** – after updates of the helper integration (with a restart button).
  After the first installation only the app page shows the hint.
* **API key of <name> rejected** – Konzertmeister rejects a saved key (e.g. because a leader
  deleted or recreated it). Enter the current key on the app page; the notice then
  disappears by itself. Can be switched off with `key_notification`.

### Connection test

**Connection test** in the card checks, one after another:

1. **Konzertmeister accepts the key** – and reloads name, groups and appointment types,
2. **MCP server answers** – and how many tools it offers,
3. **Connector URL reachable from the internet** – the app calls its own public address,
   the way your AI app does.

A block by Cloudflare's bot protection before Home Assistant is shown as a ⚠️ note, not as
an error – AI apps usually still get through.

### Security

* **Treat the connector URL like a password.** Anyone who knows it can use the enabled tools
  of that association. Don't share screenshots or logs that contain it. If it leaks, click
  **New URL**.
* **The app has no access to Home Assistant's API** (no `homeassistant_api`, `hassio_api`,
  `host_network` or `privileged`) – it cannot read, switch or change anything in Home
  Assistant. Its only access is the configuration folder (`homeassistant_config`), used
  solely to copy the helper integration into `custom_components/konzertmeister_mcp_webhook`
  (and remove it again in direct mode). Home Assistant cannot map a single folder; only the
  app's internal part uses it, never the internet-facing MCP servers.
* **AppArmor profile for the whole app:** in the configuration folder it can only write to
  `custom_components/konzertmeister_mcp_webhook`. Home Assistant rates the app 8 of 8 once
  it is installed (the store shows 7 before, because it does not know the profile yet).
* **App page:** only through Home Assistant's ingress (only the ingress proxy may load it),
  with a CSRF token and security headers (`no-store`, `no-referrer`,
  `frame-ancestors 'self'`).
* **MCP servers:** listen on `127.0.0.1` only, behind nginx, which needs the secret path and
  logs nothing (`access_log off`), so the secret never lands in a log. Each server runs as
  its own unprivileged user (`umask 077`, no extra groups); its environment carries no
  Supervisor token or other secrets, and it gets its settings read-only through its
  environment – it cannot change them. Where the Linux kernel offers *Landlock*, it
  additionally locks itself into its own folder. Home Assistant OS currently does not offer
  Landlock – the app log then says *Landlock is not available here*; that is expected, and
  the user rights and the AppArmor profile apply.
* **Helper integration:** its status channel to the app is only accepted from Home
  Assistant's internal network (`172.30.32.0/23`) and with its own key. Nothing in this
  exchange can change Home Assistant.
* **API key:** file with mode `0600` in the app's private folder; never shown again, never
  logged, sent only to Konzertmeister. It is part of Home Assistant backups.
* **Supply chain:** every Python package is pinned to an exact version (`constraints.txt`);
  Dependabot watches the GitHub actions and the base image.
* **Found a vulnerability?** Report it privately via GitHub (*Security → Report a
  vulnerability*), not in a public issue – see
  [SECURITY.md](https://github.com/mw-hbg/ha-konzertmeister-mcp/blob/main/SECURITY.md).

### Configuration

The *Configuration* tab of the app (changes take effect after restarting the app). Tools,
groups, data shares, templates and types are set per association on the app page, not here.

| Option | Description |
|---|---|
| `remote_access` | `webhook` (default) – reachable through your existing Home Assistant address, installs the helper integration, needs one Home Assistant restart. `direct` – you route your own HTTPS hostname to port 8100; switching to it removes the helper integration on the next start. The connector URLs change when switching. |
| `public_url` | Optional, usually empty. Only needed if the app page cannot work out your public address. Webhook: your Home Assistant address, e.g. `https://home.example.com`. Direct: the hostname you routed to the app. Only scheme and host are used; the page warns if it is invalid or uses `http://`. |
| `key_notification` | `true` (default): repair notice in Home Assistant if Konzertmeister rejects the API key of an association. |
| `log_level` | `debug`, `info` (default), `warning`, `error`. Only `debug` also logs every single request of the AI (for troubleshooting). |

### Language

The app page is available in English and German: the choice in the footer of the page,
otherwise your browser language, otherwise the Home Assistant language, otherwise English.
Messages to the AI stay in English on purpose. Adding a language:
[TRANSLATING.md](https://github.com/mw-hbg/ha-konzertmeister-mcp/blob/main/konzertmeister_mcp/TRANSLATING.md).

### Known limits

Version 0.1 is the first release. Honest list of what is still open or not possible:

* **Experimental:** tested with a simulated Konzertmeister API only; tests with the real
  API, other AI clients and the Basic plan are still ahead.
* **Date formats** of the Konzertmeister API (date filters when listing, the start of new
  appointments) still have to be confirmed in real use.
* **Template ids:** where Konzertmeister shows the id of a template is not documented yet.
* **Appointment type numbers** have to be entered by hand – the API offers no list.
* **The member list cannot be limited to groups** (Konzertmeister always returns all
  members).
* **Not in the Konzertmeister API, so not in the app:** messages, files, sheet music,
  absences, and appointments without a template.
* **Rate limits** of the API are unknown; the app caches answers for 60 seconds.

### Troubleshooting

| Problem | Solution |
|---|---|
| *That does not look like an API key* / *Konzertmeister rejected this key* | Copy the complete, current key. If in doubt, a leader creates a new one (this overwrites the old key). |
| State *key rejected* / repair notice *API key … rejected* | The key was deleted or recreated in Konzertmeister. Enter the current key with **Replace key**. |
| *The key could not be checked* | Konzertmeister was not reachable – try again later. |
| Remote access stays *Home Assistant must be restarted once* | Restart Home Assistant. If it stays, check *Settings → System → Logs* for `konzertmeister_mcp_webhook`. |
| Connector URL shows a placeholder | Your public address is unknown – wait until the helper integration runs, or set **Public address**. |
| Connection test: *blocked before Home Assistant* | Cloudflare bot protection – AI apps usually still get through. Otherwise allow `/api/webhook/` in your proxy or WAF. |
| No groups listed | Groups are learned from upcoming appointments – click **Load groups again** once there are some. |
| The AI finds no appointments of a type | Enter the type numbers under **Appointment types** (see the numbers seen in upcoming appointments). |
| The AI says a tool does not exist | It is not ticked under **What the AI may do**. |
| Creating appointments fails | Check the **Creator e-mail** (a Konzertmeister account) and the template ids. |

### Uninstalling

1. Uninstall the app. Home Assistant removes the entry of the helper integration by itself,
   the helper then deletes its folder `custom_components/konzertmeister_mcp_webhook` and
   shows a notification. **No restart is needed.** (If Home Assistant was off during the
   uninstall, this happens within about 20 minutes after the next start.)
2. Remove the connector in your AI app.
3. Optionally delete the API key in Konzertmeister (a leader: *association details → Edit →
   Public API*).

### All tools

*Kind*: **read** = only reads · **create** = adds something new · **change** = changes
something that exists. This table is generated from the code (`scripts/update_docs.py`).

<!-- tools:en:start -->
| Tool | What it does | Kind | Needs |
|---|---|---|---|
| `list_appointments` | List appointments | read | – |
| `get_appointment_replies` | Replies to an appointment (yes / no / maybe) | read | – |
| `get_appointment_attendance` | Attendance of an appointment | read | – |
| `list_appointment_templates` | List appointment templates | read | – |
| `list_appointment_types` | List appointment types | read | – |
| `list_members` | Member list (all groups) | read | off by default |
| `create_appointment` | Create an appointment from a template | create | off by default; templates + creator e-mail |
| `add_member` | Add a member | create | off by default |
| `update_member` | Change a member | change | off by default |
<!-- tools:en:end -->

## Deutsch

Diese App betreibt in Home Assistant einen [MCP](https://modelcontextprotocol.io)-Server
für [Konzertmeister](https://konzertmeister.app) – die Planungs-App vieler Musikvereine
(Proben, Konzerte, Rückmeldungen der Mitglieder, Anwesenheit). KI-Assistenten, die
Remote-MCP-Server unterstützen, können dann die Termine deines Vereins lesen und, wenn du
es erlaubst, Termine aus Vorlagen anlegen sowie Mitglieder hinzufügen oder ändern.

> **Inoffiziell.** Keine Verbindung zur KM Konzertmeister GmbH und nicht von ihr
> unterstützt. Die App nutzt nur die **offizielle Konzertmeister-API**
> ([Dokumentation](https://konzertmeister.app/de/help/konzertmeister-api)) mit dem
> API-Schlüssel deines Vereins – keine Passwörter, keine inoffiziellen Schnittstellen.

> **Experimentell** bis Version 1.0. Version 0.1 ist mit einer nachgebildeten
> Konzertmeister-API durchgetestet; Tests mit der echten API (mit einem **Pro**-Verein) und
> im Alltag stehen noch aus. Ob die API auch mit dem kostenlosen Basic-Tarif
> funktioniert, dokumentiert Konzertmeister nicht. Siehe [Bekannte Grenzen](#bekannte-grenzen).

### So funktioniert es

```
KI-Assistent ──HTTPS──► deine Home-Assistant-Adresse ──► /api/webhook/<geheime ID> ──► App ──► rest.konzertmeister.app
                        (Nabu Casa, Cloudflare-Tunnel,    (Hilfs-Integration)              (API-Schlüssel des Vereins)
                         Reverse Proxy …)
```

* Standardmäßig erreichst du die App über die Adresse, mit der du Home Assistant schon von
  außen nutzt – **kein zusätzlicher Hostname, Tunnel oder Port**. Eine kleine
  Hilfs-Integration **Konzertmeister MCP (remote access)** (`konzertmeister_mcp_webhook`),
  die die App installiert, stellt einen Home-Assistant-Webhook mit langer Zufalls-ID bereit
  und leitet Anfragen an die App weiter.
* Alternativ (`remote_access: direct`) leitest du einen eigenen HTTPS-Hostnamen auf Port
  8100 der App.
* Jeder Verein hat seinen eigenen MCP-Server. Er lauscht nur auf `127.0.0.1`; ein
  vorgeschaltetes nginx leitet nur Anfragen weiter, die den langen zufälligen **geheimen
  Pfad** dieses Vereins enthalten – alles andere bekommt `404`.
* Der Server spricht nur mit `https://rest.konzertmeister.app`, mit dem API-Schlüssel des
  Vereins (Header `X-KM-ORG-API-KEY`). Antworten werden 60 Sekunden zwischengespeichert.
* Die App-Seite (Seitenleiste → **Konzertmeister**) ist nur über Home Assistant und nur für
  Administratoren erreichbar.

### Einrichtung

Voraussetzung: Home Assistant **2026.2** oder neuer (OS oder Supervised) auf `amd64` oder
`aarch64`.

#### 1. Installieren und starten

*Einstellungen → Apps → App installieren → ⋮ → Repositories*, dort
`https://github.com/mw-hbg/ha-konzertmeister-mcp` eintragen. Dann **Konzertmeister MCP**
installieren, starten und in der Seitenleiste **Konzertmeister** öffnen.

#### 2. API-Schlüssel des Vereins besorgen

Der API-Schlüssel gehört dem **ganzen Verein**, nicht einer Person. Nur ein **Leiter des
Vereins** kann ihn anlegen, in der Konzertmeister-Web-App: *Vereinsdetails → Bearbeiten →
Abschnitt „Public API“*.

* Der Schlüssel wird **nur einmal angezeigt** – füge ihn gleich auf der App-Seite bei
  **API-Schlüssel des Vereins** ein und klick auf **Schlüssel speichern**.
* Ein neu erstellter Schlüssel **überschreibt den alten** – alles, was den alten nutzt (auch
  diese App), funktioniert erst wieder mit dem neuen.
* Ein Leiter einer Untergruppe (z. B. der Jugendkapelle) kann den Schlüssel meist nicht
  anlegen – frag den Vorstand oder einen Leiter des ganzen Vereins.

Beim Speichern prüft die App den Schlüssel bei Konzertmeister und lehnt einen Schlüssel ab,
den Konzertmeister nicht akzeptiert. Danach zeigt die Karte den Namen des Vereins. Der
Schlüssel liegt nur im privaten Ordner der App, wird **nie wieder angezeigt und nie
protokolliert**. **Schlüssel ersetzen** und **Schlüssel löschen** findest du in derselben
Karte.

#### 3. Home Assistant einmal neu starten

Beim ersten Start kopiert die App ihre Hilfs-Integration in Home Assistant. Die App-Seite
zeigt dann **Home Assistant einmal neu starten**: Neustart über *Einstellungen → System →
⋮ → Home Assistant neu starten*. Home Assistant selbst zeigt für diesen ersten Neustart
**keine Benachrichtigung** – die App hat keinen Zugriff auf seine API, und die
Hilfs-Integration läuft erst nach dem Neustart. Danach richtet Home Assistant die
Integration selbst ein (die App meldet ihre Einstellungen über den Discovery-Dienst des
Supervisors), und etwa eine Minute später steht bei *Fernzugriff über Home Assistant*
**aktiv**. Bringt ein späteres App-Update eine neue Version der Hilfs-Integration, zeigt
Home Assistant einen **Reparatur-Hinweis** (*Einstellungen → Reparaturen*) mit
Neustart-Knopf.

Voraussetzung: Home Assistant ist bereits per **HTTPS** aus dem Internet erreichbar (Nabu
Casa, Cloudflare-Tunnel, Reverse Proxy, …). Deine externe Adresse erfährt die App von der
Hilfs-Integration. Kann sie sie nicht ermitteln, trag sie in der App-Konfiguration als
**Öffentliche Adresse** ein.

<details>
<summary>Alternative: eigener Hostname (<code>remote_access: direct</code>)</summary>

Im Reiter *Konfiguration* **Fernzugriff** = `direct` setzen, dann einen öffentlichen
**HTTPS**-Hostnamen auf Port 8100 der App leiten – die Zieladresse zeigt die App-Seite
(z. B. mit `additional_hosts` in der Cloudflared-App):

```yaml
additional_hosts:
  - hostname: konzertmeister.example.com
    service: http://abcd1234-konzertmeister-mcp:8100
```

Diesen Hostnamen als **Öffentliche Adresse** eintragen. Port 8100 nie ohne HTTPS am Router
freigeben. Alle Vereine teilen sich den Port; jeder hat seinen eigenen geheimen Pfad.

Am besten `direct` vor dem ersten Start setzen. Wechselst du später, entfernt die App ihre
Hilfs-Integration beim nächsten Start selbst aus Home Assistant. Zurück auf `webhook`
installiert sie wieder und bittet um einen Neustart. Die Connector-URLs ändern sich beim
Wechsel, und die Ein/Aus-Schalter in Home Assistant gibt es nur im Webhook-Modus.
</details>

#### 4. KI-Assistenten verbinden

Zuerst **Verbindungstest** drücken (siehe [Verbindungstest](#verbindungstest)). Dann die
**Connector-URL für deinen KI-Assistenten** aus der Karte kopieren (**Anzeigen** /
**Kopieren**). Sie sieht so aus:
`https://home.example.com/api/webhook/konzertmeister_mcp_<geheim>` (oder
`https://konzertmeister.example.com/<geheim>/mcp` im Direkt-Modus).

* **Claude** (claude.ai, Desktop, Mobil): *Einstellungen → Konnektoren → Benutzerdefinierten
  Konnektor hinzufügen*, URL einfügen, keine Authentifizierung.
* **Andere MCP-Clients** (z. B. Mistral Vibe, ChatGPT im Entwicklermodus, Cursor, VS Code):
  einen Remote-MCP-Server mit dem Transport *Streamable HTTP* und der URL hinzufügen, ohne
  Authentifizierung. Sie sollten wie jeder MCP-Client funktionieren.

Die Connector-URL ist das **einzige Geheimnis** – eine eigene Anmeldung gibt es nicht.
Behandle sie wie ein Passwort; **Neue URL** erzeugt eine neue (die alte funktioniert sofort
nicht mehr).

### Was die KI darf

Unter **Was die KI darf** in der Karte hakst du die Tools an, die die KI bekommt – nur
angehakte Tools gibt es für die KI. Schnellauswahl: **Nur lesen**, **Lesen und anlegen**,
**Alles**. Neue Vereine starten mit „nur lesen“ und **ohne Mitgliederliste**.
**Einstellungen speichern** startet den Server dieses Vereins neu (ein paar Sekunden).

Bevor sie etwas anlegt oder ändert, wird die KI aufgefordert, dir zu zeigen, was sie senden
will, und auf dein ausdrückliches Ja zu warten – Konzertmeister benachrichtigt die
Mitglieder womöglich sofort. Die KI handelt trotzdem mit den Rechten des API-Schlüssels,
erlaube also nur, was du brauchst. Alle Tools: [Tabelle am Ende](#alle-tools).

### Was die KI sieht

Die Filter laufen **im Server** – die KI kann sie nicht umgehen, egal was sie anfragt.

* **Namen** der Mitglieder werden immer weitergegeben.
* Unter **Mitgliederdaten**: **E-Mail-Adressen**, **Handynummern**, **Adressen** und
  **Eigene Mitgliedsfelder** nur, wenn angehakt – in der Mitgliederliste **und** bei
  Rückmeldungen und Anwesenheit. Ab Werk alles aus.
* **Nie** weitergegeben: interne Links, QR-Codes, Zahlungsdaten und weitere
  Organisationsdetails aus Konzertmeister.
* Nicht veröffentlichte Termine haben keinen öffentlichen Link.

> **Datenschutz:** Alles, was die KI liest, geht an den Anbieter deines KI-Assistenten (bei
> Claude z. B. Anthropic) und wird nach dessen Datenschutzbedingungen verarbeitet. Gib nur
> frei, was du wirklich brauchst und was dein Verein erlaubt (DSGVO) – besonders bei
> **Minderjährigen** in Jugendgruppen. Kläre das vorher mit eurem Vorstand.

### Gruppen

Unter **Gruppen** kannst du **Termine, Rückmeldungen und Anwesenheit** auf einzelne Gruppen
beschränken (z. B. nur die Jugendkapelle). Nichts angehakt = alle Gruppen. **Auch Termine
ohne Gruppe (für den ganzen Verein)** ist ab Werk an.

* Die Gruppen lernt die App aus den kommenden Terminen, wenn du den Schlüssel speicherst,
  und erneut mit **Gruppen neu laden** (lädt auch Namen und Termintypen neu).
* Rückmeldungen und Anwesenheit gibt es nur für Termine, die die KI vorher aufgelistet hat
  und die in einer erlaubten Gruppe liegen.
* **Grenze:** Die **Mitgliederliste lässt sich nicht auf Gruppen beschränken** –
  Konzertmeister liefert immer alle Mitglieder des Vereins. Deshalb ist `list_members` ab
  Werk aus. Willst du nur eine Gruppe freigeben, lass es aus.

### Termine anlegen

Über die Konzertmeister-API lassen sich Termine **nur aus Vorlagen** anlegen: Ort, Gruppe,
Dauer und Fristen kommen aus der Vorlage; die KI kann Name, Beschreibung und Beginn setzen.
Unter **Termine anlegen**:

* **E-Mail des Erstellers** – die E-Mail-Adresse des Konzertmeister-Kontos, das als
  Ersteller neuer Termine erscheint (von Konzertmeister vorgeschrieben).
* **Vorlagen** – eine pro Zeile: `Name = Vorlagen-ID`, z. B. `Probe Jugendkapelle = 1a2b3c`.
  Den Namen verwendet die KI; die ID ist die ID der Vorlage in Konzertmeister (siehe Hilfe
  von Konzertmeister oder frag euren Konzertmeister-Admin – wo genau sie angezeigt wird, ist
  noch nicht dokumentiert, siehe [Bekannte Grenzen](#bekannte-grenzen)).

Ist `create_appointment` angehakt, fehlen aber E-Mail des Erstellers oder Vorlagen, weist
die Karte darauf hin. `list_appointment_templates` zeigt der KI nur die Namen eurer
Vorlagen.

### Termintypen

Zum Auflisten von Terminen braucht Konzertmeister die **Nummern** der Termintypen, bietet
aber keine Liste davon an. Unter **Termintypen** einen pro Zeile eintragen: `Name =
Nummer`, z. B. `Probe = 1`. Als Hilfe zeigt der Abschnitt die **in kommenden Terminen
gesehenen Nummern**. Ohne Einträge werden die Nummern 1–10 abgefragt.

### Mitglieder

* `add_member` – fügt ein Mitglied hinzu; die **E-Mail-Adresse ist Pflicht**,
  Konzertmeister lädt die Person dann per E-Mail ein.
* `update_member` – ändert ein Mitglied, erkannt an der E-Mail; nur die Werte, die die KI
  angibt, werden geändert.

Beide sind ab Werk aus, und wie bei jedem schreibenden Tool wird die KI aufgefordert, dich
vorher zu fragen.

### Mehrere Vereine

Eine App kann bis zu **10 Vereine** bedienen – z. B. den Hauptverein und einen
Partnerverein. **Verein hinzufügen** legt eine neue Karte an. Jeder Verein hat:

* einen eigenen API-Schlüssel und eine **eigene Connector-URL**,
* eigene Einstellungen, Verbindungstest, **Neue URL** und **Verein entfernen**,
* ein eigenes Gerät und einen eigenen Schalter in Home Assistant und einen eigenen
  Reparatur-Hinweis,
* einen eigenen MCP-Server, der als eigener eingeschränkter Benutzer läuft (`km1` …
  `km10`): Kein Verein kann den Schlüssel eines anderen lesen.

**Name:** erst ab dem zweiten Verein – bei nur einem Verein braucht es keinen. Dann ab Werk
der Name aus Konzertmeister; mit ✏️ daneben setzt du einen eigenen (**Name dieses
Vereins**, nur auf der Seite und in Home Assistant zu sehen).

**Last:** Jeder Verein läuft als eigener Server. Ab vier Vereinen warnt die Seite, dass das
spürbar mehr Arbeitsspeicher und CPU braucht – behalte kleine Geräte im Blick.

Der letzte Verein kann nicht entfernt werden – lösche stattdessen seinen Schlüssel. Jeder
Administrator von Home Assistant kann die App-Seite öffnen und sieht und verwaltet daher
**alle** Vereine samt ihren Connector-URLs.

### Server ausschalten

Im Webhook-Modus legt die Hilfs-Integration pro Verein ein Gerät mit dem Schalter
**Konzertmeister MCP <Name> Server** an (bei nur einem Verein: *Konzertmeister MCP Server*,
`switch.konzertmeister_mcp_server`). Ausgeschaltet erreicht keine KI-App diesen Verein
mehr: Home Assistant beantwortet jede MCP-Anfrage selbst mit „ausgeschaltet“, und die App
stoppt diesen Server. Schlüssel, Einstellungen und Connector-URL bleiben; wieder
eingeschaltet funktioniert alles nach wenigen Sekunden. Der Zustand übersteht Neustarts.
Der Schalter ist eine normale Entität – nutzbar in Automationen, Dashboards oder mit
Sprachassistenten.

### Was die KI statt eines Fehlers bekommt

Solange kein Schlüssel da ist, Konzertmeister den Schlüssel ablehnt, der Server startet
oder ausgeschaltet ist, bekommt die KI eine kurze, klare Meldung (z. B. dass auf der
App-Seite ein Schlüssel eingetragen werden muss) statt eines Verbindungsfehlers. Diese
Meldungen sind absichtlich auf Englisch – KI-Assistenten verstehen sie und antworten
trotzdem in deiner Sprache.

### Benachrichtigungen

Die Hilfs-Integration zeigt **Reparatur-Hinweise** (*Einstellungen → Reparaturen*) in der
Sprache von Home Assistant:

* **Neustart erforderlich** – nach Updates der Hilfs-Integration (mit Neustart-Knopf). Nach
  der ersten Installation zeigt nur die App-Seite den Hinweis.
* **API-Schlüssel von <Name> abgelehnt** – Konzertmeister lehnt einen gespeicherten
  Schlüssel ab (z. B. weil ein Leiter ihn gelöscht oder neu erstellt hat). Trag den
  aktuellen Schlüssel auf der App-Seite ein; der Hinweis verschwindet dann von selbst.
  Abschaltbar mit `key_notification`.

### Verbindungstest

**Verbindungstest** in der Karte prüft nacheinander:

1. **Konzertmeister akzeptiert den Schlüssel** – und lädt Namen, Gruppen und Termintypen
   neu,
2. **MCP-Server antwortet** – und wie viele Tools er anbietet,
3. **Connector-URL aus dem Internet erreichbar** – die App ruft ihre eigene öffentliche
   Adresse auf, so wie deine KI-App.

Eine Sperre durch den Bot-Schutz von Cloudflare vor Home Assistant erscheint als
⚠️-Hinweis, nicht als Fehler – KI-Apps kommen meist trotzdem durch.

### Sicherheit

* **Behandle die Connector-URL wie ein Passwort.** Wer sie kennt, kann die freigegebenen
  Tools dieses Vereins nutzen. Teile keine Screenshots oder Protokolle, die sie enthalten.
  Ist sie bekannt geworden: **Neue URL**.
* **Die App hat keinen Zugriff auf die Home-Assistant-API** (kein `homeassistant_api`,
  `hassio_api`, `host_network` oder `privileged`) – sie kann in Home Assistant nichts lesen,
  schalten oder ändern. Ihr einziger Zugriff ist der Konfigurationsordner
  (`homeassistant_config`), nur um die Hilfs-Integration nach
  `custom_components/konzertmeister_mcp_webhook` zu kopieren (und im Direkt-Modus wieder zu
  entfernen). Einen einzelnen Ordner kann Home Assistant nicht einbinden; nur der interne
  Teil der App nutzt ihn, nie die aus dem Internet erreichbaren MCP-Server.
* **AppArmor-Profil für die ganze App:** Im Konfigurationsordner darf sie nur in
  `custom_components/konzertmeister_mcp_webhook` schreiben. Home Assistant bewertet die App
  nach der Installation mit 8 von 8 (der Store zeigt vorher 7, weil er das Profil noch
  nicht kennt).
* **App-Seite:** nur über Ingress von Home Assistant (nur der Ingress-Proxy darf sie laden),
  mit CSRF-Token und Sicherheits-Headern (`no-store`, `no-referrer`,
  `frame-ancestors 'self'`).
* **MCP-Server:** lauschen nur auf `127.0.0.1` hinter nginx, das den geheimen Pfad verlangt
  und nichts protokolliert (`access_log off`), damit das Geheimnis nie in einem Protokoll
  landet. Jeder Server läuft als eigener eingeschränkter Benutzer (`umask 077`, keine
  weiteren Gruppen); seine Umgebung enthält kein Supervisor-Token und keine anderen
  Geheimnisse, seine Einstellungen bekommt er nur lesend über die Umgebung – ändern kann er
  sie nicht. Wo der Linux-Kernel *Landlock* anbietet, sperrt er sich zusätzlich in seinen
  eigenen Ordner ein. Home Assistant OS bietet Landlock derzeit nicht an – im App-Protokoll
  steht dann *Landlock is not available here*; das ist erwartet, dann gelten die
  Benutzerrechte und das AppArmor-Profil.
* **Hilfs-Integration:** Ihren Statuskanal zur App nimmt die App nur aus dem internen Netz
  von Home Assistant (`172.30.32.0/23`) und mit eigenem Schlüssel an. Nichts in diesem
  Austausch kann Home Assistant verändern.
* **API-Schlüssel:** Datei mit Rechten `0600` im privaten Ordner der App; nie wieder
  angezeigt, nie protokolliert, nur an Konzertmeister gesendet. Er ist Teil der
  Home-Assistant-Backups.
* **Lieferkette:** Jedes Python-Paket ist auf eine exakte Version festgelegt
  (`constraints.txt`); Dependabot überwacht die GitHub-Actions und das Basis-Image.
* **Eine Sicherheitslücke gefunden?** Bitte vertraulich über GitHub melden (*Security →
  Report a vulnerability*), nicht in einem öffentlichen Issue – siehe
  [SECURITY.md](https://github.com/mw-hbg/ha-konzertmeister-mcp/blob/main/SECURITY.md).

### Konfiguration

Der Reiter *Konfiguration* der App (Änderungen wirken nach einem Neustart der App). Tools,
Gruppen, Freigaben, Vorlagen und Typen stellst du pro Verein auf der App-Seite ein, nicht
hier.

| Option | Beschreibung |
|---|---|
| `remote_access` | `webhook` (Standard) – erreichbar über deine bestehende Home-Assistant-Adresse, installiert die Hilfs-Integration, braucht einen Neustart von Home Assistant. `direct` – du leitest einen eigenen HTTPS-Hostnamen auf Port 8100; beim Wechsel entfernt die App die Hilfs-Integration beim nächsten Start. Die Connector-URLs ändern sich beim Wechsel. |
| `public_url` | Optional, meist leer. Nur nötig, wenn die App-Seite deine öffentliche Adresse nicht ermitteln kann. Webhook: deine Home-Assistant-Adresse, z. B. `https://home.example.com`. Direct: der Hostname, den du auf die App leitest. Es werden nur Schema und Host verwendet; die Seite warnt, wenn sie ungültig ist oder `http://` nutzt. |
| `key_notification` | `true` (Standard): Reparatur-Hinweis in Home Assistant, wenn Konzertmeister den API-Schlüssel eines Vereins ablehnt. |
| `log_level` | `debug`, `info` (Standard), `warning`, `error`. Nur `debug` protokolliert zusätzlich jede einzelne Anfrage der KI (zur Fehlersuche). |

### Sprache

Die App-Seite gibt es auf Deutsch und Englisch: die Auswahl unten auf der Seite, sonst die
Sprache deines Browsers, sonst die Sprache von Home Assistant, sonst Englisch. Meldungen an
die KI bleiben absichtlich auf Englisch. Weitere Sprache hinzufügen:
[TRANSLATING.md](https://github.com/mw-hbg/ha-konzertmeister-mcp/blob/main/konzertmeister_mcp/TRANSLATING.md).

### Bekannte Grenzen

Version 0.1 ist die erste Veröffentlichung. Ehrliche Liste, was noch offen oder nicht
möglich ist:

* **Experimentell:** bisher nur mit einer nachgebildeten Konzertmeister-API getestet;
  Tests mit der echten API, anderen KI-Clients und dem Basic-Tarif stehen noch aus.
* **Datumsformate** der Konzertmeister-API (Datumsfilter beim Auflisten, Beginn neuer
  Termine) müssen sich im Alltag noch bestätigen.
* **Vorlagen-IDs:** Wo Konzertmeister die ID einer Vorlage anzeigt, ist noch nicht
  dokumentiert.
* **Nummern der Termintypen** müssen von Hand eingetragen werden – die API bietet keine
  Liste.
* **Die Mitgliederliste lässt sich nicht auf Gruppen beschränken** (Konzertmeister liefert
  immer alle Mitglieder).
* **Nicht in der Konzertmeister-API, daher auch nicht in der App:** Nachrichten, Dateien,
  Noten, Abwesenheiten und Termine ohne Vorlage.
* **Ratenbegrenzungen** der API sind unbekannt; die App speichert Antworten 60 Sekunden
  zwischen.

### Fehlerbehebung

| Problem | Lösung |
|---|---|
| *Das sieht nicht nach einem API-Schlüssel aus* / *Konzertmeister hat diesen Schlüssel abgelehnt* | Den vollständigen, aktuellen Schlüssel kopieren. Im Zweifel legt ein Leiter einen neuen an (das überschreibt den alten). |
| Zustand *Schlüssel abgelehnt* / Reparatur-Hinweis *API-Schlüssel … abgelehnt* | Der Schlüssel wurde in Konzertmeister gelöscht oder neu erstellt. Mit **Schlüssel ersetzen** den aktuellen eintragen. |
| *Der Schlüssel konnte nicht geprüft werden* | Konzertmeister war nicht erreichbar – später noch einmal versuchen. |
| Fernzugriff bleibt bei *Home Assistant muss einmal neu gestartet werden* | Home Assistant neu starten. Bleibt es, unter *Einstellungen → System → Protokolle* nach `konzertmeister_mcp_webhook` suchen. |
| Connector-URL zeigt einen Platzhalter | Deine öffentliche Adresse ist unbekannt – warten, bis die Hilfs-Integration läuft, oder **Öffentliche Adresse** setzen. |
| Verbindungstest: *vor Home Assistant blockiert* | Bot-Schutz von Cloudflare – KI-Apps kommen meist trotzdem durch. Sonst `/api/webhook/` in Proxy oder WAF erlauben. |
| Keine Gruppen aufgelistet | Gruppen kommen aus kommenden Terminen – **Gruppen neu laden** klicken, sobald es welche gibt. |
| Die KI findet keine Termine eines Typs | Die Nummern unter **Termintypen** eintragen (siehe die in kommenden Terminen gesehenen Nummern). |
| Die KI sagt, ein Tool gibt es nicht | Es ist unter **Was die KI darf** nicht angehakt. |
| Termine anlegen klappt nicht | **E-Mail des Erstellers** (ein Konzertmeister-Konto) und Vorlagen-IDs prüfen. |

### Deinstallieren

1. Die App deinstallieren. Home Assistant entfernt den Eintrag der Hilfs-Integration selbst,
   die Hilfs-Integration löscht danach ihren Ordner
   `custom_components/konzertmeister_mcp_webhook` und zeigt eine Benachrichtigung. **Kein
   Neustart nötig.** (War Home Assistant beim Deinstallieren aus, passiert das innerhalb von
   etwa 20 Minuten nach dem nächsten Start.)
2. Den Konnektor in deiner KI-App entfernen.
3. Optional den API-Schlüssel in Konzertmeister löschen (ein Leiter: *Vereinsdetails →
   Bearbeiten → Public API*).

### Alle Tools

*Art*: **lesen** = liest nur · **anlegen** = fügt etwas Neues hinzu · **ändern** = ändert
etwas Bestehendes. Diese Tabelle wird aus dem Code erzeugt (`scripts/update_docs.py`).

<!-- tools:de:start -->
| Tool | Was es tut | Art | Voraussetzung |
|---|---|---|---|
| `list_appointments` | Termine auflisten | lesen | – |
| `get_appointment_replies` | Rückmeldungen zu einem Termin (Ja / Nein / Vielleicht) | lesen | – |
| `get_appointment_attendance` | Anwesenheit bei einem Termin | lesen | – |
| `list_appointment_templates` | Terminvorlagen auflisten | lesen | – |
| `list_appointment_types` | Termintypen auflisten | lesen | – |
| `list_members` | Mitgliederliste (alle Gruppen) | lesen | ab Werk aus |
| `create_appointment` | Termin aus einer Vorlage anlegen | anlegen | ab Werk aus; Vorlagen + Ersteller-E-Mail |
| `add_member` | Mitglied hinzufügen | anlegen | ab Werk aus |
| `update_member` | Mitglied ändern | ändern | ab Werk aus |
<!-- tools:de:end -->
