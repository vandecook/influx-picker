# Roadmap: Influx Picker (`influx_picker`)

[Deutsch](ROADMAP.de.md)

Greenfield project: there is no existing code to build on. Project name: **Influx Picker**, domain `influx_picker`. If the project is published, the trademark question needs to be checked first (see Open questions).

## Requirements (as of 2026-11-17)

1. Supports InfluxDB **1.x, 2.x and 3.x**.
2. Implement **InfluxDB 2 first**. 1.x and 3.x follow later through a **plugin system** (backends).
3. **Maximum compatibility with the core Home Assistant integration** (schema, behavior, defaults), so that existing Grafana queries need as few changes as possible.
4. **Two labels** (for example `influx` and `influx-heartbeat`). Changes take effect immediately, without a restart.
5. A **manual list** in the config/options flow for entities that cannot carry labels.
6. An **overview** of selected (by label) and manually listed entities. For manual entries it shows whether the entity still exists.

## Findings that shape the design

- **Buffer decision:** the queue is bounded by count, not by age. Timestamps are preserved, so buffering longer does not distort data. A disk-backed queue only if needed.
- **Core integration, buffering:** batches of up to 100 points or 1 s of quiet, unbounded queue, events older than 30 s (plus retries) are dropped, `max_retries` defaults to 0, invalid batches are not retried, unknown/empty/unavailable states are skipped. Source: Home Assistant Core `influxdb/__init__.py` and `const.py`.
- **Core integration, configuration:** filters are YAML only, and every change needs a restart. This is the reason for this project.
- **Core integration, schema:** not yet verified (see M1).

---

## M0 – Foundation

- [x] **Project name:** Influx Picker, domain `influx_picker` (changing it later means setting the integration up again).
- [ ] **Project structure:** HACS-ready repository, config-entry based (`runtime_data`), de/en translations.
- [ ] **Neutral data model:** `Point` (measurement, tags, fields, timestamp), independent of the InfluxDB version.
- [ ] **Backend interface** and **registry** (`v1`, `v2`, `v3`): `schema()`, `async validate()`, `async write(points)`, `async close()`. A new backend is one file plus a registration.
- [ ] **Config flow** with a "choose version" step, followed by the backend-specific fields.
- [ ] **Exporter core:** selection, queue, batching, retry (independent of the backend).
- [ ] **Decision:** internal backends only, or external plugins too? Internal first.

## M1 – Compatibility with the core integration (before any data flows)

Goal: Grafana queries keep working unchanged.

- [ ] **Audit:** check the schema of the current core integration (core source code plus real data from a bucket): measurement names, field names (`value`, `state`, `*_str`), tags, handling of on/off, strings, booleans and attributes.
- [ ] **Golden tests:** one expected line-protocol example per case (numeric sensor, unit, binary_sensor, switch, text, attributes).
- [ ] **Attribute export:** numeric attributes as fields, strings as `*_str`, as in the core integration.
- [ ] **Reproduce the core options:** `default_measurement`, `override_measurement`, `measurement_attr`, static `tags`, `tags_attributes`, `ignore_attributes`, `component_config` (`_domain`, `_glob`).
- [ ] **Buffer defaults (decided):** flush after 1 s of quiet or 100 points (as in the core integration), skip rules for unknown/unavailable/empty, drop invalid batches. Queue bounded by count (default 50,000 points, about 10 MB), oldest points dropped on overflow, no extra age limit. Retry with backoff (5 s, rising to at most 60 s). Everything configurable (see M4).
- [ ] **Heartbeat tag:** decide whether `heartbeat` is set on all points, only on heartbeat points, or whether heartbeats go to a separate measurement or field. Goal: no duplicate lines or counting errors in existing panels.
- [ ] **Comparison tool:** show core-integration points and new points of an entity side by side.

Acceptance: existing Grafana queries return the same results with the new data.

## M2 – InfluxDB 2 backend and selection (first usable state)

- [ ] **v2 backend** as the first plugin (`/api/v2/write`, token, org, bucket, SSL option, real validation of token/org/bucket during setup).
- [ ] **Label selection:** two labels (names configurable), resolved through the label registry, effective on registry changes without a restart.
- [ ] **Inheritance** from device and area, can be switched off.
- [ ] **Initial write** for newly labelled entities.
- [ ] **Heartbeat write cycle** (configurable interval, writes only if the entity wrote nothing during the interval).
- [ ] **Matching tests** (unit, golden, integration against an InfluxDB 2 container).

## M3 – Manual entity list and overview

- [ ] **Options flow menu:** "Labels & interval" / "Manual list" / "Overview".
- [ ] **Two manual lists** (multi-select): "write on change" and "write on change + heartbeat".
- [ ] **Merging** of label and manual selection (union, heartbeat wins). A hint if a manually chosen entity is already selected through a label.
- [ ] **Overview:** number of entities by source (label directly, device, area, manual) and mode (change, heartbeat).
- [ ] **Status of manual entries:** exists / **no longer exists** / disabled.
- [ ] **Cleanup:** option "remove missing entries".
- [ ] **Repairs issue** when manually listed entities have been deleted.
- [ ] **Later (optional):** a dedicated panel with a searchable list, if the options-flow text block no longer suffices for many entities.

## M4 – Buffering, reliability, diagnostics

- [ ] **Configurable:** flush interval, batch size, maximum queue size (by count), backoff limits.
- [ ] **Backoff** on failure (5 s, rising to at most 60 s) instead of a fixed retry.
- [ ] **Persistent queue** (only if needed): implement only if real-world operation shows losses from longer InfluxDB outages or Home Assistant restarts during an outage.
- [ ] **Diagnostic sensors:** number of tracked entities, queue size, dropped points, write errors, last successful write.
- [ ] **Flush on shutdown.**
- [ ] **Load test:** thousands of entities, offline phases, restart behavior.

## M5 – InfluxDB 1.x backend

- [ ] Endpoint `/write?db=&rp=&precision=`, auth by user/password or none.
- [ ] Fields: URL, database, retention policy, user, password, SSL.
- [ ] Handle field type conflicts (InfluxDB 1 rejects writes when a field changes its type).
- [ ] Validation through `/ping` and a test write.
- [ ] Integration test against an InfluxDB 1 container.

## M6 – InfluxDB 3 backend

- [ ] Endpoint `/api/v3/write_lp?db=&precision=` with a bearer token.
- [ ] Fields: URL, database, token, SSL.
- [ ] Clarify specifics: field type conflicts, naming rules, per-table limits.
- [ ] Integration test against an InfluxDB 3 container.

## M7 – Migration and convenience

- [ ] **Import from the core integration:** read `include.entities`/`domains`/`entity_globs` and turn them into a manual list or label suggestions.
- [ ] **Quick label assignment** from the import.
- [ ] **Warning** if the core integration is running in parallel (double writes).
- [ ] **Options flow for connection data** (change the token without setting up again).
- [ ] Evaluate multiple instances (for example InfluxDB 2 and 3 in parallel) with separate labels per instance.

## M8 – Quality and release

- [ ] Unit tests with `pytest-homeassistant-custom-component`, CI with InfluxDB 1/2/3 in Docker.
- [ ] **README** with installation, data model and a dedicated section on the heartbeat tag: meaning of `true`/`false`, that queries counting events must filter heartbeats out (Flux example), and that older data without the tag is not matched by the filter.
- [ ] Translations de/en, documentation, HACS metadata, real repository URLs.
- [ ] Versioning and changelog.

---

## Recommended order

1. **M0** and **M1** (foundation and compatibility). The schema must be settled before production data is written.
2. **M2** (first usable state with InfluxDB 2).
3. **M3** (manual list, overview) and **M4** (buffering, diagnostics).
4. **M5**, **M6** (InfluxDB 1 and 3).
5. **M7**, **M8** in parallel as needed.

## Open questions

1. **Trademark risk on publication:** "Influx" in the name may conflict with InfluxData's trademark guidelines when the project is public. Check before publishing (mention InfluxDB only descriptively, state that the project is not affiliated with InfluxData). Not an issue for purely private use.
2. **Heartbeat tag:** on all points, only on heartbeat points, or separate? Depends on M1.
3. **Plugins:** internal only, or external too?
4. **Overview:** is the options-flow text block enough, or is a panel needed?
5. **Attributes:** write all numeric attributes, or only configured ones (like the core integration)?
6. **Multiple instances:** useful or unnecessary?
