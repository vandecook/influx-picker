# Changelog

## Unreleased

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
