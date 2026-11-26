"""New sources in match/merge/derive/release: KBA FZ10, DfT VEH0120, ADEME, KilowattApp.

Covers source-scoped aliases, DfT matching on its variant column, count periods and levels,
PublishedVariant.registrations (never summed across sources, periods or kinds), attach-only
sources (no rows of their own), the ADEME FR price policy and KilowattApp curves.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from ev_pipeline.derive.rows import registrations_block
from ev_pipeline.match.matcher import (
    RegistrationEntry,
    aggregate_counts,
    count_period,
    match_records,
    registration_entries,
)
from ev_pipeline.match.seed import load_seed, parse_seed
from ev_pipeline.merge.policy import load_policies
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.release.build import build_release
from ev_pipeline.release.validate import provenance_errors

REPO = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "release"
NOW = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)

SOURCES = {
    "kba-fz10": ("KBA FZ10", "dl-de/by-2-0"),
    "dft-veh": ("DfT VEH0120", "OGL-UK-3.0"),
    "ademe": ("ADEME Car Labelling", "Licence-Ouverte-2.0"),
    "kilowatt-openev": ("Open EV Data (KilowattApp)", "MIT-with-attribution"),
    "rdw": ("RDW Open Data", "CC0-1.0"),
    "eea": ("EEA CO2 cars", "CC-BY-4.0"),
    "openev": ("OpenEV Data", "CDLA-Permissive-2.0"),
}


def _src(sid: str) -> dict[str, str]:
    name, lic = SOURCES[sid]
    return {"id": sid, "name": name, "licence": lic}


def _count(
    sid: str,
    make: str,
    model: str,
    n: int,
    year: int | None = None,
    country: str = "DE",
    variant: str | None = None,
    key: str | None = None,
) -> SourceRecord:
    return SourceRecord(
        source=_src(sid),
        record_key=key or f"{make}|{model}|{variant}|{year}",
        kind="registration_count",
        make=make,
        model=model,
        variant_name=variant,
        year=year,
        country=country,
        specs={"registered_count": SpecValue(value=n, unit="count")},
        retrieved_at=date(2026, 11, 15),
        confidence="high",
    )


def _spec(sid: str, make: str, model: str, variant: str | None, year: int | None, **specs: Any):
    country = specs.pop("country", None)
    units = {"battery_kwh_net": "kWh", "wltp_range_km": "km", "power_kw": "kW"}
    units |= {"dc_peak_kw": "kW", "consumption_kwh_100km": "kWh/100km", "ac_kw": "kW"}
    sv: dict[str, SpecValue] = {}
    for f, v in specs.items():
        if f == "price_new":
            sv[f] = SpecValue(value=v, unit="EUR")
        elif f == "dc_curve":
            sv[f] = SpecValue(value=v, unit="kW")
        else:
            sv[f] = SpecValue(value=v, unit=units[f])
    return SourceRecord(
        source=_src(sid),
        record_key=f"{make}|{model}|{variant}|{year}|{','.join(specs)}|{country}",
        make=make,
        model=model,
        variant_name=variant,
        year=year,
        country=country,
        specs=sv,
        retrieved_at=date(2026, 11, 15),
        confidence="medium",
    )


@pytest.fixture(scope="module")
def real_seed():
    return load_seed(REPO / "data" / "seed" / "models.yaml")


def _model_of(seed, rec: SourceRecord) -> tuple[str | None, str, str | None]:
    from ev_pipeline.match.matcher import find_record_model, match_view

    m, why, note, _ = find_record_model(seed, match_view(rec))  # the lookup match_records uses
    return (m.id if m else None), ("" if m else why), note


# --- source-scoped aliases (KBA) -----------------------------------------------------------


@pytest.mark.seed
@pytest.mark.parametrize(
    ("make", "model", "expected"),
    [
        ("BMW", "4ER", "bmw-i4"),  # BEV column of the 4 series
        ("AUDI", "Q4", "audi-q4-e-tron"),
        ("AUDI", "Q8", "audi-e-tron"),
        ("MERCEDES", "GLA", "mercedes-eqa"),
        ("SEAT", "BORN", "cupra-born"),  # SEAT is in the seed (Mii); the source alias still wins
        ("SEAT", "MII", "seat-mii-electric"),  # T-136d
        ("VW", "ID.4, ID.5", "volkswagen-id4"),
        ("MG ROEWE", "4", "mg-mg4"),  # make alias
        ("MG ROEWE", "4 URBAN", None),  # a different car
        ("TESLA", "MODEL Y", "tesla-model-y"),
        ("HYUNDAI", "KONA", "hyundai-kona-electric"),  # bev_only alias
        ("MINI", "MINI", None),  # all MINIs in one row: not mapped (Q-051)
        ("AUDI", "E-TRON GT", "audi-e-tron-gt"),  # T-136: own model now, never the e-tron
        ("HONDA", "E:NY1", "honda-e-ny1"),  # T-136: own model, not the Honda e
        ("BMW", "X1", "bmw-ix1"),  # BEV column of the X1 series (T-051 added the iX1)
        ("BMW", "X2", None),  # iX2 is not in the seed: never invent models
    ],
)
def test_kba_names(real_seed, make: str, model: str, expected: str | None) -> None:
    found, _, _ = _model_of(real_seed, _count("kba-fz10", make, model, 10, 2025))
    assert found == expected


@pytest.mark.seed
def test_source_aliases_are_scoped_to_their_source(real_seed) -> None:
    # "4ER" means the i4 only in KBA; the same name in RDW (or any other source) is not an i4.
    assert _model_of(real_seed, _count("kba-fz10", "BMW", "4ER", 1, 2025))[0] == "bmw-i4"
    assert _model_of(real_seed, _count("rdw", "BMW", "4ER", 1, 2025, "NL"))[0] is None
    assert _model_of(real_seed, _count("eea", "SEAT", "BORN", 1, 2025))[0] is None


@pytest.mark.seed
def test_source_alias_note_travels_with_the_count(real_seed) -> None:
    _, _, note = _model_of(real_seed, _count("kba-fz10", "VW", "ID.4, ID.5", 1, 2025))
    assert note and "ID.5" in note
    assert _model_of(real_seed, _count("kba-fz10", "VW", "ID.3", 1, 2025))[2] is None


# --- DfT: matched on the variant column ----------------------------------------------------


@pytest.mark.seed
@pytest.mark.parametrize(
    ("genmodel", "variant", "expected"),
    [
        ("HYUNDAI IONIQ", "IONIQ PREMIUM EV", "hyundai-ioniq-electric"),
        ("HYUNDAI IONIQ", "IONIQ 5 PREMIUM EV", "hyundai-ioniq-5"),
        ("HYUNDAI IONIQ", "IONIQ 6 ULTIMATE EV", "hyundai-ioniq-6"),
        ("HYUNDAI IONIQ", "IONIQ 9 CALLIGRAPHY EV 4X4", "hyundai-ioniq-9"),  # T-136
        ("AUDI E-TRON", "E-TRON TECHNIK 50 QUATTRO", "audi-e-tron"),
        ("AUDI E-TRON", "E-TRON GT QUATTRO", "audi-e-tron-gt"),  # T-136: own model, not the e-tron
        ("AUDI Q8", "Q8 E-TRON SPORT 50 QUATTRO", "audi-e-tron"),
        ("HONDA E", "E ADVANCE", "honda-e"),
        ("HONDA E", "ENY1 ADVANCE", "honda-e-ny1"),  # T-136
        ("MG 4", "4 TROPHY", "mg-mg4"),
        ("MG 4", "4 URBAN PREMIUM EV", None),
        ("MINI COOPER", "COOPER S ELECTRIC LEVEL 2", "mini-cooper-se"),
        ("TESLA MODEL 3", "MODEL 3 LONG RANGE", "tesla-model-3"),
        ("VOLKSWAGEN ID3", "ID3 PRO S", "volkswagen-id3"),
        ("VOLKSWAGEN ID5", "ID5 MATCH PRO", "volkswagen-id5"),  # in the seed since T-068
        ("KIA NIRO", "NIRO 2 EV", "kia-niro-ev"),
    ],
)
def test_dft_names(real_seed, genmodel: str, variant: str, expected: str | None) -> None:
    make = genmodel.split()[0]
    rec = _count("dft-veh", make, genmodel, 10, None, "UK", variant)
    assert _model_of(real_seed, rec)[0] == expected


# --- periods, levels, aggregation ----------------------------------------------------------


def test_count_periods() -> None:
    kba = _count("kba-fz10", "VW", "ID.3", 1, 2026, key="fz10_2026_10:YTD 2026-01..10:VW|ID.3")
    assert count_period(kba) == "2026-01..10"
    dft = _count("dft-veh", "TESLA", "TESLA MODEL 3", 1, None, "UK", "MODEL 3",
                 key="VEH0120_UK:2026 Q2:Licensed:TESLA|TESLA MODEL 3|MODEL 3")  # fmt: skip
    assert count_period(dft) == "2026-Q2"
    assert count_period(_count("eea", "VW", "ID.3", 1, 2025)) == "2025"
    assert count_period(_count("rdw", "VW", "ID.3", 1, 2021, "NL")) == "2026-11-15"  # snapshot


TWO_GEN_SEED = {
    "makes": [
        {
            "id": "tesla",
            "name": "Tesla",
            "models": [
                {
                    "id": "tesla-model-3",
                    "name": "Model 3",
                    "generations": [
                        {"id": "tesla-model-3-gen1", "years": [2019, 2024]},
                        {"id": "tesla-model-3-highland", "years": [2024, None]},
                    ],
                },
                {
                    "id": "tesla-model-y",
                    "name": "Model Y",
                    "generations": [{"id": "tesla-model-y-gen1", "years": [2021, None]}],
                },
            ],
        }
    ]
}


def _two_gen_variants() -> list[SourceRecord]:
    # Variants in both generations so that 2024 is a real guess (ambiguous-generation).
    return [
        _spec("openev", "Tesla", "Model 3", "LR", 2022, battery_kwh_net=75),
        _spec("openev", "Tesla", "Model 3", "RWD", 2025, battery_kwh_net=60),
    ]


def test_registrations_never_sum_across_sources_periods_or_kinds() -> None:
    seed = parse_seed(TWO_GEN_SEED)
    recs = [
        *_two_gen_variants(),
        _count("kba-fz10", "TESLA", "MODEL 3", 100, 2025, key="f:YTD 2025-01..12:a"),
        _count("kba-fz10", "TESLA", "MODEL 3", 70, 2026, key="f:YTD 2026-01..10:a"),
        _count("eea", "TESLA", "MODEL 3", 99, 2025),
        _count(
            "dft-veh",
            "TESLA",
            "TESLA MODEL 3",
            500,
            None,
            "UK",
            "MODEL 3 LR",
            key="VEH0120_UK:2026 Q2:Licensed:a",
        ),  # fmt: skip
        _count(
            "dft-veh",
            "TESLA",
            "TESLA MODEL 3",
            300,
            None,
            "UK",
            "MODEL 3 RWD",
            key="VEH0120_UK:2026 Q2:Licensed:b",
        ),  # fmt: skip
        _count("rdw", "TESLA", "MODEL 3", 40, 2020, "NL"),
        _count("rdw", "TESLA", "MODEL 3", 60, 2021, "NL"),
    ]
    res = match_records(recs, seed)
    regs = registration_entries(res.count_facts, seed)
    hl = regs["tesla-model-3-highland"]
    de = {(e.source_id, e.period): e for e in hl["DE"]}
    assert de[("kba-fz10", "2025-01..12")].count == 100
    assert de[("kba-fz10", "2026-01..10")].count == 70  # periods stay apart
    assert de[("eea", "2025")].count == 99  # sources stay apart, even for the same year
    assert all(e.kind == "new_registrations" for e in hl["DE"])
    # DfT has no year: one model-level fleet count (sum of its model rows), on both generations.
    for gid in ("tesla-model-3-gen1", "tesla-model-3-highland"):
        (uk,) = regs[gid]["UK"]
        assert (uk.count, uk.kind, uk.level, uk.period) == (800, "fleet", "model", "2026-Q2")
    # RDW: fleet at generation level, equal to registered_count_nl's aggregate.
    (nl,) = regs["tesla-model-3-gen1"]["NL"]
    agg = aggregate_counts(res.count_facts, seed, "rdw", "NL")["tesla-model-3-gen1"]
    assert (nl.count, nl.kind, nl.level) == (agg.value, "fleet", "generation")
    assert nl.count == 100
    assert "NL" not in hl


def test_kba_shared_year_falls_back_to_model_level_but_not_out_of_range() -> None:
    seed = parse_seed(TWO_GEN_SEED)
    recs = [
        *_two_gen_variants(),
        _count("kba-fz10", "TESLA", "MODEL 3", 50, 2024, key="f:YTD 2024-01..12:a"),
        _count("kba-fz10", "TESLA", "MODEL 3", 5, 2017, key="f:YTD 2017-01..12:a"),
        _count("eea", "TESLA", "MODEL 3", 49, 2024),  # EEA keeps sending a guess to review
    ]
    res = match_records(recs, seed)
    regs = registration_entries(res.count_facts, seed)
    for gid in ("tesla-model-3-gen1", "tesla-model-3-highland"):
        (e,) = regs[gid]["DE"]
        assert (e.source_id, e.count, e.level) == ("kba-fz10", 50, "model")
        assert any("ambiguous-generation" in n for n in e.notes)
    reasons = {(u.source_id, u.year): u.reason for u in res.unmatched}
    assert reasons[("kba-fz10", "2017")].startswith("year 2017 outside")
    assert reasons[("eea", "2024")].startswith("ambiguous-generation")


def test_attach_only_records_do_not_make_a_shared_year_ambiguous() -> None:
    """PR #91 review: RDW model-level counts sat on Kia EV6 gen1 / XPeng G6 gen1 rows only.
    T-068 split both into gen1 + facelift; the facelift has no variant (only attach-only RDW /
    TGK / ADEME records name it, and those never make one), yet those records marked it as
    "with variants", so the shared year turned ambiguous and the cars went to model level,
    shown on the one published generation. Attach-only records still give name/kWh evidence
    but no longer count as variants, so the plain newer-wins rule (Q-014) applies."""
    seed = parse_seed(TWO_GEN_SEED)
    recs = [
        _spec("openev", "Tesla", "Model 3", "LR", 2022, battery_kwh_net=75),  # gen1 only
        _spec("rdw", "Tesla", "Model 3", None, 2025, wltp_range_km=600, country="NL"),
        _spec("ademe", "Tesla", "Model 3", "Grande Autonomie", 2025, wltp_range_km=600),
        _count("rdw", "TESLA", "MODEL 3", 40, 2023, "NL"),
        _count("rdw", "TESLA", "MODEL 3", 25, 2024, "NL"),  # shared year
        _count("kba-fz10", "TESLA", "MODEL 3", 9, 2024, key="f:YTD 2024-01..12:a"),
    ]
    res = match_records(recs, seed)
    assert not [u for u in res.unmatched if "ambiguous-generation" in u.reason]
    regs = registration_entries(res.count_facts, seed)
    gen1 = regs["tesla-model-3-gen1"]
    assert [(e.source_id, e.count, e.level) for e in gen1["NL"]] == [("rdw", 40, "generation")]
    assert "DE" not in gen1  # no model-level KBA line either
    hl = regs["tesla-model-3-highland"]
    assert [(e.count, e.level) for e in hl["NL"]] == [(25, "generation")]
    # With a variant-making record in the newer generation the year stays a real guess.
    recs.append(_spec("openev", "Tesla", "Model 3", "RWD", 2025, battery_kwh_net=60))
    regs = registration_entries(match_records(recs, seed).count_facts, seed)
    levels = sorted((e.count, e.level) for e in regs["tesla-model-3-gen1"]["NL"])
    assert levels == [(25, "model"), (40, "generation")]


def test_model_level_count_on_a_one_generation_model_is_generation_level() -> None:
    seed = parse_seed(TWO_GEN_SEED)
    recs = [_count("dft-veh", "TESLA", "TESLA MODEL Y", 7, None, "UK", "MODEL Y LR")]
    (e,) = registration_entries(match_records(recs, seed).count_facts, seed)["tesla-model-y-gen1"][
        "UK"
    ]
    assert (e.count, e.level) == (7, "generation")


def test_registrations_block_provenance_lists_every_source_and_fact() -> None:
    entries = {
        "DE": [
            RegistrationEntry(9, "new_registrations", "2025", "generation", "eea", ["eea:a"],
                              "medium"),
            RegistrationEntry(10, "new_registrations", "2025-01..12", "generation", "kba-fz10",
                              ["kba-fz10:a"], "high", ["KBA joins ID.4 and ID.5"]),
        ],
        "UK": [RegistrationEntry(5, "fleet", "2026-Q2", "model", "dft-veh", ["dft-veh:a"], "high")],
    }  # fmt: skip
    regs, pv = registrations_block(entries)
    assert [e["source_id"] for e in regs["DE"]] == ["eea", "kba-fz10"]
    assert regs["UK"] == [
        {"count": 5, "kind": "fleet", "period": "2026-Q2", "level": "model", "source_id": "dft-veh"}
    ]
    assert pv["registrations.DE"]["source_ids"] == ["eea", "kba-fz10"]
    assert pv["registrations.DE"]["fact_ids"] == ["eea:a", "kba-fz10:a"]
    assert pv["registrations.DE"]["confidence"] == "medium"  # weakest input
    assert "ID.5" in pv["registrations.DE"]["note"]
    assert "same number on every generation" in pv["registrations.UK"]["note"]


def test_provenance_guard_covers_nested_counts() -> None:
    row = {
        "variant_id": "x",
        "registrations": {"UK": [{"count": 5, "kind": "fleet", "source_id": "dft-veh"}]},
        "provenance": {},
    }
    assert provenance_errors([row]) == ["x: registrations.UK has no provenance"]
    row["provenance"] = {"registrations.UK": {"source_ids": ["rdw"], "confidence": "high"}}
    assert "not in its provenance" in provenance_errors([row])[0]
    row["provenance"] = {"registrations.UK": {"source_ids": ["dft-veh"], "confidence": "high"}}
    assert provenance_errors([row]) == []


# --- attach-only sources (ADEME, KilowattApp) ----------------------------------------------

ATTACH_SEED = {
    "makes": [
        {
            "id": "kia",
            "name": "Kia",
            "models": [
                {
                    "id": "kia-ev6",
                    "name": "EV6",
                    "generations": [{"id": "kia-ev6-gen1", "years": [2021, None]}],
                },
                {
                    "id": "kia-niro-ev",
                    "name": "Niro EV",
                    "bev_only_aliases": ["NIRO"],
                    "generations": [
                        {"id": "kia-niro-ev-de", "years": [2018, 2022]},
                        {"id": "kia-niro-ev-sg2", "years": [2022, None]},
                    ],
                },
            ],
        }
    ]
}


def _ev6_openev() -> list[SourceRecord]:
    return [
        _spec("openev", "Kia", "EV6", "58 kWh RWD", 2022, battery_kwh_net=58, power_kw=125),
        _spec("openev", "Kia", "EV6", "77.4 kWh RWD", 2022, battery_kwh_net=77.4, power_kw=168),
        _spec("openev", "Kia", "EV6", "77.4 kWh AWD", 2022, battery_kwh_net=77.4, power_kw=239),
    ]


def test_attach_only_records_never_make_variants_and_attach_on_evidence() -> None:
    seed = parse_seed(ATTACH_SEED)
    ademe = [
        _spec(
            "ademe",
            "KIA",
            "EV6",
            "EV6 Moteur électrique 168kW (229ch)",
            None,
            price_new=56130,
            country="FR",
        ),  # fmt: skip
        _spec(
            "ademe", "KIA", "EV6", "EV6 Moteur électrique 168kW (229ch)", None, wltp_range_km=528
        ),
        _spec(
            "ademe",
            "KIA",
            "EV6",
            "EV6 Moteur électrique 430kW (585ch)",
            None,
            price_new=70000,
            country="FR",
        ),  # fmt: skip
    ]
    res = match_records(_ev6_openev() + ademe, seed)
    assert set(res.variants) == {
        "kia-ev6-gen1-58-kwh-rwd",
        "kia-ev6-gen1-77-4-kwh-rwd",
        "kia-ev6-gen1-77-4-kwh-awd",
    }
    placed = {mf.fact.subject_id.root for mf in res.spec_facts if mf.source_id == "ademe"}
    assert placed == {"kia-ev6-gen1-77-4-kwh-rwd"}  # 168 kW = that variant's power
    assert res.attached["ademe"] == 2
    (um,) = [u for u in res.unmatched if u.source_id == "ademe"]
    assert "attach-only: no variant evidence" in um.reason


def test_attach_only_tie_goes_to_review() -> None:
    seed = parse_seed(ATTACH_SEED)
    kw = [_spec("kilowatt-openev", "Kia", "EV6", "Long Range", 2022, battery_kwh_net=77.4)]
    res = match_records(_ev6_openev() + kw, seed)
    (um,) = [u for u in res.unmatched if u.source_id == "kilowatt-openev"]
    assert "tie between" in um.reason
    assert res.attached["kilowatt-openev"] == 0


def test_attach_only_without_year_picks_generation_by_battery_evidence() -> None:
    seed = parse_seed(ATTACH_SEED)
    openev = [
        _spec("openev", "Kia", "Niro EV", "e-Niro 39.2 kWh", 2019, battery_kwh_net=39.2),
        _spec("openev", "Kia", "Niro EV", "e-Niro 64 kWh", 2019, battery_kwh_net=64),
        _spec("openev", "Kia", "Niro EV", "Niro EV 64.8 kWh", 2023, battery_kwh_net=64.8),
    ]
    a = _spec("ademe", "KIA", "NIRO", "e-NIRO 64kWh", None, wltp_range_km=455)
    b = _spec("ademe", "KIA", "NIRO", "Niro EV Moteur électrique (204ch)", None, wltp_range_km=460)
    res = match_records(openev + [a, b], seed)
    reasons = [u.reason for u in res.unmatched if u.source_id == "ademe"]
    # a: 64 kWh fits both generations (64 / 64.8); b: no kWh at all -> both to review.
    assert reasons == ["no year and model has 2 generations"] * 2
    c = _spec("ademe", "KIA", "NIRO", "e-NIRO 39kWh", None, wltp_range_km=289)
    res = match_records(openev + [c], seed)
    placed = {mf.fact.subject_id.root for mf in res.spec_facts if mf.source_id == "ademe"}
    assert placed == {"kia-niro-ev-de-e-niro-39-2-kwh"}


def test_kilowatt_consumption_is_not_used_as_wltp_consumption() -> None:
    seed = parse_seed(ATTACH_SEED)
    kw = _spec("kilowatt-openev", "Kia", "EV6", "58 kWh RWD", 2022, consumption_kwh_100km=17.0,
               ac_kw=11)  # fmt: skip
    res = match_records(_ev6_openev() + [kw], seed)
    fields = {mf.fact.field.value for mf in res.spec_facts if mf.source_id == "kilowatt-openev"}
    assert fields == {"ac_kw"}
    assert res.ignored_fields == {"kilowatt-openev:consumption_kwh_100km": 1}


def test_fr_price_policy_puts_ademe_first() -> None:
    pol = load_policies(REPO / "data" / "field_sources.yaml")
    fr = pol.for_field("price_new.FR")
    assert fr.order[0] == "ademe" and fr.mode == "priority"
    assert pol.for_field("price_new.DE") is pol.fields["price_new_other"]
    assert pol.for_field("price_new.NL") is pol.fields["price_new_nl"]
    for f in ("wltp_range_km", "consumption_kwh_100km", "weight_kg"):
        order = pol.fields[f].order
        assert order.index("openev") < order.index("ademe"), f


# --- end to end ------------------------------------------------------------------------------


def _jsonl(path: Path, recs: list[SourceRecord]) -> None:
    path.write_text("".join(r.model_dump_json() + "\n" for r in recs), encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    shutil.copytree(FIX / "staging", d / "staging")
    shutil.copytree(FIX / "taxonomy", d / "taxonomy")
    for n in ("models", "variants", "platforms", "battery_packs", "variant_links"):
        shutil.copy(FIX / f"{n}.yaml", d / "seed" / f"{n}.yaml")
    shutil.copy(REPO / "data" / "field_sources.yaml", d / "field_sources.yaml")
    reg = yaml.safe_load((FIX / "sources.yaml").read_text())
    for sid in ("kba-fz10", "dft-veh", "ademe", "kilowatt-openev"):
        name, lic = SOURCES[sid]
        reg["sources"].append({"id": sid, "name": name, "licence": lic, "status": "active"})
    (d / "sources.yaml").write_text(yaml.safe_dump(reg), encoding="utf-8")
    curve = {"points": [[0, 150], [50, 150], [80, 80], [100, 20]], "status": "estimated"}
    _jsonl(d / "staging" / "kba-fz10.records.jsonl", [
        _count("kba-fz10", "TESLA", "MODEL 3", 1234, 2022, key="f:YTD 2022-01..12:TESLA|MODEL 3"),
    ])  # fmt: skip
    _jsonl(d / "staging" / "dft-veh.records.jsonl", [
        _count("dft-veh", "TESLA", "TESLA MODEL 3", 9000, None, "UK", "MODEL 3 LONG RANGE",
               key="VEH0120_UK:2026 Q2:Licensed:TESLA|TESLA MODEL 3|MODEL 3 LONG RANGE"),
    ])  # fmt: skip
    _jsonl(d / "staging" / "ademe.records.jsonl", [
        _spec("ademe", "TESLA", "MODEL 3", "MODEL 3 Performance", 2022, price_new=59990,
              country="FR"),
    ])  # fmt: skip
    _jsonl(d / "staging" / "kilowatt-openev.records.jsonl", [
        _spec("kilowatt-openev", "Tesla", "Model 3", "Performance", 2022, dc_curve=curve),
    ])  # fmt: skip
    return d


def test_release_with_new_sources(data_dir: Path) -> None:
    res = build_release(data_dir, now=NOW)
    rows = {r["variant_id"]: r for r in res.catalogue["rows"]}
    assert set(rows) == {  # the attach-only sources added no rows
        "citroen-e-c4-c41-50-kwh",
        "ford-mustang-mach-e-gen1-extended-range-awd",
        "nissan-leaf-ze0-24kwh",
        "nissan-leaf-ze1-40-kwh",
        "renault-zoe-ph1-q90",
        "tesla-model-3-gen1-lr",
        "tesla-model-3-gen1-performance",
    }
    perf, lr = rows["tesla-model-3-gen1-performance"], rows["tesla-model-3-gen1-lr"]
    # Registrations: RDW NL fleet = registered_count_nl; KBA and DfT next to it, never summed.
    for r in (perf, lr):
        regs = r["registrations"]
        assert regs["NL"][0]["count"] == r["registered_count_nl"] == 3000
        assert {(e["source_id"], e["kind"]) for e in regs["NL"]} >= {("rdw", "fleet")}
        kba = [e for e in regs["DE"] if e["source_id"] == "kba-fz10"]
        assert kba == [{"count": 1234, "kind": "new_registrations", "period": "2022-01..12",
                        "level": "generation", "source_id": "kba-fz10"}]  # fmt: skip
        assert all(e["source_id"] != "kba-fz10" for e in regs["DE"] if e not in kba)
        uk = regs["UK"][0]
        assert (uk["count"], uk["kind"], uk["level"]) == (9000, "fleet", "model")
        for cc in regs:
            assert set(r["provenance"][f"registrations.{cc}"]["source_ids"]) == {
                e["source_id"] for e in regs[cc]
            }
    # ADEME: FR price on the matching existing variant only.
    assert perf["price_new"]["FR"] == {"amount": 59990.0, "currency": "EUR"}
    assert perf["provenance"]["price_new.FR"]["source_ids"] == ["ademe"]
    assert "FR" not in (lr.get("price_new") or {})
    # KilowattApp curve replaces the default curve; still an estimate, and says so.
    assert perf["dc_curve_status"] == "estimated" and lr["dc_curve_status"] == "default"
    # A sourced 10-80 % average (OpenEV here) is kept over an *estimated* curve ...
    assert perf["provenance"]["dc_avg_10_80_kw"]["source_ids"] == ["openev"]
    # ... while the curve fills what the source lacks, labelled as an estimate.
    for f in ("dc_minutes_10_80", "dc_peak_held_min"):
        p = perf["provenance"][f]
        assert p["estimate"] is True and "kilowatt-openev" in p["source_ids"], f
        assert "estimated curve" in p["note"]
    if perf.get("dc_km_per_20min") is not None:
        km = perf["provenance"]["dc_km_per_20min"]
        assert km["estimate"] is True  # motorway consumption is WLTP x 1.30
        assert (
            "sourced figure" in km["note"] and "motorway consumption is an estimate" in km["note"]
        )
    assert provenance_errors(res.catalogue["rows"]) == []
    srcs = {s["id"] for s in res.catalogue["sources"]}
    assert {"kba-fz10", "dft-veh", "ademe", "kilowatt-openev"} <= srcs
    json.dumps(res.catalogue)  # serialisable
