"""T-069: shortlist score, band and reasons per released variant and profile (Decision 038).

Reads the editorial rules (`shortlist_rules.yaml`, WS3) and scores every catalogue row with our
own published fields only. Menno's sheet values never enter here (data/editorial/README.md).

Per profile combination (trip profile x charging x home area):
  1. gates: a known value under the floor → band `ruled-out` with the gate's id as the reason;
     an unknown value passes and is listed as `gate:<id>` in `unknown`
  2. factors: value → 0..1 between `poor` and `great` (linear, clamped) x weight; unknown = 0.5
  3. bonuses / penalties: fixed points with a reason
  4. score 0..100 → band from the profile's thresholds (per voltage class where given)
More than half the weight unknown → band `not-enough-data` (score still shipped).

Winter range and real efficiency come from the same release's consumption matrix (estimates).
How rule rows map onto fields lives in shortlist_params.yaml (a bridge until T-066).
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FILE_NAME = "shortlist_scores.json"
PARAMS_FILE = Path(__file__).with_name("shortlist_params.yaml")
BAND_ORDER = {"fallback": 0, "consider": 1, "shortlist": 2}
VERDICT_BANDS = ("shortlist", "consider", "fallback")


@dataclass
class ShortlistResult:
    document: dict[str, Any] | None = None
    log: dict[str, Any] = field(default_factory=dict)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, int] = field(default_factory=dict)
    backtest: dict[str, Any] | None = None


# --- loading -----------------------------------------------------------------------------


def load_params(path: Path = PARAMS_FILE) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_rules(data_dir: Path, params: dict[str, Any]) -> Path | None:
    for rel in params["rules_paths"]:
        p = data_dir / rel
        if p.exists():
            return p
    return None


# --- derived inputs ----------------------------------------------------------------------


def _mixed_wh(
    cells: list[dict[str, Any]], temp: str, heater: str | None, mix: dict[str, float]
) -> float | None:
    tot = wsum = 0.0
    for c in cells:
        if c["temperature_band_id"] != temp or c.get("heater_type_id") != heater:
            continue
        w = float(mix.get(c["road_band"], 0))
        tot += w * float(c["wh_km"])
        wsum += w
    return tot / wsum if wsum else None


def derived_values(
    row: dict[str, Any], model: dict[str, Any] | None, params: dict[str, Any]
) -> dict[str, float]:
    """winter_range_km and real_wh_km from the matrix cells of one variant (estimates)."""
    if not model or not model.get("cells"):
        return {}
    d = params["derived"]
    cells = model["cells"]
    heaters = {c.get("heater_type_id") for c in cells}
    heater = None
    if heaters != {None}:  # several heater rows: unknown fitment → prefer the listed order
        prefs = [h for h in d["heater_preference"] if h in heaters]
        if str(row.get("heat_pump")) == "option" and "resistive" in heaters:
            prefs = ["resistive"]  # option: assume the car without it (worse case)
        heater = prefs[0] if prefs else sorted(h for h in heaters if h)[0]
    winter = _mixed_wh(cells, d["winter_temperature_band"], heater, d["road_mix"])
    mild = _mixed_wh(cells, d["mild_temperature_band"], heater, d["road_mix"])
    out: dict[str, float] = {}
    usable = row.get("battery_kwh_net") or model.get("usable_kwh")
    if winter and usable:
        out["winter_range_km"] = round(float(usable) * 1000 / winter)
    if winter and mild:
        out["real_wh_km"] = round((winter + mild) / 2, 1)
    return out


DRIVETRAINS = ("rwd", "fwd", "awd")
TRIM_LINE_POWER_GAP = 0.15  # Decision 088; shortlist_params.yaml `trim_line_power_gap` overrides


def _power(row: dict[str, Any]) -> float | None:
    v = row.get("power_kw")
    if isinstance(v, bool) or not isinstance(v, int | float) or v <= 0:
        return None
    return float(v)


def trim_lines(
    rows: list[dict[str, Any]], gap: float = TRIM_LINE_POWER_GAP
) -> list[list[dict[str, Any]]]:
    """Trim lines (Decision 088): per model and drivetrain, sorted by power; a variant whose power
    is more than `gap` above the lowest power of the current line starts a new line. Rows with no
    year, an unknown drivetrain or an unknown power are in no line (never compared)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        dt = r.get("drivetrain")
        if r.get("year_start") is None or dt not in DRIVETRAINS or _power(r) is None:
            continue
        groups[(str(r["model_id"]), str(dt))].append(r)
    lines: list[list[dict[str, Any]]] = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda r: (_power(r), str(r["variant_id"])))
        line: list[dict[str, Any]] = []
        low = 0.0
        for r in group:
            pw = _power(r) or 0.0
            limit = low * (1 + gap)
            # IEEE-754 guard: e.g. 100.0 * (1 + 0.15) == 114.99999999999999 < 115.0 (T-166)
            if line and pw > limit and not math.isclose(pw, limit, rel_tol=1e-9, abs_tol=1e-9):
                lines.append(line)
                line = []
            if not line:
                low = pw
            line.append(r)
        if line:
            lines.append(line)
    return lines


def version_flags(
    rows: list[dict[str, Any]], gap: float = TRIM_LINE_POWER_GAP
) -> dict[str, set[str]]:
    """newest-version / older-version per variant id, within one trim line (Decision 088,
    refines Decision 038's model-wide comparison). A line with one year gets neither flag;
    `older-version` needs a newer variant in the same line that charges faster."""
    flags: dict[str, set[str]] = defaultdict(set)
    for group in trim_lines(rows, gap):
        years = {int(r["year_start"]) for r in group}
        if len(years) < 2:
            continue
        top = max(years)
        for r in group:
            y = int(r["year_start"])
            if y == top:
                flags[r["variant_id"]].add("newest-version")
                continue
            mine = r.get("dc_km_per_20min")
            better = any(
                int(o["year_start"]) > y
                and mine is not None
                and o.get("dc_km_per_20min") is not None
                and o["dc_km_per_20min"] > mine
                for o in group
            )
            if better:
                flags[r["variant_id"]].add("older-version")
    return flags


# --- one factor ----------------------------------------------------------------------------


def lin(x: float, poor: float, great: float) -> float:
    if great == poor:
        return 1.0 if x >= great else 0.0
    return max(0.0, min(1.0, (x - poor) / (great - poor)))


def _modes(row: dict[str, Any]) -> set[str] | None:
    bidi = row.get("bidi")
    if not bidi:
        return None  # no bidi rows at all = not known, not "none"
    return {str(b.get("mode_id")) for b in bidi}


def row_field(rule: dict[str, Any], params: dict[str, Any]) -> str | None:
    rid = rule.get("id")
    if rid in params["field_overrides"]:
        return str(params["field_overrides"][rid])
    f = rule.get("field")
    if isinstance(f, list):
        return str(f[0]) if f else None
    return None if f is None else str(f)


def _unit_value(
    v: float, fld: str, rule: dict[str, Any], profile_id: str, params: dict[str, Any]
) -> float:
    v *= float((params.get("basis_scale") or {}).get(fld, 1.0))
    unit = rule.get("unit") or params["row_units"].get(profile_id, {}).get(rule.get("id"))
    if unit:
        return v * float(params["unit_factors"][unit])
    if fld == "consumption_kwh_100km":  # rule notes: thresholds in Wh/km
        return v * float(params["unit_factors"]["wh_km_from_kwh_100km"])
    return v


def factor_value(
    rule: dict[str, Any],
    row: dict[str, Any],
    derived: dict[str, float],
    profile_id: str,
    params: dict[str, Any],
) -> float | None:
    """0..1, or None when the car's value is not known."""
    rid = rule["id"]
    if rid == "space":
        boot = row.get("boot_l")
        if boot is None:
            return None
        return lin(float(boot) + float(row.get("frunk_l") or 0), rule["poor"], rule["great"])
    if rid == "v2l":
        m = _modes(row)
        return None if m is None else float("v2l" in m)
    if rid == "home-power":
        m = _modes(row)
        return None if m is None else float(bool(m & {"v2h", "v2g"}))
    if rid == "one-pedal":
        v = row.get("one_pedal")
        return {"yes": 1.0, "via-setting": 0.7, "no": 0.0}.get(str(v)) if v else None
    fld = row_field(rule, params)
    if fld is None:
        return None
    v = derived.get(fld, row.get(fld))
    if fld in params["categories"]:
        return None if v is None else params["categories"][fld].get(str(v))
    if v is None or (isinstance(v, str) and v == "not-disclosed"):
        return None
    if isinstance(v, bool):
        return float(v)
    if not isinstance(v, int | float):
        return None
    if "poor" not in rule or "great" not in rule:
        return None
    return lin(_unit_value(float(v), fld, rule, profile_id, params), rule["poor"], rule["great"])


def gate_value(
    gate: dict[str, Any], row: dict[str, Any], derived: dict[str, float], profile_id: str,
    params: dict[str, Any],
) -> float | None:  # fmt: skip
    fld = row_field(gate, params)
    if fld is None:
        return None
    v = derived.get(fld, row.get(fld))
    if not isinstance(v, int | float) or isinstance(v, bool):
        return None
    return _unit_value(float(v), fld, gate, profile_id, params)


def kerb_mass(row: dict[str, Any], params: dict[str, Any]) -> float | None:
    if row.get("kerb_mass_kg") is not None:
        return float(row["kerb_mass_kg"])
    mro = row.get("mass_running_order_kg")
    return None if mro is None else float(mro) - float(params["mro_driver_kg"])


def too_big(row: dict[str, Any], params: dict[str, Any]) -> bool | None:
    lim = params["too_big"]
    width = row.get("width_mm")
    mass = kerb_mass(row, params)
    if width is None and mass is None:
        return None
    return bool(
        (width is not None and float(width) > lim["width_mm"])
        or (mass is not None and mass > lim["kerb_mass_kg"])
    )


# --- one combination -----------------------------------------------------------------------


@dataclass
class Combo:
    key: str
    trip: dict[str, Any]
    kerbside: dict[str, Any] | None
    area: dict[str, Any] | None

    def factors(self) -> tuple[list[tuple[dict[str, Any], float]], Counter[str]]:
        steps: Counter[str] = Counter()
        for g in (self.kerbside, self.area):
            for fid, n in ((g or {}).get("weight_steps") or {}).items():
                steps[fid] += int(n)
        rows = list(self.trip.get("factors", []))
        rows += (self.kerbside or {}).get("extra_factors", [])
        return [(f, float(f["weight"])) for f in rows], steps

    @property
    def rural(self) -> bool:
        return bool((self.area or {}).get("use_rural_gates"))


def combos(rules: dict[str, Any], params: dict[str, Any]) -> list[Combo]:
    profiles = {p["id"]: p for p in rules["profiles"]}
    mods = {m["id"]: m for m in rules.get("modifiers", [])}
    c = params["combos"]
    out = []
    for tid in c["trip_profiles"]:
        if tid not in profiles:
            continue
        for ch in c["charging"]:
            kerb = profiles.get(ch) if ch != "home" else None
            if ch != "home" and kerb is None:
                continue
            for area in c["home_areas"]:
                mod = mods.get(area)
                key = (
                    tid + ("+kerbside" if kerb else "") + ("" if area == "suburban" else f".{area}")
                )
                out.append(Combo(key, profiles[tid], kerb, mod if area != "suburban" else None))
    return out


def band_for(pts: float, bands: dict[str, Any], voltage: Any) -> str:
    b = bands.get(str(voltage)) if voltage else None
    b = b or bands.get("default") or next(iter(bands.values()))
    return (
        "shortlist" if pts >= b["shortlist"] else "consider" if pts >= b["consider"] else "fallback"
    )


def score_combo(
    combo: Combo,
    row: dict[str, Any],
    derived: dict[str, float],
    fvals: dict[str, float | None],
    flags: set[str],
    params: dict[str, Any],
    step_factor: float,
) -> dict[str, Any]:
    pid = combo.trip["id"]
    unknown: list[str] = []
    for g in combo.trip.get("gates", []):
        v = gate_value(g, row, derived, pid, params)
        lim = g.get("min_km_per_h", g.get("min_km"))
        if combo.rural and g.get("rural_min_km") is not None:
            lim = g["rural_min_km"]
        if v is None:
            unknown.append(f"gate:{g['id']}")
        elif lim is not None and v < float(lim):
            return {
                "score": 0,
                "band": "ruled-out",
                "reasons": [f"gate:{g['id']}"],
                "unknown": unknown,
            }
    rows, steps = combo.factors()
    total = wsum = wunk = 0.0
    effects = []
    for f, w in rows:
        w *= step_factor ** steps.get(f["id"], 0)
        s = fvals.get(f["id"])
        if s is None:
            unknown.append(f["id"])
            wunk += w
            s = 0.5
        else:
            effects.append((f["id"], s, w))
        total += s * w
        wsum += w
    pts = 100 * total / wsum if wsum else 0.0
    reasons: list[str] = []
    r = params["reasons"]
    plus = sorted((e for e in effects if e[1] >= r["strength"]), key=lambda e: -(e[1] - 0.5) * e[2])
    minus = sorted((e for e in effects if e[1] <= r["weakness"]), key=lambda e: (e[1] - 0.5) * e[2])
    reasons += [f"+{e[0]}" for e in plus[: r["max_reasons"]]]
    reasons += [f"-{e[0]}" for e in minus[: r["max_reasons"]]]
    for b in combo.trip.get("bonuses", []):
        hit = b["id"] in flags or (
            b.get("field") == "charge_100_daily" and row.get("charge_100_daily") is True
        )
        if hit:
            pts += float(b["points"])
            reasons.append(f"bonus:{b['id']}")
    penalties = [
        p for p in combo.trip.get("penalties", []) if p.get("applies_with") is None or combo.rural
    ]
    pen_ids = {p["id"] for p in penalties}
    if combo.rural:
        penalties += [p for p in (combo.area or {}).get("penalties", []) if p["id"] not in pen_ids]
    for p in penalties:
        hit = p["id"] in flags
        if p["id"] == "too-big-for-b-roads":
            big = too_big(row, params)
            if big is None:
                unknown.append(f"penalty:{p['id']}")
            hit = bool(big)
        if hit:
            pts += float(p["points"])
            reasons.append(f"penalty:{p['id']}")
    pts = max(0.0, min(100.0, pts))
    band = band_for(pts, combo.trip["bands"], row.get("voltage_class_id"))
    if wsum and wunk / wsum > 0.5:
        band = "not-enough-data"
    return {"score": round(pts, 1), "band": band, "reasons": reasons, "unknown": unknown}


# --- whole release -------------------------------------------------------------------------


def rule_fields(rules: dict[str, Any], params: dict[str, Any]) -> list[str]:
    out: set[str] = set()
    for g in rules["profiles"] + rules.get("modifiers", []):
        for r in g.get("gates", []) + g.get("factors", []) + g.get("extra_factors", []):
            f = row_field(r, params)
            if f:
                out.add(f)
    return sorted(out)


def field_coverage(
    rows: list[dict[str, Any]], derived: dict[str, dict[str, float]], fields: list[str]
) -> dict[str, int]:
    cov = {}
    for f in fields:
        n = 0
        for r in rows:
            v = derived.get(r["variant_id"], {}).get(f, r.get(f))
            n += v not in (None, [], "not-disclosed")
        cov[f] = n
    return cov


def build_shortlist(
    rows: list[dict[str, Any]],
    matrix: dict[str, Any] | None,
    data_dir: Path,
    release: int,
    generated_at: str,
    params_path: Path = PARAMS_FILE,
) -> ShortlistResult:
    out = ShortlistResult()
    params = load_params(params_path)
    rules_path = find_rules(data_dir, params)
    if rules_path is None:
        out.log = {"status": "no rules file"}
        return out
    raw = rules_path.read_bytes()
    rules = yaml.safe_load(raw)
    out.inputs.append(
        {
            "path": str(rules_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "kind": "editorial rules",
        }
    )
    models = {m["variant_id"]: m for m in (matrix or {}).get("variants", [])}
    flags = version_flags(rows, float(params.get("trim_line_power_gap", TRIM_LINE_POWER_GAP)))
    step = float(rules.get("weight_step_factor", 1.5))
    cmb = combos(rules, params)
    all_rules: dict[tuple[str, str], dict[str, Any]] = {}
    for p in rules["profiles"]:
        for f in p.get("factors", []) + p.get("extra_factors", []):
            all_rules[(p["id"], f["id"])] = f
    derived_all: dict[str, dict[str, float]] = {}
    variants = []
    bands: dict[str, Counter[str]] = defaultdict(Counter)
    for row in sorted(rows, key=lambda r: r["variant_id"]):
        vid = row["variant_id"]
        derived = derived_values(row, models.get(vid), params)
        derived_all[vid] = derived
        scores = {}
        factors: dict[str, dict[str, float | None]] = {}
        unknown: dict[str, list[str]] = {}
        for c in cmb:
            fvals: dict[str, float | None] = {}
            for owner in (c.trip, c.kerbside):
                if not owner:
                    continue
                for f in owner.get("factors", []) + owner.get("extra_factors", []):
                    fvals[f["id"]] = factor_value(f, row, derived, c.trip["id"], params)
            factors.setdefault(c.trip["id"], {}).update(
                {k: None if v is None else round(v, 3) for k, v in fvals.items()}
            )
            s = score_combo(c, row, derived, fvals, flags.get(vid, set()), params, step)
            u = unknown.setdefault(c.trip["id"], [])
            u += [x for x in s.pop("unknown") if x not in u]
            scores[c.key] = s
            bands[c.key][s["band"]] += 1
        variants.append(
            {"variant_id": vid, "derived": derived, "factors": factors, "unknown": unknown,
             "scores": scores}
        )  # fmt: skip
    out.document = {
        "release": release,
        "generated_at": generated_at,
        "model_version": str(params["model_version"]),
        "estimate": True,
        "editorial": True,
        "note": "Editorial scores: one owner's selection rules applied to our own fields. "
        "Opinion, not fact. Winter range and real efficiency are model estimates.",
        "rules": {
            "path": str(rules_path.relative_to(data_dir))
            if rules_path.is_relative_to(data_dir)
            else rules_path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "schema": rules.get("schema"),
            "review": bool(rules.get("review")),
        },
        "licence": "CC-BY-4.0",
        "combos": [c.key for c in cmb],
        "bands": ["shortlist", "consider", "fallback", "ruled-out", "not-enough-data"],
        "variants": variants,
    }
    out.coverage = field_coverage(rows, derived_all, rule_fields(rules, params))
    out.log = {
        "status": "shipped",
        "variants": len(variants),
        "combos": len(cmb),
        "bands": {k: dict(sorted(v.items())) for k, v in sorted(bands.items())},
        "field_coverage": out.coverage,
    }
    out.backtest = backtest_picks(rows, out.document, data_dir)
    if out.backtest:
        out.log["backtest"] = {k: v for k, v in out.backtest.items() if k != "rows"}
    return out


# --- back-test against the owner's verdicts ---------------------------------------------------


def _drive(text: str | None) -> str | None:
    t = (text or "").upper()
    if "AWD" in t:
        return "awd"
    if any(k in t for k in ("RWD", "2WD", "FWD")):
        return "2wd"
    return None


def _pick_variant(pick: dict[str, Any], gen_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Closest released variant in the pick's generation: usable kWh within 4, same drivetrain
    family when the pick names one, rows with a DC figure first, then model year.
    The sheet's kWh only chooses which row to compare (internal, never published)."""
    kwh = (pick.get("sheet_values") or {}).get("battery_usable_kwh")
    if kwh is None:
        return None
    cand = [
        r for r in gen_rows
        if r.get("battery_kwh_net") is not None
        and abs(float(r["battery_kwh_net"]) - float(kwh)) <= 4
    ]  # fmt: skip
    want = _drive(pick.get("variant"))
    if want:
        cand = [r for r in cand if (r.get("drivetrain") == "awd") == (want == "awd")] or cand
    if not cand:
        return None
    year = pick.get("model_year")

    def key(r: dict[str, Any]) -> tuple[int, float, int]:
        ys = r.get("year_start")
        dy = abs(int(ys) - int(year)) if (ys is not None and year is not None) else 0
        return (r.get("dc_km_per_20min") is None, abs(float(r["battery_kwh_net"]) - float(kwh)), dy)

    return min(cand, key=key)


def backtest_picks(
    rows: list[dict[str, Any]], doc: dict[str, Any], data_dir: Path, combo: str = "road-tripper"
) -> dict[str, Any] | None:
    path = data_dir / "editorial" / "menno-picks.yaml"
    if not path.exists():
        return None
    picks = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("primary_car_picks") or []
    by_gen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_gen[str(r.get("generation_id"))].append(r)
    scores = {v["variant_id"]: v["scores"].get(combo) for v in doc["variants"]}
    out_rows = []
    n = hit = near = 0
    for p in picks:
        if p.get("verdict") not in VERDICT_BANDS or not p.get("seed_generation_id"):
            continue
        r = _pick_variant(p, by_gen.get(str(p["seed_generation_id"]), []))
        if r is None or not scores.get(r["variant_id"]):
            continue
        s = scores[r["variant_id"]]
        name = (
            f"{p['make']} {p['model']} {p.get('model_year') or ''} {p.get('variant') or ''}".strip()
        )
        counted = s["band"] in BAND_ORDER
        if counted:
            n += 1
            hit += s["band"] == p["verdict"]
            near += abs(BAND_ORDER[s["band"]] - BAND_ORDER[p["verdict"]]) <= 1
        out_rows.append(
            {"pick": name, "verdict": p["verdict"], "variant_id": r["variant_id"],
             "band": s["band"], "score": s["score"], "counted": counted}
        )  # fmt: skip
    return {
        "combo": combo,
        "matched": len(out_rows),
        "counted": n,
        "exact": hit,
        "within_one": near,
        "exact_share": round(hit / n, 3) if n else None,
        "gate": False,
        "rows": out_rows,
    }


def coverage_lines(log: dict[str, Any]) -> list[str]:
    if not log or log.get("status") != "shipped":
        return []
    n = log["variants"]
    lines = ["", "## Shortlist scores (T-069, editorial)", ""]
    lines.append(f"{n} variants x {log['combos']} profile combinations. Rule fields present:")
    lines.append("")
    lines.append("| Field | Variants | Share |")
    lines.append("|---|---|---|")
    for f, c in log["field_coverage"].items():
        lines.append(f"| {f} | {c} | {c / n:.0%} |" if n else f"| {f} | 0 | - |")
    lines.append("")
    lines.append(
        "| Profile | "
        + " | ".join(["shortlist", "consider", "fallback", "ruled-out", "not-enough-data"])
        + " |"
    )
    lines.append("|---|---|---|---|---|---|")
    for k, b in log["bands"].items():
        if "." in k or "+" in k:
            continue
        cells = [
            str(b.get(x, 0))
            for x in ("shortlist", "consider", "fallback", "ruled-out", "not-enough-data")
        ]
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    return lines


def readme_lines(bt: dict[str, Any] | None) -> list[str]:
    if not bt:
        return []
    lines = ["", "## Shortlist back-test (owner's picks, not a gate)", ""]
    share = f"{bt['exact_share']:.0%}" if bt["exact_share"] is not None else "-"
    lines.append(
        f"Profile `{bt['combo']}`: {bt['matched']} picks matched to a released variant, "
        f"{bt['counted']} with a band; exact {bt['exact']} ({share}),"
        f" within one band {bt['within_one']}."
    )
    if bt["rows"]:
        lines += ["", "| Pick | Owner | Rules | Score |", "|---|---|---|---|"]
        for r in bt["rows"]:
            mark = "" if not r["counted"] else (" ✓" if r["band"] == r["verdict"] else " ✗")
            lines.append(f"| {r['pick']} | {r['verdict']} | {r['band']}{mark} | {r['score']} |")
    return lines
