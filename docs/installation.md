# Installation and settings

**English** · [Deutsch](installation.de.md) · [README](../README.md)

This guide walks through installing Influx Picker, setting it up, and every
setting it has. It is based on a first real installation in the maintainer's
Home Assistant (2026-11-23).

> **Experimental.** The code is largely AI-generated and not thoroughly
> reviewed. Read [How this project is built](../README.md#how-this-project-is-built)
> before you install it. Start with a **test bucket**, not your production data.

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
- An **InfluxDB® 2.x** server. InfluxDB 1.x and 3.x are not supported yet.
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
3. Repository `https://github.com/vandecook/influx-picker`, type
   **Integration**, then **Add**.
4. Search for **Influx Picker**, open it, click **Download**.
5. **Restart Home Assistant.**

There is no release yet, so HACS installs the current state of the `main`
branch. Updates show up in HACS like for any other integration.

### Manually

1. Download the repository (**Code → Download ZIP**).
2. Copy `custom_components/influx_picker` into the `custom_components` folder of
   your Home Assistant configuration, so that
   `config/custom_components/influx_picker/manifest.json` exists.
3. **Restart Home Assistant.**

## 3. Set up

### 3.1 Create labels

Influx Picker writes entities that carry one of **two labels**. Create them
first: **Settings → Areas, labels & zones → Labels → Create label**.

| Label (suggestion) | Effect |
|---|---|
| `influx` | Write on every change. |
| `influx-heartbeat` | Write on every change **and** again periodically while nothing changes (heartbeat). |

Names are free. Influx Picker stores the label's **ID**, so renaming a label
later does not break anything. You can also use only one of the two labels.

### 3.2 Add the integration

**Settings → Devices & services → Add integration → Influx Picker.** The setup
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

**Step 3: Entity selection.** Choose the two labels, the heartbeat interval,
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
  (for example `sun.sun` or entities from YAML without `unique_id`). A manual
  list for these is planned (roadmap M3).
- **Disabled** entities are not written.
- States `unknown`, `unavailable` and empty states are never written (same as
  the core integration).

## 5. Change settings later

**Settings → Devices & services → Influx Picker → Configure.** A menu opens:

- **Entity selection:** labels, heartbeat interval, inheritance.
- **Data format:** all data format options.

Saving reloads the integration, no Home Assistant restart needed. After the
reload every selected entity gets one snapshot again, depending on
**Snapshot when Home Assistant starts** (see [section 6.1](#61-entity-selection)).

The connection (URL, token, …) cannot be changed yet (planned for M7). To
change it, remove the integration and add it again.

## 6. All settings

### 6.1 Entity selection

| Setting | Default | Meaning |
|---|---|---|
| Label: write on change | – | Entities with this label are written on every state or attribute change. |
| Label: write on change and heartbeat | – | Like above, plus a heartbeat write when nothing was written during the interval. If an entity has both labels, heartbeat wins. |
| Heartbeat interval | 15 min | 1 to 1440 minutes. Checked once per minute, so a heartbeat comes up to one minute late. |
| Include labels of the device and area | on | Off: only labels on the entity itself count. |
| Snapshot when Home Assistant starts | Current time, marked as heartbeat | See below. |

At least one label is required. Both labels must be different.

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

   | In your YAML | Field in Influx Picker |
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
  points Influx Picker would write (read-only).
- **Logs:** Settings → System → Logs, search for `influx_picker`. Write errors
  are logged once, then only at debug level until writing works again.

## 9. Troubleshooting

| Problem | Cause / fix |
|---|---|
| Setup: "The token is invalid or has no write permission." | Token wrong or without write permission for the bucket. |
| Setup: "Organization or bucket not found." | Check spelling. If the token may not list organizations, enter the organization **ID**. |
| Setup: "Cannot connect to the server." | Check URL and port, and that Home Assistant can reach the server. |
| Points land in measurements named after the entity ID (`switch.kitchen`) | No **default measurement** set. If you came from the core integration, copy `default_measurement` ([section 7](#7-coming-from-the-core-influxdb-integration)). |
| `friendly_name` is a field (`friendly_name_str`) instead of a tag | Add `friendly_name` to **Attributes written as tags**. |
| An entity is not written | Does it have a unique ID (otherwise no labels)? Is it disabled? Is its state `unknown`/`unavailable`? Is the label on the entity, device or area, and is inheritance on for device/area labels? |
| Options form shows a label as "Unknown item" | Seen once right after the labels were created while the page was open; the stored value was correct. Reload the page (Ctrl+F5). If it stays, please open an issue. |
| Every change appears twice | The core integration writes the same entities to the same bucket ([section 7](#7-coming-from-the-core-influxdb-integration), step 4). |

## 10. Remove

1. **Settings → Devices & services → Influx Picker → ⋮ → Delete.**
2. Remove it in HACS (or delete `custom_components/influx_picker`).
3. Restart Home Assistant.
4. Delete the labels if you no longer need them. Data already written stays in
   InfluxDB.

---

InfluxDB® is a registered trademark of InfluxData Inc. This project is not
affiliated with, endorsed by, or sponsored by InfluxData Inc.
