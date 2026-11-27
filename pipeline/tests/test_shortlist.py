"""T-069: shortlist scores per variant and profile. Fixture rules + rows, no network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ev_pipeline.derive import shortlist as sl

RULES: dict[str, Any] = {
    "schema": "shortlist-rules/v1",
    "review": True,
    "weight_step_factor": 1.5,
    "profiles": [
        {
            "id": "road-tripper",
            "bands": {
                "800v": {"shortlist": 70, "consider": 60},
                "default": {"shortlist": 60, "consider": 50},
            },
            "gates": [
                {"id": "dc-not-terrible", "field": "dc_km_per_20min", "min_km_per_h": 300},
                {"id": "winter-range-floor", "field": "real_range_km", "min_km": 250},
            ],
            "factors": [
                {
                    "id": "dc-speed",
                    "field": "dc_km_per_20min",
                    "poor": 450,
                    "great": 1300,
                    "weight": 30,
                },
                {
                    "id": "winter-range",
                    "field": "real_range_km",
                    "poor": 300,
                    "great": 430,
                    "weight": 20,
                },
                {"id": "space", "field": "boot_l", "poor": 380, "great": 600, "weight": 12},
                {"id": "one-pedal", "field": "one_pedal", "status": "gap", "weight": 10},
                {"id": "v2l", "field": "bidi", "weight": 5},
            ],
            "bonuses": [
                {"id": "newest-version", "points": 4},
                {"id": "lfp-daily-100", "points": 2, "field": "charge_100_daily"},
            ],
            "penalties": [
                {"id": "too-big-for-b-roads", "points": -16, "applies_with": "rural"},
                {"id": "older-version", "points": -6},
            ],
        },
        {
            "id": "daily-driver",
            "bands": {"default": {"shortlist": 62, "consider": 48}},
            "gates": [
                {
                    "id": "winter-range-daily",
                    "field": "real_range_km",
                    "min_km": 200,
                    "rural_min_km": 250,
                }
            ],
            "factors": [
                {
                    "id": "efficiency",
                    "field": "consumption_kwh_100km",
                    "poor": 220,
                    "great": 140,
                    "weight": 14,
                },
                {"id": "heat-pump", "field": "heat_pump", "weight": 8},
                {"id": "battery-health-risk", "field": "cooling_id", "weight": 10},
            ],
        },
        {
            "id": "kerbside-charger",
            "weight_steps": {"efficiency": 2},
            "extra_factors": [{"id": "fast-on-400v", "field": "fast_on_400v", "weight": 8}],
        },
    ],
    "modifiers": [
        {"id": "urban", "weight_steps": {"efficiency": 1}},
        {
            "id": "rural",
            "use_rural_gates": True,
            "weight_steps": {"winter-range": 1},
            "penalties": [{"id": "too-big-for-b-roads", "points": -8}],
        },
    ],
}


def params(**over: Any) -> dict[str, Any]:
    p = sl.load_params()
    p["combos"] = {
        "trip_profiles": ["road-tripper", "daily-driver"],
        "charging": ["home", "kerbside-charger"],
        "home_areas": ["suburban", "urban", "rural"],
    }
    p["basis_scale"] = {}  # tests check the rule maths; the bridge has its own test
    p.update(over)
    return p


def row(vid: str = "m-gen1-a", **kw: Any) -> dict[str, Any]:
    base = {
        "variant_id": vid,
        "model_id": "m",
        "generation_id": "m-gen1",
        "year_start": 2024,
        "voltage_class_id": "800v",
        "dc_km_per_20min": 400.0,
        "boot_l": 600.0,
        "battery_kwh_net": 80.0,
    }
    base.update(kw)
    return base


def matrix_for(vid: str, winter_wh: float, mild_wh: float) -> dict[str, Any]:
    cells = []
    for temp, wh in (("t1", winter_wh), ("t5", mild_wh)):
        for band in ("town", "rural", "motorway"):
            cells.append({"road_band": band, "temperature_band_id": temp, "wh_km": wh})
    return {"variant_id": vid, "usable_kwh": 80.0, "cells": cells}


def write_rules(tmp_path: Path, rules: dict[str, Any] = RULES) -> Path:
    (tmp_path / "editorial").mkdir(exist_ok=True)
    (tmp_path / "editorial" / "shortlist_rules.yaml").write_text(yaml.safe_dump(rules))
    return tmp_path


def run(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    matrix: dict[str, Any] | None = None,
    p: dict[str, Any] | None = None,
) -> sl.ShortlistResult:
    pf = tmp_path / "params.yaml"
    pf.write_text(yaml.safe_dump(p or params()))
    return sl.build_shortlist(rows, matrix, write_rules(tmp_path), 7, "2026-11-15T00:00:00Z", pf)


def scores(res: sl.ShortlistResult, vid: str) -> dict[str, Any]:
    assert res.document
    return next(v for v in res.document["variants"] if v["variant_id"] == vid)


def test_linear_factor_clamped_and_inverted() -> None:
    assert sl.lin(450, 450, 1300) == 0.0
    assert sl.lin(2000, 450, 1300) == 1.0
    assert sl.lin(180, 220, 140) == pytest.approx(0.5)  # lower is better
    assert sl.lin(5, 7, 7) == 0.0


def test_winter_override_and_unit_bridge(tmp_path: Path) -> None:
    # 80 kWh / 200 Wh/km = 400 km winter; dc 400 km/20 min = 1200 km/h
    r = row()
    res = run(tmp_path, [r], {"variants": [matrix_for(r["variant_id"], 200, 150)]})
    v = scores(res, r["variant_id"])
    assert v["derived"] == {"winter_range_km": 400, "real_wh_km": 175.0}
    f = v["factors"]["road-tripper"]
    assert f["dc-speed"] == pytest.approx((1200 - 450) / 850, abs=1e-3)
    assert f["winter-range"] == pytest.approx((400 - 300) / 130, abs=1e-3)
    assert f["space"] == 1.0


def test_basis_scale_applies_before_thresholds(tmp_path: Path) -> None:
    r = row(dc_km_per_20min=200.0)  # 600 km/h raw → 300 x 1.5 scale... checks the multiplier
    res = run(tmp_path, [r], None, params(basis_scale={"dc_km_per_20min": 1.5}))
    assert scores(res, r["variant_id"])["factors"]["road-tripper"]["dc-speed"] == pytest.approx(
        (900 - 450) / 850, abs=1e-3
    )


def test_unknown_is_neutral_and_listed(tmp_path: Path) -> None:
    r = row()
    res = run(tmp_path, [r], {"variants": [matrix_for(r["variant_id"], 200, 150)]})
    v = scores(res, r["variant_id"])
    assert "one-pedal" in v["unknown"]["road-tripper"]
    assert "v2l" in v["unknown"]["road-tripper"]  # no bidi rows = not known, not "none"
    assert v["factors"]["road-tripper"]["one-pedal"] is None


def test_more_than_half_unknown_is_not_enough_data(tmp_path: Path) -> None:
    r = row(dc_km_per_20min=None, boot_l=None)  # dc 30 + winter 20 + space 12 + gaps 15 of 77
    res = run(tmp_path, [r])
    s = scores(res, r["variant_id"])["scores"]["road-tripper"]
    assert s["band"] == "not-enough-data"
    assert "gate:dc-not-terrible" in scores(res, r["variant_id"])["unknown"]["road-tripper"]


def test_gate_fails_on_known_value_only(tmp_path: Path) -> None:
    slow = row("m-gen1-slow", dc_km_per_20min=90.0)  # 270 km/h < 300
    res = run(tmp_path, [slow])
    s = scores(res, slow["variant_id"])["scores"]["road-tripper"]
    assert s == {"score": 0, "band": "ruled-out", "reasons": ["gate:dc-not-terrible"]}


def test_rural_gate_uses_rural_floor(tmp_path: Path) -> None:
    r = row(real_range_km=230.0, consumption_kwh_100km=16.0, cooling_id="liquid")
    res = run(tmp_path, [r])
    sc = scores(res, r["variant_id"])["scores"]
    assert sc["daily-driver"]["band"] != "ruled-out"
    assert sc["daily-driver.rural"]["band"] == "ruled-out"


def test_categories_and_efficiency_units(tmp_path: Path) -> None:
    r = row(real_range_km=300.0, consumption_kwh_100km=18.0, heat_pump="option", cooling_id="air")
    p = params(field_overrides={})  # read consumption_kwh_100km directly: x10 = Wh/km
    f = scores(run(tmp_path, [r], None, p), r["variant_id"])["factors"]["daily-driver"]
    assert f["efficiency"] == pytest.approx(0.5)
    assert f["heat-pump"] == 0.6
    assert f["battery-health-risk"] == 0.0


def test_not_disclosed_heat_pump_is_unknown(tmp_path: Path) -> None:
    r = row(real_range_km=300.0, heat_pump="not-disclosed")
    v = scores(run(tmp_path, [r]), r["variant_id"])
    assert v["factors"]["daily-driver"]["heat-pump"] is None


def test_weight_steps_change_score(tmp_path: Path) -> None:
    # efficiency great, the rest poor: urban (+1 efficiency) must score higher than suburban
    r = row(real_range_km=300.0, consumption_kwh_100km=12.0, heat_pump="none", cooling_id="air")
    p = params(field_overrides={})
    sc = scores(run(tmp_path, [r], None, p), r["variant_id"])["scores"]
    assert sc["daily-driver.urban"]["score"] > sc["daily-driver"]["score"]
    assert sc["daily-driver+kerbside"]["score"] > sc["daily-driver"]["score"]


def test_kerbside_extra_factor(tmp_path: Path) -> None:
    r = row(real_range_km=300.0, fast_on_400v=True)
    v = scores(run(tmp_path, [r]), r["variant_id"])
    assert v["factors"]["daily-driver"]["fast-on-400v"] == 1.0
    assert set(v["scores"]) == {
        "road-tripper",
        "road-tripper.urban",
        "road-tripper.rural",
        "road-tripper+kerbside",
        "road-tripper+kerbside.urban",
        "road-tripper+kerbside.rural",
        "daily-driver",
        "daily-driver.urban",
        "daily-driver.rural",
        "daily-driver+kerbside",
        "daily-driver+kerbside.urban",
        "daily-driver+kerbside.rural",
    }


def vrow(vid: str, **kw: Any) -> dict[str, Any]:
    return row(vid, **{"drivetrain": "rwd", "power_kw": 200.0, **kw})


def test_version_flags_need_better_charging() -> None:
    rows = [
        vrow("m-old", year_start=2021, dc_km_per_20min=300.0),
        vrow("m-old-fast", year_start=2021, dc_km_per_20min=500.0),
        vrow("m-new", year_start=2024, dc_km_per_20min=400.0),
        vrow("x-only", model_id="x", year_start=2020),
    ]
    f = sl.version_flags(rows)
    assert f["m-new"] == {"newest-version"}
    assert f["m-old"] == {"older-version"}
    assert "m-old-fast" not in f  # the newer one charges slower: not an "older version"
    assert "x-only" not in f


def test_version_flags_new_entry_trim_is_its_own_line() -> None:
    """Decision 088: e-tron GT 2025 entry trim (a cheaper, weaker line) doesn't make the 2024
    S / RS / RS performance older; the 2024 trims are one line (435 → 500 = +15 %, not more)."""
    rows = [
        vrow(
            "gt-entry-2025",
            year_start=2025,
            drivetrain="awd",
            power_kw=350.0,
            dc_km_per_20min=600.0,
        ),
        vrow("gt-s-2024", year_start=2024, drivetrain="awd", power_kw=435.0, dc_km_per_20min=500.0),
        vrow(
            "gt-rs-2024", year_start=2024, drivetrain="awd", power_kw=500.0, dc_km_per_20min=500.0
        ),
        vrow(
            "gt-rsp-2024", year_start=2024, drivetrain="awd", power_kw=550.0, dc_km_per_20min=500.0
        ),
    ]
    lines = sl.trim_lines(rows)
    assert [[r["variant_id"] for r in ln] for ln in lines] == [
        ["gt-entry-2025"],
        ["gt-s-2024", "gt-rs-2024"],  # 500 ≤ 435 × 1.15 = 500.25
        ["gt-rsp-2024"],
    ]
    assert sl.version_flags(rows) == {}


def test_version_flags_same_line_across_years_and_split_by_drivetrain() -> None:
    rows = [
        vrow("ev6-2021-rwd", year_start=2021, power_kw=168.0, dc_km_per_20min=300.0),
        vrow("ev6-2024-rwd", year_start=2024, power_kw=168.0, dc_km_per_20min=380.0),
        vrow(
            "ev6-2021-awd", year_start=2021, drivetrain="awd", power_kw=239.0, dc_km_per_20min=290.0
        ),
    ]
    f = sl.version_flags(rows)
    assert f["ev6-2024-rwd"] == {"newest-version"}
    assert f["ev6-2021-rwd"] == {"older-version"}
    assert "ev6-2021-awd" not in f  # only AWD of its line: no newer AWD to compare with


def test_version_flags_unknown_drivetrain_or_power_never_compared() -> None:
    rows = [
        vrow("a-2021", year_start=2021, dc_km_per_20min=300.0),
        vrow("a-2024", year_start=2024, dc_km_per_20min=400.0),
        vrow("a-nodt", year_start=2020, drivetrain=None, dc_km_per_20min=100.0),
        vrow("a-nd", year_start=2020, drivetrain="not-disclosed", dc_km_per_20min=100.0),
        vrow("a-nopw", year_start=2020, power_kw=None, dc_km_per_20min=100.0),
        vrow("a-strpw", year_start=2020, power_kw="not-disclosed", dc_km_per_20min=100.0),
    ]
    f = sl.version_flags(rows)
    assert f == {"a-2024": {"newest-version"}, "a-2021": {"older-version"}}


def test_version_flags_gap_from_params() -> None:
    rows = [
        vrow("p-2021", year_start=2021, power_kw=150.0, dc_km_per_20min=300.0),
        vrow("p-2024", year_start=2024, power_kw=180.0, dc_km_per_20min=400.0),  # +20 %
    ]
    assert sl.version_flags(rows) == {}
    assert sl.version_flags(rows, gap=0.25)["p-2021"] == {"older-version"}
    assert sl.load_params()["trim_line_power_gap"] == pytest.approx(0.15)


def test_trim_lines_exact_15_percent_boundary() -> None:
    """T-166: IEEE-754 `100.0 * (1 + 0.15) == 114.99999999999999 < 115.0` must not split exact
    +15 % pairs (Stellantis 100 -> 115 kW e-CMP models), while > 15 % still starts a new line."""
    assert 100.0 * (1 + 0.15) < 115.0  # confirm the float representation we guard against
    rows = [
        vrow(
            "e208-50",
            drivetrain="fwd",
            year_start=2020,
            power_kw=100.0,
            dc_km_per_20min=180.0,
        ),
        vrow(
            "e208-51",
            drivetrain="fwd",
            year_start=2024,
            power_kw=115.0,
            dc_km_per_20min=210.0,
        ),
        vrow(
            "e208-gt-plus",
            drivetrain="fwd",
            year_start=2025,
            power_kw=115.1,
            dc_km_per_20min=220.0,
        ),
    ]
    lines = sl.trim_lines(rows, gap=0.15)
    assert [[r["variant_id"] for r in ln] for ln in lines] == [
        ["e208-50", "e208-51"],
        ["e208-gt-plus"],
    ]
    flags = sl.version_flags(rows[:2], gap=0.15)
    assert flags == {"e208-50": {"older-version"}, "e208-51": {"newest-version"}}


def test_bonus_and_rural_penalty(tmp_path: Path) -> None:
    big = row(charge_100_daily=True, mass_running_order_kg=2500.0)  # kerb 2425 > 2300
    sc = scores(run(tmp_path, [big]), big["variant_id"])["scores"]
    assert "bonus:lfp-daily-100" in sc["road-tripper"]["reasons"]
    assert "penalty:too-big-for-b-roads" not in sc["road-tripper"]["reasons"]
    assert "penalty:too-big-for-b-roads" in sc["road-tripper.rural"]["reasons"]
    # the profile's own -16 wins over the modifier's -8 (no double count)
    assert sc["road-tripper"]["score"] - sc["road-tripper.rural"]["score"] == pytest.approx(
        16, abs=3
    )


def test_bands_by_voltage_class(tmp_path: Path) -> None:
    assert sl.band_for(65, RULES["profiles"][0]["bands"], "800v") == "consider"
    assert sl.band_for(65, RULES["profiles"][0]["bands"], "400v") == "shortlist"
    assert sl.band_for(40, RULES["profiles"][0]["bands"], None) == "fallback"


def test_reasons_list_strengths_and_weaknesses(tmp_path: Path) -> None:
    r = row(dc_km_per_20min=450.0, boot_l=300.0)  # dc 1350 km/h great, space poor
    s = scores(run(tmp_path, [r]), r["variant_id"])["scores"]["road-tripper"]
    assert "+dc-speed" in s["reasons"] and "-space" in s["reasons"]


def test_no_rules_file_ships_nothing(tmp_path: Path) -> None:
    res = sl.build_shortlist([row()], None, tmp_path, 1, "2026-11-15T00:00:00Z")
    assert res.document is None and res.log == {"status": "no rules file"}


def test_coverage_counts_rule_fields(tmp_path: Path) -> None:
    rows = [row("a", heat_pump="not-disclosed"), row("b", heat_pump="standard", boot_l=None)]
    res = run(tmp_path, rows)
    assert res.coverage["heat_pump"] == 1
    assert res.coverage["boot_l"] == 1
    lines = "\n".join(sl.coverage_lines(res.log))
    assert "| heat_pump | 1 | 50% |" in lines


def test_document_is_editorial_and_json_safe(tmp_path: Path) -> None:
    res = run(tmp_path, [row()])
    doc = res.document
    assert doc and doc["editorial"] is True and doc["estimate"] is True
    assert doc["rules"]["review"] is True and len(doc["rules"]["sha256"]) == 64
    json.dumps(doc)


def test_backtest_matches_picks_by_generation_and_pack(tmp_path: Path) -> None:
    rows = [
        row("m-gen1-58", battery_kwh_net=58.0, drivetrain="rwd"),
        row("m-gen1-77-awd", battery_kwh_net=77.0, drivetrain="awd"),
        row("m-gen1-77-rwd", battery_kwh_net=77.0, drivetrain="rwd", dc_km_per_20min=450.0),
    ]
    picks = {
        "primary_car_picks": [
            {
                "make": "M",
                "model": "One",
                "model_year": 2024,
                "variant": "Long Range 2WD",
                "seed_generation_id": "m-gen1",
                "verdict": "shortlist",
                "sheet_values": {"battery_usable_kwh": 76.0},
            },
            {
                "make": "M",
                "model": "One",
                "model_year": 2024,
                "variant": "Big",
                "seed_generation_id": "m-gen1",
                "verdict": "consider",
                "sheet_values": {"battery_usable_kwh": 100.0},
            },  # no pack within 4 kWh
            {
                "make": "Z",
                "model": "Z",
                "seed_generation_id": None,
                "verdict": "shortlist",
                "sheet_values": {},
            },
        ]
    }
    write_rules(tmp_path)
    (tmp_path / "editorial" / "menno-picks.yaml").write_text(yaml.safe_dump(picks))
    res = run(tmp_path, rows)
    bt = res.backtest
    assert bt and bt["matched"] == 1 and bt["rows"][0]["variant_id"] == "m-gen1-77-rwd"
    assert bt["gate"] is False
    assert "sheet_values" not in json.dumps(bt) and "76" not in json.dumps(bt["rows"])
    assert "Shortlist back-test" in "\n".join(sl.readme_lines(bt))


def test_release_ships_shortlist_file(tmp_path: Path) -> None:
    """End to end: the fixture release with the repo's real rules writes shortlist_scores.json."""
    import shutil

    from test_t059_sections import NOW, REPO_DATA
    from test_t059_sections import data_dir as make_data_dir

    from ev_pipeline.release.build import build_release, write_release

    d = make_data_dir.__wrapped__(tmp_path)  # type: ignore[attr-defined]
    (d / "editorial").mkdir()
    shutil.copy(REPO_DATA / "editorial" / "shortlist_rules.yaml", d / "editorial")
    res = build_release(d, now=NOW)
    assert res.shortlist is not None
    assert {v["variant_id"] for v in res.shortlist["variants"]} == {
        r["variant_id"] for r in res.catalogue["rows"]
    }
    out = write_release(res, d, extras={})
    doc = json.loads((out / sl.FILE_NAME).read_text(encoding="utf-8"))
    assert doc["editorial"] is True and "road-tripper.rural" in doc["combos"]
    assert "## Shortlist scores (T-069, editorial)" in (out / "coverage.md").read_text()
    assert "shortlist_scores.json" in (out / "README.md").read_text()
