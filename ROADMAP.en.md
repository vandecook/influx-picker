# Roadmap: Influx Picker (`influx_picker`)

[Deutsch](ROADMAP.de.md) · [README](README.md)

Work started on 2026-11-17 (branch `m0-foundation`). "Done" below means implemented and covered by automated tests; a first real test ran on 2026-11-23 (one installation, InfluxDB 2). Release v0.1.0 contains M0, M1 and M2. Project name: **Influx Picker**, domain `influx_picker`. If the project is published, the trademark question needs to be checked first (see Open questions).

## Requirements (as of 2026-11-17)

1. Supports InfluxDB **1.x, 2.x and 3.x**.
2. Implement **InfluxDB 2 first**. 1.x and 3.x follow later through a **plugin system** (backends).
3. **Maximum compatibility with the core Home Assistant integration** (schema, behavior, defaults), so that existing Grafana queries need as few changes as possible.
4. **Two labels** (for example `influx` and `influx-heartbeat`). Changes take effect immediately, without a restart.
5. A **manual list** in the config/options flow for entities that cannot carry labels.
6. An **overview** of selected (by label) and manually listed entities. For manual entries it shows whether the entity still exists.
7. **Multiple instances** by design: one config entry per target, each with its own labels (for example InfluxDB 2 and 3 in parallel, or separate buckets for different retention).
8. **Trademark hygiene:** wherever InfluxDB or other InfluxData product names appear (documentation, UI strings, code comments, repository metadata), they are used descriptively only, marked as trademarks of InfluxData Inc. where required, and never in a way that suggests affiliation or endorsement.
9. **Attributes** are handled like in the core integration.
10. **Plugins** are internal only for now: backends live in this repository.

## Findings that shape the design

- **Buffer decision:** the queue is bounded by count, not by age. Timestamps are preserved, so buffering longer does not distort data. A disk-backed queue only if needed.
- **Core integration, buffering:** batches of up to 100 points or 1 s of quiet, unbounded queue, events older than 30 s (plus retries) are dropped, `max_retries` defaults to 0, invalid batches are not retried, unknown/empty/unavailable states are skipped. Source: Home Assistant Core `influxdb/__init__.py` and `const.py`.
- **Core integration, configuration:** filters are YAML only, and every change needs a restart. This is the reason for this project.
- **Core integration, schema:** audited from the source code and checked against real data from a bucket (10 entity types identical), see [docs/core-schema-audit.md](docs/core-schema-audit.md). There are no existing Grafana queries to check (maintainer, 2026-11-23).

---

## M0 – Foundation

- [x] **Project name:** Influx Picker, domain `influx_picker` (changing it later means setting the integration up again).
- [x] **Project structure:** HACS-ready repository, config-entry based (`runtime_data`), de/en translations.
- [x] **Neutral data model:** `Point` (measurement, tags, fields, timestamp), independent of the InfluxDB version.
- [x] **Backend interface** and **registry** (`v1`, `v2`, `v3`): `schema()`, `async validate()`, `async write(points)`, `async close()`. A new backend is one file plus a registration.
- [x] **Config flow** with a "choose version" step, followed by the backend-specific fields.
- [x] **Exporter core:** selection, queue, batching, retry (independent of the backend).
- [x] **Decision:** internal backends only. They live in this repository and are added through pull requests. The backend interface stays clean so external plugins remain possible later.
- [x] **Multiple instances by design:** one config entry per target, no global state, label names configurable per entry.

## M1 – Compatibility with the core integration (before any data flows)

Goal: Grafana queries keep working unchanged.

- [x] **Audit:** source part and real-data part done ([docs/core-schema-audit.md](docs/core-schema-audit.md)), with golden tests from real data. No existing Grafana queries to check (maintainer, 2026-11-23). Check the schema of the current core integration (core source code plus real data from a bucket): measurement names, field names (`value`, `state`, `*_str`), tags, handling of on/off, strings, booleans and attributes.
- [x] **Golden tests:** (plus a test that compares every case with a reference copy of the core algorithm and the official client) one expected line-protocol example per case (numeric sensor, unit, binary_sensor, switch, text, attributes).
- [x] **Attribute export:** handled like in the core integration (decided). Numeric attributes as fields, strings as `*_str`; the exact rules come from the audit.
- [x] **Reproduce the core options:** set in a "Data format" step of the config flow (before the first point is written) and changeable in the options flow. Same names and defaults as the core YAML; per-entity settings are entered as YAML in the UI. `default_measurement`, `override_measurement`, `measurement_attr`, static `tags`, `tags_attributes`, `ignore_attributes`, `component_config` (`_domain`, `_glob`).
- [x] **Buffer defaults (decided):** flush after 1 s of quiet or 100 points (as in the core integration), skip rules for unknown/unavailable/empty, drop invalid batches. Queue bounded by count (default 50,000 points, about 10 MB), oldest points dropped on overflow, no extra age limit. Retry with backoff (5 s, rising to at most 60 s). Everything configurable (see M4).
- [x] **Heartbeat marking (decided):** a **field** `_heartbeat=true`, written only on heartbeat points and on the initial snapshot of a newly selected entity. No tag, so heartbeat points stay in the same series as change points and existing panels keep their continuous lines. Change points carry no extra field. Audit result: no existing panels yet, so nothing to adapt; new panels should filter by `_field`. Optional later: switchable modes (tag / off).
- [x] **Comparison tool:** `tools/compare_with_influx.py` compares the points the core integration wrote with the points Influx Picker would write for the same states (read-only), and can save the result as a golden fixture.

Acceptance: existing Grafana queries return the same results with the new data. Status: no existing queries; the schema is checked against real core data instead (golden tests).

## M2 – InfluxDB 2 backend and selection (first usable state)

- [x] **v2 backend** as the first plugin (`/api/v2/write`, token, org, bucket, SSL option, real validation of token/org/bucket during setup).
- [x] **Label selection:** two labels, chosen in the UI with Home Assistant's label selector and stored by **label ID**, so renaming a label in Home Assistant does not break the selection. Resolved through the label registry, effective on registry changes without a restart.
- [x] **Inheritance** from device and area, can be switched off.
- [x] **Initial write** for newly labelled entities.
- [x] **Snapshot after a Home Assistant restart: configurable** (option "Snapshot when Home Assistant starts": current time with `_heartbeat` (default) / own `last_updated` with field `_startup=true` / off). Background, from the first real test: after every start and every reload of the entry (for example after saving options), each selected entity gets one point with the **current time** and `_heartbeat=true`. This closes the gap the core integration leaves for states set during start, but writes the value at the wrong time and marks it as heartbeat. Alternative proposal: write the state with its own `last_updated` timestamp and **without** `_heartbeat` (an existing point is overwritten with identical values, a missing one is filled at the correct time). Cost either way: one point per selected entity per restart/reload. Decided 2026-11-23: both, as an option, plus "off".
- [x] **Heartbeat write cycle** (configurable interval, writes only if the entity wrote nothing during the interval).
- [x] **Matching tests** (unit, golden, integration against an InfluxDB 2 container in CI). Pulled forward: CI runs from M0 on.

## M3 – Change connection data, manual entity list and overview

- [x] **Change connection data** (pulled forward from M7, decided 2026-11-23): "Reconfigure" in the entry's menu for URL, token, organization, bucket and SSL. The new data is checked for real before saving (as during setup); labels and data format are kept.
- [x] **Re-authenticate:** if InfluxDB rejects the token (401/403), Home Assistant offers "Re-authenticate" by itself and asks only for the new token. Points collected meanwhile stay in memory and are written after the reload.
- [ ] **Options flow menu:** "Labels & interval" / "Manual list" / "Overview". The menu exists (entity selection, data format); manual list and overview are added here.
- [ ] **Two manual lists** (multi-select): "write on change" and "write on change + heartbeat".
- [ ] **Merging** of label and manual selection (union, heartbeat wins). A hint if a manually chosen entity is already selected through a label.
- [ ] **Overview as a list** in the options flow: counts by source (label directly, device, area, manual) and mode (change, heartbeat), plus one line per entity (entity ID, source, mode). Shortened or paged for long lists.
- [ ] **Status of manual entries:** exists / **no longer exists** / disabled.
- [ ] **Cleanup:** option "remove missing entries".
- [ ] **Repairs issue** when manually listed entities have been deleted.
- [ ] Until the panel exists (M9), the list in the options flow is the overview.

## M4 – Buffering, reliability, diagnostics

- [ ] **Configurable:** flush interval, batch size, maximum queue size (by count), backoff limits.
- [ ] **Backoff** on failure (5 s, rising to at most 60 s) instead of a fixed retry.
- [ ] **Persistent queue** (only if needed): implement only if real-world operation shows losses from longer InfluxDB outages or Home Assistant restarts during an outage.
- [ ] **Diagnostic sensors:** number of tracked entities, queue size, dropped points, write errors, last successful write.
- [x] **Flush on shutdown.**
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
- Change connection data: pulled forward to M3.
- [ ] Test multiple instances in parallel (for example InfluxDB 2 and 3), including separate labels per instance and a warning when two instances select the same entities by accident.

## M8 – Quality and release

- [ ] Unit tests with `pytest-homeassistant-custom-component`, CI with InfluxDB 1/2/3 in Docker.
- [ ] **README** with installation, data model and a dedicated section on the `_heartbeat` field: what it marks, and that queries counting events must exclude heartbeat points (Flux pivot example).
- [ ] **Trademark review:** trademark notices in README, translations and HACS metadata; product names only descriptively and with the owner named (InfluxData Inc.).
- [ ] Translations de/en, documentation, HACS metadata, real repository URLs.
- [ ] Versioning and changelog.

## M9 – Overview panel (much later, after the first release)

Goal: select and deselect entities easily, see at a glance what is exported and why.

- [ ] **WebSocket API** (admin only): list tracked entities with source (label directly, device, area, manual), mode (change, heartbeat), status and last write; add/remove manual entries; clean up missing entries. Per instance.
- [ ] **Sidebar panel** (admin only): searchable, sortable and filterable table (by source, mode, status, domain, area).
- [ ] **Switch entities on and off from the table:** toggling assigns or removes the configured label through Home Assistant's registry, or edits the manual list for entities without a unique ID. This is the main use case of the project.
- [ ] **Bulk actions:** select many rows and enable/disable them, or switch to heartbeat mode.
- [ ] **Status display:** missing manual entries clearly flagged, entities selected twice (label and manual) marked, write errors per entity if available.
- [ ] **Frontend kept simple:** a plain web component with as few dependencies and as little build tooling as feasible, so contributors can work on it.
- [ ] **Tests:** WebSocket API unit tests; manual test checklist for the panel.

---

## Recommended order

1. **M0** and **M1** (foundation and compatibility). The schema must be settled before production data is written.
2. **M2** (first usable state with InfluxDB 2).
3. **M3** (change connection data, manual list, overview as a list) and **M4** (buffering, diagnostics).
4. **M5**, **M6** (InfluxDB 1 and 3).
5. **M7**, **M8** in parallel as needed.
6. **M9** (panel) much later, after the first release.

## Decided

- **Plugins:** internal only for now (see M0).
- **Multiple instances:** supported by design, one config entry per target (see M0, M7).
- **Attributes:** like the core integration (see M1).
- **Heartbeat marking:** field `_heartbeat`, no tag (see M1).
- **Overview:** starts as a list in the options flow (M3). The dedicated panel comes much later (M9).

## Open questions

1. **Trademark risk on publication:** "Influx" in the name may conflict with InfluxData's trademark guidelines when the project is public. Check before publishing, keep to descriptive use only, and state that the project is not affiliated with InfluxData. Not an issue for purely private use.
