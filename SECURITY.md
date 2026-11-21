# Security policy

[English](#english) · [Deutsch](#deutsch)

## English

### Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's private
vulnerability reporting instead: **Security → Report a vulnerability** in this
repository. You will get an answer as soon as possible; this is a hobby project, so
please allow a few days.

Helpful details: app and Home Assistant version, remote access mode (`webhook` /
`direct`), what an attacker could do and how to reproduce it. Never include a real
API key or connector URL.

### Scope

In scope: the Konzertmeister MCP app (app page, secret-path protection, MCP servers,
data filters, helper integration `konzertmeister_mcp_webhook`, handling of API keys).

Out of scope: vulnerabilities in Konzertmeister itself or its API – please report those
to KM Konzertmeister GmbH – and in the bundled third-party packages (please report them
upstream).

### Good to know

* **The connector URL is the credential.** Anyone who knows it can use the enabled tools
  of that association – treat it like a password and create a new one with **New URL**
  on the app page if it leaks.
* **The API key belongs to the whole association.** It is stored only in the app's
  private folder (file mode `0600`), never shown again, never logged and sent only to
  `https://rest.konzertmeister.app`. It is part of Home Assistant backups.
* **No access to the Home Assistant API:** no `homeassistant_api`, `hassio_api`,
  `host_network` or `privileged`. The only access to Home Assistant is the configuration
  folder, used solely to copy (and in direct mode remove) the helper integration.
* **AppArmor profile** for the whole app; in the configuration folder it only allows
  writing to `custom_components/konzertmeister_mcp_webhook`.
* **App page** only through Home Assistant's ingress (only the ingress proxy may load
  it), with a CSRF token and security headers (`no-store`, `no-referrer`,
  `frame-ancestors 'self'`). Every Home Assistant administrator can open it and
  therefore sees all associations and their connector URLs (by design).
* **MCP servers** listen on `127.0.0.1` only, behind nginx, which requires the secret path
  and writes no access log, so the secret never lands in a log. The status channel of the
  helper integration is only accepted from Home Assistant's internal network
  (`172.30.32.0/23`) and with its own key.
* **One unprivileged user per association** (`km1` … `km10`, `umask 077`, no extra
  groups): no association can read another one's key. A server's environment carries no
  Supervisor token or other secrets; it receives its settings read-only and cannot change
  them. The servers share the app's container, though, and are not separated on the
  network level.
* **Landlock:** where the Linux kernel offers it, each MCP server additionally confines
  itself to its own folder. Home Assistant OS currently does not offer it (the app log
  says so); then the user rights and the AppArmor profile apply.
* **Data filters run in the server:** group limits and the personal-data shares cannot be
  bypassed by the AI. Internal links, QR codes and payment data are never passed on.
* **Supply chain:** every Python package is pinned in `constraints.txt`; Dependabot
  watches the GitHub actions and the base image.

## Deutsch

### Sicherheitslücke melden

Bitte für Sicherheitsprobleme **kein** öffentliches Issue anlegen. Nutze stattdessen die
vertrauliche Meldung von GitHub: **Security → Report a vulnerability** in diesem
Repository. Du bekommst so bald wie möglich eine Antwort; es ist ein Hobbyprojekt, gib
also bitte ein paar Tage Zeit.

Hilfreich sind: Version der App und von Home Assistant, Fernzugriff (`webhook` /
`direct`), was ein Angreifer tun könnte und wie es sich nachstellen lässt. Nie einen
echten API-Schlüssel oder eine echte Connector-URL mitschicken.

### Umfang

Dazu gehört: die App Konzertmeister MCP (App-Seite, Schutz durch geheimen Pfad,
MCP-Server, Datenfilter, Hilfs-Integration `konzertmeister_mcp_webhook`, Umgang mit
API-Schlüsseln).

Nicht dazu gehört: Lücken in Konzertmeister selbst oder seiner API – bitte an die KM
Konzertmeister GmbH melden – und in den mitgelieferten Paketen Dritter (bitte dort
melden).

### Gut zu wissen

* **Die Connector-URL ist der Zugang.** Wer sie kennt, kann die freigegebenen Tools dieses
  Vereins nutzen – behandle sie wie ein Passwort und erzeuge mit **Neue URL** auf der
  App-Seite eine neue, wenn sie bekannt geworden ist.
* **Der API-Schlüssel gehört dem ganzen Verein.** Er liegt nur im privaten Ordner der App
  (Dateirechte `0600`), wird nie wieder angezeigt, nie protokolliert und nur an
  `https://rest.konzertmeister.app` gesendet. Er ist Teil der Home-Assistant-Backups.
* **Kein Zugriff auf die Home-Assistant-API:** kein `homeassistant_api`, `hassio_api`,
  `host_network` oder `privileged`. Der einzige Zugriff auf Home Assistant ist der
  Konfigurationsordner, nur um die Hilfs-Integration zu kopieren (und im Direkt-Modus zu
  entfernen).
* **AppArmor-Profil** für die ganze App; im Konfigurationsordner erlaubt es Schreiben nur in
  `custom_components/konzertmeister_mcp_webhook`.
* **App-Seite** nur über Ingress von Home Assistant (nur der Ingress-Proxy darf sie laden),
  mit CSRF-Token und Sicherheits-Headern (`no-store`, `no-referrer`,
  `frame-ancestors 'self'`). Jeder Administrator von Home Assistant kann sie öffnen und
  sieht daher alle Vereine samt Connector-URLs (so gewollt).
* **MCP-Server** lauschen nur auf `127.0.0.1` hinter nginx, das den geheimen Pfad verlangt
  und kein Zugriffsprotokoll schreibt – das Geheimnis landet nie in einem Protokoll. Den
  Statuskanal der Hilfs-Integration nimmt die App nur aus dem internen Netz von Home
  Assistant (`172.30.32.0/23`) und mit eigenem Schlüssel an.
* **Ein eingeschränkter Benutzer pro Verein** (`km1` … `km10`, `umask 077`, keine weiteren
  Gruppen): Kein Verein kann den Schlüssel eines anderen lesen. Die Umgebung eines Servers
  enthält kein Supervisor-Token und keine anderen Geheimnisse; seine Einstellungen bekommt
  er nur lesend und kann sie nicht ändern. Die Server teilen sich allerdings den Container
  der App und sind im Netzwerk nicht voneinander getrennt.
* **Landlock:** Wo der Linux-Kernel es anbietet, sperrt sich jeder MCP-Server zusätzlich in
  seinen eigenen Ordner ein. Home Assistant OS bietet es derzeit nicht an (das
  App-Protokoll sagt das); dann gelten die Benutzerrechte und das AppArmor-Profil.
* **Datenfilter laufen im Server:** Gruppenbeschränkung und Freigaben persönlicher Daten
  kann die KI nicht umgehen. Interne Links, QR-Codes und Zahlungsdaten werden nie
  weitergegeben.
* **Lieferkette:** Jedes Python-Paket ist in `constraints.txt` festgelegt; Dependabot
  überwacht die GitHub-Actions und das Basis-Image.
