"""Release QA checks (R-05 §1). Pure functions over a release's catalogue and facts.

Every check returns a `Check`: id, title, `blocking`, status and details.
Status:  pass | flag (goes to review, release still publishes) | fail (blocking only: the
release is not published) | info (report only) | skipped (nothing to compare, with a note).

Checks (blocking ones fail the release):
- provenance (blocking): every non-null number (row fields, prices, registrations) has a
  provenance entry with source(s), confidence, a licence (via the release `sources`) and a
  date: the `retrieved_at` of its facts; values without fact ids are dated by their
  source's newest fact, `model-estimate` by the release date. Every fact id resolves; every
  fact has source, licence, retrieved_at and confidence.
- licence_gate (blocking): every source in the release, in any provenance entry,
  registration count or fact passes the registry gate (data/sources.yaml, Decision 009)
  and is not ODbL.
- diff: vs the previous release, > 2 % of variants lost, or a headline field changed beyond
  its field_sources.yaml tolerance on > 20 variants -> flag. Per-field coverage deltas are
  reported; a drop of > 5 points of filled variants -> flag.
- outliers: per field and segment, values outside P1-P99 of the previous release (else of
  this release; segments with under 30 values skipped), and physically impossible values:
  usable > gross kWh, WLTP km / usable kWh > 10, DC average > DC peak, AC > 43 kW, any
  negative number -> flag.
- top40_coverage (report): share of the top-40 used models with 2+ agreeing sources per
  headline field (target 80 % before launch).
- sections (report, T-059): EPA range rows and their second EPA source, generation years
  checked against Wikidata (disagreements -> flag), known issues cohorts and the
  charging_stats.json rows per source. The licence gate also covers these sections.

Thresholds are module constants (PROVISIONAL, from R-05) so they can move to config later.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from ev_pipeline.merge.policy import Policies
from ev_pipeline.release.gate import Registry, licence_problem

# Row fields that are numbers and must carry provenance (mirrors validate.ROW_NUMBER_FIELDS).
from ev_pipeline.release.validate import ROW_NUMBER_FIELDS

ESTIMATE_SOURCE = "model-estimate"
CONFIDENCES = {"high", "medium", "low"}

# R-05 §1 thresholds (PROVISIONAL).
MAX_VARIANTS_LOST_SHARE = 0.02
MAX_CHANGED_VARIANTS_PER_HEADLINE_FIELD = 20
MAX_COVERAGE_DROP_POINTS = 5.0
PERCENTILE_LOW, PERCENTILE_HIGH = 1.0, 99.0
MIN_SEGMENT_VALUES = 30
MAX_WLTP_KM_PER_KWH = 10.0
MAX_AC_KW = 43.0
TOP_N_MODELS = 40
COVERAGE_TARGET = 0.80
EPS = 1e-6
# Row numbers are rounded to 1 decimal; pack gross figures are not (60.48 -> 60.5).
ROUNDING_KWH = 0.05

HEADLINE_FIELDS = (
    "battery_kwh_net",
    "wltp_range_km",
    "real_range_km",
    "ac_kw",
    "dc_peak_kw",
    "dc_avg_10_80_kw",
    "dc_km_per_20min",
)
# Counts and seat numbers are not "measurements"; percentiles on them say nothing.
OUTLIER_FIELDS = tuple(f for f in ROW_NUMBER_FIELDS if f not in ("registered_count_nl", "seats"))
MAX_LISTED = 50  # items per list in qa.json; the totals are always complete


@dataclass
class Check:
    id: str
    title: str
    blocking: bool
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _capped(items: list[Any]) -> list[Any]:
    return items[:MAX_LISTED]


def row_values(row: dict[str, Any]) -> list[tuple[str, Any]]:
    """(provenance key, value) for every non-null number in a row that needs provenance."""
    out = [(f, row.get(f)) for f in ROW_NUMBER_FIELDS if row.get(f) is not None]
    for cc, money in sorted((row.get("price_new") or {}).items()):
        out.append((f"price_new.{cc}", (money or {}).get("amount")))
    for cc, entries in sorted((row.get("registrations") or {}).items()):
        out.append((f"registrations.{cc}", [e.get("count") for e in entries]))
    return out


# --- provenance (blocking) ---------------------------------------------------------------


def check_provenance(catalogue: dict[str, Any], facts: list[dict[str, Any]]) -> Check:
    errors: list[str] = []
    fact_by_id = {f.get("id"): f for f in facts}
    source_licence = {s["id"]: s.get("licence") or "" for s in catalogue.get("sources", [])}
    newest_by_source: dict[str, str] = {}
    for f in facts:
        sid = (f.get("source") or {}).get("id")
        ra = f.get("retrieved_at")
        if not sid or not f.get("source", {}).get("licence") or not ra:
            errors.append(f"fact {f.get('id')}: missing source, licence or retrieved_at")
        if f.get("confidence") not in CONFIDENCES:
            errors.append(f"fact {f.get('id')}: missing confidence")
        if sid and ra and ra > newest_by_source.get(sid, ""):
            newest_by_source[sid] = ra
    release_date = str(catalogue.get("generated_at", ""))[:10]
    checked = dated_by_fact = dated_by_source = 0
    for row in catalogue.get("rows", []):
        vid = row.get("variant_id")
        prov = row.get("provenance") or {}
        for key, _ in row_values(row):
            checked += 1
            p = prov.get(key)
            if p is None:
                errors.append(f"{vid}: {key} has no provenance")
                continue
            sids = p.get("source_ids") or []
            if not sids:
                errors.append(f"{vid}: {key} has no source")
            if p.get("confidence") not in CONFIDENCES:
                errors.append(f"{vid}: {key} has no confidence")
            for sid in sids:
                if not source_licence.get(sid):
                    errors.append(f"{vid}: {key} source {sid} has no licence in release sources")
            fids = p.get("fact_ids") or []
            missing = [fid for fid in fids if fid not in fact_by_id]
            if missing:
                errors.append(f"{vid}: {key} refers to unknown fact(s) {missing[:3]}")
            if fids and not missing:
                dated_by_fact += 1
                continue
            if fids:
                continue
            # No fact ids: dated by its sources' newest fact; the estimate model by release.
            if sids and all(
                newest_by_source.get(s) or (s == ESTIMATE_SOURCE and release_date) for s in sids
            ):
                dated_by_source += 1
            else:
                errors.append(f"{vid}: {key} has no date (no facts and no dated source)")
    status = "fail" if errors else "pass"
    return Check(
        "provenance",
        "Provenance completeness",
        True,
        status,
        f"{checked} values checked; {len(errors)} problem(s)",
        {
            "values_checked": checked,
            "dated_by_fact": dated_by_fact,
            "dated_by_source": dated_by_source,
            "facts_checked": len(facts),
            "errors": _capped(errors),
            "error_count": len(errors),
        },
    )


# --- licence gate (blocking) -------------------------------------------------------------


def _gate_reason(registry: Registry, sid: str, licence: str | None = None) -> str | None:
    why = registry.reason_blocked(sid)
    if why is not None:
        return why
    if licence is not None:
        if "odbl" in licence.lower():
            return f"ODbL licence ({licence}) cannot go into a CC BY release"
        if registry.cited_facts(sid):
            return None  # Decision 068: same rule as the release gate (reason_blocked)
        return licence_problem(licence)
    return None


def section_gate_problems(
    catalogue: dict[str, Any], charging: dict[str, Any] | None, registry: Registry
) -> list[str]:
    """T-059 sections: known_issues, generation year checks, charging_stats.json."""
    errors: list[str] = []
    ki = catalogue.get("known_issues")
    if ki is not None and (why := _gate_reason(registry, str(ki.get("source_id")))):
        errors.append(f"known_issues: {ki.get('source_id')}: {why}")
    for g in catalogue.get("generations", []):
        for c in (g.get("years_corroboration") or {}).get("checks", []):
            if why := _gate_reason(registry, str(c.get("source_id"))):
                errors.append(f"{g.get('id')}: years_corroboration {c.get('source_id')}: {why}")
    for s in (charging or {}).get("sources", []):
        if why := _gate_reason(registry, str(s.get("id")), str(s.get("licence") or "")):
            errors.append(f"charging_stats source {s.get('id')}: {why}")
    for sid in sorted({str(st.get("source_id")) for st in (charging or {}).get("stats", [])}):
        if why := _gate_reason(registry, sid):
            errors.append(f"charging_stats rows from {sid}: {why}")
    return errors


def check_licence_gate(
    catalogue: dict[str, Any],
    facts: list[dict[str, Any]],
    registry: Registry,
    charging: dict[str, Any] | None = None,
) -> Check:
    errors: list[str] = []
    for s in catalogue.get("sources", []):
        why = _gate_reason(registry, s["id"], s.get("licence") or "")
        if why:
            errors.append(f"source {s['id']}: {why}")
    used: Counter[str] = Counter()
    for row in catalogue.get("rows", []):
        for key, p in (row.get("provenance") or {}).items():
            for sid in p.get("source_ids") or []:
                used[sid] += 1
                why = _gate_reason(registry, sid)
                if why:
                    errors.append(f"{row.get('variant_id')}: {key} uses {sid}: {why}")
            for fid in p.get("fact_ids") or []:
                sid = fid.split(":", 1)[0]
                why = _gate_reason(registry, sid)
                if why:
                    errors.append(f"{row.get('variant_id')}: {key} fact {fid}: {why}")
        for cc, entries in (row.get("registrations") or {}).items():
            for e in entries:
                why = _gate_reason(registry, str(e.get("source_id")))
                if why:
                    errors.append(f"{row.get('variant_id')}: registrations.{cc}: {why}")
    for f in facts:
        src = f.get("source") or {}
        sid = str(src.get("id"))
        why = _gate_reason(registry, sid, str(src.get("licence") or "")) or (
            registry.cited_url_problem(sid, src.get("url"))
        )
        if why:
            errors.append(f"fact {f.get('id')}: {why}")
    errors += section_gate_problems(catalogue, charging, registry)
    return Check(
        "licence_gate",
        "Licence gate re-check",
        True,
        "fail" if errors else "pass",
        f"{len(catalogue.get('sources', []))} sources, {len(facts)} facts; "
        f"{len(errors)} problem(s)",
        {
            "sources": sorted(s["id"] for s in catalogue.get("sources", [])),
            "values_per_source": dict(sorted(used.items())),
            "errors": _capped(errors),
            "error_count": len(errors),
        },
    )


# --- diff vs previous release --------------------------------------------------------------


def _filled_share(rows: list[dict[str, Any]], f: str) -> float:
    return sum(1 for r in rows if r.get(f) is not None) / len(rows) if rows else 0.0


def _two_plus_share(rows: list[dict[str, Any]], f: str) -> float:
    if not rows:
        return 0.0
    n = 0
    for r in rows:
        p = (r.get("provenance") or {}).get(f)
        if r.get(f) is not None and p and not p.get("estimate"):
            n += p.get("agreeing_sources", 1) >= 2
    return n / len(rows)


def check_diff(prev: dict[str, Any] | None, cur: dict[str, Any], policies: Policies) -> Check:
    if prev is None:
        return Check(
            "diff",
            "Diff vs previous release",
            False,
            "skipped",
            "first release: nothing to compare",
            {"previous_release": None, "variants": len(cur.get("rows", []))},
        )
    prev_rows = {r["variant_id"]: r for r in prev.get("rows", [])}
    cur_rows = {r["variant_id"]: r for r in cur.get("rows", [])}
    lost = sorted(set(prev_rows) - set(cur_rows))
    added = sorted(set(cur_rows) - set(prev_rows))
    lost_share = len(lost) / len(prev_rows) if prev_rows else 0.0
    flags: list[str] = []
    if lost_share > MAX_VARIANTS_LOST_SHARE:
        flags.append(f"{len(lost)} variants lost ({100 * lost_share:.1f}% > 2%)")

    coverage: dict[str, dict[str, float]] = {}
    pr, cr = list(prev_rows.values()), list(cur_rows.values())
    for f in ROW_NUMBER_FIELDS:
        a, b = 100 * _filled_share(pr, f), 100 * _filled_share(cr, f)
        a2, b2 = 100 * _two_plus_share(pr, f), 100 * _two_plus_share(cr, f)
        coverage[f] = {
            "filled_pct_previous": round(a, 1),
            "filled_pct": round(b, 1),
            "two_plus_pct_previous": round(a2, 1),
            "two_plus_pct": round(b2, 1),
        }
        if a - b > MAX_COVERAGE_DROP_POINTS:
            flags.append(f"{f}: filled share fell {a - b:.1f} points")

    beyond: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for vid in sorted(set(prev_rows) & set(cur_rows)):
        for f in ROW_NUMBER_FIELDS:
            old, new = prev_rows[vid].get(f), cur_rows[vid].get(f)
            if not (_num(old) and _num(new)):
                continue
            pol = policies.for_field(f)
            if not pol.agree(old, new):
                beyond[f].append(
                    {"variant_id": vid, "old": old, "new": new, "tolerance": pol.tolerance_text()}
                )
    for f in HEADLINE_FIELDS:
        n = len(beyond.get(f, []))
        if n > MAX_CHANGED_VARIANTS_PER_HEADLINE_FIELD:
            flags.append(f"{f}: {n} variants changed beyond tolerance (> 20)")
    return Check(
        "diff",
        "Diff vs previous release",
        False,
        "flag" if flags else "pass",
        f"vs release {prev.get('release')}: {len(prev_rows)} -> {len(cur_rows)} variants, "
        f"+{len(added)} / -{len(lost)}; {len(flags)} flag(s)",
        {
            "previous_release": prev.get("release"),
            "variants_previous": len(prev_rows),
            "variants": len(cur_rows),
            "added": _capped(added),
            "lost": _capped(lost),
            "lost_share": round(lost_share, 4),
            "coverage": coverage,
            "beyond_tolerance_counts": {f: len(v) for f, v in sorted(beyond.items())},
            "beyond_tolerance": {f: _capped(v) for f, v in sorted(beyond.items())},
            "flags": flags,
        },
    )


# --- outliers ----------------------------------------------------------------------------


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default)."""
    xs = sorted(values)
    if not xs:
        raise ValueError("no values")
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _gross_kwh(catalogue: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, float]:
    """variant id -> gross kWh, from its battery pack, else the largest gross fact for it."""
    packs = {p["id"]: p for p in catalogue.get("battery_packs") or []}
    by_variant: dict[str, float] = {}
    for f in facts:
        if f.get("field") == "battery_kwh_gross" and _num(f.get("value")):
            sid = str(f.get("subject_id"))
            by_variant[sid] = max(by_variant.get(sid, 0.0), float(f["value"]))
    out: dict[str, float] = {}
    for r in catalogue.get("rows", []):
        pack = packs.get(r.get("battery_pack_id") or "")
        g = (pack or {}).get("gross_kwh")
        if _num(g):
            out[r["variant_id"]] = float(g)
        elif r["variant_id"] in by_variant:
            out[r["variant_id"]] = by_variant[r["variant_id"]]
    return out


def impossible_values(
    catalogue: dict[str, Any], facts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    gross = _gross_kwh(catalogue, facts)
    out: list[dict[str, Any]] = []

    def add(row: dict[str, Any], rule: str, fld: str, value: Any, detail: str) -> None:
        out.append(
            {
                "variant_id": row["variant_id"],
                "rule": rule,
                "field": fld,
                "value": value,
                "detail": detail,
            }
        )

    for r in catalogue.get("rows", []):
        net, wltp = r.get("battery_kwh_net"), r.get("wltp_range_km")
        g = gross.get(r["variant_id"])
        if _num(net) and g is not None and net > g + ROUNDING_KWH + EPS:
            add(r, "usable_gt_gross", "battery_kwh_net", net, f"usable {net} > gross {g} kWh")
        if _num(net) and _num(wltp) and net > 0 and wltp / net > MAX_WLTP_KM_PER_KWH:
            add(
                r,
                "wltp_efficiency",
                "wltp_range_km",
                wltp,
                f"{wltp / net:.1f} km/kWh > {MAX_WLTP_KM_PER_KWH:g}",
            )
        worst = r.get("wltp_range_km_worst")
        if _num(worst) and _num(wltp) and worst > wltp + EPS:  # T-155 (Leaf e+ 410 > 385)
            add(
                r,
                "wltp_worst_gt_best",
                "wltp_range_km_worst",
                worst,
                f"worst case {worst} > best case {wltp} km",
            )
        avg, peak = r.get("dc_avg_10_80_kw"), r.get("dc_peak_kw")
        if _num(avg) and _num(peak) and avg > peak + EPS:
            add(r, "dc_avg_gt_peak", "dc_avg_10_80_kw", avg, f"average {avg} > peak {peak} kW")
        for af in ("ac_kw", "ac_kw_optional"):
            ac = r.get(af)
            if _num(ac) and ac > MAX_AC_KW + EPS:
                add(r, "ac_gt_43", af, ac, f"AC {ac} kW > {MAX_AC_KW:g} kW")
        std, opt = r.get("ac_kw"), r.get("ac_kw_optional")
        if _num(std) and _num(opt) and opt <= std + EPS:
            add(
                r,
                "ac_optional_not_above",
                "ac_kw_optional",
                opt,
                f"optional {opt} <= standard {std} kW",
            )
        for f in ROW_NUMBER_FIELDS:
            v = r.get(f)
            if _num(v) and v < 0:
                add(r, "negative", f, v, "negative value")
        for cc, money in (r.get("price_new") or {}).items():
            amt = (money or {}).get("amount")
            if _num(amt) and amt < 0:
                add(r, "negative", f"price_new.{cc}", amt, "negative value")
        for cc, entries in (r.get("registrations") or {}).items():
            for e in entries:
                if _num(e.get("count")) and e["count"] < 0:
                    add(r, "negative", f"registrations.{cc}", e["count"], "negative value")
    return out


def percentile_outliers(
    cur: dict[str, Any], prev: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Values outside P1-P99 of the reference (previous release, else this one)."""
    ref_rows = (prev or {}).get("rows") or []
    reference = f"release {prev.get('release')}" if prev and ref_rows else "this release"
    if not ref_rows:
        ref_rows = cur.get("rows", [])
    ref: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in ref_rows:
        for f in OUTLIER_FIELDS:
            if _num(r.get(f)):
                ref[(str(r.get("segment")), f)].append(float(r[f]))
    bounds: dict[tuple[str, str], tuple[float, float]] = {}
    skipped: Counter[str] = Counter()
    for key, vals in ref.items():
        if len(vals) < MIN_SEGMENT_VALUES:
            skipped[key[0]] += 1
            continue
        bounds[key] = (percentile(vals, PERCENTILE_LOW), percentile(vals, PERCENTILE_HIGH))
    out = []
    for r in cur.get("rows", []):
        seg = str(r.get("segment"))
        for f in OUTLIER_FIELDS:
            v = r.get(f)
            b = bounds.get((seg, f))
            if b is None or not _num(v):
                continue
            if v < b[0] - EPS or v > b[1] + EPS:
                out.append(
                    {
                        "variant_id": r["variant_id"],
                        "segment": seg,
                        "field": f,
                        "value": v,
                        "p1": round(b[0], 2),
                        "p99": round(b[1], 2),
                    }
                )
    meta = {
        "reference": reference,
        "segment_fields_checked": len(bounds),
        "segment_fields_skipped_small": sum(skipped.values()),
        "min_values_per_segment": MIN_SEGMENT_VALUES,
    }
    return out, meta


def check_outliers(
    cur: dict[str, Any], prev: dict[str, Any] | None, facts: list[dict[str, Any]]
) -> Check:
    impossible = impossible_values(cur, facts)
    pct, meta = percentile_outliers(cur, prev)
    by_rule = Counter(i["rule"] for i in impossible)
    return Check(
        "outliers",
        "Outliers and impossible values",
        False,
        "flag" if impossible or pct else "pass",
        f"{len(impossible)} impossible value(s), {len(pct)} outside P1-P99 "
        f"(reference: {meta['reference']})",
        {
            "impossible_count": len(impossible),
            "impossible_by_rule": dict(sorted(by_rule.items())),
            "impossible": _capped(impossible),
            "percentile_count": len(pct),
            "percentile_by_field": dict(sorted(Counter(o["field"] for o in pct).items())),
            "percentile": _capped(pct),
            **meta,
        },
    )


# --- top-40 coverage ---------------------------------------------------------------------


def _bucket(row: dict[str, Any], f: str) -> str:
    p = (row.get("provenance") or {}).get(f)
    if row.get(f) is None or p is None:
        return "missing"
    if p.get("estimate"):
        return "estimate"
    return "two_plus" if p.get("agreeing_sources", 1) >= 2 else "one"


def top_models(rows: list[dict[str, Any]], n: int = TOP_N_MODELS) -> list[dict[str, Any]]:
    """Rank seed models in the release by used fleet: RDW NL fleet (one generation count
    each, summed over generations), then the DfT UK fleet, then name. PROVISIONAL proxy for
    "most-bought used" (QUESTIONS.md); counts are only compared, never published as a sum."""
    models: dict[str, dict[str, Any]] = {}
    for r in rows:
        m = models.setdefault(
            r["model_id"],
            {
                "model_id": r["model_id"],
                "name": f"{r.get('make_name', '')} {r.get('model_name', '')}".strip(),
                "nl": {},
                "uk": 0,
            },
        )
        for e in (r.get("registrations") or {}).get("NL", []):
            if e.get("kind") == "fleet" and e.get("source_id") == "rdw":
                m["nl"][r["generation_id"]] = e.get("count") or 0
        for e in (r.get("registrations") or {}).get("UK", []):
            if e.get("kind") == "fleet":
                m["uk"] = max(m["uk"], e.get("count") or 0)
    ranked = sorted(models.values(), key=lambda m: (-sum(m["nl"].values()), -m["uk"], m["name"]))
    return [
        {"rank": i + 1, "model_id": m["model_id"], "name": m["name"]}
        for i, m in enumerate(ranked[:n])
    ]


def check_top40_coverage(cur: dict[str, Any]) -> Check:
    rows = cur.get("rows", [])
    top = top_models(rows)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_model[r["model_id"]].append(r)
    per_model = []
    covered = Counter()
    for m in top:
        vs = by_model[m["model_id"]]
        fields = {}
        for f in HEADLINE_FIELDS:
            c = Counter(_bucket(r, f) for r in vs)
            ok = c["two_plus"] * 2 > len(vs)  # a majority of its variants
            covered[f] += ok
            fields[f] = {"covered": ok, **dict(c)}
        per_model.append({**m, "variants": len(vs), "fields": fields})
    n = len(top) or 1
    share = {f: round(covered[f] / n, 3) for f in HEADLINE_FIELDS}
    all_fields = sum(1 for pm in per_model if all(v["covered"] for v in pm["fields"].values()))
    return Check(
        "top40_coverage",
        "Coverage of the top-40 used models",
        False,
        "info",
        f"{len(top)} models; 2+ agreeing sources on every headline field: {all_fields} "
        f"({100 * all_fields / n:.0f}%, target {100 * COVERAGE_TARGET:.0f}% before launch)",
        {
            "ranking": "RDW NL fleet, then DfT UK fleet (PROVISIONAL proxy for used popularity)",
            "headline_fields": list(HEADLINE_FIELDS),
            "rule": "a model counts for a field when a majority of its variants have 2+ "
            "agreeing sources (estimates never count)",
            "target": COVERAGE_TARGET,
            "share_two_plus_by_field": share,
            "models_all_fields_two_plus": all_fields,
            "models": per_model,
        },
    )


# --- T-059 sections (report) --------------------------------------------------------------


def check_sections(catalogue: dict[str, Any], charging: dict[str, Any] | None = None) -> Check:
    rows = catalogue.get("rows", [])
    epa = Counter()
    for r in rows:
        p = (r.get("provenance") or {}).get("epa_range_km")
        if r.get("epa_range_km") is None or p is None:
            continue
        epa["rows"] += 1
        if p.get("agreeing_sources", 1) >= 2:
            epa["two_plus_agreeing"] += 1
            epa["second_source_via_fueleconomy"] += "fueleconomy" in (p.get("source_ids") or [])
    gens = [g for g in catalogue.get("generations", []) if g.get("years_corroboration")]
    disagree = [
        f"{g['id']}: {c['boundary']} {c['year']} ({c.get('label') or c['source_id']}) vs seed "
        f"{g.get('year_start') if c['boundary'] == 'start' else g.get('year_end')}"
        for g in gens
        for c in g["years_corroboration"]["checks"]
        if not c["agrees"]
    ]
    ki = catalogue.get("known_issues") or {}
    cohorts = [c for cs in (ki.get("by_generation") or {}).values() for c in cs]
    stats = (charging or {}).get("stats", [])
    details = {
        "epa_range_km": dict(sorted(epa.items())),
        "generation_years": {
            "generations_checked": len(gens),
            "corroborated": sum(1 for g in gens if g["years_corroboration"]["corroborated"]),
            "disagreements": _capped(disagree),
        },
        "known_issues": {
            "generations": len(ki.get("by_generation") or {}),
            "cohorts": len(cohorts),
            "cohorts_few_reports": sum(1 for c in cohorts if c.get("few_reports")),
            "codes": len(ki.get("codes") or []),
        },
        "charging_stats": dict(sorted(Counter(str(s.get("source_id")) for s in stats).items())),
    }
    summary = (
        f"EPA {epa['rows']} rows ({epa['second_source_via_fueleconomy']} with a 2nd EPA source"
        f" via fueleconomy); years {details['generation_years']['corroborated']}/{len(gens)}"
        f" generations corroborated; known issues {len(cohorts)} cohorts; charging stats"
        f" {len(stats)} rows"
    )
    return Check("sections", "New sections (T-059)", False, "flag" if disagree else "info",
                 summary, details)  # fmt: skip
