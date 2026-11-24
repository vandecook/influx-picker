# Changelog

## 0.2.0 (2026-11-24)

**Upgrade note:** the project was renamed from Influx Picker to Series Picker
(domain `series_picker`, repository `series-picker`), to follow InfluxData's
trademark guidelines. Home Assistant treats it as a new integration: remove
Influx Picker and set Series Picker up again; labels and data in InfluxDB
stay. See the installation guide.

- Integration icon (light and dark), shown in Home Assistant 2026.3 and
  later.
- Diagnostic sensors per entry: tracked entities, queued points, points
  written, dropped points, write errors, last successful write.
- Each label field can now hold several labels. Entries saved with a single
  label keep working. This also avoids a display problem where the options
  form showed a valid label as "Unknown item".
- InfluxDB 1.x and 3.x backends: planned, but on hold until someone who uses
  them contributes.
- Manual list (write on change / write on change plus heartbeat) for entities
  that cannot carry labels. Merged with the label selection; heartbeat wins.
  Entries that do not exist yet are written as soon as they appear; renamed
  entity IDs are followed.
- Overview in the options: counts by source and mode, one line per entity,
  status of manual entries.
- Repairs notice when manually listed entities no longer exist, with a fix
  that removes them.
- Options menu: "Labels and interval", "Manual list", "Overview", "Data format".
- Change the connection (URL, organization, bucket, token, certificate check)
  with "Reconfigure", without setting the integration up again. An empty
  token keeps the current one.
- If InfluxDB rejects the token, Home Assistant asks for a new one
  ("Re-authenticate"), at start and while running. Points collected meanwhile
  are kept in memory and written after the new token works.

## 0.1.0 (2026-11-23)

First release. InfluxDB 2.x only.

- Select entities with two labels (write on change / write on change plus
  heartbeat), stored by label ID; labels on devices and areas count too
  (can be switched off). Changes take effect without a restart.
- Same schema as the core `influxdb` integration; its YAML options
  (`measurement_attr`, `default_measurement`, `override_measurement`, `tags`,
  `tags_attributes`, `ignore_attributes`, `component_config`, `_domain`,
  `_glob`) are set in the UI.
- Heartbeat writes for idle entities, marked with the field `_heartbeat=true`.
- Configurable snapshot at Home Assistant start: current time with
  `_heartbeat`, the state's own timestamp with `_startup`, or off.
- Batching (1 s or 100 points), bounded buffer (50,000 points), retry with
  backoff, flush on shutdown.
- Multiple instances, one per bucket or server.
- English and German translations.

Tested with automated tests (including a live InfluxDB 2 in CI) and in one
real installation.

---

InfluxDB® is a trademark registered by InfluxData Inc., which is not
affiliated with, and does not endorse, this project.
