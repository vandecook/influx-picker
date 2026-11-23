# Influx Picker

**English** · [Deutsch](README.de.md) · [Installation guide](docs/installation.md) · [Roadmap](ROADMAP.en.md)

Write selected Home Assistant entities to InfluxDB®, chosen with **labels**.
Changes take effect immediately, **without restarting Home Assistant**.

> **Status: v0.1, early version.** Covered by automated tests and tested in
> one real installation, where the points matched those of the core
> integration. The code is largely AI-generated (Claude by Anthropic) and
> not thoroughly reviewed. It handles your InfluxDB token, so review it and
> start with a test bucket. Bug reports and test results are very welcome.

## Features

- **Selection by label:** one label for "write on change", one for "write on
  change plus heartbeat". Labels on a device or area count too (can be switched
  off).
- **Compatible with the core `influxdb` integration:** same measurements, tags
  and fields. Its YAML options (`default_measurement`, `tags`,
  `tags_attributes`, `ignore_attributes`, `component_config`, …) are set in the
  UI, so existing queries and dashboards keep working.
- **Heartbeat:** entities that rarely change are written again periodically, so
  graphs have no gaps.
- **Snapshot at start:** configurable (current time, the state's own timestamp,
  or off).
- **Reliable writing:** batches (1 s or 100 points), bounded buffer
  (50,000 points), retry with backoff.
- **Multiple instances:** one entry per bucket or server, each with its own
  labels.

Supported: **InfluxDB 2.x**. 1.x and 3.x are planned.

## Installation

Requires Home Assistant 2026.10 or newer.

1. **HACS** → menu (three dots) → **Custom repositories** →
   `https://github.com/vandecook/influx-picker`, type **Integration**.
2. Download **Influx Picker**, restart Home Assistant.
3. Create two labels, for example `influx` and `influx-heartbeat`.
4. **Settings → Devices & services → Add integration → Influx Picker:**
   InfluxDB version, connection (URL, organization, bucket, token with write
   permission), labels, data format.
5. Put the labels on entities, devices or areas.

Every step and setting, migration from the core integration and
troubleshooting: **[installation guide](docs/installation.md)**.

If the core `influxdb` integration writes the same entities to the same bucket,
they are written twice. Use a separate bucket or remove them from its
`include`.

## Heartbeat marking

Heartbeat points and the snapshot of a newly selected entity carry a **field**
`_heartbeat=true`; change points carry no extra field. A field instead of a tag
keeps all points of an entity in one series, so graphs show one continuous
line. With the option "time of the last state change", the snapshot at start
gets the field `_startup=true` instead.

Queries that **count changes** must leave out heartbeat points:

```flux
from(bucket: "ha")
  |> range(start: -24h)
  |> filter(fn: (r) => r.entity_id == "my_sensor"
      and (r._field == "value" or r._field == "_heartbeat"))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => not exists r._heartbeat)
```

Graphs, averages and `last()` can use all points.

## Roadmap

Next: a manual list for entities without labels and an overview (M3),
diagnostics and buffer settings (M4), InfluxDB 1.x and 3.x (M5, M6), import
from the core YAML (M7). Details: [ROADMAP.en.md](ROADMAP.en.md).

## Development

```bash
pip install -r requirements_test.txt
pytest
```

Tests against a real InfluxDB 2 run when `INFLUXDB_V2_URL`,
`INFLUXDB_V2_TOKEN`, `INFLUXDB_V2_ORG` and `INFLUXDB_V2_BUCKET` are set; CI
runs them in a container on every pull request. Schema details:
[docs/core-schema-audit.md](docs/core-schema-audit.md).

Contributions are welcome: tests against your own setup, backends,
translations. Please open an issue before larger changes. Use InfluxData
product names descriptively only.

## License

[MIT](LICENSE)

## Disclaimer

Independent community project, not affiliated with, endorsed by, or sponsored
by InfluxData Inc. InfluxDB® and InfluxData® are registered trademarks of
InfluxData Inc. The names are used only to describe compatibility.
