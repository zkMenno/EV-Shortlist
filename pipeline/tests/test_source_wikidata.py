"""Wikidata adapter on recorded SPARQL responses (tests/fixtures/wikidata). No network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from ev_pipeline import net
from ev_pipeline.match.matcher import match_records
from ev_pipeline.match.seed import load_seed
from ev_pipeline.schema_models import Confidence
from ev_pipeline.sources.wikidata import adapter

FIXTURE = Path(__file__).parent / "fixtures" / "wikidata"
REAL_SEED = Path(__file__).parents[2] / "data" / "seed" / "models.yaml"
DAY = date(2026, 11, 15)


def _bindings(name: str) -> list[dict]:
    return json.loads((FIXTURE / name).read_text())["results"]["bindings"]


def test_fixture_is_small_recorded_sparql() -> None:
    for name in (adapter.SEARCH_FILE, adapter.DETAILS_FILE):
        assert 0 < len(_bindings(name)) <= 100, name
    meta = json.loads((FIXTURE / "_fetch.json").read_text())
    assert meta["user_agent"] == adapter.USER_AGENT
    assert adapter.REPO_URL in adapter.USER_AGENT


def test_normalise_emits_corroboration_only() -> None:
    records = adapter.normalise(FIXTURE, DAY)
    assert records, "fixture holds production years"
    for r in records:
        assert r.kind == "corroboration"
        assert r.specs == {}  # never a spec value
        assert r.source.licence == "CC0-1.0" and r.source.attribution
        assert r.confidence == Confidence.low
        assert r.retrieved_at == DAY
        assert r.record_key.startswith("wikidata:") and "#production_" in r.record_key
        assert 1990 <= (r.year or 0) <= 2100
    zoe = {
        r.record_key: r.year for r in records if r.record_key.startswith("wikidata:renault-zoe/")
    }
    assert zoe == {
        "wikidata:renault-zoe/Q1516380#production_end:P2669": 2024,
        "wikidata:renault-zoe/Q1516380#production_start:P729": 2013,
    }


def test_items_filters_chain_and_children() -> None:
    its = adapter.items(FIXTURE)
    labels = {(i["model_id"], i["label"]) for i in its}
    # Model Y "follows" Model 3 in Wikidata: a neighbour, not a generation of the Model Y.
    assert ("tesla-model-y", "Tesla Model 3") not in labels
    assert ("nissan-leaf", "Nissan Leaf (first generation)") in labels
    # Children must be car models: motors and features are dropped by the query.
    assert not any("one-pedal" in lbl or "APP550" in lbl for _, lbl in labels)


def test_body_from_known_classes_only() -> None:
    bodies = {i["model_id"]: i["body"] for i in adapter.items(FIXTURE) if i["rel"] == "self"}
    assert bodies["tesla-model-3"] == {"sedan"}
    assert bodies["bmw-ix"] == {"suv", "crossover"}  # two styles: normalise sets no body
    recs = [r for r in adapter.normalise(FIXTURE, DAY) if "/Q86663388#" in r.record_key]
    assert recs and all(r.body is None for r in recs)


def test_pick_models_prefers_electric_then_exact_label() -> None:
    targets = [
        {"model_id": "a", "search": "Opel Corsa-e"},
        {"model_id": "b", "search": "Audi Q4 e-tron"},
        {"model_id": "c", "search": "Nothing"},
    ]

    def hit(search: str, qid: str, label: str, ord_: int, electric: bool) -> dict:
        return {
            "search": {"value": search},
            "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
            "itemLabel": {"value": label},
            "ord": {"value": str(ord_)},
            "electric": {"value": "true" if electric else "false"},
        }

    rows = [
        hit("Opel Corsa-e", "Q1", "Opel Corsa E", 0, False),  # petrol generation "E"
        hit("Opel Corsa-e", "Q2", "Opel Corsa Electric", 1, True),
        hit("Audi Q4 e-tron", "Q3", "Audi Q4 e-tron", 0, False),  # no electric class
        hit("Nothing", "Q4", "Something else", 0, False),
    ]
    picked = adapter.pick_models(targets, {"results": {"bindings": rows}})
    assert picked["a"]["qid"] == "Q2"
    assert picked["b"]["qid"] == "Q3"
    assert "c" not in picked


def test_targets_use_seed_names_and_overrides() -> None:
    top = {
        "models": [
            {"model_id": "tesla-model-3", "name": "Tesla Model 3"},
            {"model_id": "polestar-2", "name": "Polestar Polestar 2"},
            {"model_id": "volvo-ex30", "name": "Volvo EX30"},
        ]
    }
    seed = {
        "makes": [
            {"name": "Tesla", "models": [{"id": "tesla-model-3", "name": "Model 3"}]},
            {"name": "Polestar", "models": [{"id": "polestar-2", "name": "Polestar 2"}]},
        ]
    }
    t = {x["model_id"]: x for x in adapter.targets_from_top40(top, seed)}
    assert t["tesla-model-3"]["search"] == "Tesla Model 3"
    assert (t["tesla-model-3"]["make"], t["tesla-model-3"]["model"]) == ("Tesla", "Model 3")
    assert t["polestar-2"]["search"] == "Polestar 2"
    assert t["volvo-ex30"]["model"] == "EX30"  # not in seed: make stripped from the name


def test_queries_are_bounded_and_literal_safe() -> None:
    q = adapter.search_query(['Evil" } DROP', "Tesla Model 3"])
    assert '"Evil\\" } DROP"' in q
    d = adapter.details_query(["Q1", "Q2"])
    assert "wd:Q1 wd:Q2" in d and "P2669" in d and "P571" in d


def test_fetch_with_mock_transport(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    search = json.loads((FIXTURE / adapter.SEARCH_FILE).read_text())
    details = json.loads((FIXTURE / adapter.DETAILS_FILE).read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        q = parse_qs(request.content.decode())["query"][0]
        return httpx.Response(200, json=search if "mwapi" in q else details)

    targets = json.loads((FIXTURE / adapter.TARGETS_FILE).read_text())["targets"]
    client = net.safe_client(
        "wikidata",
        transport=httpx.MockTransport(handler),
        hosts=["query.wikidata.org", "www.wikidata.org"],
    )
    rows = adapter.fetch(client, tmp_path, targets, sleep_s=0)
    assert rows == len(details["results"]["bindings"])
    assert len(seen) == 2
    for r in seen:
        assert r.method == "POST" and r.url.host == "query.wikidata.org"
        assert r.headers["User-Agent"] == adapter.USER_AGENT
    meta = json.loads((tmp_path / "_fetch.json").read_text())
    assert meta["models_found"] == len(
        json.loads((tmp_path / "targets.json").read_text())["picked"]
    )
    assert len(adapter.normalise(tmp_path, DAY)) == len(adapter.normalise(FIXTURE, DAY))


def test_fetch_cmd_reports_http_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EV_DATA_DIR", str(tmp_path))
    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "top40.yaml").write_text("models: [{model_id: x-y, name: X Y}]\n")
    (tmp_path / "seed" / "models.yaml").write_text("makes: []\n")
    client = net.safe_client(
        "wikidata",
        transport=httpx.MockTransport(lambda r: httpx.Response(429)),
        hosts=["query.wikidata.org"],
    )
    assert adapter.fetch_cmd(client) == 1


@pytest.mark.seed
def test_matcher_never_turns_wikidata_into_facts() -> None:
    records = adapter.normalise(FIXTURE, DAY)
    result = match_records(records, load_seed(REAL_SEED), eea_corroboration=True)
    assert result.corroboration_facts == []
    # T-059: wikidata years go to `year_records` (generation-years check), never to facts.
    assert len(result.year_records) == len(records)
    assert result.spec_facts == [] and result.count_facts == []
    assert not result.variants
