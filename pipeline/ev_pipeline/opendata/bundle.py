"""Write data/releases/<n>/open/ (Decision 016): variants.csv, variants.json, ATTRIBUTION.md,
LICENSE, README.md.

Rules:
- One flat row per variant. Every published field is documented below with its unit.
- Each measured or derived field `<f>` has `<f>_sources` (source ids, `;`-separated) and
  `<f>_confidence` (high | medium | low | estimate). `seed_manual_fields` lists the fields
  that rest on the hand-entered `seed-manual` source (kept, but flagged; confidence low).
- Licence gate: a value is published only when every source behind it passes the registry
  gate (data/sources.yaml, Decision 009) and none is ODbL. Otherwise the value, its sources
  and its confidence are left empty and counted in README.md ("values withheld"). The
  release itself already fails on an ODbL source; this is the second guard.
- Registrations are flattened per country + kind (fleet | new_registrations): the newest
  period wins, ties by the `registered_count` source order in data/field_sources.yaml.
  `registrations_json` keeps every count (per source and period); counts are never summed.
- The brand name comes from `EV_BRAND_NAME` (config), never from code beyond a neutral
  fallback.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ev_pipeline.release.gate import CITED_FACTS, Registry, licence_problem

BRAND_ENV = "EV_BRAND_NAME"
BRAND_FALLBACK = "the EV Finder project"  # neutral fallback; real name lives in config
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"
CC_BY_LEGAL = "https://creativecommons.org/licenses/by/4.0/legalcode"
SEED_SOURCE = "seed-manual"
ESTIMATE_SOURCE = "model-estimate"

# (field, unit, description). Unit "" = no unit (text, id, flag).
IDENTITY_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("release", "", "Data release number"),
    ("variant_id", "", "Stable variant id (make-model-generation-variant)"),
    ("variant_name", "", "Variant name"),
    ("generation_id", "", "Generation id"),
    ("generation_name", "", "Generation name"),
    ("generation_uncertain", "", "true when the generation boundaries are not yet verified"),
    ("model_id", "", "Model id"),
    ("model_name", "", "Model name"),
    ("make_id", "", "Make id"),
    ("make_name", "", "Make name"),
    ("year_start", "year", "First model year of the variant"),
    ("year_end", "year", "Last model year (empty = still on sale)"),
    ("era", "", "Model-year band"),
    ("segment", "", "Market segment (A-F, J = SUV)"),
    ("body", "", "Body type"),
    ("drivetrain", "", "fwd | rwd | awd"),
    ("on_sale_new", "", "true when sold new in the last two model years"),
    ("quality_tier", "", "checked | sourced (2+ sources on battery and range) | single-source"),
)
VALUE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("battery_kwh_net", "kWh", "Usable battery capacity"),
    ("wltp_range_km", "km", "WLTP combined range"),
    ("consumption_kwh_100km", "kWh/100 km", "WLTP combined consumption"),
    ("consumption_motorway_kwh_100km", "kWh/100 km", "Motorway consumption (~120 km/h)"),
    ("real_range_km", "km", "Real-world range, mild-weather mixed driving (our model)"),
    ("real_range_rung", "", "Which rung of our real-range ladder produced real_range_km"),
    (
        "real_range_winter_km",
        "km",
        "Winter range at -5 °C and colder, mixed driving"
        " (our estimate, temperature step unvalidated)",
    ),
    ("ac_kw", "kW", "AC charging power, standard on-board charger"),
    ("ac_kw_optional", "kW", "AC charging power with the optional bigger on-board charger"),
    ("ac_km_per_h", "km/h", "km of WLTP range added per hour of AC charging"),
    ("dc_peak_kw", "kW", "DC peak charging power"),
    ("dc_peak_kw_is_claim", "", "true when the DC peak is a maker claim"),
    ("dc_avg_10_80_kw", "kW", "Average DC power from 10 to 80 % state of charge"),
    ("dc_minutes_10_80", "min", "DC charging time from 10 to 80 %"),
    ("dc_km_per_10min", "km", "Motorway km added in 10 minutes of DC charging"),
    ("dc_km_per_20min", "km", "Motorway km added in 20 minutes of DC charging"),
    ("dc_peak_held_min", "min", "Minutes within 10-80 % at >= 90 % of peak power"),
    ("dc_curve_status", "", "measured | estimated | default (generic shape)"),
    ("dc_speed_is_claim", "", "true when the DC speed figures come from a maker claim"),
    ("power_kw", "kW", "Maximum motor power"),
    ("accel_0_100_s", "s", "0-100 km/h"),
    ("boot_l", "l", "Boot volume"),
    ("length_mm", "mm", "Length"),
    ("weight_kg", "kg", "Kerb weight"),
    ("towing_kg", "kg", "Braked towing capacity"),
    ("seats", "", "Number of seats"),
    ("platform_id", "", "Platform id"),
    ("battery_pack_id", "", "Battery pack id"),
    ("chemistry_id", "", "Cell chemistry (taxonomy id)"),
    ("cooling_id", "", "Battery cooling (taxonomy id)"),
    ("cell_format", "", "Cell format"),
    ("voltage_class_id", "", "400 V / 800 V class (taxonomy id)"),
    ("voltage_nominal_v", "V", "Nominal pack voltage"),
    ("voltage_max_v", "V", "Maximum pack voltage"),
    ("charger_400v_mode", "", "How an 800 V car charges on a 400 V charger"),
    ("charger_400v_kw", "kW", "DC power on a 400 V charger"),
)
REGISTRATION_KINDS = ("fleet", "new_registrations")
# Labels with no provenance of their own: published only when this field's value is.
COMPANION_OF = {
    "real_range_rung": "real_range_km",
    "dc_peak_kw_is_claim": "dc_peak_kw",
    "dc_curve_status": "dc_avg_10_80_kw",
    "dc_speed_is_claim": "dc_avg_10_80_kw",
}
# Interim credit for RDW until Q-037 is answered (same wording as the web app, Q-050).
ATTRIBUTION_OVERRIDES = {
    "rdw": "Dutch vehicle register (RDW open data, CC0). Wording pending QUESTIONS.md Q-037.",
}
LICENCE_URLS = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": CC_BY_URL,
    "OGL-UK-3.0": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    "Licence-Ouverte-2.0": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
    "dl-de/by-2-0": "https://www.govdata.de/dl-de/by-2-0",
    "CDLA-Permissive-2.0": "https://cdla.dev/permissive-2-0/",
    "MIT-with-attribution": "https://github.com/KilowattApp/open-ev-data/blob/main/LICENSE",
}
# Notices a licence requires us to carry with copies (MIT: copyright + permission notice).
NOTICES = {
    "kilowatt-openev": (
        "MIT License with Attribution Requirement. Copyright (c) 2024 Tijs Teulings.\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy of this"
        ' software and associated documentation files (the "Software"), to deal in the'
        " Software without restriction, including without limitation the rights to use, copy,"
        " modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,"
        " and to permit persons to whom the Software is furnished to do so, subject to the"
        " following conditions: 1. The above copyright notice and this permission notice shall"
        " be included in all copies or substantial portions of the Software. 2. Attribution"
        " Requirement: any public-facing use must include clear and visible attribution to"
        ' "Open EV Data (https://github.com/KilowattApp/open-ev-data)".\n'
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.'
    ),
}


@dataclass
class Bundle:
    columns: list[str]
    rows: list[dict[str, Any]]
    sources_used: list[str]
    withheld: dict[str, int] = field(default_factory=dict)  # source id -> values withheld


def brand_name() -> str:
    env = os.environ.get(BRAND_ENV, "").strip()
    if env:
        return env
    brand_file = Path(__file__).resolve().parents[3] / "config" / "brand.yaml"
    try:
        name = (yaml.safe_load(brand_file.read_text(encoding="utf-8")) or {}).get("name")
    except OSError:
        name = None
    name = str(name).strip() if name else ""
    return name or BRAND_FALLBACK  # a blank name in config must not publish an empty brand


def source_allowed(registry: Registry, licences: dict[str, str], sid: str) -> bool:
    if not registry.releasable(sid):
        return False
    entry = registry.sources.get(registry.canonical(sid))
    if entry is not None and entry.use == CITED_FACTS:
        return False  # Decision 068: cited maker facts ship in the release, never as CC BY
    lic = licences.get(sid, "")
    return bool(lic) and "odbl" not in lic.lower() and licence_problem(lic) is None


def _period_key(period: str) -> tuple[int, int, int]:
    """Comparable end of a period: '2026-11-14', '2026-Q2', '2025', '2026-01..10'."""
    p = str(period)
    if mm := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", p):
        return int(mm[1]), int(mm[2]), int(mm[3])
    if mm := re.fullmatch(r"(\d{4})-Q([1-4])", p):
        return int(mm[1]), int(mm[2]) * 3, 31
    if mm := re.fullmatch(r"(\d{4})-\d{2}\.\.(\d{2})", p):
        return int(mm[1]), int(mm[2]), 31
    if mm := re.fullmatch(r"(\d{4})-(\d{2})", p):
        return int(mm[1]), int(mm[2]), 31
    if mm := re.match(r"(\d{4})", p):
        return int(mm[1]), 12, 31
    return 0, 0, 0


def _countries(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({cc for r in rows for cc in (r.get(key) or {})})


def build_bundle(
    catalogue: dict[str, Any],
    registry: Registry,
    registration_order: tuple[str, ...] = (),
) -> Bundle:
    rows = catalogue.get("rows", [])
    licences = {s["id"]: s.get("licence") or "" for s in catalogue.get("sources", [])}
    price_cc = _countries(rows, "price_new")
    reg_cc = _countries(rows, "registrations")
    columns = [f for f, _, _ in IDENTITY_FIELDS]
    for f, _, _ in VALUE_FIELDS:
        columns += [f] if f in COMPANION_OF else [f, f"{f}_sources", f"{f}_confidence"]
    for cc in price_cc:
        c = f"price_new_{cc.lower()}"
        columns += [c, f"{c}_currency", f"{c}_sources", f"{c}_confidence"]
    for cc in reg_cc:
        for kind in REGISTRATION_KINDS:
            c = f"reg_{cc.lower()}_{kind}"
            columns += [c, f"{c}_period", f"{c}_level", f"{c}_source"]
    columns += ["registrations_json", "seed_manual_fields", "estimate_fields"]

    used: set[str] = set()
    withheld: dict[str, int] = {}

    def allowed(sids: list[str]) -> bool:
        bad = [s for s in sids if not source_allowed(registry, licences, s)]
        for s in bad:
            withheld[s] = withheld.get(s, 0) + 1
        return not bad

    def rank(sid: str) -> int:
        return registration_order.index(sid) if sid in registration_order else 999

    def put(o: dict[str, Any], marks: dict[str, list[str]], col: str, value: Any, p: Any) -> None:
        if value is None:
            return
        sids = list((p or {}).get("source_ids") or [])
        if not sids or not allowed(sids):
            return  # untraced or gated: withheld
        o[col] = value
        o[f"{col}_sources"] = ";".join(sids)
        est = bool((p or {}).get("estimate"))
        o[f"{col}_confidence"] = "estimate" if est else (p or {}).get("confidence")
        used.update(sids)
        if SEED_SOURCE in sids:
            marks["seed"].append(col)
        if est:
            marks["estimate"].append(col)

    out_rows = []
    for r in rows:
        prov = r.get("provenance") or {}
        o: dict[str, Any] = {c: None for c in columns}
        for f, _, _ in IDENTITY_FIELDS:
            o[f] = r.get(f)
        marks: dict[str, list[str]] = {"seed": [], "estimate": []}
        for f, _, _ in VALUE_FIELDS:
            if f not in COMPANION_OF:
                put(o, marks, f, r.get(f), prov.get(f))
        for f, parent in COMPANION_OF.items():
            if o[parent] is not None:
                o[f] = r.get(f)
        for cc in price_cc:
            money = (r.get("price_new") or {}).get(cc)
            if money:
                c = f"price_new_{cc.lower()}"
                put(o, marks, c, money.get("amount"), prov.get(f"price_new.{cc}"))
                if o[c] is not None:
                    o[f"{c}_currency"] = money.get("currency")
        kept: list[dict[str, Any]] = []
        for cc in reg_cc:
            entries = [
                e
                for e in (r.get("registrations") or {}).get(cc, [])
                if allowed([str(e.get("source_id"))])
            ]
            kept += [{"country": cc, **e} for e in entries]
            used.update(str(e.get("source_id")) for e in entries)
            for kind in REGISTRATION_KINDS:
                es = [e for e in entries if e.get("kind") == kind]
                if not es:
                    continue
                best = sorted(
                    es,
                    key=lambda e: (
                        tuple(-x for x in _period_key(e.get("period", ""))),
                        rank(str(e.get("source_id"))),
                        str(e.get("source_id")),
                    ),
                )[0]
                c = f"reg_{cc.lower()}_{kind}"
                o[c] = best.get("count")
                o[f"{c}_period"] = best.get("period")
                o[f"{c}_level"] = best.get("level")
                o[f"{c}_source"] = best.get("source_id")
        o["registrations_json"] = json.dumps(kept, ensure_ascii=False, separators=(",", ":"))
        o["seed_manual_fields"] = ";".join(marks["seed"])
        o["estimate_fields"] = ";".join(marks["estimate"])
        out_rows.append(o)
    return Bundle(columns, out_rows, sorted(used), dict(sorted(withheld.items())))


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def variants_csv(b: Bundle) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(b.columns)
    for r in b.rows:
        w.writerow([_csv_cell(r[c]) for c in b.columns])
    return buf.getvalue()


def field_docs(b: Bundle) -> list[dict[str, str]]:
    docs = {f: (u, d) for f, u, d in IDENTITY_FIELDS + VALUE_FIELDS}
    out = []
    for c in b.columns:
        if c in docs:
            u, d = docs[c]
        elif c.endswith("_sources") or c.endswith("_source"):
            u, d = "", "Source id(s) behind the value; see ATTRIBUTION.md"
        elif c.endswith("_confidence"):
            u, d = "", "high | medium | low | estimate (our model, no direct source)"
        elif c.endswith("_currency"):
            u, d = "", "ISO 4217 currency of the price"
        elif c.startswith("price_new_"):
            u, d = "currency", f"New list price, {c.removeprefix('price_new_').upper()}"
        elif c.startswith("reg_") and c.endswith("_period"):
            u, d = "", "Period of the count (date, quarter, year or month range)"
        elif c.startswith("reg_") and c.endswith("_level"):
            u, d = "", "generation | model (count covers the whole model)"
        elif c.startswith("reg_"):
            _, cc, kind = c.split("_", 2)
            what = "cars on the road" if kind == "fleet" else "first registrations in period"
            u, d = "vehicles", f"Official count, {cc.upper()}, {what} (newest period)"
        elif c == "registrations_json":
            u, d = "", "Every official count: country, source, period, kind, level, count"
        elif c == "seed_manual_fields":
            u, d = "", "Fields resting on hand-entered, unchecked seed data (confidence low)"
        elif c == "estimate_fields":
            u, d = "", "Fields that are our model estimates"
        else:
            u, d = "", ""
        out.append({"name": c, "unit": u, "description": d})
    return out


def _source_meta(catalogue: dict[str, Any], registry: Registry, sid: str) -> dict[str, str]:
    s = next((x for x in catalogue.get("sources", []) if x["id"] == sid), {})
    e = registry.sources.get(sid)
    return {
        "id": sid,
        "name": s.get("name") or (e.name if e else sid),
        "owner": e.owner if e else "",
        "url": s.get("url", ""),
        "licence": s.get("licence") or (e.licence if e else ""),
        "attribution": ATTRIBUTION_OVERRIDES.get(sid) or s.get("attribution") or "",
    }


def attribution_md(catalogue: dict[str, Any], registry: Registry, b: Bundle) -> str:
    n, date = catalogue.get("release"), str(catalogue.get("generated_at", ""))[:10]
    lines = [
        f"# Attribution, open data release {n} ({date})",
        "",
        f"This dataset is published by {brand_name()} under CC BY 4.0 (see LICENSE). It is"
        " built from the sources below; each keeps its own licence and credit. Only sources"
        " that passed our licence gate are included. Data under ODbL (e.g. OpenStreetMap) is"
        " never included. Values from `seed-manual` are hand-entered and unchecked.",
        "",
        "| Source | Owner | Licence | Credit |",
        "|---|---|---|---|",
    ]
    metas = [_source_meta(catalogue, registry, s) for s in b.sources_used]
    for mt in metas:
        lic = mt["licence"]
        lic_cell = f"[{lic}]({LICENCE_URLS[lic]})" if lic in LICENCE_URLS else lic
        name = f"[{mt['name']}]({mt['url']})" if mt["url"] else mt["name"]
        credit = (mt["attribution"] or mt["name"]).replace("|", "/")
        lines.append(f"| {name} (`{mt['id']}`) | {mt['owner']} | {lic_cell} | {credit} |")
    notices = [(s, NOTICES[s]) for s in b.sources_used if s in NOTICES]
    if notices:
        lines += ["", "## Licence notices", ""]
        for sid, text in notices:
            lines += [f"### `{sid}`", "", *text.splitlines(), ""]
    return "\n".join(lines).rstrip() + "\n"


def licence_text(catalogue: dict[str, Any]) -> str:
    n, date = catalogue.get("release"), str(catalogue.get("generated_at", ""))[:10]
    return (
        f"Open data release {n} ({date}) by {brand_name()}\n"
        "\n"
        "Licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0).\n"
        f"Summary: {CC_BY_URL}\n"
        f"Full legal code: {CC_BY_LEGAL}\n"
        "\n"
        "You may share and adapt this data for any purpose, including commercially, as long as\n"
        "you give appropriate credit, provide a link to the licence and indicate if changes\n"
        "were made. Third-party sources keep their own licences and credits: see\n"
        "ATTRIBUTION.md, which forms part of this notice.\n"
        "\n"
        "Note: this file is the standard short notice. The full CC BY 4.0 legal code is long\n"
        "and is incorporated by reference from the URL above rather than copied here.\n"
    )


def readme_md(catalogue: dict[str, Any], b: Bundle) -> str:
    n, date = catalogue.get("release"), str(catalogue.get("generated_at", ""))[:10]
    brand = brand_name()
    lines = [
        f"# Open EV catalogue, release {n}",
        "",
        f"- Release: {n}",
        f"- Date: {date} (generated {catalogue.get('generated_at')})",
        f"- Variants: {len(b.rows)}",
        f"- Sources: {', '.join(b.sources_used)}",
        "- Licence: CC BY 4.0 (LICENSE); third-party credits in ATTRIBUTION.md",
        "",
        "Files: `variants.csv` (UTF-8, comma-separated, header row, empty = unknown) and"
        " `variants.json` (the same rows plus this field list).",
        "",
        "## How to cite",
        "",
        f"> Source: {brand} (data release {n}, {date}), CC BY 4.0",
        "",
        "Please also keep the credits in ATTRIBUTION.md when you redistribute the data.",
        "",
        "## Read this first",
        "",
        "- Every value lists its sources (`<field>_sources`) and confidence"
        " (`<field>_confidence`); `estimate` means our own model, not a measurement.",
        "- `real_range_km` on the `body-ratio` rung is a PROVISIONAL generic ratio"
        " (mild-weather mixed driving), not a measurement.",
        "- `seed_manual_fields` marks values from hand-entered, unchecked seed data.",
        "- Registration counts are official counts per country and kind; counts from different"
        " sources or periods are never added together. `registrations_json` has them all.",
        "- Units are metric; prices carry their own currency.",
    ]
    if b.withheld:
        lines += [
            "- Values withheld by the licence gate: "
            + ", ".join(f"{k} {v}" for k, v in b.withheld.items()),
        ]
    lines += ["", "## Fields", "", "| Field | Unit | Description |", "|---|---|---|"]
    for d in field_docs(b):
        lines.append(f"| `{d['name']}` | {d['unit']} | {d['description']} |")
    return "\n".join(lines) + "\n"


def write_open_bundle(
    catalogue: dict[str, Any],
    registry: Registry,
    out_dir: Path,
    registration_order: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Write the bundle into out_dir/open/. Returns a summary for the run log / qa.json."""
    b = build_bundle(catalogue, registry, registration_order)
    d = out_dir / "open"
    d.mkdir(parents=True, exist_ok=True)
    (d / "variants.csv").write_text(variants_csv(b), encoding="utf-8")
    doc = {
        "release": catalogue.get("release"),
        "generated_at": catalogue.get("generated_at"),
        "licence": "CC-BY-4.0",
        "licence_url": CC_BY_URL,
        "sources": b.sources_used,
        "fields": field_docs(b),
        "rows": b.rows,
    }
    (d / "variants.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    (d / "ATTRIBUTION.md").write_text(attribution_md(catalogue, registry, b), encoding="utf-8")
    (d / "LICENSE").write_text(licence_text(catalogue), encoding="utf-8")
    (d / "README.md").write_text(readme_md(catalogue, b), encoding="utf-8")
    return {
        "rows": len(b.rows),
        "columns": len(b.columns),
        "sources": b.sources_used,
        "withheld": b.withheld,
        "files": {p.name: p.stat().st_size for p in sorted(d.iterdir())},
    }
