# Influx Picker

Choose which Home Assistant entities are written to InfluxDB®, and change that
choice at any time **without restarting Home Assistant**.

> **Status: early development.** Nothing is released yet. This README describes
> the goals and the planned design. Feedback and contributions are very welcome.

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

## Planned features

- **Label-based selection.** Two labels, for example `influx` (write on change)
  and `influx-heartbeat` (write on change plus periodic writes while idle).
  Label names are configurable. Labels on a device or area can be inherited.
- **Manual list.** For entities that cannot carry labels (for example entities
  without a unique ID), maintained in the integration's options.
- **Overview panel.** A sidebar panel shows which entities are exported and why,
  lets you switch entities on and off from a table, and flags manually listed
  entities that no longer exist.
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
| Compatibility | Verify the core integration's exact schema before writing any data (measurement, field and tag names, attribute handling). |
| Batching | Flush after 1 s of quiet or 100 points, like the core integration. |
| Buffer | Bounded by **count** (default 50,000 points), oldest points dropped on overflow, no age limit. Timestamps are preserved, so buffering longer does not distort data. |
| Retry | Backoff from 5 s up to 60 s. Invalid batches are dropped, not retried. |
| Attributes | Handled like in the core integration. |
| Heartbeat marking | A field `_heartbeat=true` on heartbeat points, no tag, so the series stays continuous. |
| Skipped states | `unknown`, `unavailable` and empty states are not written. |
| Persistence | A disk-backed queue is only added if real-world outages show a need. |

## Heartbeat marking (planned)

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

Full roadmap: [English](ROADMAP.md) · [Deutsch](ROADMAP.de.md)

| Milestone | Content |
|---|---|
| M0 Foundation | Project structure, neutral point model, backend interface and registry, config flow, exporter core |
| M1 Compatibility | Audit of the core integration's schema, golden tests, attribute export, native options, heartbeat marking |
| M2 InfluxDB 2 | First backend, label selection with inheritance, heartbeat writes |
| M3 Manual list & overview | Manual entity lists, basic overview, status of missing entities, repairs |
| M3b Overview panel | Sidebar panel with a searchable table, switching entities on and off, bulk actions |
| M4 Buffering & diagnostics | Configurable buffer, backoff, diagnostic sensors, load tests |
| M5 InfluxDB 1.x | Backend plugin |
| M6 InfluxDB 3 | Backend plugin |
| M7 Migration | Import from the core integration's YAML, parallel-run warning |
| M8 Quality & release | CI against InfluxDB 1/2/3, documentation, translations, HACS metadata |

Open question: the trademark check before a public release (see the roadmap).

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
