# Influx Picker

**English** · [Deutsch](README.de.md) · [Roadmap](ROADMAP.en.md)

Choose which Home Assistant entities are written to InfluxDB®, and change that
choice at any time **without restarting Home Assistant**.

> **Status: early development.** Nothing is released yet. A first version of the
> code exists (InfluxDB 2.x, label selection, heartbeat). It is covered by
> automated tests only and has **not yet run in a real Home Assistant
> installation**. This README describes the goals and the planned design.
> Feedback and contributions are very welcome.

## How this project is built

This project is developed with the help of AI (Claude by Anthropic): code,
documentation and tests are largely AI-generated. The maintainer does not have
the time or the expertise to review and test every part in depth, so **do not
assume the code has been thoroughly reviewed or tested**. Automated tests and
CI are part of the plan to make up for this. Because the integration handles
your InfluxDB token, please review the code before installing it and treat all
versions as experimental. Code reviews, test results from real setups and bug
reports are not just welcome, they are what this project needs most.

## Why

The core `influxdb` integration filters entities only through YAML
(`include` / `exclude`), and every change requires a restart of Home Assistant.
Influx Picker lets you select entities the way you already organize Home
Assistant: with **labels**. Add or remove a label in the UI and the change takes
effect immediately.

## Installation

> Experimental: read [How this project is built](#how-this-project-is-built)
> first. There is no release yet, so HACS installs the current state of the
> default branch (`main`). Requires Home Assistant 2026.10 or newer.

### With HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Open the menu (three dots, top right) and choose **Custom repositories**.
3. Enter `https://github.com/vandecook/influx-picker`, type **Integration**,
   and click **Add**.
4. Search for **Influx Picker** in HACS, open it and click **Download**.
5. Restart Home Assistant.

### Manually

1. Download this repository (green **Code** button, **Download ZIP**).
2. Copy the folder `custom_components/influx_picker` into the
   `custom_components` folder of your Home Assistant configuration (create it if
   it does not exist), so you end up with
   `config/custom_components/influx_picker/manifest.json`.
3. Restart Home Assistant.

### Set up

1. Create the labels you want to use, for example `influx` and
   `influx-heartbeat`: **Settings → Areas, labels & zones → Labels**.
2. Create an API token in InfluxDB with **write** permission for the target
   bucket.
3. In Home Assistant, go to **Settings → Devices & services → Add integration**
   and choose **Influx Picker**.
4. Choose the database version (currently only InfluxDB 2.x).
5. Enter URL (for example `http://192.168.1.10:8086`), organization, bucket and
   token. The connection is checked with a real write request.
6. Choose the labels and the heartbeat interval.
7. **Data format:** if you used the core `influxdb` integration, copy the
   values of `default_measurement`, `tags`, `tags_attributes`,
   `ignore_attributes` and the other options from its YAML, so existing queries
   keep working. Otherwise keep the defaults.
8. Put the labels on entities, devices or areas. Changes take effect within
   about a second, without a restart. Labels, interval and data format can be
   changed later with **Configure** on the integration.

For a second target (another bucket or server), add the integration again.

**Note:** if the core `influxdb` integration writes to the same bucket, the
same entities may be written twice. Remove them from the core integration's
`include` list, or use a separate bucket.

## Planned features

- **Label-based selection.** Two labels, for example `influx` (write on change)
  and `influx-heartbeat` (write on change plus periodic writes while idle).
  Label names are configurable. Labels on a device or area can be inherited.
- **Manual list.** For entities that cannot carry labels (for example entities
  without a unique ID), maintained in the integration's options.
- **Overview.** A list in the integration's options shows which entities are
  exported and why, and flags manually listed entities that no longer exist. A
  sidebar panel with switches is planned for much later.
- **Compatible by design.** Same measurement, tag and field layout as the core
  integration, so existing Grafana queries and dashboards keep working.
- **Heartbeat.** Optional periodic writes for entities that rarely change, so
  dashboards have no gaps. Heartbeat points are marked with a field so they can
  be told apart without splitting the series.
- **Reliable delivery.** Batched writes, a bounded buffer, retry with backoff,
  and the same defaults as the core integration where it makes sense.
- **Pluggable backends.** InfluxDB 2.x first. 1.x and 3.x are added as backend
  plugins. Backends are internal to this repository for now.
- **Multiple instances.** One config entry per target, each with its own
  labels, for example InfluxDB 2 and 3 in parallel.

## Design decisions so far

| Topic | Decision |
|---|---|
| Backends | Backend interface and registry from the start; InfluxDB 2.x is the first plugin. |
| Compatibility | Same schema as the core integration. Audited from its source code ([audit](docs/core-schema-audit.md)) checked by tests against a copy of the core algorithm, and compared with real data written by the core integration (10 entity types identical, kept as golden tests). The core YAML options (`default_measurement`, `tags`, `tags_attributes`, …) are set in the UI. |
| Batching | Flush after 1 s of quiet or 100 points, like the core integration. |
| Buffer | Bounded by **count** (default 50,000 points), oldest points dropped on overflow, no age limit. Timestamps are preserved, so buffering longer does not distort data. |
| Retry | Backoff from 5 s up to 60 s. Invalid batches are dropped, not retried. |
| Attributes | Handled like in the core integration. |
| Heartbeat marking | A field `_heartbeat=true` on heartbeat points, no tag, so the series stays continuous. |
| Skipped states | `unknown`, `unavailable` and empty states are not written. |
| Persistence | A disk-backed queue is only added if real-world outages show a need. |

## Heartbeat marking

Heartbeat points (periodic writes for idle entities, and the initial snapshot
written when an entity becomes selected) are marked with a **field**
`_heartbeat=true`. Change points carry no extra field.

A field is used instead of a tag on purpose: a tag would put heartbeat points
into a separate series, so existing Flux panels would show a second line per
entity. With a field, all points of an entity stay in one series, and queries
that read `value` see the heartbeats as normal values and keep a continuous line.

Anything that **counts events or state changes** has to exclude heartbeat
points. Example in Flux (untested sketch):

```flux
from(bucket: "ha")
  |> range(start: -24h)
  |> filter(fn: (r) => r.entity_id == "my_sensor"
      and (r._field == "value" or r._field == "_heartbeat"))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => not exists r._heartbeat)
```

Averages, `last()` and graphs usually want all points and need no filter.

## Roadmap

Full roadmap: [English](ROADMAP.en.md) · [Deutsch](ROADMAP.de.md)

| Milestone | Content |
|---|---|
| M0 Foundation | Project structure, neutral point model, backend interface and registry, config flow, exporter core |
| M1 Compatibility | Audit of the core integration's schema, golden tests, attribute export, native options, heartbeat marking |
| M2 InfluxDB 2 | First backend, label selection with inheritance, heartbeat writes |
| M3 Manual list & overview | Manual entity lists, overview as a list, status of missing entities, repairs |
| M4 Buffering & diagnostics | Configurable buffer, backoff, diagnostic sensors, load tests |
| M5 InfluxDB 1.x | Backend plugin |
| M6 InfluxDB 3 | Backend plugin |
| M7 Migration | Import from the core integration's YAML, parallel-run warning |
| M8 Quality & release | CI against InfluxDB 1/2/3, documentation, translations, HACS metadata |
| M9 Overview panel (much later) | Sidebar panel with a searchable table, switching entities on and off, bulk actions |

Open question: the trademark check before a public release (see the roadmap).

## Development

```bash
pip install -r requirements_test.txt
pytest
```

Tests that need a real InfluxDB 2 server are skipped unless `INFLUXDB_V2_URL`,
`INFLUXDB_V2_TOKEN`, `INFLUXDB_V2_ORG` and `INFLUXDB_V2_BUCKET` are set. CI
starts a server in a container and runs them on every pull request.

## Contributing

Contributions are welcome, especially:

- testing against your own InfluxDB 1.x / 2.x / 3.x setup,
- backend plugins and compatibility checks against the core integration,
- translations and documentation.

Please open an issue to discuss larger changes first.

When you mention InfluxDB or other InfluxData products in documentation, UI
texts or code, use the names descriptively only, name InfluxData Inc. as the
owner where a trademark notice is needed, and never use them in a way that
suggests affiliation or endorsement.

## License

[MIT](LICENSE)

## Disclaimer

This is an independent community project. It is not affiliated with, endorsed
by, or sponsored by InfluxData Inc. InfluxDB® and InfluxData® are registered
trademarks of InfluxData Inc. Telegraf™, Kapacitor™ and Chronograf™ are
trademarks of InfluxData Inc. The names are used here only to describe
compatibility.
