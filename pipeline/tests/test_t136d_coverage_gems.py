"""T-136 (#129) + T-136d: the missing-model seed places the EEA names it was built for.

Each case is a real EEA make + commercial name (EU BEV registrations 2010-2025, counts only,
pulled 2026-11-18) and the seed model it must land on, through the matcher's own lookup.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import find_record_model, match_view
from ev_pipeline.match.seed import load_seed
from ev_pipeline.records import SourceRecord
from ev_pipeline.schema_models import Source
from ev_pipeline.sources.eea.adapter import SOURCE as EEA

pytestmark = pytest.mark.seed

SEED = load_seed(Path(__file__).resolve().parents[2] / "data" / "seed" / "models.yaml")


def _model(make: str, name: str, sid: str = "eea") -> str | None:
    src = (
        EEA if sid == "eea" else Source(id=sid, name=sid, url=EEA.url, licence="x", attribution="x")
    )
    rec = SourceRecord(
        source=src,
        record_key=f"t:{make}|{name}",
        kind="registration_count",
        make=make,
        model=name,
        retrieved_at=date(2026, 11, 18),
        confidence="high",
    )
    m, _, _, _ = find_record_model(SEED, match_view(rec), True)
    return m.id if m else None


@pytest.mark.parametrize(
    ("make", "name", "expected"),
    [
        # People carriers (Menno's scope, 2026-11-18)
        ("MERCEDES-BENZ", "EQV", "mercedes-eqv"),
        ("MERCEDES-BENZ", "EVITO TOURER", "mercedes-evito-tourer"),
        ("MERCEDES-BENZ", "ECITAN TOURER/EQT", "mercedes-eqt"),
        ("MERCEDES-BENZ", "EQT", "mercedes-eqt"),
        ("CITROEN", "E-BERLINGO", "citroen-e-berlingo"),
        ("CITROEN", "JUMPY SPACETOURER", "citroen-e-spacetourer"),
        ("PEUGEOT", "E-RIFTER", "peugeot-e-rifter"),
        ("PEUGEOT", "EXPERT TRAVELLER", "peugeot-e-traveller"),
        ("OPEL", "COMBO-E LIFE", "opel-combo-e-life"),
        ("OPEL", "VIVARO ZAFIRA LIFE", "opel-zafira-e-life"),
        ("TOYOTA", "PROACE", "toyota-proace-verso"),
        ("TOYOTA", "PROACE CITY VERSO ELECTRIC", "toyota-proace-city-verso"),
        ("FIAT", "E-DOBLO", "fiat-e-doblo"),
        ("FIAT", "ULYSSE", "fiat-e-ulysse"),
        ("NISSAN", "NISSAN E-NV200", "nissan-e-nv200"),
        ("RENAULT", "KANGOO E-TECH ELECTRIC", "renault-kangoo-e-tech"),
        ("FORD", "TOURNEO CUSTOM", "ford-e-tourneo-custom"),
        ("FORD", "TOURNEO COURIER", "ford-e-tourneo-courier"),
        ("KIA", "PV5", "kia-pv5-passenger"),
        ("NISSAN", "TOWNSTAR", "nissan-townstar-ev"),
        # Gems
        ("SEAT", "MII", "seat-mii-electric"),
        ("MAXUS", "MAXUS EUNIQ 6", "maxus-euniq-6"),
        ("MAXUS", "MAXUS EUNIQ 5", "maxus-euniq-5"),
        ("DONGFENG", "BOX", "dongfeng-box"),
        ("KG MOBILITY", "TORRES EVX", "ssangyong-torres-evx"),
        ("SUZUKI", "E VITARA", "suzuki-e-vitara"),
        ("LUCID MOTORS", "AIR", "lucid-air"),
        ("DS AUTOMOBILES", "N 8", "ds-n8"),
        ("DS AUTOMOBILES", "DS3 CROSSBACK", "ds-3-e-tense"),
        ("VEPB", "BLUECAR", "bluecar-bluecar"),
        ("CADILLAC", "LYRIQ", "cadillac-lyriq"),
        ("MASERATI", "GRECALE FOLGORE", "maserati-grecale-folgore"),
        ("EGO", "EGO LIFE FIRST EDITION", "ego-life"),
        ("E.GO", "E.GO LIFE FIRST EDITION", "ego-life"),
        ("MIA", "MIA", "mia-mia"),
        ("THINK", "TH!NK CITY", "think-city"),
        ("ROLLS-ROYCE", "SPECTRE", "rolls-royce-spectre"),
        ("VINFAST", "VF8", "vinfast-vf8"),
        ("TOGG", "T10X", "togg-t10x"),
        # Not ours: hybrids misfiled as electric, cargo vans
        ("TOYOTA", "PRIUS", None),
        ("TOYOTA", "AURIS HYBRID", None),
        ("RENAULT", "KANGOO VAN E-TECH ELECTRIC", None),
    ],
)
def test_eea_names_place_on_the_new_models(make: str, name: str, expected: str | None) -> None:
    assert _model(make, name) == expected


def test_seat_born_still_goes_to_cupra_with_seat_in_the_seed() -> None:
    assert SEED.make_id_for("SEAT") == "seat"
    assert _model("SEAT", "BORN", "kba-fz10") == "cupra-born"
