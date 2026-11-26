"""Build one PublishedVariant row per variant from merged facts plus derived metrics (T-007).

Row rules:
- segment and body come from the seed model; change_markers from the seed generation.
- drivetrain comes from the records (field policy `drivetrain`, else source priority).
- on_sale_new = generation end is null AND the variant's last year is this year or last year
  (the last 2 model years; an open seed-manual span counts as this year).
- price_new per country from merged `price_new` facts (one value per country).
- registered_count_nl = RDW count summed over the whole generation (all registration years
  inside the generation span). Every variant of a generation carries the same number: RDW
  does not split by variant. It is a generation figure, not a variant one. Kept for
  backwards compatibility; the same RDW number is also registrations.NL (kind fleet).
- registrations[country] = one RegistrationCount per source and period (matcher
  `registration_entries`): fleet (RDW NL, DfT UK) or new registrations (KBA DE, EEA
  NL/DE/FR/BE), level generation or model (DfT has no year: a model-level count repeats on
  every generation's variants). Never summed across sources, periods or kinds. Provenance
  key `registrations.<country>` lists every source and fact behind that country's counts.
- Charging (Decision 009), see derive/metrics.py for the formulas:
  * a dc_curve fact gives dc_avg_10_80_kw, dc_minutes_10_80 and dc_peak_held_min;
  * else a sourced dc_avg_10_80_kw / dc_minutes_10_80 is kept as is;
  * else a generic default curve from dc_peak_kw (dc_curve_status `default`, estimate);
  * dc_km_per_10min / dc_km_per_20min use motorway consumption;
  * dc_peak_kw_is_claim = the winning dc_peak_kw fact is a maker claim.
  * the average never exceeds the peak: a modelled (non-measured) curve above dc_peak_kw is
    capped at it first; a sourced or measured average above dc_peak_kw goes to
    validation.csv instead of the row.
- Every non-null number gets a provenance entry. Derived numbers get `derived: true`; values
  from a model or ratio rather than a source also get `estimate: true` and list the
  `model-estimate` source. Derived entries carry the lowest `agreeing_sources` of their inputs.
- Numbers are rounded to 1 decimal at the very end (derived values use unrounded inputs).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ev_pipeline.derive import metrics as m
from ev_pipeline.match.matcher import CountAggregate, Problem, RegistrationEntry, VariantInfo
from ev_pipeline.match.seed import Seed
from ev_pipeline.merge.merge import Merged, merge_drivetrain, min_confidence
from ev_pipeline.merge.policy import Policies
from ev_pipeline.release.validate import in_range, range_reason

ESTIMATE_SOURCE = "model-estimate"
EPS = 1e-9
# validation.csv reason when a DC average would exceed the row's DC peak.
DC_AVG_ABOVE_PEAK = "DC average above the published DC peak"
AC_OPTIONAL_NOT_ABOVE = "optional on-board charger not above the standard one"
ESTIMATE_CONTRADICTED = "estimate from battery_kwh_gross contradicted by a citation"
MINUTES_NOTE = "battery_kwh_net x 0.7 / dc_minutes_10_80 x 60 (sourced 10-80% time, no curve)"

DIRECT_FIELDS = (
    "battery_kwh_net",
    "wltp_range_km",
    "epa_range_km",  # T-059: its own field; merged only with other EPA figures
    "consumption_kwh_100km",
    "consumption_motorway_kwh_100km",
    "ac_kw",
    "ac_kw_optional",  # T-063, Decision 034
    "dc_peak_kw",
    "dc_avg_10_80_kw",
    "dc_minutes_10_80",
    "power_kw",
    "accel_0_100_s",
    "boot_l",
    "length_mm",
    "weight_kg",
    "towing_kg",
    "seats",
    "voltage_nominal_v",
    "voltage_max_v",
    # Decision 023: own columns; never used to fill WLTP or kerb weight.
    "nedc_range_km",
    "wltp_range_km_worst",
    "mass_running_order_kg",
)
ID_FIELDS = ("chemistry_id", "cooling_id", "cell_format")
ROW_FLOAT_ORDER = (
    "battery_kwh_net",
    "wltp_range_km",
    "consumption_kwh_100km",
    "ac_kw",
    "ac_kw_optional",
    "dc_peak_kw",
    "dc_avg_10_80_kw",
    "ac_km_per_h",
    "dc_km_per_10min",
    "real_range_km",
)
INT_FIELDS = {"seats", "registered_count_nl"}


def prov(
    source_ids: list[str],
    confidence: str,
    fact_ids: list[str] | None = None,
    derived: bool = False,
    note: str | None = None,
    agreeing_sources: int | None = None,
    estimate: bool = False,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(source_ids))
    if estimate and ESTIMATE_SOURCE not in ids:
        ids.append(ESTIMATE_SOURCE)
    p: dict[str, Any] = {"source_ids": ids, "confidence": "low" if estimate else confidence}
    if fact_ids:
        p["fact_ids"] = list(dict.fromkeys(fact_ids))
    if derived:
        p["derived"] = True
    if estimate:
        p["estimate"] = True
    if agreeing_sources is not None:
        p["agreeing_sources"] = agreeing_sources
    if note:
        p["note"] = note
    return p


def derived_prov(inputs: list[dict[str, Any]], note: str, estimate: bool = False) -> dict[str, Any]:
    """Provenance of a value computed from other row values."""
    return prov(
        [s for p in inputs for s in p["source_ids"] if s != ESTIMATE_SOURCE],
        min_confidence(*[p["confidence"] for p in inputs]),
        [f for p in inputs for f in p.get("fact_ids", [])],
        derived=True,
        note=note,
        agreeing_sources=min(p.get("agreeing_sources", 1) for p in inputs),
        estimate=estimate or any(p.get("estimate") for p in inputs),
    )


def from_merged(mg: Merged, note: str | None = None) -> dict[str, Any]:
    n = "; ".join(x for x in (mg.note(), note) if x) or None
    return prov(
        mg.source_ids, mg.confidence, mg.fact_ids, note=n, agreeing_sources=mg.agreeing_sources
    )


def _num(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return float(v)


@dataclass
class _Work:
    info: VariantInfo
    merged: dict[str, Merged]
    values: dict[str, float]
    provenance: dict[str, dict[str, Any]]
    ladder: m.LadderInput
    extra: dict[str, Any]


def _round(row: dict[str, Any]) -> None:
    for k, v in list(row.items()):
        if k in INT_FIELDS and v is not None:
            row[k] = int(round(v))
        elif isinstance(v, float):
            row[k] = round(v, 1)
    for money in (row.get("price_new") or {}).values():
        money["amount"] = round(float(money["amount"]), 1)


def _curve_points(value: object) -> tuple[list[tuple[float, float]], str] | None:
    """(points, status) from a merged dc_curve value (ChargeCurve model or dict)."""
    raw = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    if not isinstance(raw, dict):
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in raw["points"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return pts, str(raw.get("status", "estimated"))


def _charging(vid, values, pv, mv, drop) -> dict[str, Any]:
    """Fill dc_* values in place. Returns row extras (dc_curve_status, dc_peak_kw_is_claim,
    dc_speed_is_claim)."""
    extra: dict[str, Any] = {}
    net = values.get("battery_kwh_net")
    net_p = [pv["battery_kwh_net"]] if net else []

    # dc_peak_kw: a plain dc_peak_kw fact, else an explicit claim fact.
    peak_mg = mv.get("dc_peak_kw")
    cl = mv.get("dc_peak_kw_claim")
    if "dc_peak_kw" not in values and cl and _num(cl.value) and in_range("dc_peak_kw", cl.value):
        values["dc_peak_kw"] = float(cl.value)
        pv["dc_peak_kw"] = from_merged(cl)
        peak_mg = cl
        extra["dc_peak_kw_is_claim"] = True
    if "dc_peak_kw" in values and "dc_peak_kw_is_claim" not in extra and peak_mg is not None:
        extra["dc_peak_kw_is_claim"] = peak_mg.claim

    curve = None
    curve_p: dict[str, Any] | None = None
    status = None
    cap_note = ""
    if (cmg := mv.get("dc_curve")) is not None and (cp := _curve_points(cmg.value)):
        curve, status = cp
        curve_p = from_merged(cmg)
        # The row's average must never exceed its peak. A curve modelled (not measured) above
        # the published dc_peak_kw (e.g. an estimated KilowattApp curve peaking at 44 kW on
        # a row whose 40 kW peak comes from another source) is capped at that peak first.
        peak_now = values.get("dc_peak_kw")
        if status != "measured" and peak_now and max(p for _, p in curve) > peak_now + EPS:
            cap_note = (
                f"; curve capped at dc_peak_kw {peak_now:g} kW"
                f" (curve peak {max(p for _, p in curve):g} kW)"
            )
            curve = m.cap_curve(curve, peak_now)
    stats = m.integrate_curve(curve, net) if curve else None
    if curve and stats is None:
        drop(vid, "dc_curve", "", "kW", "unusable charge curve (zero or negative kW)")
    from_curve = stats is not None

    # T-155: no curve and no sourced average, but a sourced 10-80 % time: the average comes
    # from that time (the inverse of minutes_from_avg). A real time beats the generic default
    # curve shape, so this runs before the default curve.
    mins = values.get("dc_minutes_10_80")
    if not from_curve and "dc_avg_10_80_kw" not in values and mins and mins > 0 and net:
        avg = m.avg_from_minutes(net, mins)
        peak = values.get("dc_peak_kw")
        if peak and avg > peak + EPS:
            # T-161 (T-155 nit 4): the time implies more than the stated peak, so one of them is
            # wrong. The time goes to review; the row falls back to the default curve below.
            drop(
                vid,
                "dc_minutes_10_80",
                mins,
                "min",
                f"{DC_AVG_ABOVE_PEAK} ({peak:g} kW): the 10-80% time implies {avg:.1f} kW;"
                " default curve used",
            )
            del values["dc_minutes_10_80"]
            pv.pop("dc_minutes_10_80", None)
        elif in_range("dc_avg_10_80_kw", avg):
            values["dc_avg_10_80_kw"] = avg
            pv["dc_avg_10_80_kw"] = derived_prov([pv["dc_minutes_10_80"], *net_p], MINUTES_NOTE)
            extra["_dc_from_minutes"] = True
            mins_mg = mv.get("dc_minutes_10_80")
            if mins_mg is not None:
                extra["dc_speed_is_claim"] = mins_mg.claim
        else:
            drop(
                vid,
                "dc_avg_10_80_kw",
                round(avg, 1),
                "kW",
                range_reason("dc_avg_10_80_kw", avg) + " (from dc_minutes_10_80)",
            )

    if not from_curve and "dc_avg_10_80_kw" not in values and "dc_peak_kw" in values:
        # No curve and no sourced average: generic default curve shape.
        curve = m.default_curve(values["dc_peak_kw"])
        stats = m.integrate_curve(curve, net)
        status = "default"
        curve_p = derived_prov(
            [pv["dc_peak_kw"]], "PROVISIONAL default curve shape from dc_peak_kw", estimate=True
        )
        from_curve = stats is not None

    if from_curve and stats is not None and curve_p is not None:
        est = status != "measured"
        inputs = [curve_p, *net_p]
        label = "PROVISIONAL default" if status == "default" else status
        if "dc_avg_10_80_kw" not in values or status == "measured":
            if in_range("dc_avg_10_80_kw", stats.avg_kw):
                values["dc_avg_10_80_kw"] = stats.avg_kw
                pv["dc_avg_10_80_kw"] = derived_prov(
                    [curve_p], f"integrated {label} curve, 10-80%{cap_note}", estimate=est
                )
            else:
                drop(
                    vid,
                    "dc_avg_10_80_kw",
                    stats.avg_kw,
                    "kW",
                    range_reason("dc_avg_10_80_kw", stats.avg_kw),
                )
        if stats.minutes is not None and ("dc_minutes_10_80" not in values or status == "measured"):
            values["dc_minutes_10_80"] = stats.minutes
            pv["dc_minutes_10_80"] = derived_prov(
                inputs, f"integrated {label} curve, 10-80%{cap_note}", estimate=est
            )
        if stats.peak_held_min is not None:
            values["dc_peak_held_min"] = stats.peak_held_min
            pv["dc_peak_held_min"] = derived_prov(
                inputs, f"minutes >= 90% of peak, {label} curve{cap_note}", estimate=est
            )
        extra["dc_curve_status"] = status

    # A sourced or measured average above the published peak contradicts it: never publish
    # both. The average goes to review (validation.csv); the peak keeps its own provenance.
    avg, peak = values.get("dc_avg_10_80_kw"), values.get("dc_peak_kw")
    if avg is not None and peak and avg > peak + EPS:
        drop(vid, "dc_avg_10_80_kw", round(avg, 1), "kW", f"{DC_AVG_ABOVE_PEAK} ({peak:g} kW)")
        del values["dc_avg_10_80_kw"]
        pv.pop("dc_avg_10_80_kw", None)

    if "dc_minutes_10_80" not in values and net and "dc_avg_10_80_kw" in values:
        values["dc_minutes_10_80"] = m.minutes_from_avg(net, values["dc_avg_10_80_kw"])
        pv["dc_minutes_10_80"] = derived_prov(
            [pv["dc_avg_10_80_kw"], *net_p], "battery_kwh_net x 0.7 / dc_avg_10_80_kw x 60"
        )
    return extra


def _curve_note(status: str | None, avg_p: dict[str, Any], from_minutes: bool = False) -> str:
    if from_minutes:
        srcs = "+".join(s for s in avg_p["source_ids"] if s != ESTIMATE_SOURCE)
        return f"; dc_avg_10_80_kw from the 10-80% time ({srcs}), no charge curve"
    if not avg_p.get("derived") or status is None:
        return "; dc_avg_10_80_kw is a sourced figure"
    if status == "measured":
        return "; measured charge curve"
    if status == "default":
        return "; PROVISIONAL default curve shape"
    srcs = "+".join(s for s in avg_p["source_ids"] if s != ESTIMATE_SOURCE)
    return f"; {status} charge curve ({srcs})"


def _mway_note(mway_p: dict[str, Any]) -> str:
    return "; motorway consumption is an estimate" if mway_p.get("estimate") else ""


def registrations_block(
    by_country: dict[str, list[RegistrationEntry]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """(row registrations, provenance entries keyed `registrations.<country>`)."""
    regs: dict[str, list[dict[str, Any]]] = {}
    pv: dict[str, dict[str, Any]] = {}
    for cc in sorted(by_country):
        entries = sorted(by_country[cc], key=lambda e: (e.source_id, e.kind, e.period or ""))
        regs[cc] = [
            {
                "count": int(e.count),
                "kind": e.kind,
                "period": e.period,
                "level": e.level,
                "source_id": e.source_id,
            }
            for e in entries
        ]
        notes = []
        for e in entries:
            n = f"{e.source_id}: {e.kind} {e.period or ''}, {e.level} level".replace(" ,", ",")
            if e.level == "model":
                n += " (whole model, same number on every generation)"
            if e.notes:
                n += " [" + "; ".join(e.notes) + "]"
            notes.append(n)
        pv[f"registrations.{cc}"] = prov(
            [e.source_id for e in entries],
            min_confidence(*[e.confidence for e in entries]),
            [f for e in entries for f in e.fact_ids],
            note="Official counts, never added across sources, periods or kinds: "
            + " | ".join(notes),
        )
    return regs, pv


def build_rows(
    variants: dict[str, VariantInfo],
    merged: dict[str, dict[str, Merged]],
    seed: Seed,
    nl_counts: dict[str, CountAggregate],
    today: date,
    release: int,
    policies: Policies | None = None,
    inherited: dict[str, dict[str, Any]] | None = None,
    registrations: dict[str, dict[str, list[RegistrationEntry]]] | None = None,
    citations: dict[str, dict[str, list[float]]] | None = None,
) -> tuple[list[dict[str, Any]], list[Problem]]:
    """`inherited`: per variant, extra row values with provenance from links/packs
    (see derive/links.py); applied after merged facts, never over them.
    `registrations`: generation id -> country -> entries (matcher.registration_entries).
    `citations`: per variant and field, values of citations that don't ship (A-06 F3
    evidence). An estimate that every such citation contradicts is not published: a value
    withheld because a citation contradicts it must not come back as a ratio estimate."""
    regs_by_gen = registrations or {}
    cites_by_vid = citations or {}
    policies = policies or Policies()
    inherited = inherited or {}
    problems: list[Problem] = []
    work: list[_Work] = []
    observations: dict[str, m.RealObservation] = {}

    def drop(vid: str, field: str, value: object, unit: str, reason: str, src: str = "") -> None:
        problems.append(Problem("row", src, "", vid, field, str(value), unit, reason))

    for vid in sorted(variants):
        info = variants[vid]
        mv = merged.get(vid) or {}
        if not mv:
            continue
        gen = seed.generations[info.generation_id]
        model = seed.models[gen.model_id]
        values: dict[str, float] = {}
        pv: dict[str, dict[str, Any]] = {}
        for f in DIRECT_FIELDS:
            mg = mv.get(f)
            if mg is None:
                continue
            x = _num(mg.value)
            if x is None:
                drop(vid, f, mg.value, mg.unit, "not a number", mg.winner.source_id)
                continue
            values[f] = x
            pv[f] = from_merged(mg)
        # T-063: an optional charger is by definition bigger than the standard one.
        std, opt = values.get("ac_kw"), values.get("ac_kw_optional")
        if std is not None and opt is not None and opt <= std + EPS:
            drop(vid, "ac_kw_optional", opt, "kW", f"{AC_OPTIONAL_NOT_ABOVE} ({std:g} kW)")
            del values["ac_kw_optional"]
            pv.pop("ac_kw_optional", None)
        inh = inherited.get(vid, {})
        for f, (val, p) in inh.get("numbers", {}).items():
            if f not in values and f != "battery_kwh_gross":
                values[f] = float(val)
                pv[f] = p

        # Net battery from gross when only gross is known.
        gross = mv.get("battery_kwh_gross")
        if "battery_kwh_net" not in values and gross is not None and _num(gross.value):
            est = m.net_from_gross(float(gross.value))
            cited = cites_by_vid.get(vid, {}).get("battery_kwh_net", [])
            pol = policies.for_field("battery_kwh_net")
            if cited and not any(pol.agree(est, c) for c in cited):
                drop(
                    vid,
                    "battery_kwh_net",
                    round(est, 1),
                    "kWh",
                    f"{ESTIMATE_CONTRADICTED} ({'/'.join(f'{c:g}' for c in cited)} kWh)",
                )
            elif in_range("battery_kwh_net", est):
                values["battery_kwh_net"] = est
                pv["battery_kwh_net"] = derived_prov(
                    [from_merged(gross)],
                    f"PROVISIONAL {m.NET_PER_GROSS} x battery_kwh_gross (no net figure)",
                    estimate=True,
                )
            else:
                drop(vid, "battery_kwh_net", est, "kWh", range_reason("battery_kwh_net", est))

        # WLTP, or WLTP equivalent from EPA.
        wltp = values.get("wltp_range_km")
        wltp_p = pv.get("wltp_range_km")
        epa_note = ""
        if wltp is None and (epa := mv.get("epa_range_km")) is not None and _num(epa.value):
            wltp = m.wltp_from_epa(float(epa.value))
            epa_note = f"WLTP estimated as EPA x {m.WLTP_PER_EPA}"
            wltp_p = derived_prov([from_merged(epa)], epa_note, estimate=True)

        # Consumption estimate.
        if "consumption_kwh_100km" not in values and "battery_kwh_net" in values and wltp:
            est = m.consumption_estimate(values["battery_kwh_net"], wltp)
            if in_range("consumption_kwh_100km", est):
                values["consumption_kwh_100km"] = est
                pv["consumption_kwh_100km"] = derived_prov(
                    [pv["battery_kwh_net"], wltp_p],
                    f"battery_kwh_net / wltp_range_km x 100 x {m.WALL_PER_BATTERY_WLTP}"
                    " (charging losses)" + (f"; {epa_note}" if epa_note else ""),
                    estimate=True,
                )
            else:
                reason = range_reason("consumption_kwh_100km", round(est, 2)) + " (derived)"
                drop(vid, "consumption_kwh_100km", round(est, 2), "kWh/100km", reason)

        extra = _charging(vid, values, pv, mv, drop)

        cons = values.get("consumption_kwh_100km")
        if "consumption_motorway_kwh_100km" not in values and cons:
            values["consumption_motorway_kwh_100km"] = m.motorway_consumption(cons)
            cp = pv["consumption_kwh_100km"]
            what = "estimated consumption" if cp.get("estimate") else "consumption"
            srcs = "+".join(s for s in cp["source_ids"] if s != ESTIMATE_SOURCE) or "estimate"
            pv["consumption_motorway_kwh_100km"] = derived_prov(
                [cp],
                f"PROVISIONAL {what} ({srcs}) x {m.MOTORWAY_PER_WLTP}",
                estimate=True,
            )
        if cons and "ac_kw" in values:
            values["ac_km_per_h"] = m.ac_km_per_h(values["ac_kw"], cons)
            pv["ac_km_per_h"] = derived_prov(
                [pv["ac_kw"], pv["consumption_kwh_100km"]], "ac_kw / consumption x 100"
            )
        mway = values.get("consumption_motorway_kwh_100km")
        if mway and "dc_avg_10_80_kw" in values:
            net = values.get("battery_kwh_net")
            inputs = [pv["dc_avg_10_80_kw"], pv["consumption_motorway_kwh_100km"]]
            if net:
                inputs.append(pv["battery_kwh_net"])
            for minutes, f in ((10, "dc_km_per_10min"), (20, "dc_km_per_20min")):
                values[f] = m.km_in_minutes(values["dc_avg_10_80_kw"], minutes, mway, net)
                pv[f] = derived_prov(
                    inputs,
                    f"dc_avg_10_80_kw x {minutes}/60 / motorway consumption x 100"
                    + (", capped at the 10-80% window" if net else ", no battery size: uncapped")
                    + _curve_note(
                        extra.get("dc_curve_status"),
                        pv["dc_avg_10_80_kw"],
                        bool(extra.get("_dc_from_minutes")),
                    )
                    + _mway_note(pv["consumption_motorway_kwh_100km"]),
                )

        drivetrain, _ = merge_drivetrain(info.drivetrains, policies.fields.get("drivetrain"))
        li = m.LadderInput(
            variant_id=vid,
            generation_id=gen.id,
            make_id=model.make_id,
            body=model.body,
            drivetrain=drivetrain,
            battery_kwh_net=values.get("battery_kwh_net"),
            wltp_km=wltp,
            wltp_source_ids=list((wltp_p or {}).get("source_ids", [])),
            wltp_fact_ids=list((wltp_p or {}).get("fact_ids", [])),
        )
        if (rr := mv.get("real_range_km")) is not None and _num(rr.value):
            observations[vid] = m.RealObservation(
                float(rr.value), "exact-test", rr.source_ids, rr.fact_ids, rr.confidence
            )
        extra["_wltp_p"] = wltp_p
        extra["_inherited"] = inh
        work.append(_Work(info, mv, values, pv, li, extra))

    inputs_all = [w.ladder for w in work]
    ratios = m.brand_body_drivetrain_ratios(inputs_all, observations)
    rows: list[dict[str, Any]] = []
    for w in work:
        rows.append(
            _finish_row(
                w,
                seed,
                inputs_all,
                observations,
                ratios,
                nl_counts,
                today,
                release,
                drop,
                regs_by_gen.get(w.info.generation_id, {}),
            )  # fmt: skip
        )
    return rows, problems


def _finish_row(
    w, seed, inputs_all, observations, ratios, nl_counts, today, release, drop, regs=None
):
    info, values, pv = w.info, w.values, w.provenance
    gen = seed.generations[info.generation_id]
    model = seed.models[gen.model_id]
    make = seed.makes[model.make_id]

    lr = m.real_range(w.ladder, inputs_all, observations, ratios)
    rung = None
    if lr is not None:
        values["real_range_km"] = lr.km
        rung = lr.rung
        measured = lr.rung in ("owner-data", "exact-test")
        base = w.extra.get("_wltp_p") or {}
        pv["real_range_km"] = prov(
            [s for s in lr.source_ids if s != ESTIMATE_SOURCE],
            lr.confidence,
            lr.fact_ids,
            derived=not measured,
            note=lr.note or None,
            agreeing_sources=1 if measured else base.get("agreeing_sources", 1),
            estimate=not measured,
        )

    if (agg := nl_counts.get(gen.id)) is not None:
        values["registered_count_nl"] = float(agg.value)
        pv["registered_count_nl"] = prov(
            agg.source_ids,
            "medium",
            agg.fact_ids,
            note="NL registrations for the whole generation (same on every variant)",
            agreeing_sources=1,
        )

    price_new: dict[str, dict[str, Any]] = {}
    for k, mg in w.merged.items():
        if not k.startswith("price_new."):
            continue
        amount = _num(mg.value)
        if amount is None:
            drop(info.id, k, mg.value, mg.unit, "not a number", mg.winner.source_id)
            continue
        price_new[k.split(".", 1)[1]] = {"amount": amount, "currency": mg.unit}
        pv[k] = from_merged(mg)

    years = sorted(info.years)
    year_start = years[0] if years else gen.year_start
    if info.explicit_end is not None:
        year_end: int | None = info.explicit_end
    elif info.open_end:
        year_end = None
    else:
        year_end = years[-1] if years else gen.year_end
    last_year = today.year if year_end is None else year_end
    on_sale = gen.year_end is None and last_year >= today.year - 1

    def independent(field: str) -> int:
        mg = w.merged.get(field)
        return mg.independent_agreeing if mg is not None else 0

    row: dict[str, Any] = {
        "release": release,
        "variant_id": info.id,
        "variant_name": info.name,
        "generation_id": gen.id,
        "generation_name": gen.name,
        "generation_uncertain": gen.uncertain,
        "model_id": model.id,
        "model_name": model.name,
        "make_id": make.id,
        "make_name": make.name,
        "year_start": year_start,
        "year_end": year_end,
        "era": m.era(year_start),
    }
    if model.segment:
        row["segment"] = model.segment
    if model.body:
        row["body"] = model.body
    if w.ladder.drivetrain:
        row["drivetrain"] = w.ladder.drivetrain
    for f in ROW_FLOAT_ORDER:
        row[f] = values.get(f)
    row["real_range_rung"] = rung
    for f in ("power_kw", "accel_0_100_s", "boot_l", "length_mm", "weight_kg", "towing_kg"):
        row[f] = values.get(f)
    row["seats"] = values.get("seats")
    row["on_sale_new"] = on_sale
    if price_new:
        row["price_new"] = dict(sorted(price_new.items()))
    row["registered_count_nl"] = values.get("registered_count_nl")
    if regs:
        row["registrations"], reg_pv = registrations_block(regs)
        pv.update(reg_pv)
    # sourced = battery and range each confirmed by 2+ agreeing sources; a derived or
    # inherited net battery does not count.
    bat_p = pv.get("battery_kwh_net", {})
    bat = (
        0
        if bat_p.get("derived") or "battery_kwh_net" not in w.merged
        else independent("battery_kwh_net")
    )
    row["quality_tier"] = m.quality_tier(bat, independent("wltp_range_km"))
    if gen.change_markers:
        row["change_markers"] = [
            {"year": int(c["year"]), "text": str(c["text"])} for c in gen.change_markers
        ]
    for f in (
        "dc_minutes_10_80",
        "dc_km_per_20min",
        "dc_peak_held_min",
        "consumption_motorway_kwh_100km",
    ):
        row[f] = values.get(f)
    if "dc_curve_status" in w.extra:
        row["dc_curve_status"] = w.extra["dc_curve_status"]
    if "dc_peak_kw_is_claim" in w.extra and row.get("dc_peak_kw") is not None:
        row["dc_peak_kw_is_claim"] = bool(w.extra["dc_peak_kw_is_claim"])
    if "dc_speed_is_claim" in w.extra and row.get("dc_avg_10_80_kw") is not None:
        row["dc_speed_is_claim"] = bool(w.extra["dc_speed_is_claim"])
    for f in (
        "epa_range_km",
        "voltage_nominal_v",
        "voltage_max_v",
        "charger_400v_kw",
        "nedc_range_km",
        "wltp_range_km_worst",
        "mass_running_order_kg",
    ):
        if values.get(f) is not None:
            row[f] = values[f]
    for f in ID_FIELDS:
        mg = w.merged.get(f)
        if mg is not None and isinstance(mg.value, str):
            row[f] = mg.value
            pv[f] = from_merged(mg)
    inh = w.extra.get("_inherited") or {}
    for f, val in inh.get("labels", {}).items():
        if row.get(f) is None and val is not None:
            row[f] = val
    for f, p in inh.get("label_provenance", {}).items():
        if row.get(f) is not None:
            pv.setdefault(f, p)
    row["provenance"] = dict(sorted(pv.items()))
    _round(row)
    return row
