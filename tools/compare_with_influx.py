"""Compare Series Picker's output with points the core integration really wrote.

For each Home Assistant state in an input file, this tool builds the point with
Series Picker's schema code and reads the point the core `influxdb` integration
wrote for the same entity at the same timestamp. It then reports differences in
measurement, tags, field names, field values and field types.

Usage (from the repository root, with the test virtualenv):

    python -m tools.compare_with_influx states.json
    python -m tools.compare_with_influx states.json --dump tests/fixtures/x.json

`--dump` writes a golden fixture for `tests/test_schema_real_data.py`: the
input states plus the point InfluxDB really holds for each of them.

Environment: INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG_ID (or INFLUX_ORG), INFLUX_BUCKET.
The token only needs read access to the bucket.

Input file (JSON):

    {
      "options": {"default_measurement": "units", "tags": {"source": "HA"},
                  "tags_attributes": ["friendly_name"]},
      "states": [
        {"entity_id": "sensor.x", "state": "1.5", "last_updated": "2026-...+00:00",
         "attributes": {"unit_of_measurement": "W",
                        "since": {"__datetime__": "2026-...+00:00"}}}
      ]
    }

The Home Assistant REST API turns datetime attributes into ISO strings, but the
core integration sees the real datetime object (its `str()` uses a space, not a
`T`). Mark such attributes with `{"__datetime__": ...}` to restore the object.

Only the standard library is used for HTTP. Nothing is written to InfluxDB.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import json
import math
import os
import sys
from typing import Any
import urllib.parse
import urllib.request

from custom_components.series_picker.schema import (
    EntityCustomization,
    SchemaOptions,
    state_to_point,
)

# Line protocol type -> Flux CSV datatype annotation.
_FLUX_TYPE = {float: "double", int: "long", bool: "boolean", str: "string"}


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__datetime__"}:
            return datetime.fromisoformat(value["__datetime__"])
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _options(raw: dict[str, Any]) -> SchemaOptions:
    raw = dict(raw)
    for key in ("component_config", "component_config_domain", "component_config_glob"):
        if key in raw:
            raw[key] = {k: EntityCustomization(**v) for k, v in raw[key].items()}
    return SchemaOptions(**raw)


def _query(env: dict[str, str], flux: str) -> list[dict[str, str]]:
    """Run a Flux query, return rows with a `_type` entry for the value column."""
    org = {"orgID": env["org_id"]} if env.get("org_id") else {"org": env["org"]}
    url = f"{env['url'].rstrip('/')}/api/v2/query?{urllib.parse.urlencode(org)}"
    body = json.dumps(
        {
            "query": flux,
            "type": "flux",
            "dialect": {"annotations": ["datatype"], "header": True},
        }
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Token {env['token']}",
            "Content-Type": "application/json",
            "Accept": "application/csv",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")

    rows: list[dict[str, str]] = []
    datatypes: list[str] = []
    header: list[str] | None = None
    for record in csv.reader(io.StringIO(text)):
        if not record or not any(record):
            header = None
            continue
        if record[0] == "#datatype":
            datatypes = record
            header = None
            continue
        if header is None:
            header = record
            continue
        row = dict(zip(header, record, strict=False))
        row["_type"] = datatypes[header.index("_value")] if datatypes else ""
        rows.append(row)
    return rows


def _flux_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _same_value(expected: Any, actual: str, flux_type: str) -> bool:
    if flux_type == "double":
        actual_f = float(actual)
        return math.isclose(float(expected), actual_f, rel_tol=1e-12, abs_tol=0.0)
    if flux_type == "boolean":
        return str(expected).lower() == actual
    return str(expected) == actual


def observed_point(env: dict[str, str], item: dict[str, Any]) -> dict[str, Any] | None:
    """Return the point InfluxDB holds for this state, as plain JSON data."""
    rows = _rows_for(env, item)
    if not rows:
        return None
    convert = {"double": float, "long": int, "boolean": lambda v: v == "true"}
    skip = {
        "",
        "result",
        "table",
        "_start",
        "_stop",
        "_time",
        "_value",
        "_field",
        "_measurement",
        "_type",
    }
    return {
        "measurement": rows[0]["_measurement"],
        "tags": {k: v for k, v in rows[0].items() if k not in skip and v != ""},
        "fields": {
            r["_field"]: convert.get(r["_type"], str)(r["_value"]) for r in rows
        },
    }


def _rows_for(env: dict[str, str], item: dict[str, Any]) -> list[dict[str, str]]:
    time = datetime.fromisoformat(item["last_updated"])
    domain, object_id = item["entity_id"].split(".", 1)
    start = (time - timedelta(microseconds=1)).isoformat()
    stop = (time + timedelta(microseconds=1)).isoformat()
    flux = (
        f"from(bucket: {_flux_string(env['bucket'])})"
        f" |> range(start: time(v: {_flux_string(start)}), stop: time(v: {_flux_string(stop)}))"
        f" |> filter(fn: (r) => r.domain == {_flux_string(domain)}"
        f" and r.entity_id == {_flux_string(object_id)})"
    )
    return _query(env, flux)


def compare_one(
    env: dict[str, str], options: SchemaOptions, item: dict[str, Any]
) -> list[str]:
    """Return a list of differences for one state (empty = identical)."""
    time = datetime.fromisoformat(item["last_updated"])
    point = state_to_point(
        item["entity_id"],
        item["state"],
        _decode(item.get("attributes", {})),
        time,
        options,
    )
    rows = _rows_for(env, item)

    if point is None:
        return [f"expected no point, found {len(rows)} field(s)"] if rows else []
    if not rows:
        return ["no point found in InfluxDB at this timestamp"]

    problems: list[str] = []
    measurements = {r["_measurement"] for r in rows}
    if measurements != {point.measurement}:
        problems.append(
            f"measurement: expected {point.measurement!r}, got {sorted(measurements)}"
        )

    skip = {
        "",
        "result",
        "table",
        "_start",
        "_stop",
        "_time",
        "_value",
        "_field",
        "_measurement",
        "_type",
    }
    actual_tags = {k: v for k, v in rows[0].items() if k not in skip and v != ""}
    if actual_tags != point.tags:
        problems.append(f"tags: expected {point.tags}, got {actual_tags}")

    actual_fields = {r["_field"]: (r["_value"], r["_type"]) for r in rows}
    for key in sorted(set(point.fields) - set(actual_fields)):
        problems.append(
            f"field {key!r} missing in InfluxDB (expected {point.fields[key]!r})"
        )
    for key in sorted(set(actual_fields) - set(point.fields)):
        problems.append(f"extra field {key!r} in InfluxDB: {actual_fields[key][0]!r}")
    for key in sorted(set(point.fields) & set(actual_fields)):
        expected = point.fields[key]
        actual, flux_type = actual_fields[key]
        want_type = _FLUX_TYPE[type(expected)]
        if flux_type != want_type:
            problems.append(
                f"field {key!r}: type {want_type} expected, got {flux_type}"
            )
        elif not _same_value(expected, actual, flux_type):
            problems.append(f"field {key!r}: expected {expected!r}, got {actual!r}")
    return problems


def main(argv: list[str]) -> int:
    dump_to = None
    if len(argv) == 4 and argv[2] == "--dump":
        dump_to = argv[3]
        argv = argv[:2]
    if len(argv) != 2:
        print(__doc__)
        return 2
    env = {
        "url": os.environ.get("INFLUX_URL", ""),
        "token": os.environ.get("INFLUX_TOKEN", ""),
        "org_id": os.environ.get("INFLUX_ORG_ID", ""),
        "org": os.environ.get("INFLUX_ORG", ""),
        "bucket": os.environ.get("INFLUX_BUCKET", ""),
    }
    if not (
        env["url"] and env["token"] and env["bucket"] and (env["org_id"] or env["org"])
    ):
        print(
            "Set INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG_ID or INFLUX_ORG, INFLUX_BUCKET."
        )
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    options = _options(data.get("options", {}))

    if dump_to:
        # Write a golden fixture: the input states plus what InfluxDB really holds.
        for item in data["states"]:
            item["observed"] = observed_point(env, item)
        with open(dump_to, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"wrote {dump_to}")
        return 0

    failed = 0
    for item in data["states"]:
        problems = compare_one(env, options, item)
        status = "OK  " if not problems else "DIFF"
        print(f"{status} {item['entity_id']}")
        for problem in problems:
            print(f"     {problem}")
        failed += bool(problems)
    print(f"\n{len(data['states']) - failed} identical, {failed} with differences")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
