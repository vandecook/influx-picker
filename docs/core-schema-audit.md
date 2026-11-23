# Audit: data schema of the core `influxdb` integration

Status: **done.** Source audit, real-data check (2026-11-23, see section 10).
There are no existing Grafana queries to check (section 9).

This document records how the Home Assistant core `influxdb` integration turns a
state change into an InfluxDB® point. Influx Picker reproduces these rules so
existing queries and dashboards keep working. Every rule below is covered by a
golden test in `tests/test_schema_golden.py` (expected line protocol per case).

Sources read on 2026-11-17:

- `homeassistant/components/influxdb/__init__.py` (`_generate_event_to_json`,
  `get_influx_connection`, `InfluxThread`) and `const.py`, branch `dev`.
- `homeassistant/helpers/state.py` (`state_as_number`), branch `dev`.
- `influxdb_client/client/write/point.py` (`Point.from_dict`,
  `to_line_protocol`), branch `master` of the official Python client. The core
  integration passes its dicts to this client for InfluxDB 2, so this file
  decides the exact line protocol.

The rules were then compared with real data from the maintainer's bucket
(section 10).

## 1. Skipped states

No point is written when the new state is missing or its state is `unknown`,
`unavailable`, the empty string, or `None`.

## 2. Measurement

Options: `override_measurement`, `measurement_attr` (default
`unit_of_measurement`), `default_measurement`, per-entity `override_measurement`
in `component_config` / `component_config_domain` / `component_config_glob`.

Order:

1. Per-entity `override_measurement` (from `component_config*`), if not empty.
2. Global `override_measurement`, if set.
3. Depending on `measurement_attr`:
   - `unit_of_measurement` (default): the value of that attribute.
   - `domain__device_class`: `<domain>__<device_class>`, or only `<domain>`
     when the entity has no device class.
   - `entity_id`: the full entity ID (`sensor.kitchen_temp`).
4. If that gives `None` or `""`: `default_measurement` if set, else the **full
   entity ID**.

Line breaks in the measurement are replaced by spaces.

## 3. Tags

- `domain`: the domain (`sensor`).
- `entity_id`: the **object ID only**, without the domain (`kitchen_temp`).
- Every attribute listed in `tags_attributes` becomes a tag instead of a field
  (string values with line breaks replaced by spaces).
- Static `tags` from the config are applied **last**, so they override the
  above (even `domain` / `entity_id`).
- The client drops tags whose value is `None` or the empty string.

## 4. Fields from the state

`float(state)` is tried first:

| State | Fields |
|---|---|
| numeric, for example `21.5` | `value=21.5` (float) |
| `on`, `locked`, `above_horizon`, `open`, `home` | `state="on"` and `value=1` |
| `off`, `unlocked`, `below_horizon`, `closed`, `not_home` | `state="off"` and `value=0` |
| anything else, for example `heat` | `state="heat"` only |

`value` is always a float (`21`, not `21i`). Strings in `state` have line breaks
replaced by spaces.

## 5. Fields from attributes

For each attribute (in the entity's attribute order):

1. In `tags_attributes`: becomes a tag (see above), not a field.
2. Skipped: `unit_of_measurement` when it was used as the measurement;
   `device_class` when it was used in a `domain__device_class` measurement;
   any key in the global or per-entity `ignore_attributes`.
3. If the key already exists as a field (`state`, `value`, or a previous
   attribute), it gets a trailing `_` (`value_`).
4. `float(value)` is tried. Booleans therefore become `1` / `0` floats.
5. If that fails, the field `<key>_str` gets `str(value)` (line breaks replaced
   by spaces). Lists and dicts are written as their Python `str()` form.
   If the string matches `^[^.]*\d+\.?\d+[^.]*$`, the key **also** gets a float
   made of the string with every character except digits and `.` removed
   (`"12 min"` gives `x=12` and `x_str="12 min"`).
6. Non-finite floats (`nan`, `inf`) are removed.

Finally a field named `time` is renamed to `time_` (more underscores if needed),
because InfluxDB reserves it.

## 6. Line protocol details (from the Python client)

- Tags and fields are **sorted by key**.
- Measurement escapes `,`, space, `\n`, `\t`, `\r`. `=` and `\` are not escaped.
- Tag keys, tag values and field keys escape `,`, `=`, space, `\n`, `\t`, `\r`.
  A tag value that ends with `\` gets a trailing space.
- String fields escape `"` and `\`.
- Floats use Python's `str()`, a trailing `.0` is removed (`21.0` → `21`).
  Large and small numbers use exponent notation (`1e+16`).
- Booleans are written as `true` / `false`.
- A point without fields is not written.
- Timestamp: the event's `time_fired`. Default precision is nanoseconds; the
  optional `precision` option (`s`, `ms`, `us`, `ns`) truncates.

## 7. Buffering (for reference)

- Batches of up to 100 points, flushed after 1 s without a new event.
- Unbounded queue; events older than 30 s plus `max_retries × 20 s` are dropped.
- `max_retries` defaults to 0. HTTP 400 means invalid data and is not retried.

## 8. Where Influx Picker deviates on purpose

- Heartbeat points and the initial snapshot carry the extra field
  `_heartbeat=true` (decision in the roadmap). Change points are identical to
  core points.
- Buffering: queue bounded by count (50,000), backoff 5 s to 60 s, no age limit.
  HTTP 400, 413 and 422 drop the batch.

## 9. Open points

1. ~~Do the maintainer's points match sections 3 to 6?~~ Yes, see section 10.
2. ~~Which YAML options does the maintainer use?~~ Derived from the data, see
   section 10.
3. Do the existing Grafana panels filter by `_field`? If not, the extra
   `_heartbeat` field shows up as its own series in those panels, and the
   heartbeat decision must be revisited with the maintainer. **Answer
   (2026-11-23):** the maintainer has no existing Grafana queries, so nothing
   needs to be adapted and the `_heartbeat` field decision stands.

## 10. Real-data check (2026-11-23)

Data: the maintainer's InfluxDB 2.7 bucket, written by the core integration of
Home Assistant 2026.11.2. Read-only access.

### Method

1. Schema overview with Flux (`schema.measurements`, `schema.tagKeys`,
   `schema.tagValues`, `schema.fieldKeys`) and the latest point per domain.
2. `tools/compare_with_influx.py`: for a set of entities, take the current state
   from Home Assistant, build the point with `schema.state_to_point`, and read
   the point the core integration wrote **at exactly the same timestamp**
   (`last_updated`, ±1 µs). Measurement, tags, field names, values and field
   types are compared.
3. The result was saved as a golden fixture
   (`tests/fixtures/real_data_2026-11-23.json`, written by the tool's `--dump`
   option, not by the code under test) and is checked by
   `tests/test_schema_real_data.py`.

### Options the maintainer uses (derived from the data)

- `default_measurement: units` (no measurement named after an entity ID exists;
  entities without a unit are in `units`).
- `tags: {source: HA}` (every Home Assistant point has the tag `source=HA`).
- `tags_attributes: [friendly_name]` (`friendly_name` is a tag, never a field).
- `measurement_attr` is the default (measurements are units such as `W`, `°C`).
- No `ignore_attributes` visible in the compared entities.
- An `include`/`exclude` filter is in use: for example `device_tracker`,
  `automation`, `script` and `update` entities are not in the bucket.

### Result

All 10 compared entities are identical (measurement, tags, every field, every
field type): `switch`, `cover`, `binary_sensor` with many attributes, `sensor`
without unit, `sensor` with unit, `weather`, `input_datetime`, `counter`,
`media_player`, `sun`.

This confirms in particular:

- Tag `entity_id` is the object ID without the domain.
- `value` is always a float; on/off-like states also get `state` as a string.
- Numeric attributes (including booleans) become float fields; other values
  become `<key>_str`, and digit-containing strings additionally get the
  digits-only float (for example `device_id` and timestamps).
- Datetime attributes are written with `str()` (space between date and time),
  not in ISO form with `T`. The Home Assistant REST API shows them with `T`, so
  test inputs must use the real datetime object.
- `None` attributes become the string `"None"`, empty strings stay empty string
  fields, lists and tuples use their Python `str()` form.
- Timestamps are the state's `last_updated` with microsecond resolution.

### Observations that are not schema questions

- **States set during a Home Assistant restart are missing.** One compared
  entity (`input_number`, state set at 19:02:33 UTC on 2026-11-17) has no point
  at all. The bucket has no Home Assistant points between 19:02:00 and
  19:02:30 that day: the core integration was not listening yet. Influx Picker
  writes an initial snapshot for newly tracked entities; whether it should also
  write one after every restart is a question for M2.
- The bucket also holds InfluxDB's own metrics (`go_*`, `storage_*`, …), not
  from Home Assistant. They have no `domain` tag and do not affect this audit.
- Measurements mix float and string fields (for example `value` and `state`
  in `units`). Flux queries without a `_field` filter fail with "schema
  collision" in some functions (seen with `limit()` after `group()`). This is
  existing behaviour of the core data, not caused by Influx Picker.
