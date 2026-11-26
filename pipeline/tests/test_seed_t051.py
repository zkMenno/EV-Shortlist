"""T-051: the 8 top-40 models (part 1) and the 15 next-biggest models (part 2) added to the real
seed place the source names they were built from.

Records are built in memory from the names seen in staging (RDW, EEA, KBA, DfT, KilowattApp);
no network, no staging files. Generations are picked by year, as in the release.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import (
    find_generation,
    find_record_model,
    match_view,
)
from ev_pipeline.match.seed import load_seed
from ev_pipeline.records import SourceRecord, SpecValue

pytestmark = pytest.mark.seed

REAL_SEED = Path(__file__).parents[2] / "data" / "seed" / "models.yaml"
SOURCES = {
    "rdw": {"id": "rdw", "name": "RDW", "licence": "CC0-1.0"},
    "eea": {"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"},
    "kba-fz10": {"id": "kba-fz10", "name": "KBA", "licence": "DL-DE-BY-2.0"},
    "dft-veh": {"id": "dft-veh", "name": "DfT", "licence": "OGL-UK-3.0"},
    "kilowatt-openev": {"id": "kilowatt-openev", "name": "KilowattApp", "licence": "MIT"},
}
NEW_MODELS = {
    "volvo-ex30",
    "bmw-ix1",
    "bmw-ix3",
    "opel-mokka",
    "mercedes-eqb",
    "porsche-taycan",
    "bmw-ix",
    "ford-explorer",
}
# Part 2: next biggest missing BEVs by NL used + UK fleet + DE new share (QUESTIONS Q-083).
NEW_MODELS_2 = {
    "volkswagen-id7",
    "skoda-elroq",
    "audi-q6-e-tron",
    "cupra-tavascan",
    "audi-a6-e-tron",
    "bmw-i5",
    "kia-ev3",
    "renault-5-e-tech",
    "volkswagen-id-buzz",
    "hyundai-inster",
    "toyota-bz4x",
    "mercedes-cla",
    "ford-puma-gen-e",
    "porsche-macan-electric",
    "renault-scenic-e-tech",
}


@pytest.fixture(scope="module")
def seed():
    return load_seed(REAL_SEED)


def _rec(sid: str, make: str, model: str, year: int | None, variant: str | None = None):
    return SourceRecord(
        source=SOURCES[sid],
        record_key=f"{sid}:{make}|{model}|{variant}|{year}",
        kind="registration_count",
        make=make,
        model=model,
        variant_name=variant,
        year=year,
        country="NL",
        specs={"registered_count": SpecValue(value=10, unit="count")},
        retrieved_at=date(2026, 11, 15),
        confidence="high",
    )


def _place(seed, rec):
    model, why, _, _ = find_record_model(seed, match_view(rec), True)  # as match_records
    if model is None:
        return None, None, why
    gen, why = find_generation(model, rec.year)
    return model.id, gen.id if gen else None, why


def test_all_eight_models_in_seed(seed):
    assert set(seed.models) >= NEW_MODELS


@pytest.mark.parametrize(
    ("sid", "make", "model", "year", "variant", "model_id", "gen_id"),
    [
        ("rdw", "VOLVO", "EX30 CROSS COUNTRY", 2025, None, "volvo-ex30", "volvo-ex30-gen1"),
        ("dft-veh", "VOLVO", "VOLVO EX30", None, "EX30 PLUS AWD", "volvo-ex30", "volvo-ex30-gen1"),
        ("rdw", "BMW", "IX1 EDRIVE20", 2024, None, "bmw-ix1", "bmw-ix1-gen1"),
        ("kba-fz10", "BMW", "X1", 2025, None, "bmw-ix1", "bmw-ix1-gen1"),
        # iX3: plain name = first car; power-number names from 2026 = second car (year picks)
        ("rdw", "BMW", "IX3", 2025, None, "bmw-ix3", "bmw-ix3-gen1"),
        ("rdw", "BMW", "IX3 50 XDRIVE", 2026, None, "bmw-ix3", "bmw-ix3-gen2"),
        ("rdw", "BMW", "IX3-40", 2026, None, "bmw-ix3", "bmw-ix3-gen2"),
        ("kba-fz10", "BMW", "X3", 2026, None, "bmw-ix3", "bmw-ix3-gen2"),
        ("eea", "BMW AG", "IX3 50 XDRIVE", 2025, None, "bmw-ix3", "bmw-ix3-gen1"),
        # iX must not take iX1 / iX3 names, and the reverse
        ("rdw", "BMW", "IX XDRIVE40", 2022, None, "bmw-ix", "bmw-ix-gen1"),
        ("rdw", "BMW", "IX M70 XDRIVE", 2025, None, "bmw-ix", "bmw-ix-gen1"),
        ("rdw", "OPEL", "MOKKA", 2021, None, "opel-mokka", "opel-mokka-gen1"),
        ("rdw", "OPEL", "MOKKA ULTIMATE EV", 2021, None, "opel-mokka", "opel-mokka-gen1"),
        ("dft-veh", "VAUXHALL", "VAUXHALL MOKKA", None, "MOKKA GS EV", "opel-mokka", "opel-mokka-gen1"),  # noqa: E501
        ("kba-fz10", "OPEL", "MOKKA", 2026, None, "opel-mokka", "opel-mokka-gen1"),
        ("rdw", "MERCEDES-BENZ", "EQB 250+", 2024, None, "mercedes-eqb", "mercedes-eqb-gen1"),
        ("eea", "MERCEDES-BENZ", "CLASSE EQB", 2025, None, "mercedes-eqb", "mercedes-eqb-gen1"),
        ("rdw", "MERCEDES-BENZ", "GLB 250+", 2026, None, "mercedes-eqb", "mercedes-eqb-glb"),
        ("kba-fz10", "MERCEDES", "GLB", 2025, None, "mercedes-eqb", "mercedes-eqb-gen1"),
        ("kba-fz10", "MERCEDES", "GLB", 2026, None, "mercedes-eqb", "mercedes-eqb-glb"),
        ("rdw", "PORSCHE", "TAYCAN 4S", 2020, None, "porsche-taycan", "porsche-taycan-gen1"),
        ("rdw", "FORD", "EXPLORER", 2024, None, "ford-explorer", "ford-explorer-gen1"),
        ("dft-veh", "FORD", "FORD EXPLORER", None, "EXPLORER SELECT EV", "ford-explorer", "ford-explorer-gen1"),  # noqa: E501
        ("kilowatt-openev", "Ford", "Explorer Extended Range AWD", 2024, None, "ford-explorer", "ford-explorer-gen1"),  # noqa: E501
    ],
)  # fmt: skip
def test_source_names_place(seed, sid, make, model, year, variant, model_id, gen_id):
    rec = _rec(sid, make, model, year, variant)
    mid, gid, why = _place(seed, rec)
    if year is None:  # no year (DfT): model level; only the model is checked
        assert mid == model_id, why
        return
    assert (mid, gid) == (model_id, gen_id), why


@pytest.mark.parametrize(
    ("make", "model", "year"),
    [
        ("OPEL", "MOKKA X", 2018),  # ICE predecessor name: outside the generation
        ("VOLVO", "EX30", 2022),  # before the first evidence year
        ("FORD", "EXPLORER", 2010),  # single stray car
    ],
)
def test_out_of_range_stays_unplaced(seed, make, model, year):
    _, gid, why = _place(seed, _rec("rdw", make, model, year))
    assert gid is None
    assert "outside every generation" in why or "not in seed" in why


def test_bare_x1_x3_only_for_kba(seed):
    # KBA's series name means the BEV column there; RDW 'X1' cars stay unmatched.
    for name in ("X1", "X3"):
        mid, _, _ = _place(seed, _rec("rdw", "BMW", name, 2022))
        assert mid is None


def test_part2_models_in_seed(seed):
    assert set(seed.models) >= NEW_MODELS_2
    for mid in NEW_MODELS_2:
        assert all(g.uncertain for g in seed.models[mid].generations), mid


@pytest.mark.parametrize(
    ("sid", "make", "model", "year", "variant", "model_id", "gen_id"),
    [
        ("rdw", "VOLKSWAGEN", "ID.7 TOURER PRO", 2024, None, "volkswagen-id7", "volkswagen-id7-gen1"),  # noqa: E501
        ("eea", "VOLKSWAGEN, VW", "ID.7 PRO S", 2025, None, "volkswagen-id7", "volkswagen-id7-gen1"),  # noqa: E501
        ("dft-veh", "VOLKSWAGEN", "VOLKSWAGEN ID7", None, "ID7 MATCH PRO", "volkswagen-id7", None),
        ("kba-fz10", "VW", "ID.7", 2025, None, "volkswagen-id7", "volkswagen-id7-gen1"),
        ("rdw", "SKODA", "ELROQ 85", 2025, None, "skoda-elroq", "skoda-elroq-gen1"),
        ("rdw", "AUDI", "Q6 SUV E-TRON PERFORMANCE", 2024, None, "audi-q6-e-tron", "audi-q6-e-tron-gen1"),  # noqa: E501
        ("rdw", "AUDI", "SQ6 SUV E-TRON", 2025, None, "audi-q6-e-tron", "audi-q6-e-tron-gen1"),
        ("eea", "AUDI", "Q6 SB E-TRON QUATTRO", 2025, None, "audi-q6-e-tron", "audi-q6-e-tron-gen1"),  # noqa: E501
        ("kba-fz10", "AUDI", "Q6", 2025, None, "audi-q6-e-tron", "audi-q6-e-tron-gen1"),
        ("kba-fz10", "SEAT", "TAVASCAN", 2025, None, "cupra-tavascan", "cupra-tavascan-gen1"),
        ("rdw", "CUPRA", "TAVASCAN", 2024, None, "cupra-tavascan", "cupra-tavascan-gen1"),
        ("rdw", "AUDI", "A6 AV E-TRON", 2025, None, "audi-a6-e-tron", "audi-a6-e-tron-gen1"),
        ("rdw", "AUDI", "S6 AV E-TRON", 2024, None, "audi-a6-e-tron", "audi-a6-e-tron-gen1"),
        ("dft-veh", "AUDI", "AUDI S6", None, "S6 E-TRON EDITION 1 QUATTRO", "audi-a6-e-tron", None),
        ("kba-fz10", "AUDI", "A6", 2025, None, "audi-a6-e-tron", "audi-a6-e-tron-gen1"),
        ("rdw", "BMW", "I5 EDRIVE40", 2023, None, "bmw-i5", "bmw-i5-gen1"),
        ("kba-fz10", "BMW", "5ER", 2025, None, "bmw-i5", "bmw-i5-gen1"),
        ("rdw", "KIA", "EV3", 2024, None, "kia-ev3", "kia-ev3-gen1"),
        ("rdw", "RENAULT", "RENAULT 5 E-TECH ELECTRIC", 2024, None, "renault-5-e-tech", "renault-5-e-tech-gen1"),  # noqa: E501
        ("dft-veh", "RENAULT", "RENAULT 5", None, "5 TECHNO E-TECH EV", "renault-5-e-tech", None),
        ("kba-fz10", "RENAULT", "R5", 2025, None, "renault-5-e-tech", "renault-5-e-tech-gen1"),
        ("rdw", "VOLKSWAGEN", "ID. BUZZ PRO 150 KW", 2022, None, "volkswagen-id-buzz", "volkswagen-id-buzz-gen1"),  # noqa: E501
        ("rdw", "VOLKSWAGEN", "ID.BUZZ PRO LR 210 KW", 2026, None, "volkswagen-id-buzz", "volkswagen-id-buzz-gen1"),  # noqa: E501
        ("kba-fz10", "VW", "ID. BUZZ", 2023, None, "volkswagen-id-buzz", "volkswagen-id-buzz-gen1"),
        ("rdw", "HYUNDAI", "INSTER", 2025, None, "hyundai-inster", "hyundai-inster-gen1"),
        ("rdw", "TOYOTA", "TOYOTA BZ4X", 2022, None, "toyota-bz4x", "toyota-bz4x-gen1"),
        ("rdw", "TOYOTA", "TOYOTA BZ4X TOURING", 2026, None, "toyota-bz4x", "toyota-bz4x-gen1"),
        ("kba-fz10", "TOYOTA", "BZ4", 2025, None, "toyota-bz4x", "toyota-bz4x-gen1"),
        ("rdw", "MERCEDES-BENZ", "CLA 250+", 2025, None, "mercedes-cla", "mercedes-cla-gen1"),
        ("dft-veh", "MERCEDES-BENZ", "MERCEDES-BENZ CLA", None, "CLA250+WTH EQ TC AMG LN PRM ED", "mercedes-cla", None),  # noqa: E501
        ("kba-fz10", "MERCEDES", "CLA-KLASSE", 2026, None, "mercedes-cla", "mercedes-cla-gen1"),
        ("rdw", "FORD", "PUMA", 2025, None, "ford-puma-gen-e", "ford-puma-gen-e-gen1"),
        ("dft-veh", "FORD", "FORD PUMA", None, "PUMA PREMIUM EV", "ford-puma-gen-e", None),
        ("kba-fz10", "FORD", "PUMA", 2025, None, "ford-puma-gen-e", "ford-puma-gen-e-gen1"),
        ("rdw", "PORSCHE", "MACAN 4S", 2024, None, "porsche-macan-electric", "porsche-macan-electric-gen1"),  # noqa: E501
        ("dft-veh", "PORSCHE", "PORSCHE MACAN", None, "MACAN 4 ELECTRIC", "porsche-macan-electric", None),  # noqa: E501
        ("kilowatt-openev", "Porsche", "Macan Turbo Electric", 2024, None, "porsche-macan-electric", "porsche-macan-electric-gen1"),  # noqa: E501
        ("rdw", "RENAULT", "SCENIC E-TECH ELECTRIC", 2024, None, "renault-scenic-e-tech", "renault-scenic-e-tech-gen1"),  # noqa: E501
        ("dft-veh", "RENAULT", "RENAULT SCENIC", None, "SCENIC TECHNO E-TECH EV", "renault-scenic-e-tech", None),  # noqa: E501
        ("kba-fz10", "RENAULT", "SCENIC", 2025, None, "renault-scenic-e-tech", "renault-scenic-e-tech-gen1"),  # noqa: E501
    ],
)  # fmt: skip
def test_part2_source_names_place(seed, sid, make, model, year, variant, model_id, gen_id):
    test_source_names_place(seed, sid, make, model, year, variant, model_id, gen_id)


@pytest.mark.parametrize(
    ("make", "model", "year"),
    [
        ("MERCEDES-BENZ", "CLA 220", 2019),  # combustion CLA stray: before the electric CLA
        ("AUDI", "A6 AVANT", 2017),  # combustion A6 name: never aliased
        ("PORSCHE", "MACAN S", 2015),  # combustion Macan stray
        ("FORD", "PUMA", 2020),  # combustion Puma stray
        ("SKODA", "ELROQ 60", 2024),  # before the first RDW year
    ],
)
def test_part2_shared_ice_names_stay_unplaced(seed, make, model, year):
    _, gid, why = _place(seed, _rec("rdw", make, model, year))
    assert gid is None
    assert "outside every generation" in why or "not in seed" in why


def test_part2_new_names_do_not_steal_existing_models(seed):
    # The new prefixes (Q6, A6, 5, SCENIC, CLA) must not take seed models' names.
    cases = [
        ("rdw", "AUDI", "Q4 SPORTBACK 45 E-TRON", 2023, "audi-q4-e-tron"),
        ("rdw", "AUDI", "Q8 E-TRON", 2023, "audi-e-tron"),
        ("rdw", "RENAULT", "MEGANE E-TECH", 2023, "renault-megane-e-tech"),
        ("dft-veh", "RENAULT", "RENAULT ZOE", "ZOE GT LINE R135 EV50", "renault-zoe"),
        ("eea", "MERCEDES-BENZ", "CLASSE EQB", 2025, "mercedes-eqb"),
        ("rdw", "VOLKSWAGEN", "ID.4 PRO 150 KW", 2023, "volkswagen-id4"),
    ]
    for case in cases:
        if case[0] == "dft-veh":
            sid, make, model, variant, want = case
            rec = _rec(sid, make, model, None, variant)
        else:
            sid, make, model, year, want = case
            rec = _rec(sid, make, model, year)
        mid, _, why = _place(seed, rec)
        assert mid == want, (case, why)


def test_part2_eqe_kba_series_not_mapped(seed):
    # KBA E-KLASSE (BEV column) holds EQE saloon and EQE SUV: not mapped (Q-083).
    mid, _, _ = _place(seed, _rec("kba-fz10", "MERCEDES", "E-KLASSE", 2025))
    assert mid is None
