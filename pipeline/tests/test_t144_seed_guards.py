"""T-144 (catalogue batch, 2026-11-18): seed guards from the T-136 reviews (#129, #142).

Real register names, through `find_record_model` (the lookup match_records uses):
- BYD Seal: 'DM' / 'DM-i' names are plug-in hybrids, never the Seal.
- Zafira-e Life: register names with ZAFIRA LIFE / ZAFIRA-E / VIVARO, or the whole name
  'ZAFIRA', but not any name that only starts with ZAFIRA (RDW 'ZAFIRA TOURER', 2012).
- Abarth 500e: its own model; 'Abarth 500e' is no longer a Fiat 500e alias.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import find_record_model, match_view
from ev_pipeline.match.seed import load_seed
from ev_pipeline.records import SourceRecord, SpecValue

pytestmark = pytest.mark.seed

REAL_SEED = Path(__file__).parents[2] / "data" / "seed" / "models.yaml"

RDW = {"id": "rdw", "name": "RDW", "licence": "CC0-1.0"}
EEA = {"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"}


@pytest.fixture(scope="module")
def real():
    return load_seed(REAL_SEED)


def _count(make: str, model: str, source: dict) -> SourceRecord:
    return SourceRecord(
        source=source,
        record_key=f"{source['id']}:{make}|{model}",
        kind="registration_count",
        make=make,
        model=model,
        year=2024,
        country="NL",
        specs={"registered_count": SpecValue(value=1, unit="count")},
        retrieved_at=date(2026, 11, 18),
        confidence="medium",
    )


@pytest.mark.parametrize(
    ("make", "model", "source", "expected"),
    [
        # BYD Seal: the electric Seal still matches; DM / DM-i names never land on it.
        ("BYD", "SEAL", RDW, "byd-seal"),
        ("BYD", "BYD SEAL", EEA, "byd-seal"),
        ("BYD", "BYD SEAL U DM", RDW, None),  # RDW 2025, a PHEV under a BEV filter
        ("BYD", "BYD SEAL U DM-I", EEA, None),  # EEA, 19 cars filed as electric
        ("BYD", "SEAL U", RDW, "byd-seal-u"),
        # Zafira-e Life: passenger van names, not any ZAFIRA.
        ("OPEL", "ZAFIRA TOURER", RDW, None),  # RDW 2012 conversion
        ("OPEL", "ZAFIRA", EEA, "opel-zafira-e-life"),  # EEA DE 2023-2025 whole name
        ("OPEL", "ZAFIRA LIFE", EEA, "opel-zafira-e-life"),
        ("OPEL", "ZAFIRA-E LIFE", EEA, "opel-zafira-e-life"),
        ("OPEL", "ZAFIRA-E LIFE M BUSINESS EDITION BEV 330 100KW / 1", EEA, "opel-zafira-e-life"),
        ("OPEL", "ZAFIRA LIFE ELECTRIC L BUSINESS EDITION BEV 230 10", EEA, "opel-zafira-e-life"),
        ("OPEL", "VIVARO ZAFIRA LIFE", EEA, "opel-zafira-e-life"),
        # Abarth 500e is its own model.
        ("FIAT", "ABARTH 500E", EEA, "abarth-500e"),  # EEA files a few under make FIAT
        ("FIAT", "500", EEA, "fiat-500e"),
        ("ABARTH", "500", EEA, "abarth-500e"),
    ],
)
def test_seed_guards(real, make, model, source, expected) -> None:
    found, why, _note, _known = find_record_model(
        real, match_view(_count(make, model, source)), True
    )
    assert (found.id if found else None) == expected, why


def test_fiat_500e_has_no_abarth_alias(real) -> None:
    fiat = real.models["fiat-500e"]
    assert not any("abarth" in a.lower() for a in fiat.aliases)
