# Changelog

## Unreleased

- First release: MCP server for Konzertmeister in Home Assistant, using only the official
  Konzertmeister API with the API key of the association (checked with Konzertmeister when
  saving, never shown again, never logged).
- 9 tools: list appointments, replies, attendance, templates, appointment types, member
  list, create an appointment from a template, add and change members. New associations
  start read only and without the member list; quick choice *Read only*, *Read and
  create*, *Everything*. Before writing, the AI is told to ask for an explicit yes.
- Filters in the server: names always; e-mail, mobile phone, address and custom member
  fields only if ticked; internal links, QR codes and payment data never. Appointments,
  replies and attendance can be limited to groups (plus appointments without a group).
- Templates (`name = template id`) and creator e-mail for creating appointments;
  appointment types (`name = number`) with the numbers seen in upcoming appointments.
- Up to 10 associations, each with its own key, connector URL, switch in Home Assistant
  and its own unprivileged server user.
- Remote access through the existing Home Assistant address (webhook, helper integration
  “Konzertmeister MCP (remote access)”, one restart) or an own hostname (direct).
- Connection test, repair notice when Konzertmeister rejects a key, clear messages for the
  AI instead of errors, page in English and German.
- Security: no access to the Home Assistant API, own AppArmor profile, page only via
  ingress, MCP servers only behind the secret path, Landlock where the kernel offers it,
  all packages pinned.
- Experimental: tested with a simulated Konzertmeister API; real-world tests are still ahead.

---

- Erste Veröffentlichung: MCP-Server für Konzertmeister in Home Assistant, nutzt nur die
  offizielle Konzertmeister-API mit dem API-Schlüssel des Vereins (beim Speichern bei
  Konzertmeister geprüft, nie wieder angezeigt, nie protokolliert).
- 9 Tools: Termine auflisten, Rückmeldungen, Anwesenheit, Vorlagen, Termintypen,
  Mitgliederliste, Termin aus einer Vorlage anlegen, Mitglieder hinzufügen und ändern. Neue
  Vereine starten mit „nur lesen“ und ohne Mitgliederliste; Schnellauswahl *Nur lesen*,
  *Lesen und anlegen*, *Alles*. Vor dem Schreiben wird die KI aufgefordert, auf ein
  ausdrückliches Ja zu warten.
- Filter im Server: Namen immer; E-Mail, Handynummer, Adresse und eigene Mitgliedsfelder
  nur, wenn angehakt; interne Links, QR-Codes und Zahlungsdaten nie. Termine, Rückmeldungen
  und Anwesenheit lassen sich auf Gruppen beschränken (plus Termine ohne Gruppe).
- Vorlagen (`Name = Vorlagen-ID`) und E-Mail des Erstellers zum Anlegen von Terminen;
  Termintypen (`Name = Nummer`) mit den in kommenden Terminen gesehenen Nummern.
- Bis zu 10 Vereine, jeder mit eigenem Schlüssel, eigener Connector-URL, eigenem Schalter
  in Home Assistant und eigenem eingeschränkten Server-Benutzer.
- Fernzugriff über die bestehende Home-Assistant-Adresse (Webhook, Hilfs-Integration
  „Konzertmeister MCP (remote access)“, ein Neustart) oder einen eigenen Hostnamen
  (direct).
- Verbindungstest, Reparatur-Hinweis, wenn Konzertmeister einen Schlüssel ablehnt, klare
  Meldungen an die KI statt Fehlern, Seite auf Deutsch und Englisch.
- Sicherheit: kein Zugriff auf die Home-Assistant-API, eigenes AppArmor-Profil, Seite nur
  über Ingress, MCP-Server nur hinter dem geheimen Pfad, Landlock, wo der Kernel es
  anbietet, alle Pakete festgelegt.
- Experimentell: mit einer nachgebildeten Konzertmeister-API getestet; Tests im echten Betrieb stehen noch aus.
