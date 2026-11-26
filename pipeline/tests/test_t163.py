"""T-163 tests: cited maker facts publish with provenance (Decisions 068 / 087), dc_speed_is_claim
wiring (rows + open data), and TGK variant-code split evidence (Model S / Model X).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from ev_pipeline.opendata import bundle as ob
from ev_pipeline.qa import checks as qc
from ev_pipeline.release.build import build_release
from ev_pipeline.release.gate import load_registry, parse_registry
from ev_pipeline.schema_models import ChargeCurve, PublishedVariant
from tests.test_derive_edges import _curve_fact, _fact, _row

REPO = Path(__file__).resolve().parents[2]
QA_FIXTURES = Path(__file__).parent / "fixtures" / "qa"


# --- Part 3: dc_speed_is_claim --------------------------------------------------------------


def test_dc_speed_is_claim_set_true_for_maker_claim_minutes() -> None:
    """Ioniq 5 facelift case: cited 'as little as 18 min' from manual -> claim=True."""
    mf = _fact("dc_minutes_10_80", 18, "min", source="manual")
    mf.fact.claim = True
    row, problems = _row(
        [
            _fact("battery_kwh_net", 84, "kWh"),
            _fact("wltp_range_km", 507, "km"),
            mf,
        ]
    )
    assert problems == []
    assert row["dc_avg_10_80_kw"] == 196.0
    assert row["dc_speed_is_claim"] is True
    PublishedVariant.model_validate(row)


def test_dc_speed_is_claim_set_false_for_measured_minutes() -> None:
    """Measured 10-80 % time (claim=False) -> dc_speed_is_claim=False."""
    mf = _fact("dc_minutes_10_80", 28, "min", source="naf")
    mf.fact.claim = False
    row, problems = _row(
        [
            _fact("battery_kwh_net", 70, "kWh"),
            _fact("wltp_range_km", 500, "km"),
            mf,
        ]
    )
    assert problems == []
    assert row["dc_avg_10_80_kw"] is not None
    assert row["dc_speed_is_claim"] is False
    PublishedVariant.model_validate(row)


def test_dc_speed_is_claim_omitted_for_curve_and_default_curve_fallback() -> None:
    curve = ChargeCurve.model_validate({"points": [[10, 100], [80, 100]], "status": "estimated"})
    mf = _fact("dc_minutes_10_80", 18, "min", source="manual")
    mf.fact.claim = True
    row_curve, _ = _row(
        [
            _fact("battery_kwh_net", 70, "kWh"),
            _fact("wltp_range_km", 500, "km"),
            mf,
            _curve_fact(curve),
        ]
    )
    assert row_curve["dc_curve_status"] == "estimated"
    assert "dc_speed_is_claim" not in row_curve

    # Minutes above peak -> falls back to default curve, so not from the claimed time
    row_fallback, problems = _row(
        [
            _fact("battery_kwh_net", 84, "kWh"),
            _fact("wltp_range_km", 507, "km"),
            _fact("dc_peak_kw", 150, "kW", source="eea"),
            mf,
        ]
    )
    assert [p.field for p in problems] == ["dc_minutes_10_80"]
    assert row_fallback["dc_curve_status"] == "default"
    assert "dc_speed_is_claim" not in row_fallback


def test_opendata_carries_and_gates_dc_speed_is_claim_as_companion() -> None:
    assert ob.COMPANION_OF["dc_speed_is_claim"] == "dc_avg_10_80_kw"
    cat = json.loads((QA_FIXTURES / "catalogue.json").read_text())
    reg = load_registry(QA_FIXTURES / "sources.yaml")
    r0 = cat["rows"][0]
    r0["dc_avg_10_80_kw"] = 196.0
    r0["dc_speed_is_claim"] = True
    r0["provenance"]["dc_avg_10_80_kw"] = {"source_ids": ["testsrc"], "confidence": "medium"}

    b = ob.build_bundle(cat, reg)
    docs = {d["name"]: d for d in ob.field_docs(b)}
    assert "dc_speed_is_claim" in docs and docs["dc_speed_is_claim"]["description"]
    out = next(r for r in b.rows if r["variant_id"] == r0["variant_id"])
    assert out["dc_avg_10_80_kw"] == 196.0
    assert out["dc_speed_is_claim"] is True

    # When dc_avg_10_80_kw comes from a cited-facts source (not CC BY), companion is withheld too
    reg_cited = parse_registry(
        {
            "sources": [
                {
                    "id": "manual",
                    "name": "Manual",
                    "licence": "facts cited, no licence (Decision 068)",
                    "status": "active",
                    "use": "cited-facts",
                    "decision": "068",
                },
                {
                    "id": "testsrc",
                    "name": "Test",
                    "licence": "CC-BY-4.0",
                    "status": "active",
                },
            ]
        }
    )
    r0["provenance"]["dc_avg_10_80_kw"] = {"source_ids": ["manual"], "confidence": "medium"}
    b2 = ob.build_bundle(cat, reg_cited)
    out2 = next(r for r in b2.rows if r["variant_id"] == r0["variant_id"])
    assert out2["dc_avg_10_80_kw"] is None
    assert out2["dc_speed_is_claim"] is None


# --- Part 2: cited maker facts publish with provenance (Decisions 068 / 087) ----------------


def test_repo_maker_docs_registry_enforces_cited_hosts() -> None:
    reg = load_registry(REPO / "data" / "sources.yaml")
    assert reg.releasable("maker-docs")
    assert reg.cited_facts("maker-docs")
    entry = reg.sources["maker-docs"]
    assert entry.cited_hosts, "maker-docs must declare cited_hosts"
    whole = {h for h in entry.cited_hosts if "/" not in h}
    assert not whole & {"cdn.uc.assets.prezly.com", "mb.cision.com", "www.louwman.nl"}

    # Maker-hosted URLs pass
    for ok in (
        "https://cdn.skoda-storyboard.com/2025/06/Skoda_Elroq_Technical_data_d5686460.pdf",
        "https://www.volkswagen-newsroom.com/en/id7",
        "https://www.media.stellantis.com/em-en/opel/press/mokka",
        "https://cdn.uc.assets.prezly.com/34359316-f25e-44da-a593-c7ea94745496/-/inline/no/pack.pdf",
    ):
        assert reg.fact_blocked("maker-docs", ok) is None, ok

    # Third-party / dealer hosts and other Prezly accounts stay blocked
    for bad in (
        "https://xr793.com/wp-content/uploads/2022/12/2016-Renault-Zoe-UK.pdf",
        "https://www.widmann-winterholler.de/Kia-Germany-EV6_Pricelist-Juni2026.pdf",
        "https://projekt-renault.de/images/pdf/ZOE_R110.pdf",
        "https://www.vaielettrico.it/wp-content/uploads/Scheda.pdf",
        "https://www.rinnovabili.it/wp-content/uploads/Listino.pdf",
        "https://cdn.uc.assets.prezly.com/other-account/file.pdf",
        "",
    ):
        assert reg.fact_blocked("maker-docs", bad) is not None, bad


def test_maker_docs_excluded_from_cc_by_opendata_bundle() -> None:
    reg = load_registry(REPO / "data" / "sources.yaml")
    assert not ob.source_allowed(reg, {"maker-docs": "facts cited, no licence"}, "maker-docs")


def test_check_licence_gate_enforces_cited_hosts_on_shipped_facts() -> None:
    cat = json.loads((QA_FIXTURES / "catalogue.json").read_text())
    reg = load_registry(REPO / "data" / "sources.yaml")
    cat["sources"] = [
        {"id": "openev", "name": "OpenEV", "licence": "CDLA-Permissive-2.0"},
        {"id": "maker-docs", "name": "Maker docs", "licence": "facts cited, no licence"},
    ]
    cat["rows"] = []
    facts = [
        {
            "id": "maker-docs:ok",
            "source": {
                "id": "maker-docs",
                "name": "Maker docs: Skoda",
                "licence": "facts cited, no licence",
                "url": "https://cdn.skoda-storyboard.com/2025/06/elroq.pdf",
            },
        }
    ]
    assert qc.check_licence_gate(cat, facts, reg).status == "pass"

    facts[0]["source"]["url"] = "https://www.widmann-winterholler.de/dealer-copy.pdf"
    c = qc.check_licence_gate(cat, facts, reg)
    assert c.status == "fail"
    assert any("cited_hosts" in e for e in c.details["errors"])


def test_build_release_publishes_maker_hosted_cited_facts_and_withholds_third_party(
    tmp_path: Path,
) -> None:
    """End-to-end release build: maker-hosted cited power_kw + battery_kwh_gross publish with
    provenance; third-party-hosted cited power_kw stays evidence only (never ships, still
    withholds a contradicting lone source via guard_contradicted)."""
    data = tmp_path / "data"
    (data / "seed").mkdir(parents=True)
    (data / "staging").mkdir(parents=True)
    (data / "releases").mkdir(parents=True)

    (data / "seed" / "models.yaml").write_text(
        yaml.safe_dump(
            {
                "makes": [
                    {
                        "id": "skoda",
                        "name": "Skoda",
                        "models": [
                            {
                                "id": "skoda-elroq",
                                "name": "Elroq",
                                "segment": "C",
                                "body": "suv",
                                "generations": [
                                    {
                                        "id": "skoda-elroq-gen1",
                                        "name": "Gen 1",
                                        "years": [2024, None],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data / "seed" / "variants.yaml").write_text(
        yaml.safe_dump(
            {
                "source": {
                    "id": "seed-manual",
                    "name": "Seed",
                    "licence": "CC-BY-4.0",
                    "attribution": "EV Finder",
                },
                "variants": [
                    {
                        "generation_id": "skoda-elroq-gen1",
                        "id": "skoda-elroq-gen1-85",
                        "name": "Elroq 85",
                        "years": [2025, None],
                        "drivetrain": "rwd",
                        "specs": {},
                        "cited": {
                            "battery_kwh_gross": {
                                "value": 82,
                                "source_url": "https://cdn.skoda-storyboard.com/elroq.pdf",
                                "source_name": "Skoda tech data",
                                "retrieved": "2026-11-18",
                                "quote": "82 kWh gross",
                                "confidence": "high",
                            },
                            "power_kw": {
                                "value": 210,
                                "source_url": "https://cdn.skoda-storyboard.com/elroq.pdf",
                                "source_name": "Skoda tech data",
                                "retrieved": "2026-11-18",
                                "quote": "210 kW",
                                "confidence": "high",
                            },
                        },
                        "confidence": "high",
                    },
                    {
                        "generation_id": "skoda-elroq-gen1",
                        "id": "skoda-elroq-gen1-dealer",
                        "name": "Elroq Dealer",
                        "years": [2025, None],
                        "drivetrain": "rwd",
                        "specs": {},
                        "cited": {
                            "battery_kwh_gross": {
                                "value": 63,
                                "source_url": "https://press.kia.com/ev6.pdf",
                                "source_name": "Kia press kit",
                                "retrieved": "2026-11-18",
                                "quote": "63 kWh",
                                "confidence": "medium",
                            },
                            "power_kw": {
                                "value": 125,
                                "source_url": "https://www.widmann-winterholler.de/elroq.pdf",
                                "source_name": "Dealer copy",
                                "retrieved": "2026-11-18",
                                "quote": "125 kW",
                                "confidence": "medium",
                            },
                        },
                        "confidence": "medium",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (data / "sources.yaml").write_text(
        (REPO / "data" / "sources.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (data / "field_sources.yaml").write_text(
        (REPO / "data" / "field_sources.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )

    res = build_release(data, now=datetime(2026, 11, 26, tzinfo=UTC), release=1)
    by_id = {r["variant_id"]: r for r in res.catalogue["rows"]}

    r_ok = by_id["skoda-elroq-gen1-85"]
    assert r_ok["power_kw"] == 210
    assert r_ok["provenance"]["power_kw"]["source_ids"] == ["maker-docs"]
    assert r_ok["provenance"]["power_kw"]["confidence"] == "high"
    # battery_kwh_net derived from the published cited battery_kwh_gross (0.93 * 82 = 76.3)
    assert r_ok["battery_kwh_net"] == pytest.approx(76.3, abs=0.1)
    assert "maker-docs" in r_ok["provenance"]["battery_kwh_net"]["source_ids"]
    # Shipped facts keep only the maker URLs (never the dealer URL)
    ok_urls = {f["source"]["url"] for f in res.facts if f["source"]["id"] == "maker-docs"}
    assert ok_urls == {
        "https://cdn.skoda-storyboard.com/elroq.pdf",
        "https://press.kia.com/ev6.pdf",
    }

    r_dealer = by_id["skoda-elroq-gen1-dealer"]
    assert r_dealer["power_kw"] is None
    assert "power_kw" not in r_dealer["provenance"]
    assert "maker-docs" in res.gated and res.gated["maker-docs"]["records"] == 1

    # Licence gate QA re-check passes on the built release
    reg = load_registry(data / "sources.yaml")
    assert qc.check_licence_gate(res.catalogue, res.facts, reg).status == "pass"

    # Open data bundle withholds maker-docs values (no CC BY licence)
    bundle = ob.build_bundle(res.catalogue, reg)
    assert "maker-docs" not in bundle.sources_used
    assert bundle.withheld.get("maker-docs", 0) >= 2
    assert res.release == 1


# --- Part 1: TGK variant codes as split evidence (Model S / Model X) ------------------------


def _load_split_fixture():
    from ev_pipeline.records import SourceRecord

    p = Path(__file__).parent / "fixtures" / "rdw_tgk" / "split_t163.jsonl"
    recs = [SourceRecord.model_validate(json.loads(x)) for x in p.read_text().splitlines()]
    return (
        [r for r in recs if r.source.id.root == "rdw-tgk"],
        [r for r in recs if r.source.id.root == "openev"],
    )


def _tgk_rec(tgk_recs, sub: str, year: int):
    for r in tgk_recs:
        if sub in r.record_key and r.year == year:
            return r
    raise LookupError((sub, year))


def _place_one(rec, openev_recs, extra_variants=None, table=None) -> str:
    from ev_pipeline.match.matcher import load_tgk_split, match_records
    from ev_pipeline.match.seed import (
        load_manual_variants,
        load_seed,
        parse_manual_variants,
    )

    seed = load_seed(REPO / "data" / "seed" / "models.yaml")
    manual, _ = load_manual_variants(REPO / "data" / "seed" / "variants.yaml")
    if extra_variants:
        extra, probs = parse_manual_variants(
            {"variants": extra_variants}, datetime(2026, 11, 26).date()
        )
        assert probs == []
        manual = [*manual, *extra]
    split = load_tgk_split() if table is None else table
    res = match_records([*openev_recs, rec], seed, manual, tgk_split=split)
    placed = {
        mf.fact.subject_id.root
        for mf in res.spec_facts
        if mf.source_id == "rdw-tgk" and mf.fact.source_record == rec.record_key
    }
    if placed:
        [vid] = placed
        return vid
    [why] = [u.reason for u in res.unmatched if u.record_key == rec.record_key]
    return why


@pytest.mark.seed
def test_model_s_75r_ruled_out_of_75d_and_splits_when_75_rwd_row_exists() -> None:
    """T-163: 75R (RWD) no longer lands on AWD 75D; with a 75 RWD row + type_codes [75R],
    both 75D and 75R land on their own rows."""
    from ev_pipeline.match.matcher import TGK_MISFIT, load_tgk_split

    tgk, oe = _load_split_fixture()
    r75d = _tgk_rec(tgk, "|75D|B19B5N|", 2017)
    r75r = _tgk_rec(tgk, "|75R|B19B5N|", 2017)

    # Before T-163 (empty table): both 75D and 75R landed on 75d
    assert _place_one(r75r, oe, table={}) == "tesla-model-s-facelift-75d"
    # With T-163 tgk_split.yaml: 75D stays, 75R is ruled out for review
    assert _place_one(r75d, oe) == "tesla-model-s-facelift-75d"
    why = _place_one(r75r, oe)
    assert why.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in why

    # Once a future 75 RWD row is seeded (even without pack kWh), type_codes splits 75R vs 75D
    rwd_row = {
        "generation_id": "tesla-model-s-facelift",
        "id": "tesla-model-s-facelift-75",
        "name": "75",
        "years": [2016, 2018],
        "drivetrain": "rwd",
        "specs": {},
        "confidence": "medium",
    }
    table = {**load_tgk_split(), "tesla-model-s-facelift-75": {"type_codes": {"75R"}}}
    assert (
        _place_one(r75d, oe, extra_variants=[rwd_row], table=table) == "tesla-model-s-facelift-75d"
    )
    assert (
        _place_one(r75r, oe, extra_variants=[rwd_row], table=table) == "tesla-model-s-facelift-75"
    )


@pytest.mark.seed
@pytest.mark.parametrize(
    ("code", "year", "want"),
    [
        ("|85|B19|", 2014, "tesla-model-s-gen1-85"),
        ("|85D|B19B5|", 2015, "tesla-model-s-gen1-85d-90d"),
        ("|100D|B19B5N|", 2018, "tesla-model-s-facelift-100d"),
        ("|100D|P21P5N|", 2018, "tesla-model-s-facelift-p100d"),
        ("|SA3|EBS15N|", 2020, "tesla-model-s-facelift-raven-long-range"),
        ("|SB1D|B1T1S5M1C2|", 2022, "tesla-model-s-palladium-long-range"),
        ("|SB1D|B1T1S5M1C2|", 2024, "tesla-model-s-palladium-long-range"),
        ("|SB1T|B1T1S5M2C2|", 2024, "tesla-model-s-palladium-plaid"),
        ("|XB1D|B1T2S6M1C4|", 2025, "tesla-model-x-palladium-long-range"),
        ("|XB1T|B1T2S6M2C3|", 2025, "tesla-model-x-palladium-plaid"),
    ],
)
def test_model_s_and_x_ties_resolve_via_tgk_variant_codes(code: str, year: int, want: str) -> None:
    from ev_pipeline.match.matcher import TGK_TIE

    tgk, oe = _load_split_fixture()
    rec = _tgk_rec(tgk, code, year)
    assert _place_one(rec, oe) == want
    # Before T-163 (no split table): ties on every multi-row group (or wrong match on Palladium)
    if (
        code
        not in ("|SB1D|B1T1S5M1C2|", "|SB1T|B1T1S5M2C2|", "|XB1D|B1T2S6M1C4|", "|XB1T|B1T2S6M2C3|")
        or year == 2022
    ):
        assert TGK_TIE in _place_one(rec, oe, table={})


@pytest.mark.seed
def test_model_x_gen1_splits_by_variant_code_without_pack_kwh() -> None:
    """T-163 / T-162: Model X gen1 rows seeded without pack kWh (Tesla type approval gives
    60X / 75X / 90X / 100X / XA1 / XA3, no pack kWh) split cleanly via type_codes."""
    from ev_pipeline.match.matcher import TGK_MISFIT, load_tgk_split

    tgk, oe = _load_split_fixture()
    mx_rows = [
        {
            "generation_id": "tesla-model-x-gen1",
            "id": f"tesla-model-x-gen1-{slug}",
            "name": name,
            "years": [2016, 2020],
            "drivetrain": "awd",
            "specs": {},  # pack kWh intentionally absent
            "confidence": "medium",
        }
        for slug, name in (
            ("60d", "60D"),
            ("75d", "75D"),
            ("90d", "90D"),
            ("100d", "100D"),
        )
    ]
    table = {
        **load_tgk_split(),
        "tesla-model-x-gen1-60d": {"type_codes": {"60X"}},
        "tesla-model-x-gen1-75d": {"type_codes": {"75X", "XA1"}},
        "tesla-model-x-gen1-90d": {"type_codes": {"90X"}},
        "tesla-model-x-gen1-100d": {"type_codes": {"100X", "XA3"}},
    }
    cases = [
        ("|60X|B20B", 2017, "tesla-model-x-gen1-60d"),
        ("|75X|B20B", 2017, "tesla-model-x-gen1-75d"),
        ("|90X|B20B", 2017, "tesla-model-x-gen1-90d"),
        ("|100X|B20B", 2018, "tesla-model-x-gen1-100d"),
        ("|XA1|EBX1", 2019, "tesla-model-x-gen1-75d"),
        ("|XA3|EBX1", 2019, "tesla-model-x-gen1-100d"),
    ]
    for code, yr, want in cases:
        rec = _tgk_rec(tgk, code, yr)
        # Without type_codes evidence, missing pack kWh fails with battery unknown
        assert TGK_MISFIT in _place_one(rec, oe, extra_variants=mx_rows, table={})
        # With type_codes evidence, each variant code lands on its own row
        assert _place_one(rec, oe, extra_variants=mx_rows, table=table) == want
