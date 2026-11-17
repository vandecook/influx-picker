# Influx Picker

Choose which Home Assistant entities are written to InfluxDB, and change that
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
- **Overview.** See which entities are exported and why, and spot manually
  listed entities that no longer exist.
- **Compatible by design.** Same measurement, tag and field layout as the core
  integration, so existing Grafana queries and dashboards keep working.
- **Heartbeat.** Optional periodic writes for entities that rarely change, so
  dashboards have no gaps. Heartbeat points carry a tag so they can be filtered.
- **Reliable delivery.** Batched writes, a bounded buffer, retry with backoff,
  and the same defaults as the core integration where it makes sense.
- **Pluggable backends.** InfluxDB 2.x first. 1.x and 3.x are added as backend
  plugins.

## Design decisions so far

| Topic | Decision |
|---|---|
| Backends | Backend interface and registry from the start; InfluxDB 2.x is the first plugin. |
| Compatibility | Verify the core integration's exact schema before writing any data (measurement, field and tag names, attribute handling). |
| Batching | Flush after 1 s of quiet or 100 points, like the core integration. |
| Buffer | Bounded by **count** (default 50,000 points), oldest points dropped on overflow, no age limit. Timestamps are preserved, so buffering longer does not distort data. |
| Retry | Backoff from 5 s up to 60 s. Invalid batches are dropped, not retried. |
| Skipped states | `unknown`, `unavailable` and empty states are not written. |
| Persistence | A disk-backed queue is only added if real-world outages show a need. |

## Heartbeat tag (planned)

Points will carry a `heartbeat` tag that separates real state changes from
periodic heartbeat points and from the initial snapshot written when an entity
becomes selected. Anything that **counts events or state changes** has to filter
heartbeats out, for example in Flux:

```flux
from(bucket: "ha")
  |> range(start: -24h)
  |> filter(fn: (r) => r.heartbeat == "false")
```

Averages, `last()` and graphs usually want both kinds of points. Data written by
other tools has no `heartbeat` tag, so such a filter will not match it. Whether
the tag is set on all points or only on heartbeat points is still open (see the
roadmap below).

## Roadmap

Full roadmap: [English](ROADMAP.md) · [Deutsch](ROADMAP.de.md)

| Milestone | Content |
|---|---|
| M0 Foundation | Project structure, neutral point model, backend interface and registry, config flow, exporter core |
| M1 Compatibility | Audit of the core integration's schema, golden tests, attribute export, native options, heartbeat tag decision |
| M2 InfluxDB 2 | First backend, label selection with inheritance, heartbeat writes |
| M3 Manual list & overview | Manual entity lists, overview, status of missing entities, repairs |
| M4 Buffering & diagnostics | Configurable buffer, backoff, diagnostic sensors, load tests |
| M5 InfluxDB 1.x | Backend plugin |
| M6 InfluxDB 3 | Backend plugin |
| M7 Migration | Import from the core integration's YAML, parallel-run warning |
| M8 Quality & release | CI against InfluxDB 1/2/3, documentation, translations, HACS metadata |

Open questions:

1. Should the `heartbeat` tag be on all points, only on heartbeat points, or
   should heartbeats go to a separate measurement or field?
2. Internal backends only, or support external backend plugins?
3. Is the options-flow overview enough, or is a dedicated panel needed?
4. Write all numeric attributes, or only configured ones (like the core
   integration)?
5. Multiple instances, for example InfluxDB 2 and 3 in parallel?

## Contributing

Contributions are welcome, especially:

- testing against your own InfluxDB 1.x / 2.x / 3.x setup,
- backend plugins and compatibility checks against the core integration,
- translations and documentation.

Please open an issue to discuss larger changes first.

## License

[MIT](LICENSE)

## Disclaimer

This is an independent community project. It is not affiliated with, endorsed
by, or sponsored by InfluxData Inc. "InfluxDB" is a trademark of InfluxData Inc.
and is used here only to describe compatibility.
