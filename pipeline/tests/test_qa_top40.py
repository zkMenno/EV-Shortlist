"""Top-40 used models: ranking from staged counts, coverage levels, Wikidata year check."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from ev_pipeline.match.seed import load_seed, parse_seed
from ev_pipeline.qa import top40
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.schema_models import FactField, Source

DAY = date(2026, 11, 15)
REPO = Path(__file__).parents[2]
RDW = Source(id="rdw", name="RDW", licence="CC0-1.0", attribution="RDW")
DFT = Source(id="dft-veh", name="DfT", licence="OGL-UK-3.0", attribution="DfT")
KBA = Source(id="kba-fz10", name="KBA", licence="dl-de/by-2-0", attribution="KBA")
WD = Source(id="wikidata", name="Wikidata", licence="CC0-1.0", attribution="Wikidata")

SEED = parse_seed(
    {
        "makes": [
            {
                "id": "tesla",
                "name": "Tesla",
                "models": [
                    {
                        "id": "tesla-model-3",
                        "name": "Model 3",
                        "generations": [
                            {"id": "tesla-model-3-gen1", "years": [2019, 2023]},
                            {"id": "tesla-model-3-highland", "years": [2024, None]},
                        ],
                    }
                ],
            },
            {"id": "bmw", "name": "BMW", "models": []},
        ]
    }
)


def count(src: Source, make: str, model: str, n: int, year: int | None = None, **kw):
    country = {"rdw": "NL", "dft-veh": "UK", "kba-fz10": "DE"}[src.id.root]
    key = kw.pop("key", f"{src.id.root}:{make}|{model}|{year}")
    return SourceRecord(
        source=src,
        record_key=key,
        kind="registration_count",
        make=make,
        model=model,
        year=year,
        country=country,
        specs={FactField.registered_count: SpecValue(value=n, unit="count")},
        retrieved_at=DAY,
        confidence="high",
        **kw,
    )


def records() -> list[SourceRecord]:
    return [
        count(RDW, "TESLA", "MODEL 3", 600, 2019),
        count(RDW, "TESLA", "MODEL 3", 9999, 2017),  # outside the used window
        count(RDW, "TESLA", "MODEL 3", 8888, 2025),  # outside the used window
        count(RDW, "BMW", "IX1 XDRIVE30", 300, 2023),
        count(RDW, "BMW", "IX3", 100, 2021),
        count(DFT, "TESLA", "TESLA MODEL 3", 500, variant_name="MODEL 3 LONG RANGE",
              key="VEH0120_UK:2026 Q2:Licensed:TESLA|MODEL 3|LR"),
        count(DFT, "BMW", "BMW IX1", 500, variant_name="IX1 XDRIVE 30 M SPORT",
              key="VEH0120_UK:2026 Q2:Licensed:BMW|IX1|X30"),
        count(KBA, "BMW", "X1", 50000, 2025, key="FZ10 YTD 2025-01..12 BMW|X1"),
    ]  # fmt: skip


def test_window_is_2018_to_2024() -> None:
    assert (top40.USED_FIRST_YEAR, top40.USED_LAST_YEAR) == (2018, 2024)


def test_rank_uses_used_fleets_only() -> None:
    r = top40.rank(records(), SEED, top_n=3)
    by_id = {m["model_id"]: m for m in r["models"]}
    m3, ix1 = by_id["tesla-model-3"], by_id["bmw-ix1"]
    # NL total 1000 (600+300+100), UK total 1000: Model 3 = mean(60 %, 50 %) = 55 %.
    assert m3["score_pct"] == pytest.approx(55.0)
    assert ix1["score_pct"] == pytest.approx(40.0)  # mean(30 %, 50 %); KBA never scored
    assert [m["model_id"] for m in r["models"]] == ["tesla-model-3", "bmw-ix1", "bmw-ix3"]
    assert m3["in_seed"] and not ix1["in_seed"]
    nl = m3["counts"]["NL"][0]
    assert nl["count"] == 600 and nl["used_in_rank"] and "2018-2024" in nl["period"]
    de = ix1["counts"]["DE"][0]
    assert (de["source"], de["count"], de["used_in_rank"]) == ("kba-fz10", 50000, False)
    totals = {(t["country"], t["source"]): t["cars"] for t in r["totals"]}
    assert totals[("NL", "rdw")] == 1000  # 2017 and 2025 cars left out


def test_kba_series_rule_and_generic_keys() -> None:
    rec = count(KBA, "BMW", "5ER", 10, 2025)
    assert top40.place(SEED, rec).model_id == "bmw-i5"
    assert top40._generic_model_key(["id", "7", "pro"]) == "id7"
    assert top40._generic_model_key(["mx", "30"]) == "mx30"
    assert top40._generic_model_key(["eqb", "250"]) == "eqb"
    assert top40._generic_model_key(["ioniq", "9"]) == "ioniq9"
    assert top40._generic_model_key(["model", "x"]) == "modelx"
    assert top40._model_tokens("mg", "MG", "MG5 ELECTRIC") == ["5", "electric"]
    assert top40._model_tokens("polestar", "POLESTAR", "POLESTAR 4 PLUS") == ["4", "plus"]


def test_row_and_model_levels() -> None:
    def row(**prov):
        return {"wltp_range_km": 400, "provenance": {"wltp_range_km": prov}}

    assert top40.row_level(row(source_ids=["openev", "rdw"], agreeing_sources=2),
                           "wltp_range_km") == "two_plus"  # fmt: skip
    assert top40.row_level(row(source_ids=["openev"]), "wltp_range_km") == "one"
    assert top40.row_level(row(source_ids=["seed-manual"]), "wltp_range_km") == "estimate"
    assert top40.row_level(row(source_ids=["x"], estimate=True), "wltp_range_km") == "estimate"
    assert top40.row_level({"wltp_range_km": None}, "wltp_range_km") == "none"
    priced = {"price_new": {"NL": {"amount": 1}}, "provenance": {"price_new.NL": {
        "source_ids": ["rdw"]}}}  # fmt: skip
    assert top40.row_level(priced, "price_new.NL") == "one"
    assert top40.row_level(priced, "price_new.DE") == "none"
    assert top40.model_level(["two_plus", "two_plus", "none"]) == "two_plus"
    assert top40.model_level(["two_plus", "one", "none"]) == "one"
    assert top40.model_level(["estimate", "none"]) == "none"
    assert top40.model_level([]) == "none"


def wd(model_id: str, boundary: str, year: int) -> SourceRecord:
    return SourceRecord(
        source=WD,
        record_key=f"wikidata:{model_id}/Q1#{boundary}:P571",
        kind="corroboration",
        make="Tesla",
        model="Model 3",
        year=year,
        retrieved_at=DAY,
        confidence="low",
    )


GENS = [
    {"id": "g1", "model_id": "tesla-model-3", "year_start": 2019, "year_end": 2023},
    {"id": "g2", "model_id": "tesla-model-3", "year_start": 2024, "year_end": None},
]


def test_generation_years_check() -> None:
    ok = top40.generation_years_check(
        "tesla-model-3", GENS, [wd("tesla-model-3", "production_start", 2018)]
    )
    assert ok["level"] == "two_plus"  # within one year of 2019
    bad = top40.generation_years_check(
        "tesla-model-3", GENS, [wd("tesla-model-3", "production_end", 2020)]
    )
    assert bad["level"] == "one" and bad["checks"][0]["agrees"] is False
    assert top40.generation_years_check("tesla-model-3", GENS, [])["level"] == "none"
    none = top40.generation_years_check("bmw-ix1", GENS, [wd("bmw-ix1", "production_start", 2022)])
    assert none["level"] == "none" and none["checks"][0]["agrees"] is None


def test_coverage_counts_models_and_registrations() -> None:
    top = top40.rank(records(), SEED, top_n=2)
    catalogue = {
        "release": 9,
        "generations": GENS,
        "rows": [
            {
                "model_id": "tesla-model-3",
                "ac_kw": 11,
                "provenance": {"ac_kw": {"source_ids": ["openev", "kilowatt-openev"],
                                         "agreeing_sources": 2}},
            }
        ],
    }  # fmt: skip
    cov = top40.coverage(top, catalogue, [wd("tesla-model-3", "production_start", 2019)])
    assert cov["models"] == 2
    assert cov["by_field"]["ac_kw"]["two_plus"] == 1 and cov["by_field"]["ac_kw"]["none"] == 1
    assert cov["by_field"]["price_used"]["none"] == 2
    assert cov["by_field"]["registrations.NL"]["one"] == 2
    assert cov["by_field"]["registrations.DE"]["one"] == 1  # the iX1 has a KBA count
    assert cov["by_field"]["generation_years"]["two_plus"] == 1
    assert "| AC kW | 1 | 0 | 0 | 1 | 50 % |" in top40.coverage_md(cov)


def test_top40_section_skips_without_list(tmp_path: Path) -> None:
    assert top40.top40_section({"rows": []}, tmp_path)["status"] == "skipped"


@pytest.mark.seed
def test_committed_top40_yaml_is_consistent() -> None:
    path = REPO / "data" / "seed" / "top40.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    seed = load_seed(REPO / "data" / "seed" / "models.yaml")
    models = doc["models"]
    assert [m["rank"] for m in models] == list(range(1, len(models) + 1))
    assert len(models) == top40.TOP_N
    assert len({m["model_id"] for m in models}) == len(models)
    assert doc["method"]["used_window"]["first_admission_years"] == [2018, 2024]
    for m in models:
        assert m["in_seed"] == (m["model_id"] in seed.models), m["model_id"]
        assert m["counts"], m["model_id"]
        for entries in m["counts"].values():
            for e in entries:
                assert e["source"] in top40.COUNT_SOURCES and e["period"] and e["count"] > 0
    assert doc["summary"]["not_in_seed"] == sum(1 for m in models if not m["in_seed"])
