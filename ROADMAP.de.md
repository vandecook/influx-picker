# Roadmap: Influx Picker (`influx_picker`)

[English](ROADMAP.md)

Neustart auf der grünen Wiese: Es gibt keinen bestehenden Code, auf dem aufgebaut wird. Projektname: **Influx Picker**, Domain `influx_picker`. Bei einer Veröffentlichung ist zuerst die Markenfrage zu prüfen (siehe Offene Fragen).

## Anforderungen (Stand 17.11.2026)

1. Unterstützt InfluxDB **1.x, 2.x und 3.x**.
2. Zuerst nur **InfluxDB 2** umsetzen. 1 und 3 kommen später über ein **Plugin-System** (Backends).
3. **Maximale Kompatibilität zur nativen HA-Integration** (Schema, Verhalten, Standardwerte), damit der Aufwand für Änderungen in Grafana gering bleibt.
4. **Zwei Labels** (z. B. `influx` und `influx-heartbeat`). Änderungen wirken sofort, ohne Neustart.
5. Für Entitäten, die keine Labels tragen können, eine **eigene Liste** im Config-/Options-Flow.
6. **Übersicht** der selektierten (Label) und manuell gepflegten Entitäten. Bei manuellen Einträgen wird angezeigt, ob die Entität noch existiert.
7. **Mehrere Instanzen** von Anfang an möglich: ein Config-Entry pro Ziel, jeweils mit eigenen Labels (z. B. InfluxDB 2 und 3 parallel oder getrennte Buckets mit unterschiedlicher Aufbewahrung).
8. **Markenhygiene:** Wo InfluxDB oder andere InfluxData-Produktnamen vorkommen (Doku, UI-Texte, Code-Kommentare, Repository-Metadaten), werden sie nur beschreibend verwendet, bei Bedarf als Marken der InfluxData Inc. gekennzeichnet und nie so, dass eine Verbindung oder Billigung durch InfluxData nahegelegt wird.
9. **Attribute** werden wie in der nativen Integration behandelt.
10. **Plugins** vorerst nur intern: Backends liegen in diesem Repository.

## Erkenntnisse, die das Design bestimmen

- **Puffer-Entscheidung:** Queue nach Anzahl statt Alter (die Zeitstempel bleiben erhalten, längeres Puffern verfälscht nichts). Persistenz auf Platte nur bei Bedarf.
- **Native Integration, Puffer:** Batch bis 100 Einträge oder 1 s Ruhe, unbegrenzte Queue, Events älter als 30 s (plus Retries) werden verworfen, `max_retries` Standard 0, ungültige Batches werden nicht wiederholt, unbekannte/leere/nicht verfügbare Zustände werden übersprungen. Quelle: HA Core `influxdb/__init__.py` und `const.py`.
- **Native Integration, Konfiguration:** Filter nur per YAML, jede Änderung braucht einen Neustart. Das ist der Grund für dieses Projekt.
- **Schema der nativen Integration:** noch nicht verifiziert (siehe M1).

---

## M0 – Fundament

- [x] **Projektname:** Influx Picker, Domain `influx_picker` (später nur mit Neueinrichtung änderbar).
- [ ] **Projektstruktur:** HACS-fähiges Repository, Config-Entry-basiert (`runtime_data`), de/en-Übersetzungen.
- [ ] **Neutrales Datenmodell:** `Point` (measurement, tags, fields, timestamp), unabhängig von der Influx-Version.
- [ ] **Backend-Interface** und **Registry** (`v1`, `v2`, `v3`): `schema()`, `async validate()`, `async write(points)`, `async close()`. Neues Backend = eine Datei plus Registrierung.
- [ ] **Config-Flow** mit Schritt „Version wählen“, danach die backend-spezifischen Felder.
- [ ] **Exporter-Kern:** Selektion, Queue, Batching, Retry (unabhängig vom Backend).
- [x] **Entscheidung:** Nur interne Backends. Sie liegen in diesem Repository und kommen per Pull Request dazu. Das Backend-Interface bleibt sauber, damit externe Plugins später möglich bleiben.
- [ ] **Mehrere Instanzen von Anfang an:** ein Config-Entry pro Ziel, kein globaler Zustand, Label-Namen pro Entry konfigurierbar.

## M1 – Kompatibilität zur nativen Integration (vor dem ersten Datenfluss)

Ziel: Grafana-Abfragen laufen unverändert weiter.

- [ ] **Audit:** Schema der aktuellen nativen Integration prüfen (Core-Quellcode plus echte Daten aus einem Bucket): Measurement-Namen, Feldnamen (`value`, `state`, `*_str`), Tags, Behandlung von on/off, Strings, Booleans und Attributen.
- [ ] **Golden-Tests:** pro Fall (numerischer Sensor, Einheit, binary_sensor, switch, Text, Attribute) ein erwartetes Line-Protocol-Beispiel festschreiben.
- [ ] **Attribut-Export:** wie in der nativen Integration (beschlossen). Numerische Attribute als Felder, Strings als `*_str`; die genauen Regeln ergibt der Audit.
- [ ] **Native Optionen nachbilden:** `default_measurement`, `override_measurement`, `measurement_attr`, statische `tags`, `tags_attributes`, `ignore_attributes`, `component_config` (`_domain`, `_glob`).
- [ ] **Puffer-Standardwerte (beschlossen):** Flush nach 1 s Ruhe oder 100 Einträgen (wie nativ), Skip-Regeln für unknown/unavailable/leer, Verwerfen ungültiger Batches. Queue-Begrenzung nach Anzahl (Standard 50.000 Punkte, ca. 10 MB), bei Überlauf werden die ältesten verworfen, kein zusätzliches Alters-Limit. Wiederholung bei Fehler mit Backoff (5 s, steigend bis max. 60 s). Alles konfigurierbar (siehe M4).
- [x] **Heartbeat-Markierung (beschlossen):** ein **Feld** `_heartbeat=true`, nur an Heartbeat-Punkten und am Startwert einer neu selektierten Entität. Kein Tag, damit Heartbeat-Punkte in derselben Series wie Änderungspunkte bleiben und bestehende Panels ihre durchgehenden Linien behalten. Änderungspunkte tragen kein Zusatzfeld. Im Audit prüfen, ob bestehende Panels nach `_field` filtern. Optional später: umschaltbare Modi (Tag / aus).
- [ ] **Vergleichswerkzeug:** native und neue Punkte einer Entität nebeneinander darstellen.

Abnahme: Bestehende Grafana-Abfragen liefern mit den neuen Daten dasselbe Ergebnis.

## M2 – InfluxDB-2-Backend und Selektion (erster nutzbarer Stand)

- [ ] **v2-Backend** als erstes Plugin (`/api/v2/write`, Token, Org, Bucket, SSL-Option, echte Prüfung von Token/Org/Bucket beim Einrichten).
- [ ] **Label-Selektion:** zwei Labels, in der UI mit dem Label-Selector von Home Assistant gewählt und über die **Label-ID** gespeichert, damit das Umbenennen eines Labels in Home Assistant die Auswahl nicht kaputt macht. Auflösung über die Label-Registry, Wirkung bei Registry-Änderung ohne Neustart.
- [ ] **Vererbung** von Gerät und Bereich, abschaltbar.
- [ ] **Initialer Schreibvorgang** für neu gelabelte Entitäten.
- [ ] **Heartbeat-Schreibzyklus** (Intervall konfigurierbar, schreibt nur, wenn die Entität im Intervall nichts geschrieben hat).
- [ ] **Zugehörige Tests** (Unit, Golden, Integration gegen InfluxDB 2 im Container).

## M3 – Manuelle Entitätenliste und Übersicht

- [ ] **Options-Flow-Menü:** „Labels & Intervall“ / „Manuelle Liste“ / „Übersicht“.
- [ ] **Zwei manuelle Listen** (Mehrfachauswahl): „bei Änderung schreiben“ und „bei Änderung + Heartbeat“.
- [ ] **Zusammenführung** von Label und manueller Selektion (Vereinigung, Heartbeat gewinnt). Hinweis, wenn eine manuell gewählte Entität schon per Label erfasst wird.
- [ ] **Übersicht als Liste** im Options-Flow: Anzahl nach Quelle (Label direkt, Gerät, Bereich, manuell) und Modus (Änderung, Heartbeat), dazu eine Zeile pro Entität (Entity-ID, Quelle, Modus). Bei langen Listen gekürzt oder seitenweise.
- [ ] **Status manueller Einträge:** vorhanden / **nicht mehr vorhanden** / deaktiviert.
- [ ] **Aufräumen:** Option „fehlende Einträge entfernen“.
- [ ] **Repairs-Meldung**, wenn manuell gepflegte Entitäten gelöscht wurden.
- [ ] Bis es das Panel gibt (M9), ist die Liste im Options-Flow die Übersicht.

## M4 – Puffer, Zuverlässigkeit, Diagnose

- [ ] **Konfigurierbar:** Flush-Intervall, Batch-Größe, maximale Queue-Größe (nach Anzahl), Backoff-Grenzen.
- [ ] **Backoff** bei Ausfall (5 s, steigend bis max. 60 s) statt fester Wiederholung.
- [ ] **Persistente Queue** (nur bei Bedarf): erst umsetzen, wenn im Betrieb Verluste durch längere Influx-Ausfälle oder HA-Neustarts im Ausfall auftreten.
- [ ] **Diagnose-Sensoren:** Zahl der getrackten Entitäten, Queue-Größe, verworfene Punkte, Schreibfehler, letzter erfolgreicher Write.
- [ ] **Flush beim Herunterfahren.**
- [ ] **Lasttest:** Tausende Entitäten, Offline-Phasen, Neustart-Verhalten.

## M5 – InfluxDB 1.x Backend

- [ ] Endpoint `/write?db=&rp=&precision=`, Auth per Benutzer/Passwort oder ohne.
- [ ] Felder: URL, Datenbank, Retention Policy, Benutzer, Passwort, SSL.
- [ ] Feldtyp-Konflikte behandeln (InfluxDB 1 verweigert das Schreiben, wenn ein Feld seinen Typ wechselt).
- [ ] Validierung per `/ping` und Test-Write.
- [ ] Integrationstest gegen InfluxDB-1-Container.

## M6 – InfluxDB 3 Backend

- [ ] Endpoint `/api/v3/write_lp?db=&precision=` mit Bearer-Token.
- [ ] Felder: URL, Datenbank, Token, SSL.
- [ ] Besonderheiten klären: Feldtyp-Konflikte, Namensregeln, Limits pro Tabelle.
- [ ] Integrationstest gegen InfluxDB-3-Container.

## M7 – Migration und Komfort

- [ ] **Import aus der nativen Integration:** `include.entities`/`domains`/`entity_globs` einlesen und als manuelle Liste oder Label-Vorschlag übernehmen.
- [ ] **Label-Schnellvergabe** aus dem Import.
- [ ] **Warnung**, wenn die native Integration parallel läuft (doppelte Writes).
- [ ] **Options-Flow für Verbindungsdaten** (Token ändern ohne Neuanlage).
- [ ] Mehrere Instanzen parallel testen (z. B. Influx 2 und 3), inklusive eigener Labels pro Instanz und einer Warnung, wenn zwei Instanzen versehentlich dieselben Entitäten selektieren.

## M8 – Qualität und Veröffentlichung

- [ ] Unit-Tests mit `pytest-homeassistant-custom-component`, CI mit InfluxDB 1/2/3 in Docker.
- [ ] **README** mit Installation, Datenmodell und einem eigenen Abschnitt zum Feld `_heartbeat`: was es markiert und dass Zähl-Abfragen Heartbeat-Punkte ausschließen müssen (Flux-Pivot-Beispiel).
- [ ] **Markenprüfung:** Markenhinweise in README, Übersetzungen und HACS-Metadaten; Produktnamen nur beschreibend und mit Nennung des Inhabers (InfluxData Inc.).
- [ ] Übersetzungen de/en, Doku, HACS-Metadaten, echte Repo-URLs.
- [ ] Versionierung und Changelog.

## M9 – Übersichts-Panel (viel später, nach dem ersten Release)

Ziel: Entitäten einfach an- und abwählen und auf einen Blick sehen, was exportiert wird und warum.

- [ ] **WebSocket-API** (nur Admin): getrackte Entitäten mit Quelle (Label direkt, Gerät, Bereich, manuell), Modus (Änderung, Heartbeat), Status und letztem Schreibzeitpunkt auflisten; manuelle Einträge hinzufügen/entfernen; fehlende Einträge aufräumen. Pro Instanz.
- [ ] **Seitenleisten-Panel** (nur Admin): durchsuchbare, sortierbare und filterbare Tabelle (nach Quelle, Modus, Status, Domain, Bereich).
- [ ] **Entitäten direkt in der Tabelle an- und abschalten:** Das Umschalten setzt oder entfernt das konfigurierte Label über die Registry von Home Assistant, oder ändert die manuelle Liste bei Entitäten ohne Unique ID. Das ist der Hauptanwendungsfall des Projekts.
- [ ] **Sammelaktionen:** viele Zeilen markieren und gemeinsam aktivieren/deaktivieren oder auf Heartbeat-Modus stellen.
- [ ] **Statusanzeige:** fehlende manuelle Einträge deutlich markiert, doppelt selektierte Entitäten (Label und manuell) gekennzeichnet, Schreibfehler pro Entität, falls verfügbar.
- [ ] **Frontend schlicht halten:** eine einfache Web-Komponente mit möglichst wenigen Abhängigkeiten und wenig Build-Werkzeug, damit Mitwirkende daran arbeiten können.
- [ ] **Tests:** Unit-Tests der WebSocket-API; manuelle Testliste für das Panel.

---

## Empfohlene Reihenfolge

1. **M0** und **M1** (Fundament und Kompatibilität). Das Schema muss feststehen, bevor produktiv Daten geschrieben werden.
2. **M2** (erster nutzbarer Stand mit InfluxDB 2).
3. **M3** (manuelle Liste, Übersicht als Liste) und **M4** (Puffer, Diagnose).
4. **M5**, **M6** (InfluxDB 1 und 3).
5. **M7**, **M8** parallel nach Bedarf.
6. **M9** (Panel) viel später, nach dem ersten Release.

## Beschlossen

- **Plugins:** vorerst nur intern (siehe M0).
- **Mehrere Instanzen:** von Anfang an möglich, ein Config-Entry pro Ziel (siehe M0, M7).
- **Attribute:** wie in der nativen Integration (siehe M1).
- **Heartbeat-Markierung:** Feld `_heartbeat`, kein Tag (siehe M1).
- **Übersicht:** beginnt als Liste im Options-Flow (M3). Das eigene Panel kommt viel später (M9).

## Offene Fragen

1. **Markenrisiko bei Veröffentlichung:** „Influx“ im Namen kann bei öffentlicher Nutzung Probleme mit den Markenrichtlinien von InfluxData machen. Vor dem Veröffentlichen prüfen, nur beschreibend verwenden und auf die fehlende Verbindung zu InfluxData hinweisen. Bei rein privater Nutzung unkritisch.
