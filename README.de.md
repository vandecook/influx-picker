# Series Picker

[English](README.md) · **Deutsch** · [Installationsanleitung](docs/installation.de.md) · [Roadmap](ROADMAP.de.md)

Schreibt ausgewählte Home-Assistant-Entitäten nach InfluxDB®, ausgewählt über
**Labels**. Änderungen wirken sofort, **ohne Neustart von Home Assistant**.

Series Picker ist ein freies, unabhängiges Open-Source-Projekt (MIT-Lizenz).
Es gibt es aus einem Grund: Bei der nativen `influxdb`-Integration stehen die
zu schreibenden Entitäten im YAML, und jede Änderung braucht einen Neustart
von Home Assistant. Series Picker macht diese Neustarts überflüssig: Entitäten
werden per Label oder Liste in der Oberfläche ausgewählt, die Änderung gilt
sofort.

> **Status: v0.1, frühe Version.** Mit automatischen Tests abgedeckt und in
> einer echten Installation getestet; dort stimmten die Punkte mit denen der
> nativen Integration überein. Der Code ist großteils KI-generiert (Claude von
> Anthropic) und nicht gründlich geprüft. Er verwaltet deinen InfluxDB-Token,
> also prüf ihn und fang mit einem Test-Bucket an. Fehlerberichte und
> Testergebnisse sind sehr willkommen.

## Funktionen

- **Auswahl per Label:** ein Label für "bei Änderung schreiben", eines für "bei
  Änderung und als Heartbeat schreiben". Labels an Gerät oder Bereich zählen
  mit (abschaltbar).
- **Manuelle Liste** für Entitäten, die keine Labels tragen können (zum
  Beispiel ohne Unique-ID), und eine **Übersicht** über alles, was geschrieben
  wird.
- **Kompatibel mit der nativen `influxdb`-Integration:** gleiche Measurements,
  Tags und Felder. Ihre YAML-Optionen (`default_measurement`, `tags`,
  `tags_attributes`, `ignore_attributes`, `component_config`, …) werden in der
  Oberfläche eingestellt, bestehende Abfragen und Dashboards funktionieren
  weiter.
- **Heartbeat:** Entitäten, die sich selten ändern, werden regelmäßig erneut
  geschrieben, damit Graphen keine Lücken haben.
- **Startwert beim Start:** einstellbar (aktuelle Zeit, eigener Zeitstempel des
  Zustands oder aus).
- **Zuverlässiges Schreiben:** Pakete (1 s oder 100 Punkte), begrenzter Puffer
  (50.000 Punkte), Wiederholung mit Backoff.
- **Mehrere Instanzen:** ein Eintrag pro Bucket oder Server, jeweils mit eigenen
  Labels.

Unterstützt: **InfluxDB 2.x**. Backends für 1.x und 3.x sind geplant, aber
derzeit arbeitet niemand daran, weil der Maintainer diese Versionen nicht
nutzt. Beiträge sind willkommen; die Backend-Schnittstelle ist dafür gebaut.

## Installation

Benötigt Home Assistant 2026.10 oder neuer.

1. **HACS** → Menü (drei Punkte) → **Benutzerdefinierte Repositories** →
   `https://github.com/vandecook/series-picker`, Typ **Integration**.
2. **Series Picker** herunterladen, Home Assistant neu starten.
3. Zwei Labels anlegen, zum Beispiel `influx` und `influx-heartbeat`.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Series
   Picker:** InfluxDB-Version, Verbindung (URL, Organisation, Bucket, Token mit
   Schreibrecht), Labels, Datenformat.
5. Die Labels an Entitäten, Geräte oder Bereiche hängen.

Alle Schritte und Einstellungen, Umstieg von der nativen Integration und
Fehlersuche: **[Installationsanleitung](docs/installation.de.md)**.

Schreibt die native `influxdb`-Integration dieselben Entitäten in denselben
Bucket, landen sie doppelt. Einen eigenen Bucket nehmen oder sie aus ihrem
`include` entfernen.

## Heartbeat-Markierung

Heartbeat-Punkte und der Startwert einer neu ausgewählten Entität tragen ein
**Feld** `_heartbeat=true`; Änderungspunkte haben kein Zusatzfeld. Ein Feld
statt eines Tags hält alle Punkte einer Entität in einer Series, Graphen zeigen
also eine durchgehende Linie. Mit der Option "Zeit der letzten
Zustandsänderung" bekommt der Startwert beim Start stattdessen das Feld
`_startup=true`.

Abfragen, die **Änderungen zählen**, müssen Heartbeat-Punkte weglassen:

```flux
from(bucket: "ha")
  |> range(start: -24h)
  |> filter(fn: (r) => r.entity_id == "my_sensor"
      and (r._field == "value" or r._field == "_heartbeat"))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => not exists r._heartbeat)
```

Graphen, Mittelwerte und `last()` können alle Punkte verwenden.

## Roadmap

Als Nächstes: Diagnose und Puffer-Einstellungen (M4), Import aus dem nativen
YAML (M7). InfluxDB 1.x und 3.x (M5, M6) sind geplant, ruhen aber, bis jemand,
der sie nutzt, sie beisteuert. Details: [ROADMAP.de.md](ROADMAP.de.md).

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Tests gegen ein echtes InfluxDB 2 laufen, wenn `INFLUXDB_V2_URL`,
`INFLUXDB_V2_TOKEN`, `INFLUXDB_V2_ORG` und `INFLUXDB_V2_BUCKET` gesetzt sind;
die CI führt sie bei jedem Pull Request in einem Container aus. Details zum
Schema: [docs/core-schema-audit.md](docs/core-schema-audit.md).

Beiträge sind willkommen: Tests mit deinem eigenen Setup, Backends,
Übersetzungen. Größere Änderungen bitte vorher in einem Issue besprechen.
Produktnamen von InfluxData nur beschreibend verwenden.

## Lizenz

[MIT](LICENSE)

## Haftungsausschluss

InfluxDB® und InfluxData® sind eingetragene Marken der InfluxData Inc., die
mit diesem Projekt nicht verbunden ist und es nicht unterstützt. Series Picker
ist ein unabhängiges Community-Projekt; die Namen werden nur zur Beschreibung
der Kompatibilität verwendet. Bis Version 0.1.0 hieß das Projekt
„Influx Picker“.
