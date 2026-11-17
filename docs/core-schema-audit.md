# Audit: data schema of the core `influxdb` integration

Status: **source audit done, real-data check still open.**

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

**Not yet done:** comparison with real data from the maintainer's bucket and
with real Grafana queries. Until then the rules are "as the source says", not
"as observed".

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

## 9. Open points for the real-data check

1. Do the maintainer's points match section 3 to 6 (especially `entity_id`
   without domain and measurement = unit)?
2. Which YAML options does the maintainer use (`measurement_attr`,
   `default_measurement`, `tags`, `tags_attributes`, `ignore_attributes`,
   `precision`)?
3. Do the existing Grafana panels filter by `_field`? If not, the extra
   `_heartbeat` field shows up as its own series in those panels, and the
   heartbeat decision must be revisited with the maintainer.
