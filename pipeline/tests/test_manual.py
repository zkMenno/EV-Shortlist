"""P7 manual facts: file format, validation rules, `ev manual check`, licence gate."""

from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from ev_pipeline.commands.manual import check
from ev_pipeline.manual.facts import (
    MANUAL_SOURCE_ID,
    expected_unit,
    load_manual_dir,
    parse_manual_file,
    url_matches,
)
from ev_pipeline.release.build import build_release
from ev_pipeline.release.gate import load_registry

FIX = Path(__file__).parent / "fixtures" / "manual"
REPO_DATA = Path(__file__).resolve().parents[2] / "data"
TODAY = date(2026, 11, 15)
NOW = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)
RELEASE_FIX = Path(__file__).parent / "fixtures" / "release"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Same layout as test_release.data_dir: the release fixtures in a scratch data dir."""
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    shutil.copytree(RELEASE_FIX / "staging", d / "staging")
    shutil.copytree(RELEASE_FIX / "taxonomy", d / "taxonomy")
    for n in ("models", "variants", "platforms", "battery_packs", "variant_links"):
        shutil.copy(RELEASE_FIX / f"{n}.yaml", d / "seed" / f"{n}.yaml")
    for n in ("sources", "field_sources"):
        shutil.copy(RELEASE_FIX / f"{n}.yaml", d / f"{n}.yaml")
    return d


def _with_manual(d: Path, *topics: str) -> Path:
    for t in topics:
        shutil.copytree(FIX / t, d / "manual" / t)
    return d


def _set_manual_registry(d: Path, entry: dict | None) -> None:
    p = d / "sources.yaml"
    reg = yaml.safe_load(p.read_text())
    reg["sources"] = [s for s in reg["sources"] if s["id"] != MANUAL_SOURCE_ID]
    if entry is not None:
        reg["sources"].append(entry)
    p.write_text(yaml.safe_dump(reg))


BLOCKED = {
    "id": "manual",
    "name": "Manual entries",
    "licence": "none (individual facts cited by URL and date)",
    "access": "manual",
    "status": "blocked",
}


def _write(tmp: Path, facts: list[dict], **file_keys) -> Path:
    p = tmp / "t.yaml"
    p.write_text(yaml.safe_dump({"schema": "manual-facts/v1", **file_keys, "facts": facts}))
    return p


GOOD = {
    "variant_id": "tesla-model-3-gen1-lr",
    "field": "ac_kw",
    "value": 11,
    "unit": "kW",
    "source_url": "https://example.org/x",
    "retrieved": "2026-11-01",
    "locator": "p. 2",
    "entered_by": "test",
    "confidence": "low",
}


def test_valid_file_parses_to_schema_facts() -> None:
    facts, issues, fixture = parse_manual_file(
        FIX / "warranty" / "fixture-warranty.yaml", "data/manual/warranty/f.yaml", "warranty", TODAY
    )
    assert issues == [] and not fixture
    assert len(facts) == 2
    f = facts[0].fact
    assert (
        f.source.id.root == "manual" and f.source.url == "https://example.org/fixture/warranty.pdf"
    )
    assert f.retrieved_at == date(2026, 11, 1) and f.unit == "km" and f.claim is True
    assert f.id == "manual:warranty/fixture-warranty:tesla-model-3-gen1-lr:warranty_km"
    assert facts[1].fact.subject_type.value == "generation" and facts[1].fact.claim is None


def test_broken_file_lists_every_rule() -> None:
    _, issues, _ = parse_manual_file(
        FIX / "broken" / "fixture-broken.yaml", "data/manual/broken/b.yaml", "broken", TODAY
    )
    text = "\n".join(i.message for i in issues)
    for needle in (
        "source_url is required",
        "entered_by is required",
        "unit 'mi' does not match wltp_range_km (use 'km')",
        "retrieved date is required",
        "give a quote or a page locator",
        "give exactly one of variant_id or generation_id",
        "unknown field 'colour'",
        "price_new needs a country",
        "is in the future",
        "confidence must be high, medium or low",
    ):
        assert needle in text, needle
    assert {i.index for i in issues} == {0, 1, 2, 3, 4}


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"value": 99}, "out of range"),
        ({"value": "eleven"}, "needs a number"),
        ({"value": True}, "needs a number"),
        ({"source_url": "not a url"}, "source_url"),
        ({"retrieved": "15/11/2026"}, "ISO date"),
        ({"field": "registered_count", "unit": "count"}, "registered_count"),
        ({"field": "heat_pump", "unit": "enum", "value": "maybe"}, "not an allowed value"),
        ({"field": "chemistry_id", "unit": "id", "value": "NMC 811"}, "taxonomy id"),
        ({"country": "XX"}, "country"),
        ({"claim": "yes"}, "claim must be"),
        ({"colour": "red"}, "unknown key 'colour'"),
        ({"variant_id": "Not An Id"}, "schema Fact subject_id"),
    ],
)
def test_single_rule(tmp_path: Path, change: dict, needle: str) -> None:
    p = _write(tmp_path, [{**GOOD, **change}])
    facts, issues, _ = parse_manual_file(p, "data/manual/x/t.yaml", "x", TODAY)
    assert facts == [] and any(needle in i.message for i in issues), [i.message for i in issues]


def test_price_curve_enum_and_file_level_entered_by(tmp_path: Path) -> None:
    rows = [
        {
            **GOOD,
            "field": "price_new",
            "unit": "EUR",
            "value": 41990,
            "country": "NL",
            "year": 2024,
        },
        {
            **GOOD,
            "field": "dc_curve",
            "unit": "kW",
            "value": {"points": [[10, 150], [80, 50]], "status": "measured"},
        },
        {**GOOD, "field": "heat_pump", "unit": "enum", "value": "option"},
    ]
    for r in rows:
        r.pop("entered_by")
    p = _write(tmp_path, rows, entered_by="menno")
    facts, issues, _ = parse_manual_file(p, "data/manual/x/t.yaml", "x", TODAY)
    assert issues == [], [i.message for i in issues]
    assert [m.entered_by for m in facts] == ["menno"] * 3
    assert facts[0].fact.country.value == "NL" and facts[0].record_key.endswith(":NL:2024")
    assert facts[0].year == 2024


def test_expected_units_cover_every_field_but_price() -> None:
    from ev_pipeline.schema_models import FactField

    missing = [f.value for f in FactField if expected_unit(f.value) is None]
    assert missing == ["price_new"]


def test_duplicates_and_topic_folder(tmp_path: Path) -> None:
    d = tmp_path / "data"
    for name in ("a", "b"):
        (d / "manual" / "t").mkdir(parents=True, exist_ok=True)
        _write(tmp_path, [GOOD]).rename(d / "manual" / "t" / f"{name}.yaml")
    _write(tmp_path, [GOOD]).rename(d / "manual" / "loose.yaml")
    load = load_manual_dir(d, TODAY)
    assert len(load.facts) == 1
    msgs = [i.message for i in load.errors]
    assert any("duplicate of t/a:" in m for m in msgs)
    assert any("topic folder" in m for m in msgs)


def test_example_folder_is_checked_but_never_released(tmp_path: Path) -> None:
    d = tmp_path / "data"
    shutil.copytree(REPO_DATA / "manual" / "_example", d / "manual" / "_example")
    assert load_manual_dir(d, TODAY).facts == []
    full = load_manual_dir(d, TODAY, for_release=False)
    assert len(full.facts) == 1 and full.errors == []
    assert full.fixture_files == {"data/manual/_example/example.yaml"}


def test_repo_example_and_registry_entry() -> None:
    """The committed example passes `ev manual check`; `manual` is releasable (Decision 068,
    was blocked under Q-008)."""
    # Real repo data, so check against the real date: a fixed TODAY fails every newer fact.
    code, lines = check(REPO_DATA, date.today())
    assert code == 0, lines
    assert lines[-1].endswith("Release status of source `manual`: releasable")
    reg = load_registry(REPO_DATA / "sources.yaml")
    assert reg.reason_blocked("manual") is None


def test_check_command_exit_codes(tmp_path: Path, capsys) -> None:
    from ev_pipeline.cli import main

    d = tmp_path / "data"
    shutil.copytree(FIX / "broken", d / "manual" / "broken")
    assert main(["manual", "check", "--data-dir", str(d)]) == 1
    out = capsys.readouterr().out
    assert "facts[1]: error: unit 'mi'" in out
    shutil.rmtree(d / "manual" / "broken")
    shutil.copytree(FIX / "warranty", d / "manual" / "warranty")
    assert main(["manual", "check", "--data-dir", str(d)]) == 0


def test_release_gate_keeps_manual_facts_internal(data_dir: Path) -> None:
    d = _with_manual(data_dir, "warranty")
    _set_manual_registry(d, BLOCKED)
    res = build_release(d, now=NOW)
    assert not any(f["source"]["id"] == "manual" for f in res.facts)
    assert "manual" not in {s["id"] for s in res.catalogue["sources"]}
    assert res.gated["manual"] == {"reason": "status blocked", "records": 2}
    assert any(i["path"] == "data/manual/warranty/fixture-warranty.yaml" for i in res.inputs)

    _set_manual_registry(d, None)  # not listed at all: blocked as well (fail closed)
    res = build_release(d, now=NOW)
    assert not any(f["source"]["id"] == "manual" for f in res.facts)
    assert res.gated["manual"]["reason"] == "not in data/sources.yaml"


def test_release_uses_manual_facts_once_releasable(data_dir: Path) -> None:
    d = _with_manual(data_dir, "warranty")
    _set_manual_registry(d, {**BLOCKED, "status": "active", "licence": "CC-BY-4.0"})
    res = build_release(d, now=NOW)
    manual = [f for f in res.facts if f["source"]["id"] == "manual"]
    by_field = {f["field"]: f for f in manual}
    assert by_field["warranty_km"]["subject_id"] == "tesla-model-3-gen1-lr"
    # A generation fact lands on every variant of that generation in the release.
    leaf = [f for f in manual if f["field"] == "warranty_years"]
    vids = {
        r["variant_id"] for r in res.catalogue["rows"] if r["generation_id"] == "nissan-leaf-ze0"
    }
    assert {f["subject_id"] for f in leaf} == vids and vids
    assert all(f["id"].endswith("@" + f["subject_id"]) for f in leaf)


def test_release_lists_bad_manual_entries(data_dir: Path) -> None:
    d = _with_manual(data_dir, "broken")
    _set_manual_registry(d, {**BLOCKED, "status": "active", "licence": "CC-BY-4.0"})
    res = build_release(d, now=NOW)
    stages = [p for p in res.problems if p.stage == "manual"]
    assert stages and all(p.source_id == "manual" for p in stages)
    assert not any(f["source"]["id"] == "manual" for f in res.facts)


def test_price_year_is_parsed_and_kept_apart_per_year() -> None:
    p = FIX / "new-prices" / "fixture-new-prices.yaml"
    facts, issues, _ = parse_manual_file(p, "data/manual/new-prices/f.yaml", "new-prices", TODAY)
    assert [(m.fact.country.value, m.year) for m in facts] == [
        ("BE", 2021), ("BE", 2023), ("FR", None)
    ]  # fmt: skip
    assert facts[0].record_key.endswith(":BE:2021") and facts[1].record_key.endswith(":BE:2023")
    # no year: kept, with a warning (not an error) that the estimate cannot use it
    assert [i.warning for i in issues] == [True] and "no `year`" in issues[0].message


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"year": 2021}, "year is only for price_new"),
        ({"field": "price_new", "unit": "EUR", "value": 40000, "country": "NL", "year": "2021"},
         "whole year"),
        ({"field": "price_new", "unit": "EUR", "value": 40000, "country": "NL", "year": 1990},
         "outside 2000"),
    ],
)  # fmt: skip
def test_bad_year(tmp_path: Path, change: dict, needle: str) -> None:
    p = _write(tmp_path, [{**GOOD, **change}])
    facts, issues, _ = parse_manual_file(p, "data/manual/x/t.yaml", "x", TODAY)
    assert facts == [] and any(needle in i.message for i in issues), [i.message for i in issues]


def test_manual_price_year_feeds_the_used_price_lookup(data_dir: Path) -> None:
    """The bug: manual price_new facts had no record year, so used_price.list_prices skipped
    them. Now the year reaches fact_years and the estimate's list-price lookup."""
    d = _with_manual(data_dir, "new-prices")
    _set_manual_registry(d, {**BLOCKED, "status": "active", "licence": "CC-BY-4.0"})
    res = build_release(d, now=NOW)
    years = {
        (f["country"], f["value"]): y
        for f, y in zip(res.facts, res.fact_years, strict=True)
        if f["source"]["id"] == "manual" and f["field"] == "price_new"
    }
    assert years == {("BE", 52990): 2021, ("BE", 49990): 2023, ("FR", 55000): None}
    up = res.used_prices
    assert up is not None
    v = next(v for v in up["variants"] if v["variant_id"] == "tesla-model-3-gen1-lr")
    be = {b["build_year"]: b for b in v["bands"]["BE"]}
    assert (be[2021]["list_price"], be[2021]["list_basis"]) == (53000, "year")
    assert be[2021]["list_source_ids"] == ["manual"]
    assert (be[2023]["list_price"], be[2023]["list_basis"]) == (50000, "year")
    assert be[2022]["list_basis"] == "nearest_year"
    # FR has no year: never used as FR's own list price
    assert all(b.get("list_basis") != "year" for b in v["bands"].get("FR", []))


def test_own_schema_topics_are_left_alone(tmp_path: Path) -> None:
    """data/manual/prices and data/manual/charging have their own loaders (T-081, T-025)."""
    shutil.copytree(REPO_DATA / "manual", tmp_path / "manual")
    shutil.copy(REPO_DATA / "sources.yaml", tmp_path / "sources.yaml")
    (tmp_path / "manual" / "prices").mkdir(exist_ok=True)
    (tmp_path / "manual" / "prices" / "x.yaml").write_text(
        "generation_id: g\ncountry: NL\nrows: []\n"
    )
    # Real date: this copies the repo's manual data, whose facts carry real retrieval dates.
    code, lines = check(tmp_path, date.today())
    assert code == 0, lines


# --- Decision 080: a file may name its own source; a blocked one never ships ---------------

AUTOTIJD = {
    "id": "autotijd",
    "name": "Autotijd.be",
    "access": "manual",
    "licence": "none (all rights reserved; no reuse terms)",
    "status": "blocked",
}
PRICE = {
    "variant_id": "tesla-model-3-gen1-lr",
    "field": "price_new",
    "value": 50000,
    "unit": "EUR",
    "country": "BE",
    "source_url": "https://example.org/price",
    "retrieved": "2026-11-01",
    "quote": "EUR 50.000",
    "entered_by": "test",
    "confidence": "low",
}


def _add_source(d: Path, entry: dict) -> None:
    p = d / "sources.yaml"
    reg = yaml.safe_load(p.read_text())
    reg["sources"] = [s for s in reg["sources"] if s["id"] != entry["id"]] + [entry]
    p.write_text(yaml.safe_dump(reg))


def _write_topic(d: Path, name: str, facts: list[dict], **file_keys) -> None:
    (d / "manual" / "new-prices").mkdir(parents=True, exist_ok=True)
    (d / "manual" / "new-prices" / f"{name}.yaml").write_text(
        yaml.safe_dump({"schema": "manual-facts/v1", **file_keys, "facts": facts})
    )


def test_file_source_must_be_registered(tmp_path: Path) -> None:
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(RELEASE_FIX / "sources.yaml", d / "sources.yaml")
    _write_topic(d, "x", [PRICE], source="no-such-site")
    reg = load_registry(d / "sources.yaml")
    load = load_manual_dir(d, TODAY, reg)
    assert load.facts == []
    assert any("not in data/sources.yaml" in i.message for i in load.errors)
    _write_topic(d, "x", [PRICE], source="Not An Id")
    assert any("sources.yaml id" in i.message for i in load_manual_dir(d, TODAY, reg).errors)


def test_blocked_file_source_never_ships_even_when_manual_is_releasable(data_dir: Path) -> None:
    d = data_dir
    _set_manual_registry(d, {**BLOCKED, "status": "active", "licence": "CC-BY-4.0"})
    _add_source(d, AUTOTIJD)
    held = {**PRICE, "variant_id": "tesla-model-3-gen1-lr", "value": 51111}
    other = {**PRICE, "variant_id": "nissan-leaf-ze0-24kwh", "value": 29999}
    _write_topic(d, "held", [held, other], source="autotijd")
    maker = {**PRICE, "value": 49990, "source_url": "https://maker.example/price"}
    _write_topic(d, "maker", [maker])  # same car + country, source `manual`: not a duplicate
    load = load_manual_dir(d, TODAY, load_registry(d / "sources.yaml"))
    assert load.errors == [] and len(load.facts) == 3
    assert {mf.fact.source.id.root for mf in load.facts} == {"autotijd", "manual"}

    res = build_release(d, now=NOW)
    prices = [f for f in res.facts if f["field"] == "price_new" and f.get("country") == "BE"]
    assert not any(f["source"]["id"] == "autotijd" for f in res.facts)
    assert {f["value"] for f in prices} == {49990}  # only the maker value ships
    assert res.gated["autotijd"] == {"reason": "status blocked", "records": 2}
    assert "autotijd" not in {s["id"] for s in res.catalogue["sources"]}


def test_repo_autotijd_rows_are_held() -> None:
    """Decision 080: every Autotijd row in the repo names the blocked `autotijd` source."""
    reg = load_registry(REPO_DATA / "sources.yaml")
    assert reg.reason_blocked("autotijd") == "status blocked"
    load = load_manual_dir(REPO_DATA, date.today(), reg, for_release=False)
    autotijd_urls = [mf for mf in load.facts if "autotijd.be" in str(mf.fact.source.url)]
    assert autotijd_urls, "expected the T-112 Autotijd rows"
    assert all(mf.fact.source.id.root == "autotijd" for mf in autotijd_urls)
    code, lines = check(REPO_DATA, date.today())
    assert code == 0, lines
    assert any(ln.startswith("Source `autotijd`:") and "internal only" in ln for ln in lines)


# --- Decision 068: single cited maker facts ship; third-party and Autotijd rows never do ---

CITED = {
    "id": "manual",
    "name": "Manual entries",
    "licence": "facts cited, no licence (Decision 068)",
    "access": "manual",
    "status": "active",
    "use": "cited-facts",
    "decision": "068",
    "cited_hosts": ["maker.example"],
}
THIRD = {
    "id": "cited-third-party",
    "name": "Press pages",
    "licence": "none",
    "access": "manual",
    "status": "blocked",
}
MAKER_PRICE = {**PRICE, "value": 49990, "source_url": "https://maker.example/price.pdf"}


def test_cited_facts_ship_without_a_licence_only_with_a_decision() -> None:
    from ev_pipeline.release.gate import parse_registry

    assert parse_registry({"sources": [CITED]}).reason_blocked("manual") is None
    no_decision = {**CITED, "decision": ""}
    assert "no named licence" in parse_registry({"sources": [no_decision]}).reason_blocked("manual")
    held = {**CITED, "status": "blocked"}
    assert parse_registry({"sources": [held]}).reason_blocked("manual") == "status blocked"


def test_cited_fact_must_cite_a_listed_maker_host(tmp_path: Path) -> None:
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(RELEASE_FIX / "sources.yaml", d / "sources.yaml")
    _add_source(d, CITED)
    _add_source(d, THIRD)
    press = {
        **PRICE,
        "variant_id": "nissan-leaf-ze0-24kwh",
        "source_url": "https://press.example/x",
    }
    _write_topic(d, "x", [MAKER_PRICE, press])
    reg = load_registry(d / "sources.yaml")
    load = load_manual_dir(d, TODAY, reg)
    assert [mf.fact.source.url for mf in load.facts] == ["https://maker.example/price.pdf"]
    assert any("'press.example' is not a maker host" in i.message for i in load.errors)
    # Naming the blocked third-party source per fact makes it valid internal evidence.
    _write_topic(d, "x", [MAKER_PRICE, {**press, "source": "cited-third-party"}])
    load = load_manual_dir(d, TODAY, reg)
    assert load.errors == []
    assert {mf.fact.source.id.root for mf in load.facts} == {"manual", "cited-third-party"}
    assert any(str(mf.fact.id).startswith("cited-third-party:") for mf in load.facts)
    # A per-fact source must be registered, like a file source.
    _write_topic(d, "x", [{**press, "source": "no-such-site"}])
    assert any(
        "not in data/sources.yaml" in i.message for i in load_manual_dir(d, TODAY, reg).errors
    )
    # Fixture files are never released, so the host rule does not apply to them.
    _write_topic(d, "x", [press], fixture=True)
    assert load_manual_dir(d, TODAY, reg, for_release=False).errors == []


def test_release_ships_maker_facts_and_holds_third_party_and_autotijd(data_dir: Path) -> None:
    d = data_dir
    _set_manual_registry(d, CITED)
    _add_source(d, THIRD)
    _add_source(d, AUTOTIJD)
    leaf = "nissan-leaf-ze0-24kwh"
    _write_topic(d, "held", [{**PRICE, "value": 51111}], source="autotijd")
    _write_topic(
        d,
        "maker",
        [
            MAKER_PRICE,
            {**PRICE, "variant_id": leaf, "value": 29999, "source_url": "https://press.example/a",
             "source": "cited-third-party"},
        ],
    )  # fmt: skip
    res = build_release(d, now=NOW)
    be = {
        f["subject_id"]: f
        for f in res.facts
        if f["field"] == "price_new" and f.get("country") == "BE"
    }
    assert be["tesla-model-3-gen1-lr"]["value"] == 49990
    assert be["tesla-model-3-gen1-lr"]["source"]["id"] == "manual"
    assert leaf not in be  # the third-party figure never ships
    assert not any(f["source"]["id"] in ("autotijd", "cited-third-party") for f in res.facts)
    assert res.gated["autotijd"]["reason"] == "status blocked"
    assert res.gated["cited-third-party"]["reason"] == "status blocked"
    ids = {s["id"] for s in res.catalogue["sources"]}
    assert "manual" in ids and not ids & {"autotijd", "cited-third-party"}

    # The CC BY open-data bundle still needs a named licence: cited maker facts stay out.
    from ev_pipeline.opendata.bundle import source_allowed

    reg = load_registry(d / "sources.yaml")
    licences = {s["id"]: s.get("licence") or "" for s in res.catalogue["sources"]}
    assert not source_allowed(reg, licences, "manual")


def test_repo_manual_facts_split_as_decision_068_says() -> None:
    """Real data/manual: maker facts are releasable and cite a listed maker host; every
    Autotijd row and every press/dealer/review fact is held."""
    reg = load_registry(REPO_DATA / "sources.yaml")
    load = load_manual_dir(REPO_DATA, date.today(), reg)
    assert load.errors == [], [i.text() for i in load.errors]
    hosts = set(reg.sources["manual"].cited_hosts)
    shipping = [mf for mf in load.facts if reg.releasable(mf.fact.source.id.root)]
    held = [mf for mf in load.facts if not reg.releasable(mf.fact.source.id.root)]
    assert shipping and held
    assert {mf.fact.source.id.root for mf in shipping} == {"manual"}
    assert all(any(url_matches(h, str(mf.fact.source.url)) for h in hosts) for mf in shipping)
    # Hosting services and dealer sites are allowed by path only, never as a whole host.
    whole = {h for h in hosts if "/" not in h}
    assert not whole & {"mb.cision.com", "cdn.uc.assets.prezly.com", "www.louwman.nl"}
    assert not any("autotijd" in str(mf.fact.source.url) for mf in shipping)
    assert {mf.fact.source.id.root for mf in held} <= {"autotijd", "cited-third-party"}
    assert reg.reason_blocked("autotijd") == "status blocked"
    assert reg.reason_blocked("cited-third-party") == "status blocked"
    assert reg.releasable("maker-docs")  # T-163 (Decisions 068 / 087): maker hosts only
    assert reg.cited_url_problem("maker-docs", "https://xr793.com/brochure.pdf") is not None


# --- PR #80 review: a manual fact can't borrow an open source's id; hosts by path ---

RDW = {
    "id": "rdw",
    "name": "RDW Open Data",
    "licence": "CC0-1.0",
    "access": "api",
    "status": "active",
    "hosts": ["opendata.rdw.nl"],
}
PRESS_URL = "https://www.meinauto.de/elektroauto/tesla-model-3"


def test_url_matches_host_and_path_prefix() -> None:
    lw = "www.louwman.nl/uploads/*/Peugeot/prijslijsten/"
    assert url_matches(lw, "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/p.pdf")
    assert not url_matches(lw, "https://www.louwman.nl/occasions/peugeot-e-208")
    assert not url_matches(lw, "https://www.louwman.nl/uploads/2023/Toyota/prijslijsten/t.pdf")
    assert not url_matches(lw, "https://www.louwman.nl/uploads/peugeot/prijslijsten/p.pdf")
    cision = "mb.cision.com/Main/23604/"
    assert url_matches(cision, "https://mb.cision.com/Main/23604/4174345/3536170.pdf")
    assert not url_matches(cision, "https://mb.cision.com/Main/99999/1/2.pdf")
    assert not url_matches(cision, "https://mb.cision.com.evil.example/Main/23604/x.pdf")
    assert url_matches("WWW.Audi-MediaCenter.com", "https://www.audi-mediacenter.com/en/x")
    assert url_matches("*.googleusercontent.com", "https://doc-0.googleusercontent.com/a")
    # Dot segments, plain or percent-encoded, can't step out of an allowed prefix.
    for probe in (
        "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/../../../occasions/x",
        "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/%2e%2e/%2E%2E/x",
        "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/.%2e/x",
        "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/./x",
        "https://www.louwman.nl/uploads/2023/Peugeot/prijslijsten/a%2f..%2fb",
    ):
        assert not url_matches(lw, probe), probe


def test_open_source_on_a_shared_host_is_matched_by_its_own_repo_only(tmp_path: Path) -> None:
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(RELEASE_FIX / "sources.yaml", d / "sources.yaml")
    _add_source(d, CITED)
    repo = "github.com/open-ev-data/open-ev-data-dataset/"
    openev = {"id": "openev", "name": "Open EV Data", "licence": "CDLA-Permissive-2.0",
              "access": "bulk", "status": "active", "hosts": ["github.com"]}  # fmt: skip
    _add_source(d, openev)
    other = {**PRICE, "source": "openev", "source_url": "https://github.com/someone/ev-prices"}
    _write_topic(d, "x", [other])
    reg = load_registry(d / "sources.yaml")
    # Without cite_paths, github.com (a shared host) never vouches for a claim.
    assert any("'openev' is not a hand-entry source" in i.message
               for i in load_manual_dir(d, TODAY, reg).errors)  # fmt: skip
    _add_source(d, {**openev, "cite_paths": [repo]})
    reg = load_registry(d / "sources.yaml")
    load = load_manual_dir(d, TODAY, reg)
    assert load.facts == [] and any("'openev'" in i.message for i in load.errors)
    own = {**other, "source_url": f"https://{repo}blob/main/src/tesla/model_3.json"}
    _write_topic(d, "x", [own])
    assert load_manual_dir(d, TODAY, reg).errors == []
    _write_topic(d, "x", [{**own, "source_url": f"https://{repo}%2e%2e/%2e%2e/someone/x"}])
    assert load_manual_dir(d, TODAY, reg).errors != []


def test_repo_open_sources_on_github_cite_only_their_own_repo() -> None:
    reg = load_registry(REPO_DATA / "sources.yaml")
    for sid, repo in (
        ("openev", "open-ev-data/open-ev-data-dataset"),
        ("kilowatt-openev", "KilowattApp/open-ev-data"),
    ):
        assert f"github.com/{repo}/" in reg.sources[sid].cite_paths
        assert all("/" in p for p in reg.sources[sid].cite_paths), sid


@pytest.mark.parametrize("where", ["fact", "file"])
def test_manual_fact_cannot_name_an_open_source_for_a_third_party_page(
    tmp_path: Path, where: str
) -> None:
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(RELEASE_FIX / "sources.yaml", d / "sources.yaml")
    _add_source(d, CITED)
    _add_source(d, RDW)
    laundered = {**PRICE, "source_url": PRESS_URL}
    if where == "fact":
        _write_topic(d, "x", [{**laundered, "source": "rdw"}])
    else:
        _write_topic(d, "x", [laundered], source="rdw")
    reg = load_registry(d / "sources.yaml")
    load = load_manual_dir(d, TODAY, reg)
    assert load.facts == []
    assert any(
        "'rdw' is not a hand-entry source" in i.message and "www.meinauto.de" in i.message
        for i in load.errors
    ), [i.text() for i in load.errors]
    code, _ = check(d, TODAY)
    assert code != 0
    # The same label on the source's own host is fine (a fact read from the RDW register).
    rdw_url = "https://opendata.rdw.nl/resource/gr7t-qfnb.json?x=1"
    _write_topic(d, "x", [{**PRICE, "source_url": rdw_url, "source": "rdw"}])
    assert load_manual_dir(d, TODAY, reg).errors == []
    # Every `access: manual` source may still be named, whatever the URL host.
    _add_source(d, THIRD)
    _write_topic(d, "x", [{**laundered, "source": "cited-third-party"}])
    assert load_manual_dir(d, TODAY, load_registry(d / "sources.yaml")).errors == []


def test_laundered_fact_never_reaches_release_or_open_data_bundle(data_dir: Path) -> None:
    from ev_pipeline.opendata.bundle import source_allowed

    d = data_dir
    _set_manual_registry(d, CITED)
    _add_source(d, RDW)
    _write_topic(
        d, "x", [MAKER_PRICE, {**PRICE, "variant_id": "nissan-leaf-ze0-24kwh", "value": 27777,
                               "source_url": PRESS_URL, "source": "rdw"}],
    )  # fmt: skip
    res = build_release(d, now=NOW)
    assert not any(f["value"] == 27777 for f in res.facts)
    assert not any("meinauto" in str(f["source"].get("url", "")) for f in res.facts)
    assert any(p.stage == "manual" and "hand-entry source" in p.reason for p in res.problems)
    # `rdw` itself is open (CC0) and in the bundle, which is why the label must not be borrowable.
    reg = load_registry(d / "sources.yaml")
    licences = {s["id"]: s.get("licence") or "" for s in res.catalogue["sources"]}
    assert source_allowed(reg, {**licences, "rdw": "CC0-1.0"}, "rdw")
    rdw_facts = [f for f in res.facts if f["source"]["id"] == "rdw"]
    assert not any(f["value"] == 27777 for f in rdw_facts)


def _years_file(d: Path, facts: list[dict]) -> None:
    base = {
        "field": "heat_pump",
        "source_url": "https://example.org/fixture/heat-pump.pdf",
        "retrieved": "2026-11-01",
        "quote": "heat pump",
        "confidence": "medium",
    }
    p = d / "manual" / "heat-pump" / "fixture-years.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "schema": "manual-facts/v1",
                "entered_by": "test",
                "facts": [{**base, **f} for f in facts],
            }
        )
    )


def test_years_scopes_a_generation_fact_to_variants_fully_inside(data_dir: Path) -> None:
    """WS3 ask (Decision 059): `years: [from, to]` on a generation fact. Fixture
    tesla-model-3-gen1: lr 2019-2023 (straddles 2021), performance 2021."""
    unit = expected_unit("heat_pump")
    _years_file(
        data_dir,
        [
            {
                "generation_id": "tesla-model-3-gen1",
                "value": "standard",
                "unit": unit,
                "years": [2021, None],
            },
            {
                "generation_id": "tesla-model-3-gen1",
                "value": "none",
                "unit": unit,
                "years": [2017, 2020],
            },
            {
                "generation_id": "nissan-leaf-ze0",
                "value": "none",
                "unit": unit,
                "years": [2024, None],
            },
        ],
    )
    _set_manual_registry(data_dir, {**BLOCKED, "status": "active", "licence": "CC-BY-4.0"})
    res = build_release(data_dir, now=NOW)
    hp = {f["subject_id"]: f["value"] for f in res.facts if f["source"]["id"] == "manual"}
    assert hp == {"tesla-model-3-gen1-performance": "standard"}  # lr straddles 2021: neither value
    problems = " | ".join(p.reason for p in res.problems)
    assert "no variant of the generation lies fully inside years 2017-2020" in problems
    assert "fully inside years 2024-" in problems


@pytest.mark.parametrize(
    ("fact", "needle"),
    [
        ({"variant_id": "tesla-model-3-gen1-lr", "years": [2021, None]}, "only for generation"),
        ({"generation_id": "tesla-model-3-gen1", "years": [2021]}, "years must be [from, to]"),
        ({"generation_id": "tesla-model-3-gen1", "years": [2022, 2021]}, "years must be"),
        ({"generation_id": "tesla-model-3-gen1", "years": "2021+"}, "years must be"),
        ({"generation_id": "tesla-model-3-gen1", "years": [1999, None]}, "years must be"),
    ],
)
def test_years_validation(tmp_path: Path, fact: dict, needle: str) -> None:
    d = tmp_path / "data"
    _years_file(d, [{"value": "standard", "unit": expected_unit("heat_pump"), **fact}])
    load = load_manual_dir(d, TODAY, load_registry(d / "sources.yaml"), for_release=False)
    assert any(needle in i.message for i in load.errors), [i.message for i in load.errors]


def test_years_lets_two_scoped_facts_share_a_generation_and_field(tmp_path: Path) -> None:
    d = tmp_path / "data"
    u = expected_unit("heat_pump")
    g = "tesla-model-3-gen1"
    _years_file(
        d,
        [
            {"generation_id": g, "value": "none", "unit": u, "years": [2019, 2020]},
            {"generation_id": g, "value": "standard", "unit": u, "years": [2021, None]},
        ],
    )
    load = load_manual_dir(d, TODAY, load_registry(d / "sources.yaml"), for_release=False)
    assert not load.errors and [mf.years for mf in load.facts] == [(2019, 2020), (2021, None)]


def test_check_fails_on_facts_for_retired_ids(tmp_path: Path) -> None:
    """A-36 S7: a fact on a retired id never applies, so `ev manual check` stops it."""
    d = tmp_path / "data"
    shutil.copytree(FIX / "warranty", d / "manual" / "warranty")
    (d / "seed").mkdir(parents=True)
    (d / "seed" / "retired_ids.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "retired-ids/v1",
                "ids": {
                    "tesla-model-3-gen1-lr": "tesla-model-3-gen1-lr-2021",
                    "nissan-leaf-ze0": None,
                },
            }
        )
    )
    code, lines = check(d, today=TODAY)
    assert code == 1
    text = "\n".join(lines)
    assert "error: variant tesla-model-3-gen1-lr is retired" in text
    assert "use tesla-model-3-gen1-lr-2021" in text
    assert "generation nissan-leaf-ze0 is retired" in text and "no successor" in text
    assert "2 errors" in text
