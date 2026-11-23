# Influx Picker

[English](README.md) · **Deutsch** · [Roadmap](ROADMAP.de.md)

Wähle aus, welche Home-Assistant-Entitäten in InfluxDB® geschrieben werden, und
ändere die Auswahl jederzeit **ohne Neustart von Home Assistant**.

> **Status: frühe Entwicklung.** Es gibt noch kein Release. Eine erste Version
> des Codes existiert (InfluxDB 2.x, Auswahl per Label, Heartbeat). Sie ist nur
> durch automatische Tests abgedeckt und lief **noch nicht in einer echten
> Home-Assistant-Installation**. Dieses README beschreibt die Ziele und das
> geplante Design. Rückmeldungen und Beiträge sind sehr willkommen.

## Wie dieses Projekt entsteht

Dieses Projekt wird mit Hilfe von KI entwickelt (Claude von Anthropic): Code,
Dokumentation und Tests sind größtenteils KI-generiert. Der Maintainer hat weder
die Zeit noch das Fachwissen, jeden Teil gründlich zu prüfen und zu testen.
**Geh also nicht davon aus, dass der Code gründlich geprüft oder getestet ist.**
Automatische Tests und CI sollen das ausgleichen. Weil die Integration dein
InfluxDB-Token verwendet, prüfe den Code bitte vor der Installation und
betrachte alle Versionen als experimentell. Code-Reviews, Testergebnisse aus
echten Installationen und Fehlermeldungen sind nicht nur willkommen, sie sind
das, was dieses Projekt am meisten braucht.

## Warum

Die native `influxdb`-Integration filtert Entitäten nur per YAML
(`include` / `exclude`), und jede Änderung braucht einen Neustart von Home
Assistant. Mit Influx Picker wählst du Entitäten so aus, wie du Home Assistant
ohnehin organisierst: mit **Labels**. Label in der Oberfläche setzen oder
entfernen, und die Änderung wirkt sofort.

## Installation

> Experimentell: Lies zuerst [Wie dieses Projekt entsteht](#wie-dieses-projekt-entsteht).
> Es gibt noch kein Release, HACS installiert daher den aktuellen Stand des
> Standard-Branches (`main`). Voraussetzung: Home Assistant 2026.10 oder neuer.

### Mit HACS (empfohlen)

1. In Home Assistant **HACS** öffnen.
2. Das Menü öffnen (drei Punkte oben rechts) und **Benutzerdefinierte
   Repositories** wählen.
3. `https://github.com/vandecook/influx-picker` eintragen, Typ **Integration**
   wählen und auf **Hinzufügen** klicken.
4. In HACS nach **Influx Picker** suchen, öffnen und **Herunterladen** klicken.
5. Home Assistant neu starten.

### Manuell

1. Dieses Repository herunterladen (grüner Button **Code**, **Download ZIP**).
2. Den Ordner `custom_components/influx_picker` in den Ordner
   `custom_components` deiner Home-Assistant-Konfiguration kopieren (anlegen,
   falls er fehlt). Am Ende muss es
   `config/custom_components/influx_picker/manifest.json` geben.
3. Home Assistant neu starten.

### Einrichten

1. Die gewünschten Labels anlegen, zum Beispiel `influx` und
   `influx-heartbeat`: **Einstellungen → Bereiche, Labels & Zonen → Labels**.
2. In InfluxDB ein API-Token mit **Schreibrecht** auf den Ziel-Bucket anlegen.
3. In Home Assistant **Einstellungen → Geräte & Dienste → Integration
   hinzufügen** öffnen und **Influx Picker** wählen.
4. Die Datenbankversion wählen (derzeit nur InfluxDB 2.x).
5. URL (zum Beispiel `http://192.168.1.10:8086`), Organisation, Bucket und
   Token eintragen. Die Verbindung wird mit einer echten Schreibanfrage geprüft.
6. Die Labels und das Heartbeat-Intervall wählen.
7. Die Labels an Entitäten, Geräte oder Bereiche hängen. Änderungen wirken nach
   etwa einer Sekunde, ohne Neustart. Labels und Intervall lassen sich später
   über **Konfigurieren** bei der Integration ändern.

Für ein zweites Ziel (anderer Bucket oder Server) die Integration einfach noch
einmal hinzufügen.

**Hinweis:** Schreibt die native `influxdb`-Integration in denselben Bucket,
werden dieselben Entitäten unter Umständen doppelt geschrieben. Entferne sie aus
der `include`-Liste der nativen Integration oder nutze einen eigenen Bucket.

## Geplante Funktionen

- **Auswahl per Label.** Zwei Labels, zum Beispiel `influx` (bei Änderung
  schreiben) und `influx-heartbeat` (bei Änderung schreiben, dazu regelmäßig im
  Ruhezustand). Die Labels sind frei wählbar. Labels von Gerät oder Bereich
  können vererbt werden.
- **Manuelle Liste.** Für Entitäten, die keine Labels tragen können (zum
  Beispiel Entitäten ohne eindeutige ID), gepflegt in den Optionen der
  Integration.
- **Übersicht.** Eine Liste in den Optionen zeigt, welche Entitäten exportiert
  werden und warum, und markiert manuell eingetragene Entitäten, die es nicht
  mehr gibt. Ein Seitenleisten-Panel mit Schaltern ist für viel später geplant.
- **Kompatibel.** Gleiche Measurement-, Tag- und Feldstruktur wie die native
  Integration, damit bestehende Grafana-Abfragen und Dashboards weiter
  funktionieren.
- **Heartbeat.** Optionale regelmäßige Schreibvorgänge für Entitäten, die sich
  selten ändern, damit Dashboards keine Lücken haben. Heartbeat-Punkte sind mit
  einem Feld markiert, sodass man sie unterscheiden kann, ohne die Series zu
  teilen.
- **Zuverlässige Übertragung.** Gebündelte Schreibvorgänge, ein begrenzter
  Puffer, Wiederholung mit Backoff und, wo sinnvoll, dieselben Standardwerte wie
  die native Integration.
- **Austauschbare Backends.** Zuerst InfluxDB 2.x. 1.x und 3.x kommen als
  Backend-Plugins dazu. Backends liegen vorerst in diesem Repository.
- **Mehrere Instanzen.** Ein Config-Entry pro Ziel, jeweils mit eigenen Labels,
  zum Beispiel InfluxDB 2 und 3 parallel.

## Bisherige Entscheidungen

| Thema | Entscheidung |
|---|---|
| Backends | Backend-Interface und Registry von Anfang an; InfluxDB 2.x ist das erste Plugin. |
| Kompatibilität | Gleiches Schema wie die native Integration. Anhand ihres Quellcodes geprüft ([Audit](docs/core-schema-audit.md), englisch) per Test gegen eine Kopie des Core-Algorithmus abgesichert und mit echten Daten der nativen Integration abgeglichen (10 Entitätstypen identisch, als Golden-Tests hinterlegt). Echte Grafana-Abfragen sind noch nicht geprüft. |
| Bündelung | Flush nach 1 s Ruhe oder 100 Punkten, wie die native Integration. |
| Puffer | Begrenzt nach **Anzahl** (Standard 50.000 Punkte), bei Überlauf werden die ältesten verworfen, kein Alters-Limit. Die Zeitstempel bleiben erhalten, längeres Puffern verfälscht also nichts. |
| Wiederholung | Backoff von 5 s bis 60 s. Ungültige Batches werden verworfen, nicht wiederholt. |
| Attribute | Wie in der nativen Integration. |
| Heartbeat-Markierung | Ein Feld `_heartbeat=true` an Heartbeat-Punkten, kein Tag, damit die Series durchgehend bleibt. |
| Übersprungene Zustände | `unknown`, `unavailable` und leere Zustände werden nicht geschrieben. |
| Persistenz | Eine Warteschlange auf der Platte kommt nur, wenn echte Ausfälle das nötig machen. |

## Heartbeat-Markierung

Heartbeat-Punkte (regelmäßige Schreibvorgänge für ruhende Entitäten sowie der
Startwert, der beim Aufnehmen einer Entität geschrieben wird) tragen ein
**Feld** `_heartbeat=true`. Änderungspunkte haben kein Zusatzfeld.

Ein Feld statt eines Tags ist Absicht: Ein Tag würde Heartbeat-Punkte in eine
eigene Series legen, und bestehende Flux-Panels zeigten dann eine zweite Linie
pro Entität. Mit einem Feld bleiben alle Punkte einer Entität in einer Series,
und Abfragen auf `value` sehen die Heartbeats als normale Werte und behalten
eine durchgehende Linie.

Alles, was **Ereignisse oder Zustandswechsel zählt**, muss Heartbeat-Punkte
ausschließen. Beispiel in Flux (ungetestete Skizze):

```flux
from(bucket: "ha")
  |> range(start: -24h)
  |> filter(fn: (r) => r.entity_id == "my_sensor"
      and (r._field == "value" or r._field == "_heartbeat"))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => not exists r._heartbeat)
```

Mittelwerte, `last()` und Graphen wollen meist alle Punkte und brauchen keinen
Filter.

## Roadmap

Vollständige Roadmap: [Deutsch](ROADMAP.de.md) · [English](ROADMAP.en.md)

| Meilenstein | Inhalt |
|---|---|
| M0 Fundament | Projektstruktur, neutrales Datenmodell, Backend-Interface und Registry, Config-Flow, Exporter-Kern |
| M1 Kompatibilität | Audit des Schemas der nativen Integration, Golden-Tests, Attribut-Export, native Optionen, Heartbeat-Markierung |
| M2 InfluxDB 2 | Erstes Backend, Auswahl per Label mit Vererbung, Heartbeat |
| M3 Manuelle Liste & Übersicht | Manuelle Entitätenlisten, Übersicht als Liste, Status fehlender Entitäten, Reparaturhinweise |
| M4 Puffer & Diagnose | Konfigurierbarer Puffer, Backoff, Diagnose-Sensoren, Lasttests |
| M5 InfluxDB 1.x | Backend-Plugin |
| M6 InfluxDB 3 | Backend-Plugin |
| M7 Migration | Import aus der YAML der nativen Integration, Warnung bei Parallelbetrieb |
| M8 Qualität & Release | CI gegen InfluxDB 1/2/3, Dokumentation, Übersetzungen, HACS-Metadaten |
| M9 Übersichts-Panel (viel später) | Seitenleisten-Panel mit durchsuchbarer Tabelle, Entitäten ein- und ausschalten, Sammelaktionen |

Offene Frage: die Markenprüfung vor einer öffentlichen Veröffentlichung (siehe
Roadmap).

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Tests, die einen echten InfluxDB-2-Server brauchen, werden übersprungen, solange
`INFLUXDB_V2_URL`, `INFLUXDB_V2_TOKEN`, `INFLUXDB_V2_ORG` und
`INFLUXDB_V2_BUCKET` nicht gesetzt sind. Die CI startet einen Server im
Container und führt sie bei jedem Pull Request aus.

## Mitmachen

Beiträge sind willkommen, besonders:

- Tests mit deiner eigenen InfluxDB-1.x-/2.x-/3.x-Installation,
- Backend-Plugins und Kompatibilitätsprüfungen gegen die native Integration,
- Übersetzungen und Dokumentation.

Größere Änderungen bitte zuerst in einem Issue besprechen.

Wenn du InfluxDB oder andere InfluxData-Produkte in Dokumentation, UI-Texten
oder Code erwähnst, verwende die Namen nur beschreibend, nenne InfluxData Inc.
als Inhaber, wo ein Markenhinweis nötig ist, und verwende sie nie so, dass eine
Verbindung oder Billigung nahegelegt wird.

## Lizenz

[MIT](LICENSE)

## Haftungsausschluss

Dies ist ein unabhängiges Community-Projekt. Es steht in keiner Verbindung zu
InfluxData Inc. und wird von InfluxData Inc. weder unterstützt noch gesponsert.
InfluxDB® und InfluxData® sind eingetragene Marken der InfluxData Inc.
Telegraf™, Kapacitor™ und Chronograf™ sind Marken der InfluxData Inc. Die Namen
werden hier nur verwendet, um die Kompatibilität zu beschreiben.
