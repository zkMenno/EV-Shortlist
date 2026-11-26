"""Seed-manual `cited:` values: each carries its own source URL, retrieval date and confidence.

The i3s case (Q-091): the seed's i3s row had no battery, so 120 Ah i3s type-approval versions
tied with the 120 Ah row ("battery fits ..., name only i3s"). With the BMW press figure
(42.2 kWh gross) cited on the row, the 120 Ah i3s versions land on it; a 2017 i3s with the
94 Ah pack does not fit 42.2 kWh and stays a battery tie for review.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
import yaml
from test_tgk_attach import I3S_2017, VARIANTS, _placed, _reason, _run

from ev_pipeline.match.matcher import TGK_TIE
from ev_pipeline.match.seed import parse_manual_variants
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.schema_models import FactField

URL = "https://newsroom.bmwgroup.com/emea/the-all-electric-bmw-i3-120ah"
CITED = {
    "battery_kwh_gross": {
        "value": 42.2,
        "source_url": URL,
        "source_name": "BMW Group PressClub, 28 Sep 2018",
        "retrieved": date(2026, 11, 15),
        "quote": "gross energy content of 42.2kWh",
        "confidence": "medium",
    }
}
REPO = Path(__file__).resolve().parents[2]


def _variants_with_cited() -> list[dict]:
    out = [dict(v) for v in VARIANTS]
    for v in out:
        if v["id"] == "bmw-i3-i01-i3s":
            v["cited"] = CITED
    return out


def _i3s_120ah(year: int = 2019) -> SourceRecord:
    """A 120 Ah i3s version as in the 2026-11-15 TGK staging: WLTP 285 km x 16.1 kWh/100 km."""
    specs = {
        FactField.wltp_range_km: SpecValue(value=285.0, unit="km"),
        FactField.consumption_kwh_100km: SpecValue(value=16.1, unit="kWh/100km"),
        FactField.power_30min_kw: SpecValue(value=75.0, unit="kW"),
    }
    return I3S_2017.model_copy(
        update={
            "record_key": I3S_2017.record_key.replace("|7Z61|", "|9Z61|"),
            "year": year,
            "variant_name": "I REIHE / I SERIES / I3S · 30-min 75 · 1365 kg",
            "specs": specs,
        }
    )


def test_cited_value_becomes_its_own_record_with_provenance() -> None:
    mvs, problems = parse_manual_variants({"variants": _variants_with_cited()}, date(2026, 1, 1))
    assert problems == []
    [i3s] = [m for m in mvs if m.id == "bmw-i3-i01-i3s"]
    [rec] = i3s.cited_records
    assert rec.record_key == "bmw-i3-i01-i3s#cited:battery_kwh_gross"
    # A-06 F3: the cited document's source (maker-docs), not the seed's CC BY licence.
    assert rec.source.id.root == "maker-docs"
    assert "unchecked" not in rec.source.name and "CC-BY" not in rec.source.licence
    assert rec.source.url == URL
    assert rec.retrieved_at == date(2026, 11, 15)  # the cited date, not the file date
    assert rec.confidence.value == "medium"
    assert rec.specs[FactField.battery_kwh_gross].value == 42.2
    assert FactField.battery_kwh_gross not in i3s.record.specs


def test_cited_value_without_source_is_skipped_with_a_problem() -> None:
    bad = {k: v for k, v in CITED["battery_kwh_gross"].items() if k != "source_url"}
    variants = _variants_with_cited()
    for v in variants:
        if v["id"] == "bmw-i3-i01-i3s":
            v["cited"] = {"battery_kwh_gross": bad}
    mvs, problems = parse_manual_variants({"variants": variants}, date(2026, 1, 1))
    assert any("no https source_url" in p for p in problems)
    assert all(not m.cited_records for m in mvs)


def test_cited_fact_carries_the_cited_source() -> None:
    res = _run([], _variants_with_cited())
    [fact] = [
        mf.fact
        for mf in res.spec_facts
        if mf.fact.subject_id.root == "bmw-i3-i01-i3s"
        and mf.fact.field.value == "battery_kwh_gross"
    ]
    assert fact.source.url == URL and fact.retrieved_at == date(2026, 11, 15)


def test_i3s_120ah_versions_land_on_the_i3s_once_its_battery_is_cited() -> None:
    rec = _i3s_120ah()
    before = _run([rec])
    assert _placed(before, rec) == set()
    assert "name only bmw-i3-i01-i3s" in _reason(before, rec)
    after = _run([rec], _variants_with_cited())
    assert _placed(after, rec) == {"bmw-i3-i01-i3s"}


def test_94ah_i3s_does_not_fit_the_cited_120ah_pack_and_stays_in_review() -> None:
    res = _run([I3S_2017], _variants_with_cited())
    assert _placed(res, I3S_2017) == set()
    why = _reason(res, I3S_2017)
    assert TGK_TIE in why and "bmw-i3-i01-i3s" not in why


def _validator():
    spec = importlib.util.spec_from_file_location(
        "validate_variants", REPO / "data" / "seed" / "validate_variants.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_validator_checks_cited_entries() -> None:
    v = _validator()
    ok = v.validate_cited(CITED, {"power_kw": 135}, "x", today=date(2026, 11, 15))
    assert ok == []
    errs = v.validate_cited(
        {
            "battery_kwh_gross": {**CITED["battery_kwh_gross"], "source_url": "http://x.org/a"},
            "power_kw": {"value": 135},
        },
        {"power_kw": 135},
        "x",
        today=date(2026, 11, 15),
    )
    text = " | ".join(errs)
    assert "public https URL" in text
    assert "also in specs" in text
    assert "missing keys" in text and "quote or a locator" in text
    future = {**CITED["battery_kwh_gross"], "retrieved": date(2027, 1, 1)}
    assert v.validate_cited({"battery_kwh_gross": future}, {}, "x", today=date(2026, 11, 15))


@pytest.mark.seed
def test_repo_seed_cites_the_i3s_battery() -> None:
    data = yaml.safe_load((REPO / "data" / "seed" / "variants.yaml").read_text(encoding="utf-8"))
    [i3s] = [v for v in data["variants"] if v["id"] == "bmw-i3-i01-i3s"]
    cited = i3s["cited"]["battery_kwh_gross"]
    assert cited["value"] == 42.2 and cited["source_url"].startswith("https://")
    assert isinstance(cited["retrieved"], date)


def test_plain_i3_120ah_version_is_not_an_i3s_once_both_have_a_battery() -> None:
    """Both the 120 Ah row and the i3s fit 47 kWh drawn; the "I3" trade name (no "I3S")
    rules out the i3s (tgk_pick step 6)."""
    from test_tgk_attach import I3_2018_120

    res = _run([I3_2018_120, _i3s_120ah()], _variants_with_cited())
    assert _placed(res, I3_2018_120) == {"bmw-i3-i01-120ah"}
    assert _placed(res, _i3s_120ah()) == {"bmw-i3-i01-i3s"}


def test_cited_ac_kw_uses_the_zoe_q_motor_exception() -> None:
    """43 kW AC is allowed only on the Zoe Q-motor rows, cited or not."""
    v = _validator()
    ac = {
        "ac_kw": {
            "value": 43,
            "source_url": "https://example.org/kit.pdf",
            "retrieved": date(2026, 11, 15),
            "locator": "charging table",
            "confidence": "medium",
        }
    }
    day = date(2026, 11, 15)
    assert v.validate_cited(ac, {}, "x", today=day, vid="renault-zoe-ph1-q90") == []
    errs = v.validate_cited(ac, {}, "x", today=day, vid="renault-zoe-ph1-r90")
    assert errs and "outside plausible range" in errs[0]


@pytest.mark.seed
def test_repo_seed_cites_zoe_phase1_ac_power() -> None:
    data = yaml.safe_load((REPO / "data" / "seed" / "variants.yaml").read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in data["variants"]}
    want = {"q210": (43, "low"), "r240": (22, "low"), "q90": (43, "medium"), "r110": (22, "medium")}
    for motor, (kw, conf) in want.items():
        c = by_id[f"renault-zoe-ph1-{motor}"]["cited"]["ac_kw"]
        assert (c["value"], c["confidence"]) == (kw, conf)
        assert "ac_kw" not in by_id[f"renault-zoe-ph1-{motor}"]["specs"]
