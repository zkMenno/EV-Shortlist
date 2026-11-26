"""T-005 matching rules: normalisation, model/generation/variant matching, unmatched output."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import (
    aggregate_counts,
    find_generation,
    find_model,
    match_records,
    normalise_unit,
    registration_entries,
)
from ev_pipeline.match.normalise import key, slug, strip_accents, tokens
from ev_pipeline.match.review import unmatched_rows, write_unmatched
from ev_pipeline.match.seed import load_manual_variants, load_seed
from ev_pipeline.records import SourceRecord, SpecValue

FIX = Path(__file__).parent / "fixtures" / "release"


@pytest.fixture(scope="module")
def seed():
    return load_seed(FIX / "models.yaml")


def _rec(make: str, model: str, variant: str | None = None, year: int | None = None, **kw):
    src = kw.pop(
        "source", {"id": "openev", "name": "OpenEV Data", "licence": "CDLA-Permissive-2.0"}
    )
    return SourceRecord(
        source=src,
        record_key=kw.pop("record_key", f"{make}/{model}/{variant}/{year}"),
        make=make,
        model=model,
        variant_name=variant,
        year=year,
        specs=kw.pop("specs", {"battery_kwh_net": SpecValue(value=50, unit="kWh")}),
        retrieved_at=date(2026, 11, 14),
        confidence="medium",
        **kw,
    )


def _load_staging(name: str) -> list[SourceRecord]:
    path = FIX / "staging" / f"{name}.records.jsonl"
    return [SourceRecord.model_validate_json(x) for x in path.read_text().splitlines() if x]


# --- normalisation -----------------------------------------------------------------------


def test_normalise_accents_case_punctuation() -> None:
    assert strip_accents("ë-C4") == "e-C4"
    assert key("ë-C4") == key("e-C4") == key("E-C4") == "ec4"
    assert key("Mustang Mach-E") == key("MUSTANG MACH E") == "mustangmache"
    assert key("ID.3") == key("ID 3") == "id3"
    assert tokens("MODEL 3 LONG RANGE") == ["model", "3", "long", "range"]
    assert slug("Long Range AWD") == "long-range-awd"
    assert slug("50 kWh") == "50-kwh"


# --- make / model ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("make", "model", "expected"),
    [
        ("Tesla", "Model 3", "tesla-model-3"),
        ("TESLA", "MODEL 3", "tesla-model-3"),  # RDW upper case
        ("TESLA", "MODEL 3 LONG RANGE", "tesla-model-3"),  # longest token prefix
        ("Tesla", "Tesla Model 3", "tesla-model-3"),  # make repeated in model name
        ("Citroën", "ë-C4", "citroen-e-c4"),
        ("CITROEN", "E-C4", "citroen-e-c4"),  # alias + accent-free make
        ("Ford", "Mustang Mach-E", "ford-mustang-mach-e"),
        ("Ford", "MACH-E", "ford-mustang-mach-e"),  # name_alias
        ("Nissan", "LEAF", "nissan-leaf"),
    ],
)
def test_model_matching(seed, make: str, model: str, expected: str) -> None:
    make_id = seed.make_id_for(make)
    assert make_id is not None
    found, why = find_model(seed, make_id, _rec(make, model))
    assert found is not None, why
    assert found.id == expected


def test_model_prefix_respects_token_boundaries(seed) -> None:
    # "Model 30" must not match "Model 3": prefixes are whole tokens.
    found, why = find_model(seed, "tesla", _rec("Tesla", "Model 30"))
    assert found is None and why == "model not in seed"


def test_make_aliases(seed) -> None:
    assert seed.make_id_for("CITROËN") == "citroen"
    assert seed.make_id_for("Polestar") is None


# --- generation --------------------------------------------------------------------------


def test_generation_by_year_and_open_end(seed) -> None:
    m3 = seed.models["tesla-model-3"]
    assert find_generation(m3, 2019)[0].id == "tesla-model-3-gen1"
    assert find_generation(m3, 2023)[0].id == "tesla-model-3-gen1"
    assert find_generation(m3, 2031)[0].id == "tesla-model-3-highland"  # end null = open
    gen, why = find_generation(m3, 2017)
    assert gen is None and "outside every generation" in why


def test_shared_boundary_year_goes_to_newer_generation(seed) -> None:
    assert find_generation(seed.models["renault-zoe"], 2019)[0].id == "renault-zoe-ph2"


def test_no_year_needs_single_generation(seed) -> None:
    assert find_generation(seed.models["citroen-e-c4"], None)[0].id == "citroen-e-c4-c41"
    gen, why = find_generation(seed.models["tesla-model-3"], None)
    assert gen is None and "2 generations" in why


# --- variants ----------------------------------------------------------------------------


def test_variant_ids_and_year_merge(seed) -> None:
    res = match_records(
        _load_staging("openev") + _load_staging("wikidata") + _load_staging("eea"), seed
    )
    lr = res.variants["tesla-model-3-gen1-long-range"]
    assert lr.years == {2022, 2023}  # two openev years + wikidata merge into one variant
    assert lr.source_ids == {"openev", "wikidata"}  # eea spec rows are count-only
    assert "tesla-model-3-gen1-performance" in res.variants  # RDW-style upper case
    assert "citroen-e-c4-c41-50-kwh" in res.variants
    assert res.variants["citroen-e-c4-c41-50-kwh"].source_ids == {"openev", "wikidata"}
    assert res.count_only_skipped == {"eea": 2}
    assert all(mf.source_id != "eea" for mf in res.spec_facts)


def test_seed_manual_lends_its_id_to_same_named_variant(seed) -> None:
    manual, problems = load_manual_variants(FIX / "variants.yaml")
    assert problems == []
    res = match_records(_load_staging("openev"), seed, manual)
    assert "tesla-model-3-gen1-long-range" not in res.variants
    lr = res.variants["tesla-model-3-gen1-lr"]
    assert lr.source_ids == {"openev", "seed-manual"}
    assert lr.explicit_end == 2023


def test_base_variant_when_no_name(seed) -> None:
    res = match_records([_rec("Citroën", "e-C4", None, 2022)], seed)
    assert list(res.variants) == ["citroen-e-c4-c41-base"]


def test_fact_ids_and_units(seed) -> None:
    res = match_records(_load_staging("openev"), seed)
    ids = {mf.fact.id: mf.fact for mf in res.spec_facts}
    f = ids["openev:citroen/e-c4/2021-50:consumption_kwh_100km"]
    assert f.value == pytest.approx(15.5)  # 155 Wh/km -> kWh/100km
    assert f.unit == "kWh/100km"
    assert f.subject_type.value == "variant"
    assert f.subject_id.root == "citroen-e-c4-c41-50-kwh"
    assert str(f.retrieved_at) == "2026-11-14"


def test_unit_conversion_and_rejection() -> None:
    assert normalise_unit("wltp_range_km", SpecValue(value=100, unit="mi"))[0] == pytest.approx(
        160.9344
    )
    assert normalise_unit("price_new", SpecValue(value=1, unit="eur"))[1] == "EUR"
    assert normalise_unit("price_new", SpecValue(value=1, unit="USD"))[2]
    assert normalise_unit("battery_kwh_net", SpecValue(value=1, unit="Ah"))[2]


# --- registration counts -----------------------------------------------------------------


def test_registration_counts_aggregate_to_generation(seed) -> None:
    res = match_records(_load_staging("rdw"), seed)
    agg = aggregate_counts(res.count_facts, seed, "rdw", "NL")
    assert agg["tesla-model-3-gen1"].value == 3000  # 2020 + 2021
    assert agg["tesla-model-3-highland"].value == 500
    assert len(agg["tesla-model-3-gen1"].fact_ids) == 2
    # LEAF has no year and two generations: kept as a model-level fact, not split.
    assert "nissan-leaf-ze0" not in agg and "nissan-leaf-ze1" not in agg
    assert any(mf.fact.subject_type.value == "model" for mf in res.count_facts)


def test_model_level_count_used_for_single_generation_model(seed) -> None:
    rec = _rec(
        "CITROEN",
        "E-C4",
        None,
        None,
        source={"id": "rdw", "name": "RDW", "licence": "CC0-1.0"},
        kind="registration_count",
        country="NL",
        specs={"registered_count": SpecValue(value=42, unit="count")},
    )
    agg = aggregate_counts(match_records([rec], seed).count_facts, seed, "rdw", "NL")
    assert agg["citroen-e-c4-c41"].value == 42
    assert agg["citroen-e-c4-c41"].level == "model"


# --- unmatched ---------------------------------------------------------------------------


def test_unmatched_csv(seed, tmp_path: Path) -> None:
    res = match_records(_load_staging("openev") + _load_staging("rdw"), seed)
    reasons = {r.record_key: r.reason for r in res.unmatched}
    assert reasons["tesla/cybertruck/2024"] == "model not in seed"
    assert "outside every generation" in reasons["nissan/leaf/2010"]
    assert "no year" in reasons["tesla/model-3/no-year"]
    # Makes not in the seed are only counted, not listed one by one.
    assert res.other_makes[("rdw", "POLESTAR")] == 1
    assert res.other_makes[("openev", "POLESTAR")] == 1
    rows = unmatched_rows(res)
    out = tmp_path / "unmatched.csv"
    write_unmatched(out, rows)
    lines = list(csv.DictReader(out.open()))
    assert list(lines[0]) == [
        "source_id",
        "record_key",
        "make",
        "model",
        "variant_name",
        "year",
        "reason",
    ]
    assert sum(1 for r in lines if r["record_key"] == "(summary)") == 3
    assert len(lines) == 6


def test_unmatched_file_stays_small(seed) -> None:
    recs = [_rec("Tesla", f"Roadster {i}", None, 2022, record_key=f"k{i}") for i in range(3000)]
    recs += [_rec(f"Make{i}", "X", None, 2022, record_key=f"m{i}") for i in range(500)]
    res = match_records(recs, seed)
    rows = unmatched_rows(res)
    assert len(rows) < 2000
    assert rows[-1].make == "(other makes)"


def test_nyland_never_matches(seed) -> None:
    # Synthetic Testcar (fixture seed has it), so the record would match under any other source.
    rec = _rec(
        "Testmake",
        "Testcar Alpha",
        "Long Range",
        2024,
        source={"id": "nyland", "name": "Nyland (synthetic)", "licence": "none"},
    )
    assert find_model(seed, "testmake", rec)[0].id == "testmake-testcar-alpha"
    res = match_records([rec], seed)
    assert res.spec_facts == [] and res.variants == {}
    assert res.excluded["nyland"] == 1
    assert match_records([_rec("Testmake", "Testcar Alpha", "Long Range", 2024)], seed).variants


# --- seed guards: name_excludes, bev_only_aliases (T-005 review) -------------------------


GUARD_SEED = {
    "makes": [
        {
            "id": "audi",
            "name": "Audi",
            "models": [
                {
                    "id": "audi-e-tron",
                    "name": "e-tron",
                    "name_aliases": ["Q8 e-tron", "e-tron Sportback"],
                    "name_excludes": ["e-tron GT", "RS e-tron GT"],
                    "generations": [{"id": "audi-e-tron-ge", "years": [2019, 2022]}],
                },
                {
                    "id": "audi-q4-e-tron",
                    "name": "Q4 e-tron",
                    "name_aliases": ["Q4 40 e-tron", "Q4 Sportback 40 e-tron"],
                    "generations": [{"id": "audi-q4-e-tron-gen1", "years": [2021, None]}],
                },
            ],
        },
        {
            "id": "hyundai",
            "name": "Hyundai",
            "models": [
                {
                    "id": "hyundai-kona-electric",
                    "name": "Kona Electric",
                    "bev_only_aliases": ["KONA", "KONA, KAUAI"],
                    "generations": [{"id": "kona-os", "years": [2018, 2023]}],
                }
            ],
        },
        {
            "id": "fiat",
            "name": "Fiat",
            "models": [
                {
                    "id": "fiat-500e",
                    "name": "500e",
                    "bev_only_aliases": ["500"],
                    "generations": [{"id": "fiat-500e-gen1", "years": [2020, None]}],
                }
            ],
        },
        {
            "id": "volkswagen",
            "name": "Volkswagen",
            "models": [
                {
                    "id": "volkswagen-id4",
                    "name": "ID.4",
                    "generations": [{"id": "id4-gen1", "years": [2020, None]}],
                },
                {
                    "id": "volkswagen-e-golf",
                    "name": "e-Golf",
                    "bev_only_aliases": ["GOLF"],
                    "generations": [{"id": "e-golf", "years": [2014, 2020]}],
                },
            ],
        },
    ]
}

RDW = {"id": "rdw", "name": "RDW", "licence": "CC0-1.0"}


@pytest.fixture(scope="module")
def guard_seed():
    from ev_pipeline.match.seed import parse_seed

    return parse_seed(GUARD_SEED)


@pytest.mark.parametrize(
    ("make", "model", "source", "expected"),
    [
        ("AUDI", "E-TRON", RDW, "audi-e-tron"),
        ("AUDI", "E-TRON SPORTBACK 55", RDW, "audi-e-tron"),
        ("AUDI", "Q8 E-TRON", None, "audi-e-tron"),
        ("AUDI", "E-TRON GT", RDW, None),  # different car
        ("AUDI", "AUDI E-TRON GT", RDW, None),
        ("AUDI", "E-TRON GT QUATTRO", RDW, None),
        ("Audi", "e-tron GT", None, None),
        ("AUDI", "RS E-TRON GT", RDW, None),
        ("AUDI", "Q4 40 E-TRON", RDW, "audi-q4-e-tron"),
        ("AUDI", "Q4 SPORTBACK 40 E-TRON", None, "audi-q4-e-tron"),
        ("HYUNDAI", "KONA", RDW, "hyundai-kona-electric"),  # BEV-filtered source
        ("HYUNDAI", "KONA, KAUAI", RDW, "hyundai-kona-electric"),
        ("HYUNDAI", "KONA", None, None),  # openev: bare names are not scoped to it
        ("HYUNDAI", "KONA HYBRID", RDW, None),  # whole-name only, never a prefix
        ("FIAT", "500", RDW, "fiat-500e"),
        ("FIAT", "500", None, None),
        ("FIAT", "500 1.4 16V", RDW, None),  # petrol leak through the RDW proxy
        ("FIAT", "500 HYBRID", RDW, None),
        ("FIAT", "500E", None, "fiat-500e"),
        ("VOLKSWAGEN", "GOLF", RDW, "volkswagen-e-golf"),
        ("VOLKSWAGEN", "GOLF GTI", RDW, None),
        ("Volkswagen", "ID.4 GTX", None, "volkswagen-id4"),  # trim, not another model
    ],
)
def test_seed_guards(guard_seed, make, model, source, expected) -> None:
    kw = {"source": source} if source else {}
    found, why = find_model(guard_seed, guard_seed.make_id_for(make), _rec(make, model, **kw))
    assert (found.id if found else None) == expected, why


def test_excluded_name_has_a_review_reason(guard_seed) -> None:
    res = match_records([_rec("AUDI", "E-TRON GT", None, 2021, source=RDW)], guard_seed)
    assert res.variants == {} and res.spec_facts == []
    assert res.unmatched[0].reason == "model not in seed (name excluded from audi-e-tron)"


@pytest.mark.seed
def test_real_seed_guards() -> None:
    # The committed seed carries the guards the review asked for.
    real = load_seed(FIX.parents[2].parent / "data" / "seed" / "models.yaml")
    rdw = {"source": RDW}
    cases = [
        # T-136: the e-tron GT is its own seed model now; guard: never the e-tron.
        ("AUDI", "E-TRON GT", "audi-e-tron-gt"),
        ("AUDI", "RS E-TRON GT", "audi-e-tron-gt"),
        ("AUDI", "E-TRON", "audi-e-tron"),
        ("AUDI", "Q4 40 E-TRON", "audi-q4-e-tron"),
        ("AUDI", "Q4 SPORTBACK 45 E-TRON", "audi-q4-e-tron"),
        ("HYUNDAI", "KONA", "hyundai-kona-electric"),
        ("HYUNDAI", "KONA, KAUAI", "hyundai-kona-electric"),
        ("FIAT", "500", "fiat-500e"),
        ("FIAT", "FIAT 500 1.4 16V", None),
        ("PEUGEOT", "208", "peugeot-e-208"),
        ("PEUGEOT", "2008", "peugeot-e-2008"),
        ("OPEL", "CORSA", "opel-corsa-e"),
        ("KIA", "NIRO", "kia-niro-ev"),
        ("HONDA", "E:NY1", "honda-e-ny1"),  # Honda e:Ny1 is not the Honda e (own model since T-136)
        ("HONDA", "HONDA E", "honda-e"),
    ]
    for make, model, expected in cases:
        found, why = find_model(real, real.make_id_for(make), _rec(make, model, **rdw))
        assert (found.id if found else None) == expected, (make, model, why)
    # Not scoped to spec sources: OpenEV "208" is not assumed to be the e-208.
    found, _ = find_model(real, "peugeot", _rec("Peugeot", "208"))
    assert found is None


# --- shared-year generations (T-005 review) ----------------------------------------------


LEAF_SEED = {
    "makes": [
        {
            "id": "nissan",
            "name": "Nissan",
            "models": [
                {
                    "id": "nissan-leaf",
                    "name": "Leaf",
                    "generations": [
                        {"id": "nissan-leaf-ze1", "years": [2018, 2025]},
                        {"id": "nissan-leaf-gen3", "years": [2025, None]},
                    ],
                }
            ],
        },
        {
            "id": "hyundai",
            "name": "Hyundai",
            "models": [
                {
                    "id": "hyundai-kona-electric",
                    "name": "Kona Electric",
                    "bev_only_aliases": ["KONA"],
                    "generations": [
                        {"id": "kona-os", "years": [2018, 2023]},
                        {"id": "kona-sx2", "years": [2023, None]},
                    ],
                }
            ],
        },
    ]
}


def _manual(gen: str, vid: str, name: str, year: int, net: float):
    from ev_pipeline.match.seed import parse_manual_variants

    data = {
        "variants": [
            {
                "generation_id": gen,
                "id": vid,
                "name": name,
                "years": [year, None],
                "specs": {"battery_kwh_net": net},
            }
        ]
    }
    return parse_manual_variants(data, date(2026, 11, 14))[0]


def _count(model: str, year: int, n: int = 100):
    return _rec(
        "NISSAN" if "LEAF" in model else "HYUNDAI",
        model,
        None,
        year,
        source=RDW,
        kind="registration_count",
        country="NL",
        record_key=f"{model}|{year}",
        specs={"registered_count": SpecValue(value=n, unit="count")},
    )


def test_leaf_shared_year_prefers_older_generation_on_battery_evidence() -> None:
    from ev_pipeline.match.seed import parse_seed

    seed = parse_seed(LEAF_SEED)
    manual = _manual("nissan-leaf-ze1", "nissan-leaf-ze1-40kwh", "40 kWh", 2018, 39)
    manual += _manual("nissan-leaf-ze1", "nissan-leaf-ze1-e-plus", "e+ 62 kWh", 2019, 59)
    packs = {"nissan-leaf-gen3": {52.0, 75.0}}
    recs = [
        _count("NISSAN LEAF 40KWH", 2025, 121),  # RDW style, kWh in the name
        _count("NISSAN LEAF 62 KWH", 2025, 7),
        _count("NISSAN LEAF 75KWH", 2025, 3),  # gen3 pack
        _count("NISSAN LEAF", 2025, 26),  # no evidence; gen3 has no variants -> newer
        _rec(
            "Nissan",
            "Leaf",
            "40 kWh",
            2025,
            specs={"battery_kwh_net": SpecValue(value=39, unit="kWh")},
        ),
    ]
    res = match_records(recs, seed, manual, packs)
    gen_of = {mf.fact.source_record: mf.generation_id for mf in res.count_facts}
    assert gen_of["NISSAN LEAF 40KWH|2025"] == "nissan-leaf-ze1"
    assert gen_of["NISSAN LEAF 62 KWH|2025"] == "nissan-leaf-ze1"
    assert gen_of["NISSAN LEAF 75KWH|2025"] == "nissan-leaf-gen3"
    assert gen_of["NISSAN LEAF|2025"] == "nissan-leaf-gen3"
    # The spec record named like a ZE1 variant lands on that ZE1 variant, not on gen3.
    assert "nissan-leaf-ze1-40kwh" in res.variants
    assert not any(v.startswith("nissan-leaf-gen3") for v in res.variants)
    agg = aggregate_counts(res.count_facts, seed, "rdw", "NL")
    assert agg["nissan-leaf-ze1"].value == 128 and agg["nissan-leaf-gen3"].value == 29


def test_shared_year_without_evidence_is_counted_at_model_level_never_split():
    """RDW shared year, both generations have variants, no name/battery evidence: the cars
    are counted for the model (level "model"), not guessed into a generation, not split by
    a ratio and not sent to review (coverage-gaps finding 6)."""
    from ev_pipeline.match.matcher import SHARED_YEAR_NOTE
    from ev_pipeline.match.seed import parse_seed

    seed = parse_seed(LEAF_SEED)
    manual = _manual("kona-os", "kona-os-64", "64 kWh", 2018, 64)
    manual += _manual("kona-sx2", "kona-sx2-65", "65.4 kWh", 2023, 65.4)
    res = match_records([_count("KONA", 2023, 1667), _count("KONA", 2022, 1192)], seed, manual)
    assert res.unmatched == []
    by_year = {mf.year: mf for mf in res.count_facts}
    assert by_year[2022].generation_id == "kona-os"  # 2022: one generation
    shared = by_year[2023]
    assert shared.generation_id is None and shared.model_id == "hyundai-kona-electric"
    assert shared.fact.subject_type.value == "model" and shared.fact.value == 1667
    assert SHARED_YEAR_NOTE in (shared.note or "") and "ambiguous-generation" in shared.note
    # registered_count_nl (aggregate_counts) stays generation level: the 2023 cars are not in it.
    agg = aggregate_counts(res.count_facts, seed, "rdw", "NL")
    assert {g: a.value for g, a in agg.items()} == {"kona-os": 1192}
    # PublishedVariant.registrations: one model-level entry with the whole shared-year count on
    # every generation, next to (never added to) the generation-level entry.
    regs = registration_entries(res.count_facts, seed)
    for gid in ("kona-os", "kona-sx2"):
        model_level = [e for e in regs[gid]["NL"] if e.level == "model"]
        assert [(e.count, e.kind, e.source_id) for e in model_level] == [(1667, "fleet", "rdw")]
        assert model_level[0].fact_ids == [shared.fact.id]
        assert any(SHARED_YEAR_NOTE in n for n in model_level[0].notes)
    assert [(e.count, e.level) for e in regs["kona-os"]["NL"] if e.level == "generation"] == [
        (1192, "generation")
    ]
    assert not [e for e in regs["kona-sx2"]["NL"] if e.level == "generation"]
    # Without the evidence index the plain "newer wins" rule still applies (Q-014).
    assert find_generation(seed.models["hyundai-kona-electric"], 2023)[0].id == "kona-sx2"


# --- year bands (T-005 review) -----------------------------------------------------------


def _id3(year: int, wltp: float, dc: float, source: str = "openev"):
    src = {"id": source, "name": source, "licence": "CDLA-Permissive-2.0"}
    return _rec(
        "Volkswagen",
        "ID.3",
        "Pro",
        year,
        source=src,
        record_key=f"vw/id3/{year}-pro",
        specs={
            "wltp_range_km": SpecValue(value=wltp, unit="km"),
            "dc_peak_kw": SpecValue(value=dc, unit="kW"),
            "battery_kwh_net": SpecValue(value=58, unit="kWh"),
        },
    )


ID3_SEED = {
    "makes": [
        {
            "id": "volkswagen",
            "name": "Volkswagen",
            "models": [
                {
                    "id": "volkswagen-id3",
                    "name": "ID.3",
                    "generations": [{"id": "volkswagen-id3-gen1", "years": [2020, None]}],
                }
            ],
        }
    ]
}


def test_year_bands_split_a_real_change_and_keep_small_ones() -> None:
    from ev_pipeline.match.seed import parse_seed
    from ev_pipeline.merge.merge import merge_variant_facts

    seed = parse_seed(ID3_SEED)
    recs = [
        _id3(2020, 420, 100),
        _id3(2021, 426, 100),  # +1.4% WLTP: same band
        _id3(2023, 426, 120),  # DC +20%: new band
        _id3(2024, 428, 135),  # DC +12.5% vs 2023's 120: another band
    ]
    res = match_records(recs, seed)
    base = "volkswagen-id3-gen1-pro"
    assert set(res.variants) == {base, f"{base}-2023", f"{base}-2024"}
    assert res.variants[base].years == {2020, 2021}
    assert res.variants[base].explicit_end == 2022
    assert res.variants[f"{base}-2023"].explicit_end == 2023
    assert res.variants[f"{base}-2024"].name == "Pro (2024+)"
    assert res.year_bands[0]["bands"] == ["2020-2021", "2023-2023", "2024-2024"]
    by_v: dict[str, list] = {}
    for mf in res.spec_facts:
        by_v.setdefault(mf.fact.subject_id.root, []).append(mf)
    m0 = merge_variant_facts(by_v[base])
    assert m0["dc_peak_kw"].value == 100 and m0["wltp_range_km"].value == 420  # earliest year
    assert [c.fact.value for c in m0["wltp_range_km"].conflicts] == []  # 426 within 2%
    assert merge_variant_facts(by_v[f"{base}-2024"])["dc_peak_kw"].value == 135


def test_year_band_small_change_stays_one_variant_with_conflict() -> None:
    from ev_pipeline.match.seed import parse_seed
    from ev_pipeline.merge.merge import merge_variant_facts

    res = match_records([_id3(2020, 400, 100), _id3(2022, 416, 105)], parse_seed(ID3_SEED))
    assert list(res.variants) == ["volkswagen-id3-gen1-pro"] and res.year_bands == []
    m = merge_variant_facts(res.spec_facts)
    assert m["wltp_range_km"].value == 400  # earliest kept
    assert [c.fact.value for c in m["wltp_range_km"].conflicts] == [416]  # change logged


def test_year_band_split_ends_an_open_seed_manual_span() -> None:
    from ev_pipeline.match.seed import parse_manual_variants, parse_seed

    seed = parse_seed(ID3_SEED)
    data = {
        "variants": [
            {
                "generation_id": "volkswagen-id3-gen1",
                "id": "volkswagen-id3-gen1-pro",
                "name": "Pro",
                "years": [2020, None],
                "specs": {"battery_kwh_net": 58, "dc_peak_kw": 100},
            }
        ]
    }
    manual, _ = parse_manual_variants(data, date(2026, 11, 14))
    res = match_records([_id3(2024, 428, 135), _id3(2025, 428, 135)], seed, manual)
    base = res.variants["volkswagen-id3-gen1-pro"]
    later = res.variants["volkswagen-id3-gen1-pro-2024"]
    assert base.years == {2020} and base.explicit_end == 2023 and not base.open_end
    assert later.years == {2024, 2025} and later.open_end
    assert base.source_ids == {"seed-manual"} and later.source_ids == {"openev"}


# --- Q-062: seed variant source_names (one row per real car) ------------------------------

MG_SEED = {
    "makes": [
        {
            "id": "mg",
            "name": "MG",
            "make_aliases_by_source": {"openev": ["MG Motor"]},
            "models": [
                {
                    "id": "mg-mg4",
                    "name": "MG4",
                    "generations": [{"id": "mg4-g1", "years": [2022, None]}],
                }
            ],
        }
    ]
}


def _mg_manual(source_names: dict | None = None):
    from ev_pipeline.match.seed import parse_manual_variants

    v = {
        "generation_id": "mg4-g1",
        "id": "mg4-g1-standard",
        "name": "Standard Range (51 kWh)",
        "years": [2023, None],
        "specs": {"battery_kwh_net": 51},
    }
    if source_names is not None:
        v["source_names"] = source_names
    return parse_manual_variants({"variants": [v]}, date(2026, 11, 14))[0]


def _mg_openev(variant: str, year: int = 2024, net: float = 49):
    return _rec(
        "MG Motor",
        "MG4",
        variant,
        year,
        specs={
            "battery_kwh_net": SpecValue(value=net, unit="kWh"),
            "wltp_range_km": SpecValue(value=350, unit="km"),
        },
    )


def test_source_names_join_other_sources_trims_to_the_seed_variant() -> None:
    from ev_pipeline.match.seed import parse_seed

    seed = parse_seed(MG_SEED)
    manual = _mg_manual({"openev": ["Standard", "Standard Range"]})
    recs = [_mg_openev("Standard"), _mg_openev("Standard Range"), _mg_openev("Trophy", net=61)]
    res = match_records(recs, seed, manual, scoped_aliases=True)
    assert sorted(res.variants) == ["mg4-g1-standard", "mg4-g1-trophy"]
    on_seed = {
        mf.fact.source_record
        for mf in res.spec_facts
        if mf.fact.subject_id.root == "mg4-g1-standard"
    }
    assert on_seed == {
        "mg4-g1-standard",
        "MG Motor/MG4/Standard/2024",
        "MG Motor/MG4/Standard Range/2024",
    }
    assert res.variants["mg4-g1-standard"].name == "Standard Range (51 kWh)"  # seed name kept


def test_source_names_are_scoped_to_their_source() -> None:
    from ev_pipeline.match.seed import parse_seed

    seed = parse_seed(MG_SEED)
    manual = _mg_manual({"kilowatt-openev": ["Standard"]})  # not an OpenEV name
    res = match_records([_mg_openev("Standard Range")], seed, manual, scoped_aliases=True)
    assert "mg4-g1-standard-range" in res.variants  # OpenEV's name was not aliased: own row
    assert res.variants["mg4-g1-standard"].source_names == {"kilowatt-openev": {"standard"}}


def test_without_source_names_openev_trims_stay_separate_rows() -> None:
    from ev_pipeline.match.seed import parse_seed

    seed = parse_seed(MG_SEED)
    res = match_records([_mg_openev("Standard Range")], seed, _mg_manual(), scoped_aliases=True)
    assert sorted(res.variants) == ["mg4-g1-standard", "mg4-g1-standard-range"]


def test_attach_only_record_matches_a_source_name_exactly() -> None:
    from ev_pipeline.match.seed import parse_manual_variants, parse_seed

    seed = parse_seed(MG_SEED)
    data = {
        "variants": [
            {"generation_id": "mg4-g1", "id": "mg4-g1-standard", "name": "Standard Range (51 kWh)",
             "years": [2022, None], "specs": {"battery_kwh_net": 51},
             "source_names": {"kilowatt-openev": ["SR"]}},
            {"generation_id": "mg4-g1", "id": "mg4-g1-long-range", "name": "Long Range (64 kWh)",
             "years": [2022, None], "specs": {"battery_kwh_net": 61.7}},
        ]
    }  # fmt: skip
    manual = parse_manual_variants(data, date(2026, 11, 14))[0]
    kw = {"id": "kilowatt-openev", "name": "KilowattApp", "licence": "MIT"}
    rec = _rec(
        "MG", "MG4 EV", "SR", 2022, source=kw, specs={"dc_peak_kw": SpecValue(value=117, unit="kW")}
    )
    res = match_records([rec], seed, manual, scoped_aliases=True)
    [mf] = [m for m in res.spec_facts if m.source_id == "kilowatt-openev"]
    assert mf.fact.subject_id.root == "mg4-g1-standard"


def test_source_names_bad_shapes_and_clashes_are_rejected() -> None:
    from ev_pipeline.match.seed import parse_manual_variants, parse_seed, parse_source_names

    assert parse_source_names({"openev,kilowatt-openev": ["Std"]}, "v") == {
        "openev": {"std"},
        "kilowatt-openev": {"std"},
    }
    for bad in (["Standard"], {"openev": "Standard"}, {"openev": [""]}, {"": ["x"]}):
        with pytest.raises(ValueError):
            parse_source_names(bad, "v")
    seed = parse_seed(MG_SEED)
    data = {
        "variants": [
            {"generation_id": "mg4-g1", "id": f"mg4-g1-{i}", "name": n, "years": [2022, None],
             "specs": {}, "source_names": {"openev": ["Standard"]}}
            for i, n in (("a", "A"), ("b", "B"))
        ]
    }  # fmt: skip
    manual = parse_manual_variants(data, date(2026, 11, 14))[0]
    with pytest.raises(ValueError, match="source_names"):
        match_records([], seed, manual)


def test_variants_validator_checks_source_names() -> None:
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "data" / "seed" / "validate_variants.py"
    spec = importlib.util.spec_from_file_location("validate_variants", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = {"generation_id": "g", "years": [2022, None], "drivetrain": "rwd", "specs": {},
            "confidence": "low"}  # fmt: skip
    doc = {
        "source": {"id": "seed-manual", "name": "s", "licence": "CC-BY-4.0", "attribution": "a"},
        "variants": [
            {**base, "id": "g-a", "name": "A", "source_names": {"openev": ["Standard"]}},
            {**base, "id": "g-b", "name": "B", "source_names": {"openev": ["STANDARD"]}},
            {**base, "id": "g-c", "name": "C", "source_names": {"openev": "Standard"}},
            {**base, "id": "g-d", "name": "D", "source_names": {"openev": ["Trophy"]}},
        ],
    }
    errors = mod.validate(doc, {"g": (2022, None)})
    assert any("g-b" in e and "also on g-a" in e for e in errors)
    assert any("g-c" in e and "non-empty names" in e for e in errors)
    assert not any("g-d" in e or "g-a)" in e for e in errors)


def test_rdw_spec_records_never_create_variants() -> None:
    """Q-068: RDW trade names are registration names; RDW specs may only attach to existing rows."""
    from ev_pipeline.match import matcher

    assert "rdw" in matcher.ATTACH_ONLY_SOURCES


def test_fueleconomy_is_attach_only_and_never_sets_wltp_consumption() -> None:
    """Q-075: EPA figures are a US cross-check; they never create variants or set WLTP fields."""
    from ev_pipeline.match import matcher

    assert "fueleconomy" in matcher.ATTACH_ONLY_SOURCES
    assert "consumption_kwh_100km" in matcher.IGNORED_FIELDS["fueleconomy"]


def test_rdw_tgk_is_attach_only_and_shares_origin_with_rdw() -> None:
    """Q-087: type approvals never create variants, and RDW plate values copied from them
    don't count as a second independent source."""
    from ev_pipeline.match import matcher
    from ev_pipeline.merge import merge

    assert "rdw-tgk" in matcher.ATTACH_ONLY_SOURCES
    assert merge.SAME_ORIGIN["rdw-tgk"] == "rdw"
