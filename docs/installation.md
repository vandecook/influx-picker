# Installation and settings

**English** · [Deutsch](installation.de.md) · [README](../README.md)

This guide walks through installing Series Picker, setting it up, and every
setting it has. It is based on a first real installation in the maintainer's
Home Assistant (2026-11-23).

> **Early version.** The code is largely AI-generated and not thoroughly
> reviewed (see the [status note](../README.md)). Start with a **test
> bucket**, not your production data.

> **Coming from Influx Picker 0.1.0?** The project was renamed to Series
> Picker, and the integration domain changed from `influx_picker` to
> `series_picker`. Home Assistant treats it as a new integration: delete the
> old Influx Picker entry, remove the old repository in HACS (or delete
> `custom_components/influx_picker`), install Series Picker as described
> below and set it up again. Your labels and the data in InfluxDB stay as
> they are; choose the same labels and data format again.

## Contents

1. [Before you start](#1-before-you-start)
2. [Install](#2-install)
3. [Set up](#3-set-up)
4. [Select entities](#4-select-entities)
5. [Change settings later](#5-change-settings-later)
6. [All settings](#6-all-settings)
7. [Coming from the core `influxdb` integration](#7-coming-from-the-core-influxdb-integration)
8. [Check that it works](#8-check-that-it-works)
9. [Troubleshooting](#9-troubleshooting)
10. [Remove](#10-remove)

## 1. Before you start

You need:

- **Home Assistant 2026.10 or newer.**
- **HACS** (on Home Assistant 2026.11 and newer: the built-in **Marketplace**),
  or access to the `config` folder for a manual install.
- An **InfluxDB® 2.x** server. InfluxDB 1.x and 3.x are not supported (planned, but on hold
  until someone who uses them contributes).
- In InfluxDB:
  - the **organization** (name or ID),
  - a **bucket** to write to (for a first test, create a separate one, for
    example `ha_test`),
  - an **API token with write permission** for that bucket.

The token only needs write access to this one bucket. A token with more rights
works but is not needed.

## 2. Install

### With HACS / Marketplace (recommended)

1. Open **HACS** (or **Settings → Marketplace**).
2. Menu (three dots, top right) → **Custom repositories**.
3. Repository `https://github.com/vandecook/series-picker`, type
   **Integration**, then **Add**.
4. Search for **Series Picker**, open it, click **Download**.
5. **Restart Home Assistant.**

HACS installs the latest release. Updates show up in HACS like for any other
integration.

### Manually

1. Download the repository (**Code → Download ZIP**).
2. Copy `custom_components/series_picker` into the `custom_components` folder of
   your Home Assistant configuration, so that
   `config/custom_components/series_picker/manifest.json` exists.
3. **Restart Home Assistant.**

## 3. Set up

### 3.1 Create labels

Series Picker writes entities that carry one of its labels. There are **two
fields**, one per mode, and each can hold one or more labels. Create the labels
first: **Settings → Areas, labels & zones → Labels → Create label**.

| Label (suggestion) | Effect |
|---|---|
| `influx` | Write on every change. |
| `influx-heartbeat` | Write on every change **and** again periodically while nothing changes (heartbeat). |

Names are free. Series Picker stores the label's **ID**, so renaming a label
later does not break anything. You can also fill only one of the two fields,
or put several labels into one field (for example existing labels such as
`pv` or `heat-pump`).

### 3.2 Add the integration

**Settings → Devices & services → Add integration → Series Picker.** The setup
has four steps.

**Step 1: Database version.** Choose **InfluxDB 2.x**.

**Step 2: Connection.**

| Field | Example | Note |
|---|---|---|
| URL | `http://192.168.1.10:8086` | Address of the InfluxDB server, with port. |
| Organization | `home` or `0123456789abcdef` | Name **or** ID. If the token is not allowed to list organizations, use the ID (InfluxDB UI → organization → About). |
| Bucket | `ha_test` | Must exist. |
| API token | | Needs write permission for the bucket. |
| Verify SSL certificate | on | Only relevant for `https`. Turn off for self-signed certificates. |

The connection is checked with a **real write request**, so a wrong token,
organization or bucket is reported right here.

**Step 3: Entity selection.** Choose the labels for both modes, the heartbeat interval,
whether labels of devices and areas count, and what is written at start. Details in
[section 6.1](#61-entity-selection).

**Step 4: Data format.** Decides how points look in InfluxDB.

The form comes **pre-filled** with `default_measurement: units`, the static
tag `source=HA` and `friendly_name` as a tag. These are common settings, **not**
the core defaults (the core integration leaves all three empty).

- **New to InfluxDB:** keep the pre-filled values or clear them.
- **Coming from the core `influxdb` integration:** copy your YAML values here
  and clear pre-filled fields that are not in your YAML
  (see [section 7](#7-coming-from-the-core-influxdb-integration)).
  **Do this now**, before data flows. Otherwise the first points use the
  defaults and end up in different measurements than your existing data.

## 4. Select entities

Put a label on an **entity**, a **device** or an **area**:

- **Entity:** entity settings (gear icon) → **Labels**.
- **Device:** device page → pencil → **Labels**. Applies to all its entities.
- **Area:** area settings → **Labels**. Applies to all entities in the area
  (entity area, otherwise device area).

Changes take effect **within about a second, without a restart**. A newly
selected entity gets one write of its current state right away (marked as
heartbeat, see [section 6.1](#61-entity-selection)).

**Limits:**

- Only entities with a **unique ID** can carry labels. Some entities have none
  (for example `sun.sun` or entities from YAML without `unique_id`). Use the
  **manual list** for these (see below).
- **Disabled** entities are not written.
- States `unknown`, `unavailable` and empty states are never written (same as
  the core integration).

### Manual list

**Settings → Devices & services → Series Picker → Configure → Manual list.**
Two lists: **Write on change** and **Write on change and heartbeat**. They work
in addition to the labels. If an entity is selected twice, heartbeat wins. The
form shows which listed entities no longer exist and which a label selects
anyway.

- An entity that does not exist (yet) stays in the list and is written as soon
  as it appears.
- If a listed entity is gone after Home Assistant has started, a **repairs
  notice** appears (Settings → System → Repairs). Its fix removes the missing
  entries. The manual list form offers the same with **Remove entries that no
  longer exist**.
- If you rename an entity ID, the list follows automatically.
- With entries in the manual list, the labels may be left empty.

### Overview

**Configure → Overview** lists everything that is written: counts by source
(label on the entity, device, area, manual list) and mode (on change,
heartbeat), then one line per entity. Manual entries that no longer exist or
are disabled are marked. Long lists are cut after 100 lines.

## 5. Change settings later

**Settings → Devices & services → Series Picker → Configure.** A menu opens:

- **Labels and interval:** labels, heartbeat interval, inheritance, snapshot.
- **Manual list:** see [section 4](#4-select-entities).
- **Overview:** what is written and why (read only).
- **Data format:** all data format options.

Saving reloads the integration, no Home Assistant restart needed. After the
reload every selected entity gets one snapshot again, depending on
**Snapshot when Home Assistant starts** (see [section 6.1](#61-entity-selection)).

### Change the connection (URL, token, …)

**Settings → Devices & services → Series Picker → ⋮ → Reconfigure.** Change
URL, organization, bucket, token or the certificate check. Leave the token
empty to keep the current one. The new connection is checked with a real write
request before it is saved; labels and data format stay as they are. If you
change the bucket, the integration writes to the new bucket from then on
(nothing is copied over).

**Token rejected:** if InfluxDB rejects the token (for example after it was
deleted or replaced), Home Assistant shows a **Re-authenticate** notice under
Settings → Devices & services. It asks only for the new token. This happens at
start as well as while running. Points collected while the token was rejected
stay in memory (up to the buffer limit) and are written once the new token
works, unless Home Assistant is restarted in between.

## 6. All settings

### 6.1 Entity selection

| Setting | Default | Meaning |
|---|---|---|
| Labels: write on change | – | Entities with one of these labels are written on every state or attribute change. |
| Labels: write on change and heartbeat | – | Like above, plus a heartbeat write when nothing was written during the interval. If an entity has labels from both fields, heartbeat wins. |
| Heartbeat interval | 15 min | 1 to 1440 minutes. Checked once per minute, so a heartbeat comes up to one minute late. |
| Include labels of the device and area | on | Off: only labels on the entity itself count. |
| Snapshot when Home Assistant starts | Current time, marked as heartbeat | See below. |

At least one label is required (or an entry in the manual list). A label can
only be in one of the two fields.

**Heartbeat and snapshot points** carry an extra field `_heartbeat=true`.
Change points do not. Points marked like this are written:

- by the heartbeat timer,
- once for each entity that becomes selected while the integration runs,
- once for every selected entity after Home Assistant starts and after the
  integration is reloaded (for example after saving options), unless
  **Snapshot when Home Assistant starts** says otherwise.

Graphs, averages and `last()` can use all points. Queries that **count
changes** must leave out points with `_heartbeat`; see
[Heartbeat marking](../README.md#heartbeat-marking) for a Flux example.

**Snapshot when Home Assistant starts** decides what is written for every
selected entity when Home Assistant starts or the integration is reloaded:

| Choice | Timestamp | Marker | Use |
|---|---|---|---|
| Current time, marked as heartbeat (default) | now | `_heartbeat=true` | A fresh point right after the start; behaves like a heartbeat. |
| Time of the last state change, marked with `_startup` | the state's `last_updated` | `_startup=true` | Fills a change that was lost around a restart at the **right** time. If the point already exists (same time), it is overwritten with the same values plus `_startup`. |
| Do not write | – | – | Nothing at start. Only real changes (and heartbeats) are written. |

Entities that become selected **later**, while the integration runs, always
get the normal heartbeat snapshot. `_startup` is a field, not a tag, for the
same reason as `_heartbeat`: a tag would split the series. A `_startup` point
usually stands for a real change, so **do not** leave it out when counting
changes. If the state is older than the bucket's retention period, InfluxDB
rejects the point.

### 6.2 Data format

Same names, meaning and defaults as the YAML options of the core `influxdb`
integration. In a **new** setup, default measurement, static tags and
attributes written as tags come pre-filled (see
[step 4](#32-add-the-integration)); the "Default" column shows the value of an
empty field.

| Setting | Core YAML option | Default | Meaning |
|---|---|---|---|
| Measurement from | `measurement_attr` | Unit of measurement | Where the measurement name comes from: the unit (`W`, `°C`), `<domain>__<device_class>` (for example `sensor__temperature`), or the entity ID. |
| Default measurement | `default_measurement` | empty | Used when the entity has no value for "Measurement from" (for example no unit). Empty means: the full entity ID (`switch.kitchen`). |
| Override measurement | `override_measurement` | empty | Writes **every** point to this one measurement. |
| Static tags | `tags` | empty | One `key=value` per line, for example `source=HA`. Added to every point. |
| Attributes written as tags | `tags_attributes` | empty | These attributes become tags instead of fields, for example `friendly_name`. Type the name and press Enter. |
| Attributes to ignore | `ignore_attributes` | empty | These attributes are not written. |
| Per entity | `component_config` | empty | YAML, see below. |
| Per domain | `component_config_domain` | empty | YAML, see below. |
| Per entity pattern | `component_config_glob` | empty | YAML, see below. |

**Per entity / domain / pattern** take a mapping to `override_measurement`
and/or `ignore_attributes`, exactly like in the core YAML:

```yaml
# Per entity
sensor.kitchen_temp:
  override_measurement: temperature
# Per domain
light:
  ignore_attributes:
    - effect_list
    - supported_color_modes
# Per entity pattern
"sensor.*_power":
  override_measurement: power
```

If several apply, the order is: domain, then pattern, then entity (the most
specific wins), as in the core integration.

**What a point looks like** (defaults plus `default_measurement: units`,
`tags: source=HA`, `tags_attributes: friendly_name`):

```text
W,domain=sensor,entity_id=house_total_power,friendly_name=House\ Total\ Power,source=HA device_class_str="power",state_class_str="measurement",value=412 1795448400123456000
units,domain=switch,entity_id=kitchen,friendly_name=Kitchen,source=HA state="on",value=1 1795448400123456000
```

- `value`: the state as a number (on/off-like states as `1`/`0`).
- `state`: the state as text, for states that are not plain numbers.
- Attributes: numbers as fields with their name, text as `<name>_str`.
- The tag `entity_id` is the entity ID **without** the domain.

The full rules are in [docs/core-schema-audit.md](core-schema-audit.md).

## 7. Coming from the core `influxdb` integration

Goal: new points look exactly like the old ones, so queries and dashboards keep
working.

1. Open the `influxdb:` section of your `configuration.yaml` (or the included
   file).
2. Copy these values into **Data format** (setup step 4, or later via
   **Configure → Data format**):

   | In your YAML | Field in Series Picker |
   |---|---|
   | `measurement_attr: …` | Measurement from |
   | `default_measurement: units` | Default measurement: `units` |
   | `override_measurement: …` | Override measurement |
   | `tags:` `source: HA` | Static tags: `source=HA` |
   | `tags_attributes:` `- friendly_name` | Attributes written as tags: `friendly_name` |
   | `ignore_attributes:` | Attributes to ignore |
   | `component_config:` | Per entity (paste the mapping below the key) |
   | `component_config_domain:` | Per domain |
   | `component_config_glob:` | Per entity pattern |

   Options not in your YAML stay empty: the defaults are the same. Clear the
   pre-filled fields if your YAML does not have them.
3. **Test first** with a separate bucket and a few entities, compare with your
   existing data ([section 8](#8-check-that-it-works)).
4. **Avoid double writes:** as long as both integrations write the **same
   entities** to the **same bucket**, every change is written twice. Either
   remove those entities from the core integration's `include`, or use a
   separate bucket. Running both in parallel into **different** buckets is fine
   and useful for testing.

## 8. Check that it works

- **In InfluxDB:** Data Explorer → bucket → the measurement (for example `W`) →
  filter `entity_id`. A newly selected entity appears within a few seconds.
- **Flux, the last points of one entity:**

  ```flux
  from(bucket: "ha_test")
    |> range(start: -15m)
    |> filter(fn: (r) => r.entity_id == "house_total_power" and r._field == "value")
  ```

- **Compare with the core integration** (developers): `tools/compare_with_influx.py`
  compares, for given states, the points the core integration wrote with the
  points Series Picker would write (read-only).
- **Diagnostic sensors:** every entry has a device with six sensors
  (**Settings → Devices & services → Series Picker → the entry → device**,
  section "Diagnostic"). Updated every 30 seconds:

  | Sensor | Meaning |
  |---|---|
  | Tracked entities | Entities currently selected (labels and manual list). |
  | Queued points | Points waiting to be written. Rises while InfluxDB cannot be reached; at most 50,000. |
  | Points written | Points written successfully. |
  | Dropped points | Points dropped because the queue was full or InfluxDB rejected them as invalid. |
  | Write errors | Failed write attempts (each one is retried). |
  | Last successful write | Time of the last successful write. |

  The counters start at 0 when Home Assistant starts and when the entry is
  reloaded (for example after saving options). The sensors are not written
  to InfluxDB unless you give them a label.
- **Logs:** Settings → System → Logs, search for `series_picker`. Write errors
  are logged once, then only at debug level until writing works again.

## 9. Troubleshooting

| Problem | Cause / fix |
|---|---|
| Setup: "The token is invalid or has no write permission." | Token wrong or without write permission for the bucket. |
| Setup: "Organization or bucket not found." | Check spelling. If the token may not list organizations, enter the organization **ID**. |
| Setup: "Cannot connect to the server." | Check URL and port, and that Home Assistant can reach the server. |
| Notice "Re-authenticate" / "New token" | InfluxDB rejected the stored token. Create a token with write permission for the bucket and enter it ([section 5](#5-change-settings-later)). |
| Points land in measurements named after the entity ID (`switch.kitchen`) | No **default measurement** set. If you came from the core integration, copy `default_measurement` ([section 7](#7-coming-from-the-core-influxdb-integration)). |
| `friendly_name` is a field (`friendly_name_str`) instead of a tag | Add `friendly_name` to **Attributes written as tags**. |
| An entity is not written | Does it have a unique ID (otherwise no labels)? Is it disabled? Is its state `unknown`/`unavailable`? Is the label on the entity, device or area, and is inheritance on for device/area labels? |
| Options form shows a label as "Unknown item" (up to 0.1.0) | A display problem of the single-label picker in the Home Assistant frontend; the stored value was correct. Since the label fields allow several labels, a different picker is used. If it still happens, reload the page (Ctrl+F5) and please open an issue. |
| Every change appears twice | The core integration writes the same entities to the same bucket ([section 7](#7-coming-from-the-core-influxdb-integration), step 4). |

## 10. Remove

1. **Settings → Devices & services → Series Picker → ⋮ → Delete.**
2. Remove it in HACS (or delete `custom_components/series_picker`).
3. Restart Home Assistant.
4. Delete the labels if you no longer need them. Data already written stays in
   InfluxDB.

---

InfluxDB® and InfluxData® are trademarks registered by InfluxData Inc., which
is not affiliated with, and does not endorse, this project.
