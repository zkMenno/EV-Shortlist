"""T-165: seed-pinned tests in data_qa.sh (G-61), missing-input derived-flag report in ev verify
(G-62), and CI data-qa running `ev release approvals`. Fixture-only, no network."""

from __future__ import annotations

import json
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from ev_pipeline.release.build import release_cmd
from ev_pipeline.verify.run import missing_input_flag_changes, report_md, verify

REPO = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "release"
NOW = datetime(2026, 11, 26, 1, tzinfo=UTC)


# --- G-61: seed marker + data_qa.sh + CI data-qa approvals -----------------------------------


def test_seed_marker_registered_and_wired_into_data_qa() -> None:
    cfg = tomllib.loads((REPO / "pipeline" / "pyproject.toml").read_text(encoding="utf-8"))
    markers = cfg["tool"]["pytest"]["ini_options"].get("markers") or []
    assert any(str(m).startswith("seed:") for m in markers)
    sh = (REPO / "data" / "seed" / "data_qa.sh").read_text(encoding="utf-8")
    assert "pytest -m seed" in sh


def test_seed_pinned_modules_carry_the_seed_marker() -> None:
    import test_a06_fixes
    import test_match
    import test_pack_guard
    import test_qa_top40
    import test_registrations
    import test_seed_cited
    import test_seed_t051
    import test_shared_year_source_names
    import test_source_wikidata
    import test_t134_images
    import test_t136d_coverage_gems
    import test_t144_seed_guards
    import test_t153_split
    import test_t159_split

    def has_seed_mark(obj: Any) -> bool:
        marks = getattr(obj, "pytestmark", [])
        if not isinstance(marks, list):
            marks = [marks]
        return any(getattr(m, "name", None) == "seed" for m in marks)

    for mod in (
        test_t153_split,
        test_t159_split,
        test_t144_seed_guards,
        test_t136d_coverage_gems,
        test_seed_t051,
    ):
        assert has_seed_mark(mod), mod.__name__
    for fn in (
        test_match.test_real_seed_guards,
        test_registrations.test_kba_names,
        test_registrations.test_dft_names,
        test_shared_year_source_names.test_shipped_seed_pins_ioniq5_my2024_base_and_awd_to_gen1,
        test_shared_year_source_names.test_retired_ioniq5_release1_ids_have_live_successors,
        test_seed_cited.test_repo_seed_cites_the_i3s_battery,
        test_seed_cited.test_repo_seed_cites_zoe_phase1_ac_power,
        test_qa_top40.test_committed_top40_yaml_is_consistent,
        test_a06_fixes.test_repo_seed_has_no_cited_value_under_the_seed_source,
        test_pack_guard.test_committed_ev6_links_point_at_the_pre_facelift_pack,
        test_source_wikidata.test_matcher_never_turns_wikidata_into_facts,
        test_t134_images.test_refresh_fetch_step_fetches_listed_photos,
        test_t134_images.test_photos_pending_lets_a_photo_only_night_publish,
    ):
        assert has_seed_mark(fn), fn.__name__


def test_ci_data_qa_runs_ev_release_approvals() -> None:
    ci = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = ci["jobs"]["data-qa"]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert checkout.get("with", {}).get("fetch-depth") == 0
    assert any("ev release approvals" in str(s.get("run", "")) for s in steps)


# --- G-62: missing-input derived-flag changes (unit tests) -----------------------------------


def _cat(*rows: dict[str, Any]) -> dict[str, Any]:
    return {"rows": list(rows)}


def _row(vid: str, model: str = "m", **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "variant_id": vid,
        "model_id": model,
        "drivetrain": "awd",
        "power_kw": 200.0,
        "year_start": 2024,
        "dc_km_per_20min": 250.0,
        "charge_100_daily": None,
        "width_mm": None,
        "kerb_mass_kg": None,
    }
    base.update(kw)
    return base


def _scores(**by_vid: dict[str, tuple[str, list[str]]]) -> dict[str, Any]:
    return {
        "variants": [
            {
                "variant_id": vid,
                "scores": {
                    combo: {"band": band, "reasons": reasons}
                    for combo, (band, reasons) in combos.items()
                },
            }
            for vid, combos in by_vid.items()
        ]
    }


def test_missing_power_kw_lists_lost_version_flags() -> None:
    old_r = _row("m-old", year_start=2021, power_kw=None, dc_km_per_20min=180.0)
    new_r = _row("m-new", year_start=2024, power_kw=None, dc_km_per_20min=240.0)
    cat = _cat(old_r, new_r)
    old_sc = _scores(
        **{
            "m-old": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-new": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "m-old": {"road-tripper": ("consider", [])},
            "m-new": {"road-tripper": ("consider", [])},
        }
    )
    got = missing_input_flag_changes(cat, cat, new_sc, old_sc, gap=0.15)
    assert got == [
        {
            "variant_id": "m-new",
            "flag": "newest-version",
            "change": "lost",
            "missing": ["power_kw"],
        },
        {"variant_id": "m-old", "flag": "older-version", "change": "lost", "missing": ["power_kw"]},
    ]


def test_true_trim_line_split_is_not_reported() -> None:
    """All inputs present (500 kW vs 430 kW > 15 %): trim-line split, not missing data."""
    rs = _row("gt-rs", year_start=2024, power_kw=500.0, dc_km_per_20min=280.0)
    entry = _row("gt-entry", year_start=2025, power_kw=430.0, dc_km_per_20min=290.0)
    cat = _cat(rs, entry)
    old_sc = _scores(
        **{
            "gt-rs": {"road-tripper": ("consider", ["penalty:older-version"])},
            "gt-entry": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "gt-rs": {"road-tripper": ("shortlist", [])},
            "gt-entry": {"road-tripper": ("shortlist", [])},
        }
    )
    assert missing_input_flag_changes(cat, cat, new_sc, old_sc, gap=0.15) == []


def test_missing_power_with_no_same_drivetrain_peer_is_not_reported() -> None:
    """Sole RWD row vs AWD peer would lose the flag even if power_kw were known (not 'solely')."""
    rwd = _row("m-rwd", drivetrain="rwd", year_start=2021, power_kw=None, dc_km_per_20min=150.0)
    awd = _row("m-awd", drivetrain="awd", year_start=2024, power_kw=300.0, dc_km_per_20min=250.0)
    cat = _cat(rwd, awd)
    old_sc = _scores(
        **{
            "m-rwd": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-awd": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "m-rwd": {"road-tripper": ("consider", [])},
            "m-awd": {"road-tripper": ("consider", [])},
        }
    )
    assert missing_input_flag_changes(cat, cat, new_sc, old_sc, gap=0.15) == []


@pytest.mark.parametrize(
    ("missing_field", "patch"),
    [
        ("drivetrain", {"drivetrain": None}),
        ("year_start", {"year_start": None}),
        ("dc_km_per_20min", {"dc_km_per_20min": None}),
    ],
)
def test_names_other_missing_version_inputs(missing_field: str, patch: dict[str, Any]) -> None:
    a_old = _row("m-old", year_start=2021, power_kw=200.0, dc_km_per_20min=180.0)
    a_new = {**a_old, **patch}
    b = _row("m-new", year_start=2024, power_kw=200.0, dc_km_per_20min=260.0)
    old_sc = _scores(
        **{
            "m-old": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-new": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "m-old": {"road-tripper": ("consider", [])},
            "m-new": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    got = missing_input_flag_changes(_cat(a_new, b), _cat(a_old, b), new_sc, old_sc, gap=0.15)
    assert got == [
        {
            "variant_id": "m-old",
            "flag": "older-version",
            "change": "lost",
            "missing": [missing_field],
        }
    ]


def test_peer_missing_power_explains_lost_and_gained_flags() -> None:
    r21 = _row("m-21", year_start=2021, power_kw=200.0, dc_km_per_20min=180.0)
    r23 = _row("m-23", year_start=2023, power_kw=200.0, dc_km_per_20min=210.0)
    r25_old = _row("m-25", year_start=2025, power_kw=200.0, dc_km_per_20min=260.0)
    r25_new = _row("m-25", year_start=2025, power_kw=None, dc_km_per_20min=260.0)
    old_sc = _scores(
        **{
            "m-21": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-23": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-25": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "m-21": {"road-tripper": ("fallback", ["penalty:older-version"])},
            "m-23": {"road-tripper": ("shortlist", ["bonus:newest-version"])},
            "m-25": {"road-tripper": ("consider", [])},
        }
    )
    got = missing_input_flag_changes(
        _cat(r21, r23, r25_new), _cat(r21, r23, r25_old), new_sc, old_sc, gap=0.15
    )
    assert {(x["variant_id"], x["flag"], x["change"], tuple(x["missing"])) for x in got} == {
        ("m-23", "older-version", "lost", ("power_kw (on m-25)",)),
        ("m-23", "newest-version", "gained", ("power_kw (on m-25)",)),
        ("m-25", "newest-version", "lost", ("power_kw",)),
    }


def test_ruled_out_row_is_not_blamed_on_missing_input() -> None:
    a = _row("m-old", year_start=2021, power_kw=200.0, dc_km_per_20min=180.0)
    b = _row("m-new", year_start=2024, power_kw=None, dc_km_per_20min=80.0)
    cat = _cat(a, b)
    old_sc = _scores(
        **{
            "m-old": {"road-tripper": ("consider", [])},
            "m-new": {"road-tripper": ("consider", ["bonus:newest-version"])},
        }
    )
    new_sc = _scores(
        **{
            "m-old": {"road-tripper": ("consider", [])},
            "m-new": {"road-tripper": ("ruled-out", ["gate:dc-not-terrible"])},
        }
    )
    assert missing_input_flag_changes(cat, cat, new_sc, old_sc, gap=0.15) == []


def test_lfp_and_too_big_missing_input_flags() -> None:
    old_cat = _cat(
        _row("lfp-miss", charge_100_daily=True),
        _row("lfp-false", charge_100_daily=True),
        _row("big-miss", width_mm=2000, kerb_mass_kg=2100),
        _row("big-lighter", width_mm=1850, kerb_mass_kg=2400),
    )
    new_cat = _cat(
        _row("lfp-miss", charge_100_daily=None),
        _row("lfp-false", charge_100_daily=False),
        _row("big-miss", width_mm=None, kerb_mass_kg=2100),
        _row("big-lighter", width_mm=1850, kerb_mass_kg=2200),
    )
    old_sc = _scores(
        **{
            "lfp-miss": {"road-tripper": ("shortlist", ["bonus:lfp-daily-100"])},
            "lfp-false": {"road-tripper": ("shortlist", ["bonus:lfp-daily-100"])},
            "big-miss": {"road-tripper.rural": ("consider", ["penalty:too-big-for-b-roads"])},
            "big-lighter": {"road-tripper.rural": ("consider", ["penalty:too-big-for-b-roads"])},
        }
    )
    new_sc = _scores(
        **{
            "lfp-miss": {"road-tripper": ("consider", [])},
            "lfp-false": {"road-tripper": ("consider", [])},
            "big-miss": {"road-tripper.rural": ("shortlist", [])},
            "big-lighter": {"road-tripper.rural": ("shortlist", [])},
        }
    )
    got = missing_input_flag_changes(new_cat, old_cat, new_sc, old_sc, gap=0.15)
    assert got == [
        {
            "variant_id": "big-miss",
            "flag": "too-big-for-b-roads",
            "change": "lost",
            "missing": ["width_mm"],
        },
        {
            "variant_id": "lfp-miss",
            "flag": "lfp-daily-100",
            "change": "lost",
            "missing": ["charge_100_daily"],
        },
    ]


# --- G-62: end-to-end ev verify + report_md on a fixture with shortlist rules ----------------


def test_verify_reports_missing_input_flag_changes_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    (d / "editorial").mkdir(parents=True)
    shutil.copytree(FIX / "taxonomy", d / "taxonomy")
    for n in ("platforms", "battery_packs", "variant_links"):
        shutil.copy(FIX / f"{n}.yaml", d / "seed" / f"{n}.yaml")
    for n in ("sources", "field_sources"):
        shutil.copy(FIX / f"{n}.yaml", d / f"{n}.yaml")
    shutil.copy(REPO / "data" / "editorial" / "shortlist_rules.yaml", d / "editorial")
    (d / "seed" / "models.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "seed-models/v1",
                "makes": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "models": [
                            {
                                "id": "demo-ev",
                                "name": "EV",
                                "generations": [{"id": "demo-ev-gen1", "years": [2021, None]}],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (d / "seed" / "variants.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "seed-variants/v1",
                "variants": [
                    {
                        "id": "demo-ev-gen1-old",
                        "generation_id": "demo-ev-gen1",
                        "name": "Old",
                        "years": [2021, 2022],
                        "drivetrain": "rwd",
                        "source_names": {"openev": ["Old"]},
                    },
                    {
                        "id": "demo-ev-gen1-new",
                        "generation_id": "demo-ev-gen1",
                        "name": "New",
                        "years": [2024, None],
                        "drivetrain": "rwd",
                        "source_names": {"openev": ["New"]},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (d / "staging").mkdir()
    src = {
        "id": "openev",
        "name": "Open EV Data",
        "url": "https://example.org",
        "licence": "CDLA-Permissive-2.0",
        "attribution": "Open EV Data",
    }

    def rec(name: str, year: int, dc: float, power: float | None) -> dict[str, Any]:
        specs: dict[str, Any] = {
            "battery_kwh_net": {"value": 75.0, "unit": "kWh"},
            "wltp_range_km": {"value": 520.0, "unit": "km"},
            "dc_peak_kw": {"value": dc, "unit": "kW"},
            "ac_kw": {"value": 11.0, "unit": "kW"},
            "boot_l": {"value": 500.0, "unit": "L"},
        }
        if power is not None:
            specs["power_kw"] = {"value": power, "unit": "kW"}
        return {
            "source": src,
            "record_key": f"openev:demo/{name.lower()}/{year}",
            "kind": "spec",
            "make": "Demo",
            "model": "EV",
            "variant_name": name,
            "year": year,
            "drivetrain": "rwd",
            "specs": specs,
            "retrieved_at": "2026-11-26",
            "confidence": "high",
        }

    staging = d / "staging" / "openev.records.jsonl"
    staging.write_text(
        "\n".join(
            json.dumps(r) for r in (rec("Old", 2021, 130.0, 150.0), rec("New", 2024, 240.0, 150.0))
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EV_DATA_DIR", str(d))
    monkeypatch.delenv("EV_RUNS_DIR", raising=False)
    assert release_cmd(False, data_dir=d, now=NOW) == 0

    # Drop power_kw from the 2024 variant: Decision 088 drops both version flags.
    staging.write_text(
        "\n".join(
            json.dumps(r) for r in (rec("Old", 2021, 130.0, 150.0), rec("New", 2024, 240.0, None))
        )
        + "\n",
        encoding="utf-8",
    )
    rep = verify(d, repo=tmp_path, skip_tests=True, tricky=[], now=NOW)
    items = rep.sections["missing_input_flags"]["items"]
    assert rep.numbers["missing_input_flag_changes"] == len(items) == 2
    assert any(
        x["variant_id"] == "demo-ev-gen1-new"
        and x["flag"] == "newest-version"
        and x["missing"] == ["power_kw"]
        for x in items
    )
    assert any(
        x["variant_id"] == "demo-ev-gen1-old"
        and x["flag"] == "older-version"
        and x["missing"] == ["power_kw (on demo-ev-gen1-new)"]
        for x in items
    )
    md = report_md(rep)
    assert "## Derived flag changes from missing inputs (G-62)" in md
    assert "| demo-ev-gen1-new | newest-version | lost | power_kw |" in md
    assert f"missing_input_flag_changes: {len(items)}" in md
