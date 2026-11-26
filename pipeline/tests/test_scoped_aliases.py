"""Q-021: source-scoped aliases (`aliases_by_source` in models.yaml, flag EV_SCOPED_ALIASES)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import (
    BEV_FILTERED_SOURCES,
    SCOPED_ALIASES_ENV,
    find_by_source_alias,
    find_model,
    find_model_noted,
    match_records,
    scoped_aliases_enabled,
)
from ev_pipeline.match.normalise import key
from ev_pipeline.match.seed import load_seed, parse_seed
from ev_pipeline.records import SourceRecord, SpecValue

REAL_SEED = Path(__file__).parents[2] / "data" / "seed" / "models.yaml"

RDW = {"id": "rdw", "name": "RDW", "licence": "CC0-1.0"}
EEA = {"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"}
KBA = {"id": "kba-fz10", "name": "KBA", "licence": "DL-DE-BY-2.0"}
OPENEV = {"id": "openev", "name": "OpenEV Data", "licence": "CDLA-Permissive-2.0"}


def _rec(make: str, model: str, source: dict, year: int | None = 2020, count: bool = True):
    specs = (
        {"registered_count": SpecValue(value=10, unit="count")}
        if count
        else {"battery_kwh_net": SpecValue(value=50, unit="kWh")}
    )
    return SourceRecord(
        source=source,
        record_key=f"{source['id']}:{make}|{model}|{year}",
        kind="registration_count" if count else "spec",
        make=make,
        model=model,
        year=year,
        country="NL",
        specs=specs,
        retrieved_at=date(2026, 11, 14),
        confidence="medium",
    )


SEED = {
    "makes": [
        {
            "id": "smart",
            "name": "Smart",
            "models": [
                {
                    "id": "smart-eq-fortwo",
                    "name": "EQ fortwo",
                    "name_aliases": ["fortwo ED"],
                    "source_aliases": {"dft-veh": ["FORTWO"]},  # legacy, ignored when scoped
                    "aliases_by_source": {
                        "rdw": ["FORTWO COUPE ED"],
                        "dft-veh": [{"name": "FORTWO", "match": "prefix"}],
                    },
                    "generations": [{"id": "smart-eq-fortwo-453", "years": [2017, 2024]}],
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
                    "bev_only_aliases": ["KONA"],  # legacy: every BEV-filtered source
                    "aliases_by_source": {"rdw,kba-fz10": ["KONA"]},  # scoped: two sources
                    "generations": [{"id": "hyundai-kona-electric-os", "years": [2018, 2023]}],
                },
                {
                    # No aliases_by_source: keeps its legacy bev_only_aliases either way.
                    "id": "hyundai-ioniq-electric",
                    "name": "Ioniq Electric",
                    "bev_only_aliases": ["IONIQ"],
                    "generations": [{"id": "hyundai-ioniq-electric-gen1", "years": [2016, 2022]}],
                },
            ],
        },
        {
            "id": "cupra",
            "name": "Cupra",
            "models": [
                {
                    "id": "cupra-born",
                    "name": "Born",
                    "aliases_by_source": {
                        "kba-fz10": [
                            {"name": "SEAT BORN", "match": "prefix", "note": "KBA files it as SEAT"}
                        ]
                    },
                    "generations": [{"id": "cupra-born-gen1", "years": [2021, None]}],
                }
            ],
        },
    ]
}


@pytest.fixture(scope="module")
def seed():
    return parse_seed(SEED)


def _found(seed, rec, scoped: bool) -> str | None:
    model, _ = find_model(seed, seed.make_id_for(rec.make), rec, scoped)
    return model.id if model else None


# --- parsing ------------------------------------------------------------------------------


def test_parse_entries_and_comma_keys(seed) -> None:
    kona = seed.models["hyundai-kona-electric"]
    assert set(kona.aliases_by_source) == {"rdw", "kba-fz10"}
    assert kona.aliases_by_source["rdw"][0].match == "exact"  # bare string = whole name
    smart = seed.models["smart-eq-fortwo"].aliases_by_source
    assert smart["dft-veh"][0].match == "prefix"
    assert seed.models["hyundai-ioniq-electric"].aliases_by_source is None  # key absent


@pytest.mark.parametrize(
    "bad",
    [{"rdw": [{"name": "X", "match": "fuzzy"}]}, {"rdw": [{"note": "no name"}]}, {"": ["X"]}],
)
def test_parse_rejects_bad_entries(bad) -> None:
    data = {
        "makes": [
            {
                "id": "m",
                "name": "M",
                "models": [{"id": "m-x", "name": "X", "aliases_by_source": bad}],
            }
        ]
    }
    with pytest.raises(ValueError):
        parse_seed(data)


# --- flag ---------------------------------------------------------------------------------


def test_flag_env_and_explicit(monkeypatch) -> None:
    monkeypatch.setenv(SCOPED_ALIASES_ENV, "0")
    assert scoped_aliases_enabled() is False
    assert scoped_aliases_enabled(True) is True  # explicit value wins
    monkeypatch.setenv(SCOPED_ALIASES_ENV, "on")
    assert scoped_aliases_enabled() is True
    monkeypatch.setenv(SCOPED_ALIASES_ENV, "maybe")
    with pytest.raises(ValueError):
        scoped_aliases_enabled()


def test_match_records_reads_the_flag(seed, monkeypatch) -> None:
    rec = _rec("SMART", "FORTWO COUPE ED", RDW, 2018)
    monkeypatch.setenv(SCOPED_ALIASES_ENV, "0")
    off = match_records([rec], seed)
    assert off.scoped_aliases is False and len(off.unmatched) == 1
    monkeypatch.setenv(SCOPED_ALIASES_ENV, "1")
    on = match_records([rec], seed)
    assert on.scoped_aliases is True and on.unmatched == []
    assert on.count_facts[0].generation_id == "smart-eq-fortwo-453"


# --- scoping rules ------------------------------------------------------------------------


def test_scoped_alias_only_for_its_source(seed) -> None:
    assert _found(seed, _rec("SMART", "FORTWO COUPE ED", RDW), True) == "smart-eq-fortwo"
    assert _found(seed, _rec("SMART", "FORTWO COUPE ED", EEA), True) is None
    assert _found(seed, _rec("SMART", "FORTWO COUPE ED", OPENEV, count=False), True) is None
    # Flag off: aliases_by_source is ignored entirely.
    assert _found(seed, _rec("SMART", "FORTWO COUPE ED", RDW), False) is None


def test_exact_alias_is_whole_name_only(seed) -> None:
    assert _found(seed, _rec("SMART", "FORTWO COUPE ED BRABUS", RDW), True) is None
    assert _found(seed, _rec("HYUNDAI", "KONA HYBRID", RDW), True) is None


def test_prefix_alias(seed) -> None:
    dft = {"id": "dft-veh", "name": "DfT", "licence": "OGL-UK-3.0"}
    assert _found(seed, _rec("SMART", "FORTWO PRIME EV", dft), True) == "smart-eq-fortwo"


def test_scoped_list_replaces_legacy_keys(seed) -> None:
    # Legacy bev_only KONA covers EEA too; the scoped list names rdw and kba-fz10 only.
    assert _found(seed, _rec("HYUNDAI", "KONA", EEA), False) == "hyundai-kona-electric"
    assert _found(seed, _rec("HYUNDAI", "KONA", EEA), True) is None
    assert _found(seed, _rec("HYUNDAI", "KONA", KBA), True) == "hyundai-kona-electric"


def test_model_without_scoped_list_keeps_legacy(seed) -> None:
    assert _found(seed, _rec("HYUNDAI", "IONIQ", EEA), True) == "hyundai-ioniq-electric"
    assert _found(seed, _rec("HYUNDAI", "IONIQ", OPENEV, count=False), True) is None


def test_scoped_alias_with_foreign_make_and_note(seed) -> None:
    rec = _rec("SEAT", "BORN", KBA, 2023)
    model, note = find_by_source_alias(seed, rec, scoped=True)
    assert model is not None and model.id == "cupra-born" and note == "KBA files it as SEAT"
    assert find_by_source_alias(seed, rec, scoped=False) == (None, None)
    res = match_records([rec], seed, scoped_aliases=True)
    assert res.count_facts[0].note == "KBA files it as SEAT"


# --- the committed seed -------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    return load_seed(REAL_SEED)


@pytest.mark.seed
def test_real_seed_migration_is_complete(real) -> None:
    """Every legacy alias of a model with `aliases_by_source` is still there for the sources
    it was valid for, so turning the flag on never loses a match."""
    for m in real.models.values():
        if m.aliases_by_source is None:
            continue
        scoped = m.aliases_by_source

        def has(sid: str, name: str, prefix: bool, model=m, scoped=scoped) -> bool:
            for a in scoped.get(sid, []):
                if key(a.name) == key(name) and (a.match == "prefix" or not prefix):
                    return True
            return False

        for name in m.bev_only_aliases:
            for sid in BEV_FILTERED_SOURCES:
                assert has(sid, name, prefix=False), (m.id, sid, name)
        for sid, aliases in m.source_aliases.items():
            for a in aliases:
                assert has(sid, a.name, prefix=True), (m.id, sid, a.name)


@pytest.mark.seed
@pytest.mark.parametrize(
    ("make", "model", "source", "expected"),
    [
        ("SMART", "FORTWO COUPE ED", RDW, "smart-eq-fortwo"),
        ("SMART", "FORTWO CABRIO ED", RDW, "smart-eq-fortwo"),
        ("SMART", "FORFOUR ED", RDW, "smart-eq-forfour"),  # T-136: own model
        ("MG", "ROEWE ZS EV", RDW, "mg-zs-ev"),
        ("MERCEDES-BENZ", "CLASSE EQA", EEA, "mercedes-eqa"),
        ("MERCEDES-BENZ", "CLASSE EQA", RDW, None),  # scoped to EEA
        ("HYUNDAI", "KONA", RDW, "hyundai-kona-electric"),
        ("FIAT", "500", EEA, "fiat-500e"),
        ("FIAT", "FIAT 500 1.4 16V", RDW, None),
        ("AUDI", "E-TRON GT", RDW, "audi-e-tron-gt"),  # T-136: own model, not the e-tron
        ("BMW", "4ER", KBA, "bmw-i4"),
        ("PEUGEOT", "208", OPENEV, None),  # never for spec sources
        # T-136 van-based people carriers (M1 only): longest alias wins, cargo names stay out.
        ("TOYOTA", "PROACE CITY VERSO ELECTRIC", EEA, "toyota-proace-city-verso"),
        ("TOYOTA", "PROACE", EEA, "toyota-proace-verso"),
        ("RENAULT", "KANGOO E-TECH ELECTRIC", EEA, "renault-kangoo-e-tech"),
        ("RENAULT", "KANGOO VAN E-TECH ELECTRIC", EEA, None),
        ("OPEL", "VIVARO ZAFIRA LIFE", EEA, "opel-zafira-e-life"),
        ("OPEL", "COMBO-E LIFE L1 EDITION", EEA, "opel-combo-e-life"),
        ("CITROEN", "JUMPY SPACETOURER", EEA, "citroen-e-spacetourer"),
        ("CITROEN", "E-BERLINGO VAN", RDW, None),
        ("PEUGEOT", "EXPERT TRAVELLER", EEA, "peugeot-e-traveller"),
        ("PEUGEOT", "E-RIFTER", EEA, "peugeot-e-rifter"),
        ("MERCEDES-BENZ", "ECITAN TOURER/EQT", EEA, "mercedes-eqt"),
        ("MERCEDES-BENZ", "EVITO TOURER", EEA, "mercedes-evito-tourer"),
        ("MERCEDES-BENZ", "EQV 300", EEA, "mercedes-eqv"),
        ("NISSAN", "NISSAN E-NV200", EEA, "nissan-e-nv200"),
        ("FORD", "TRANSIT CUSTOM", EEA, "ford-e-tourneo-custom"),
        ("FORD", "TOURNEO COURIER", EEA, "ford-e-tourneo-courier"),
        ("FIAT", "ULYSSE TRIPOD", EEA, "fiat-e-ulysse"),
        ("KIA", "PV5 PASSENGER", EEA, "kia-pv5-passenger"),
    ],
)
def test_real_seed_scoped(real, make, model, source, expected) -> None:
    rec = _rec(make, model, source, count=source is not OPENEV)
    found, why, _ = find_model_noted(real, real.make_id_for(make), rec, scoped=True)
    assert (found.id if found else None) == expected, why


# --- make-level aliases per source --------------------------------------------------------


def test_make_alias_per_source() -> None:
    s = parse_seed(
        {
            "makes": [
                {
                    "id": "volkswagen",
                    "name": "Volkswagen",
                    "make_aliases_by_source": {"eea": ["VOLKSWAGEN, VW"], "openev,rdw": ["VW AG"]},
                    "models": [],
                }
            ]
        }
    )
    assert s.make_id_for("VOLKSWAGEN, VW", "eea", scoped=True) == "volkswagen"
    assert s.make_id_for("VOLKSWAGEN, VW", "eea", scoped=False) is None  # flag off
    assert s.make_id_for("VOLKSWAGEN, VW", "rdw", scoped=True) is None  # other source
    assert s.make_id_for("VW AG", "rdw", scoped=True) == "volkswagen"
    assert s.make_id_for("VW", "kba-fz10") == "volkswagen"  # global MAKE_ALIASES unchanged


def test_make_alias_on_two_makes_is_an_error() -> None:
    mk = {"make_aliases_by_source": {"eea": ["GROUP"]}, "models": []}
    with pytest.raises(ValueError):
        parse_seed({"makes": [{"id": "a", "name": "A", **mk}, {"id": "b", "name": "B", **mk}]})


@pytest.mark.seed
@pytest.mark.parametrize(
    ("make", "model", "source", "expected"),
    [
        ("VOLKSWAGEN, VW", "ID.3 PRO 150 KW", EEA, "volkswagen-id3"),
        ("VOLKSWAGEN, VW", "ID.4 GTX 220 KW", EEA, "volkswagen-id4"),
        ("MG Motor", "MG4", OPENEV, "mg-mg4"),
        ("AUDI AG", "Q4 E-TRON", EEA, "audi-q4-e-tron"),
        ("VOLKSWAGEN, VW", "ID.3 PRO", RDW, None),  # scoped to EEA
    ],
)
def test_real_seed_make_aliases(real, make, model, source, expected) -> None:
    rec = _rec(make, model, source, year=2025, count=source is not OPENEV)
    res = match_records([rec], real, scoped_aliases=True)
    placed = {mf.model_id for mf in res.count_facts + res.spec_facts}
    assert placed == ({expected} if expected else set()), res.unmatched
