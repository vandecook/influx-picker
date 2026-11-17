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
- [ ] **Entscheidung:** Nur interne Backends oder auch externe Plugins? Zunächst intern.

## M1 – Kompatibilität zur nativen Integration (vor dem ersten Datenfluss)

Ziel: Grafana-Abfragen laufen unverändert weiter.

- [ ] **Audit:** Schema der aktuellen nativen Integration prüfen (Core-Quellcode plus echte Daten aus einem Bucket): Measurement-Namen, Feldnamen (`value`, `state`, `*_str`), Tags, Behandlung von on/off, Strings, Booleans und Attributen.
- [ ] **Golden-Tests:** pro Fall (numerischer Sensor, Einheit, binary_sensor, switch, Text, Attribute) ein erwartetes Line-Protocol-Beispiel festschreiben.
- [ ] **Attribut-Export:** numerische Attribute als Felder, Strings als `*_str`, wie nativ.
- [ ] **Native Optionen nachbilden:** `default_measurement`, `override_measurement`, `measurement_attr`, statische `tags`, `tags_attributes`, `ignore_attributes`, `component_config` (`_domain`, `_glob`).
- [ ] **Puffer-Standardwerte (beschlossen):** Flush nach 1 s Ruhe oder 100 Einträgen (wie nativ), Skip-Regeln für unknown/unavailable/leer, Verwerfen ungültiger Batches. Queue-Begrenzung nach Anzahl (Standard 50.000 Punkte, ca. 10 MB), bei Überlauf werden die ältesten verworfen, kein zusätzliches Alters-Limit. Wiederholung bei Fehler mit Backoff (5 s, steigend bis max. 60 s). Alles konfigurierbar (siehe M4).
- [ ] **Heartbeat-Tag:** Entscheidung, ob `heartbeat` an allen Punkten steht oder nur an Heartbeat-Punkten, oder ob Heartbeat in ein eigenes Measurement/Feld geht. Ziel: keine Doppellinien oder Zählfehler in bestehenden Panels.
- [ ] **Vergleichswerkzeug:** native und neue Punkte einer Entität nebeneinander darstellen.

Abnahme: Bestehende Grafana-Abfragen liefern mit den neuen Daten dasselbe Ergebnis.

## M2 – InfluxDB-2-Backend und Selektion (erster nutzbarer Stand)

- [ ] **v2-Backend** als erstes Plugin (`/api/v2/write`, Token, Org, Bucket, SSL-Option, echte Prüfung von Token/Org/Bucket beim Einrichten).
- [ ] **Label-Selektion:** zwei Labels (Namen konfigurierbar), Auflösung über die Label-Registry, Wirkung bei Registry-Änderung ohne Neustart.
- [ ] **Vererbung** von Gerät und Bereich, abschaltbar.
- [ ] **Initialer Schreibvorgang** für neu gelabelte Entitäten.
- [ ] **Heartbeat-Schreibzyklus** (Intervall konfigurierbar, schreibt nur, wenn die Entität im Intervall nichts geschrieben hat).
- [ ] **Zugehörige Tests** (Unit, Golden, Integration gegen InfluxDB 2 im Container).

## M3 – Manuelle Entitätenliste und Übersicht

- [ ] **Options-Flow-Menü:** „Labels & Intervall“ / „Manuelle Liste“ / „Übersicht“.
- [ ] **Zwei manuelle Listen** (Mehrfachauswahl): „bei Änderung schreiben“ und „bei Änderung + Heartbeat“.
- [ ] **Zusammenführung** von Label und manueller Selektion (Vereinigung, Heartbeat gewinnt). Hinweis, wenn eine manuell gewählte Entität schon per Label erfasst wird.
- [ ] **Übersicht:** Anzahl der Entitäten nach Quelle (Label direkt, Gerät, Bereich, manuell) und Modus (Änderung, Heartbeat).
- [ ] **Status manueller Einträge:** vorhanden / **nicht mehr vorhanden** / deaktiviert.
- [ ] **Aufräumen:** Option „fehlende Einträge entfernen“.
- [ ] **Repairs-Meldung**, wenn manuell gepflegte Entitäten gelöscht wurden.
- [ ] **Später (optional):** eigenes Panel mit durchsuchbarer Liste, falls der Options-Flow-Textblock bei vielen Entitäten nicht mehr reicht.

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
- [ ] Mehrere Instanzen (z. B. Influx 2 und 3 parallel) mit eigenen Labels pro Instanz prüfen.

## M8 – Qualität und Veröffentlichung

- [ ] Unit-Tests mit `pytest-homeassistant-custom-component`, CI mit InfluxDB 1/2/3 in Docker.
- [ ] **README** mit Installation, Datenmodell und einem eigenen Abschnitt zum Heartbeat-Tag: Bedeutung von `true`/`false`, dass Zähl-Abfragen Heartbeats herausfiltern müssen (Flux-Beispiel), und dass Altdaten ohne Tag nicht mit dem Filter erfasst werden.
- [ ] Übersetzungen de/en, Doku, HACS-Metadaten, echte Repo-URLs.
- [ ] Versionierung und Changelog.

---

## Empfohlene Reihenfolge

1. **M0** und **M1** (Fundament und Kompatibilität). Das Schema muss feststehen, bevor produktiv Daten geschrieben werden.
2. **M2** (erster nutzbarer Stand mit InfluxDB 2).
3. **M3** (manuelle Liste, Übersicht) und **M4** (Puffer, Diagnose).
4. **M5**, **M6** (InfluxDB 1 und 3).
5. **M7**, **M8** parallel nach Bedarf.

## Offene Fragen

1. **Markenrisiko bei Veröffentlichung:** „Influx“ im Namen kann bei öffentlicher Nutzung Probleme mit den Markenrichtlinien von InfluxData machen. Vor dem Veröffentlichen prüfen (Nennung von InfluxDB nur beschreibend, Hinweis auf fehlende Verbindung zu InfluxData). Bei rein privater Nutzung unkritisch.
2. **Heartbeat-Tag:** an allen Punkten, nur an Heartbeat-Punkten oder getrennt? Hängt von M1 ab.
3. **Plugins:** nur intern oder auch extern?
4. **Übersicht:** reicht der Options-Flow-Textblock oder wird ein Panel gebraucht?
5. **Attribute:** alle numerischen schreiben oder nur nach Konfiguration (wie nativ)?
6. **Mehrere Instanzen:** sinnvoll oder unnötig?
