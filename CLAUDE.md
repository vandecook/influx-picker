# Series Picker: project brief (CLAUDE.md)

Hand-over document. Everything decided so far, in one place. Read it fully before writing code.

## 1. What this is

A **Home Assistant custom integration** that writes only selected entities to InfluxDB, selected through **Home Assistant labels** (plus a manual list), with changes taking effect **immediately, without restarting Home Assistant**.

- Repository: https://github.com/vandecook/series-picker (MIT license, owner `vandecook`)
- Name: **Series Picker**, domain `series_picker`, repo `series-picker` (renamed from Influx Picker / `influx_picker` on 2026-11-24 for trademark reasons; the GitHub repository rename is done by the maintainer)
- Docs: README.md (en), README.de.md (de), ROADMAP.en.md (en), ROADMAP.de.md (de). Code for M0 exists on branch `m0-foundation`.
- Language: the maintainer talks to you in **German**. Repository documentation, code comments, commit messages and UI source strings are **English**. German translation files are provided too.
- The maintainer has little time and no deep expertise to review or test. **Automated tests are therefore the main safety net.** Be honest in docs about what is tested.

## 2. Why

The core `influxdb` integration filters only via YAML (`include`/`exclude` with entities, domains, entity_globs) and every change needs a Home Assistant restart. It cannot filter by label, area or group.

## 3. Requirements

1. Supports InfluxDB **1.x, 2.x, 3.x**, but **implement InfluxDB 2 first**. 1.x and 3.x come later as **backend plugins**. Status 2026-11-24: 1.x and 3.x stay planned but are **on hold** (maintainer does not use them); contributions welcome.
2. **Maximum compatibility with the core integration** (schema, behavior, defaults) so existing Grafana queries and dashboards need as few changes as possible.
3. **Two labels**, suggested names `influx` (write on change) and `influx-heartbeat` (write on change plus periodic heartbeat). The heartbeat label alone is enough (it implies export). Since 2026-11-24 each of the two fields holds a **list** of label IDs (several labels per mode); old single string values are still read (`selection.label_lists`).
4. A **manual entity list** in the config/options flow for entities that cannot carry labels (for example entities without a unique ID).
5. An **overview** of selected (label) and manually listed entities. For manual entries, show whether the entity still exists.
6. **Multiple instances** by design: one config entry per target, each with its own labels.
7. **Trademark hygiene**, see section 9.

## 4. Decisions (final unless the maintainer changes them)

| Topic | Decision |
|---|---|
| Plugins | **Internal only.** Backends live in this repo. Keep the backend interface clean so external plugins stay possible later. |
| Label selection | Chosen in the UI with Home Assistant's **label selector**, stored by **label ID** (not name), so renaming a label in HA does not break anything. Resolve through the label registry. |
| Inheritance | Labels on the **device** and **area** also apply to an entity. Can be switched off. |
| Heartbeat marking | A **field `_heartbeat=true`** on heartbeat points and on the initial snapshot of a newly selected entity. **No tag.** Change points carry no extra field. Reason: a tag would split the series and cause duplicate lines in existing Flux panels. Optional later: switchable modes (tag / off). |
| Attributes | Handled **like the core integration** (exact rules come from the M1 audit). |
| Batching | Flush after **1 s of quiet or 100 points** (as in the core integration). |
| Buffer | Bounded by **count**: default **50,000 points** (about 10 MB), oldest dropped on overflow, **no age limit** (timestamps are preserved, so buffering longer distorts nothing). |
| Retry | **Backoff 5 s rising to max 60 s.** Invalid batches (HTTP 400/413/422) are dropped, not retried. |
| Skipped states | `unknown`, `unavailable`, empty: not written (like core). |
| Persistence | A disk-backed queue **only if** real-world outages show a need. |
| Overview | Starts as a **list in the options flow** (M3). A dedicated sidebar **panel** with switches is **M9, much later**, after the first release. |
| Dependencies | Prefer talking to InfluxDB over HTTP with Home Assistant's aiohttp client session (line protocol). Avoid pinning `influxdb-client` unless needed. |

## 5. Known facts about the core integration (from its source)

Source: Home Assistant Core `homeassistant/components/influxdb/__init__.py` and `const.py`.

- Batches up to `BATCH_BUFFER_SIZE = 100` points, or after `BATCH_TIMEOUT = 1` s of quiet.
- Queue is an unbounded `SimpleQueue`. Events older than `queue_seconds = QUEUE_BACKLOG_SECONDS (30) + max_tries * RETRY_DELAY (20)` are dropped with a warning.
- `max_retries` defaults to 0 (a single attempt). On a connection error with retries left it sleeps `RETRY_DELAY` and retries; on the last failure the batch is discarded.
- A `ValueError` (invalid input) is logged and the batch is not retried.
- Events with a missing, unknown, empty or unavailable new state are skipped; the include/exclude filter is applied in `event_to_json`.
- Core options to reproduce (verify in the audit): `default_measurement`, `override_measurement`, `measurement_attr`, `tags`, `tags_attributes`, `ignore_attributes`, `component_config` (+ `_domain`, `_glob`), include/exclude filters.
- **The exact schema (measurement names, field names such as `value`, `state`, `*_str`, tags such as `domain`, `entity_id`, handling of on/off, strings, booleans, attributes) is NOT verified.** Verify it against the core source and real data before writing any data (M1).

## 6. Architecture sketch

- **Config-entry based**, `entry.runtime_data`, no global state (multiple instances).
- **Neutral `Point` model** (measurement, tags, fields, timestamp), independent of the InfluxDB version.
- **Backend interface + registry** (`v1`, `v2`, `v3`): `schema()` (config-flow fields), `async validate()`, `async write(points)`, `async close()`. A new backend is one file plus a registration. Shared line-protocol serializer for v1/v2/v3.
- **Config flow**: step 1 choose version, step 2 backend-specific fields (from `schema()`), then labels and heartbeat interval. **Options flow** for labels, interval, manual lists, inheritance, overview.
- **Exporter core** (backend independent): selection, queue, batching, backoff.

### Technical notes from a discarded prototype (untested; verify against current Home Assistant APIs)

- Listen to `EVENT_STATE_CHANGED` with `event_filter` (must be a `@callback`) to cheaply ignore untracked entities.
- Rebuild the tracked set when the registries change: entity registry, device registry, area registry, **label registry** update events. Debounce (about 1 s) because registry events come in bursts.
- Entity labels: `entity_entry.labels`; also union with the device's labels and the area's labels (entity area, else device area) when inheritance is on. Skip disabled entities.
- Only entities in the entity registry (with a unique ID) can carry labels; others need the manual list.
- Newly tracked entities get one initial write of the current state (marked as heartbeat).
- Heartbeat: a timer (about every 60 s) writes entities whose last write is older than the configured interval; changes also reset that clock.
- Writing: POST to `/api/v2/write?org=&bucket=&precision=us` with `Authorization: Token ...`, line protocol body, 204 = success. Log a failure once, then at debug level; log recovery.
- Line protocol escaping: measurement escapes `,` and space; tag keys/values escape `,` `=` and space; string field values escape `\` and `"` and newlines. Skip NaN/inf.
- Float values via `state_as_number` from `homeassistant.helpers.state`; non-numeric states as a string field.
- Flush on shutdown (`EVENT_HOMEASSISTANT_STOP`) and on unload.
- The setup check should validate token, org and bucket for real (a plain `/health` check is not enough).
- Home Assistant APIs change between versions: check names and signatures (`runtime_data`, `OptionsFlow`, label selector, registry event constants) against the current docs before relying on them.

## 7. Milestones

- **M0 Foundation:** project structure (HACS-ready), neutral Point model, backend interface and registry, config flow with version step, exporter core, multi-instance by design.
- **M1 Compatibility:** audit of the core schema, golden tests (one expected line-protocol example per case: numeric sensor, unit, binary_sensor, switch, text, attributes), attribute export, core options, buffer defaults, `_heartbeat` field, comparison tool. Acceptance: existing Grafana queries return the same results. Check that existing panels filter by `_field`.
- **M2 InfluxDB 2 backend + selection:** v2 backend, label selection by ID, inheritance, initial write, heartbeat cycle, tests incl. integration tests against an InfluxDB 2 container.
- **M3 Change connection + manual list + overview as a list:** reconfigure flow for connection data (URL, token, org, bucket, SSL; real validation, options kept) and reauth on 401/403 (pulled forward from M7, decided 2026-11-23), two manual lists (write on change / write on change + heartbeat), merge with labels (union, heartbeat wins), overview list with counts and per-entity lines, status of manual entries (exists / missing / disabled), cleanup of missing entries, repairs issue when manual entities were deleted.
- **M4 Buffering, reliability, diagnostics:** configurable flush interval, batch size, max queue size, backoff limits; diagnostic sensors (tracked entities, queue size, dropped points, write errors, last success); flush on shutdown; load test; optional persistent queue only if needed.
- **M5 InfluxDB 1.x backend:** `/write?db=&rp=&precision=`, optional user/password, field type conflicts (v1 rejects a type change), `/ping` plus test write, container integration test.
- **M6 InfluxDB 3 backend:** `/api/v3/write_lp?db=&precision=` with bearer token, check specifics (type conflicts, naming rules, limits), container integration test.
- **M7 Migration and convenience:** import `include` entities/domains/globs from the core YAML into the manual list or label suggestions, warning when the core integration runs in parallel (double writes), test multiple instances (incl. warning when two instances select the same entities).
- **M8 Quality and release:** CI with InfluxDB 1/2/3 in Docker, unit tests with `pytest-homeassistant-custom-component`, README section on `_heartbeat` (with a Flux pivot example), trademark review, translations de/en, HACS metadata, versioning and changelog.
- **M9 Overview panel (much later):** WebSocket API (admin only) plus a sidebar panel with a searchable table, switching entities on/off (assigns or removes the label via the registry, or edits the manual list), bulk actions, status display. Plain web component, minimal build tooling.

**Recommended order:** M0 and M1 first (the schema must be settled before production data is written), then M2, then M3 and M4, then M5 and M6, M7 and M8 as needed, M9 last. **Suggested change not yet applied:** pull the automated tests forward so golden tests and CI against InfluxDB containers run from M0/M1, not only in M8. Do this.

## 8. Heartbeat details

- Purpose: fill gaps for entities that rarely change, so dashboards and `last()` queries have continuous data, and detect dead sensors.
- Marking is a **field** `_heartbeat=true` (not a tag) on heartbeat points and on the initial snapshot of a newly selected entity.
- Queries that **count events or state changes** must exclude heartbeat points. Flux sketch (untested):
  ```flux
  from(bucket: "ha")
    |> range(start: -24h)
    |> filter(fn: (r) => r.entity_id == "my_sensor" and (r._field == "value" or r._field == "_heartbeat"))
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    |> filter(fn: (r) => not exists r._heartbeat)
  ```
- The field name must not collide with entity attributes (hence the leading underscore).

## 9. Trademarks and disclosure (important for any public text)

- InfluxDB®, InfluxData®, Telegraf™, Kapacitor™, Chronograf™ are trademarks of **InfluxData Inc.**
- Mention product names **descriptively only**, name InfluxData Inc. as the owner where a notice is needed, and never in a way that suggests affiliation or endorsement. Applies to docs, UI strings, code comments, translations, HACS metadata, repository description.
- Source: InfluxData "Guidelines for Using InfluxData Trademarks" (https://www.influxdata.com/legal/guidelines-for-using-influxdata-trademarks/, checked 2026-11-24). No InfluxData mark (and no "Influx" shortening) in the project name; use marks as adjectives with ® / ™ ("for InfluxDB®"); no InfluxData logos.
- Every page (Markdown file) that names an InfluxData mark ends with the notice: "InfluxDB® and InfluxData® are trademarks registered by InfluxData Inc., which is not affiliated with, and does not endorse, this project." (German: "… sind eingetragene Marken der InfluxData Inc., die mit diesem Projekt nicht verbunden ist und es nicht unterstützt.")
- Keep the disclaimer in the README.
- The README says honestly that the code is AI-generated and **not** thoroughly reviewed or tested. Keep that statement true: update it only when it changes.

## 10. Open questions

1. None. (The trademark question was resolved on 2026-11-24 by renaming to Series Picker.) Everything is decided. Anything that comes up during the M1 audit that contradicts a decision above must be raised with the maintainer, not silently changed (especially the `_heartbeat` field if existing panels do not filter by `_field`).

## 11. Working agreements

- Talk to the maintainer in German, keep it concise and plain. Docs and code in English.
- Do not claim anything works unless it has been run. Say plainly what was and was not tested.
- Keep README.md, README.de.md, ROADMAP.en.md and ROADMAP.de.md in sync with decisions. Update all four together.
- Work on branches and open pull requests; do not push to `main` directly.
- Commit messages: English, short. Do not commit secrets or tokens.
- Things Home Assistant objects created by AI (entities, helpers, automations) get a **label** in Home Assistant (not a name suffix). Relevant if you create such objects during testing.
- Setting GitHub topics and the repository description is done by the maintainer in the GitHub UI (suggested topics: `home-assistant`, `homeassistant`, `home-assistant-custom-component`, `custom-integration`, `hacs`, `influxdb`, `influxdb2`, `labels`, `time-series`, `grafana`).

## 12. Next step

Start with **M0 and M1**, with tests first: Point model, backend interface and registry, v2 line-protocol serializer with golden tests, and the compatibility audit of the core integration's schema. Ask the maintainer for a sample of real data from their existing InfluxDB 2 bucket (a few points per entity type, as line protocol or a Flux export) and example Grafana queries, so the audit can be done against real data.
