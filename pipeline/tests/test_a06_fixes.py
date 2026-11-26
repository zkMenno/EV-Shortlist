"""A-06 fixes (audits/A-06-merge-rules-review.md, "Fixes"): cited seed values carry their real
source and go through the licence gate (F3), a blocked or low-confidence citation withholds a
lone value it contradicts, guards never resurrect an overruled value (F2) or delete a backed
one (F1), explicit policy keys (F4, F8), and git runs without the user's gitconfig (L4).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from test_a06_review import REPO_POLICIES, VID, _mf

from ev_pipeline import net
from ev_pipeline.match.seed import parse_manual_variants
from ev_pipeline.merge.merge import merge_facts, merge_variant_facts
from ev_pipeline.merge.policy import parse_policies
from ev_pipeline.qa.value_guard import (
    CITATION_OUTVOTED,
    CONTRADICTED,
    CONTRADICTED_LOW,
    citation_values,
    guard_contradicted,
    guard_impossible,
    guard_needs_backing,
    run_guards,
)

REPO = Path(__file__).resolve().parents[2]
FORD = "https://www.fordpers.be/editor/files/ford_mustang_mach_e_2020_techspecs_eu_2.pdf"


def _merged(facts):  # type: ignore[no-untyped-def]
    return {VID: merge_variant_facts(facts, REPO_POLICIES)}


def _blocked_cite(fname: str, value: float, confidence: str = "medium"):  # type: ignore[no-untyped-def]
    return _mf("maker-docs", fname, value, cited=True, confidence=confidence, url=FORD)


# --- F3: cited seed values are maker-docs facts --------------------------------------------


def test_seed_cited_value_is_a_maker_docs_fact_with_its_url() -> None:
    v = {
        "generation_id": "g",
        "id": "g-gt",
        "name": "GT",
        "years": [2021, 2023],
        "cited": {
            "battery_kwh_net": {
                "value": 88,
                "source_url": FORD,
                "source_name": "Ford Mach-E tech specs",
                "retrieved": date(2026, 11, 15),
                "locator": "p. 2",
                "confidence": "medium",
            }
        },
    }
    [mv], problems = parse_manual_variants({"variants": [v]}, date(2026, 1, 1))
    assert problems == []
    [rec] = mv.cited_records
    assert rec.source.id.root == "maker-docs"
    assert rec.source.url == FORD
    assert rec.retrieved_at == date(2026, 11, 15)
    assert "unchecked" not in rec.source.name and "CC-BY" not in rec.source.licence


def test_seed_cited_value_may_name_another_source_but_never_the_seed() -> None:
    def cite(sid: str) -> dict:
        c = {"value": 41, "source_url": FORD, "retrieved": "2026-11-15", "locator": "p. 1"}
        return {"battery_kwh_net": {**c, "confidence": "medium", "source_id": sid}}

    base = {"generation_id": "g", "id": "g-x", "name": "X", "years": [2020, 2021]}
    [mv], _ = parse_manual_variants({"variants": [{**base, "cited": cite("manual")}]}, date.today())
    assert mv.cited_records[0].source.id.root == "manual"
    [mv], problems = parse_manual_variants(
        {"variants": [{**base, "cited": cite("seed-manual")}]}, date.today()
    )
    assert mv.cited_records == [] and problems


def test_repo_seed_has_no_cited_value_under_the_seed_source() -> None:
    doc = yaml.safe_load((REPO / "data" / "seed" / "variants.yaml").read_text(encoding="utf-8"))
    mvs, _ = parse_manual_variants(doc, date(2026, 11, 15))
    cited = [r for mv in mvs for r in mv.cited_records]
    assert cited, "the repo seed cites values"
    assert all(r.source.id.root == "maker-docs" and r.source.url for r in cited)


def test_released_facts_hold_no_blocked_citation() -> None:
    """No fact from a source that isn't releasable ships, and every shipped fact keeps its source
    URL column. Under Decisions 068 / 087 (`manual` and `maker-docs`, T-163), maker-hosted cited
    facts are releasable while third-party URLs and blocked sources (`autotijd`,
    `cited-third-party`) stay held."""
    from ev_pipeline.release.gate import load_registry

    registry = load_registry(REPO / "data" / "sources.yaml")
    import pyarrow.parquet as pq

    latest = REPO / "data" / "releases" / "latest"
    if not latest.exists():
        return
    n = latest.read_text(encoding="utf-8").strip() if latest.is_file() else "latest"
    path = REPO / "data" / "releases" / n / "facts.parquet"
    if not path.exists():
        return
    table = pq.read_table(path)
    assert "source_url" in table.column_names
    rows = table.select(["source_id", "source_url", "source_record"]).to_pylist()
    assert not [r for r in rows if registry.fact_blocked(r["source_id"], r["source_url"])]
    for held in ("autotijd", "cited-third-party"):
        assert not registry.releasable(held)
    assert registry.releasable("maker-docs")
    assert registry.fact_blocked("maker-docs", "https://xr793.com/brochure.pdf") is not None
    assert registry.fact_blocked("maker-docs", "https://cdn.skoda-storyboard.com/x.pdf") is None


# --- F3 knock-on: contradicted values are withheld -----------------------------------------


def test_lone_value_contradicted_by_a_blocked_citation_is_withheld() -> None:
    """Mach-E GT: OpenEV's lone 82 kWh, Ford says 88 (maker-docs, blocked until Q-008)."""
    facts = [_mf("openev", "battery_kwh_net", 82)]
    merged = _merged(facts)
    rows = guard_contradicted(
        merged, {VID: facts}, REPO_POLICIES, {VID: [_blocked_cite("battery_kwh_net", 88)]}
    )
    assert "battery_kwh_net" not in merged[VID]
    assert [r["value"] for r in rows] == [82]
    assert rows[0]["tolerance"].startswith(CONTRADICTED)
    assert "maker-docs 88 kWh" in rows[0]["tolerance"]


def test_withholding_lets_a_value_that_agrees_with_the_citation_ship() -> None:
    """The contradicted group goes; KilowattApp's 88 (agreeing with Ford) is merged again and
    ships, with the citation noted as provenance only."""
    facts = [
        _mf("openev", "battery_kwh_net", 82),
        _mf("kilowatt-openev", "battery_kwh_net", 88),
    ]
    merged = _merged(facts)
    assert merged[VID]["battery_kwh_net"].value == 82
    cite = _blocked_cite("battery_kwh_net", 88)
    guard_contradicted(merged, {VID: facts}, REPO_POLICIES, {VID: [cite]})
    mg = merged[VID]["battery_kwh_net"]
    assert mg.value == 88 and mg.source_ids == ["kilowatt-openev"]
    assert mg.evidence == [cite]
    assert "not published until Q-008" in (mg.note() or "")
    assert cite.fact.id not in mg.fact_ids


def test_two_agreeing_origins_keep_their_value_against_a_blocked_citation() -> None:
    facts = [
        _mf("openev", "battery_kwh_net", 82),
        _mf("kilowatt-openev", "battery_kwh_net", 82),
    ]
    merged = _merged(facts)
    cite = _blocked_cite("battery_kwh_net", 88)
    rows = guard_contradicted(merged, {VID: facts}, REPO_POLICIES, {VID: [cite]})
    assert merged[VID]["battery_kwh_net"].value == 82
    assert [(r["source_id"], r["tolerance"]) for r in rows] == [("maker-docs", CITATION_OUTVOTED)]


def test_agreeing_blocked_citation_is_provenance_only() -> None:
    facts = [_mf("openev", "battery_kwh_net", 88)]
    merged = _merged(facts)
    before = merged[VID]["battery_kwh_net"]
    rows = guard_contradicted(
        merged, {VID: facts}, REPO_POLICIES, {VID: [_blocked_cite("battery_kwh_net", 88)]}
    )
    mg = merged[VID]["battery_kwh_net"]
    assert rows == [] and mg is before
    assert mg.source_ids == ["openev"] and mg.confidence == "medium"
    assert len(mg.evidence) == 1


def test_low_confidence_citation_withholds_a_lone_contradicted_value() -> None:
    """Zoe Q210: KilowattApp 11 kW AC alone; Renault's price list (low: names trims only) says
    43 kW. A low citation cannot win, but we no longer ship the value it contradicts."""
    facts = [
        _mf("kilowatt-openev", "ac_kw", 11),
        _mf("seed-manual", "ac_kw", 43, cited=True, confidence="low"),
    ]
    merged = _merged(facts)
    assert merged[VID]["ac_kw"].value == 11
    rows = guard_contradicted(merged, {VID: facts}, REPO_POLICIES, {})
    assert rows and rows[0]["tolerance"].startswith(CONTRADICTED_LOW)
    # What is left is the citation itself (low): it may ship, labelled low.
    assert merged[VID]["ac_kw"].value == 43 and merged[VID]["ac_kw"].confidence == "low"


def test_citations_that_disagree_among_themselves_withhold_nothing() -> None:
    facts = [_mf("openev", "battery_kwh_net", 82)]
    merged = _merged(facts)
    ev = [_blocked_cite("battery_kwh_net", 88), _blocked_cite("battery_kwh_net", 70)]
    assert guard_contradicted(merged, {VID: facts}, REPO_POLICIES, {VID: ev}) == []
    assert merged[VID]["battery_kwh_net"].value == 82


# --- F1, F4: needs_backing ----------------------------------------------------------------


def test_adding_kilowattapp_never_removes_a_seed_value_that_would_ship() -> None:
    seed = _mf("seed-manual", "dc_peak_kw", 50, confidence="low")
    alone = _merged([seed])
    guard_needs_backing(alone, {VID: [seed]}, REPO_POLICIES)
    assert alone[VID]["dc_peak_kw"].value == 50
    facts = [_mf("kilowatt-openev", "dc_peak_kw", 150), seed]
    merged = _merged(facts)
    rows = guard_needs_backing(merged, {VID: facts}, REPO_POLICIES)
    assert merged[VID]["dc_peak_kw"].value == 50
    assert [r["value"] for r in rows] == [150]


def test_seed_counts_as_backing_only_where_the_policy_says_so() -> None:
    strict = parse_policies(
        {
            "fields": {
                "dc_peak_kw": {
                    "primary": ["kilowatt-openev"],
                    "fallbacks": ["seed-manual"],
                    "needs_backing": ["kilowatt-openev"],
                }
            }
        }  # fmt: skip
    )
    assert REPO_POLICIES.for_field("dc_peak_kw").seed_counts_as_backing is True
    facts = [
        _mf("kilowatt-openev", "dc_peak_kw", 125),
        _mf("seed-manual", "dc_peak_kw", 125, confidence="low"),
    ]
    lenient = {VID: merge_variant_facts(facts, REPO_POLICIES)}
    guard_needs_backing(lenient, {VID: facts}, REPO_POLICIES)
    assert lenient[VID]["dc_peak_kw"].value == 125
    assert lenient[VID]["dc_peak_kw"].source_ids == ["kilowatt-openev", "seed-manual"]
    tight = {VID: merge_variant_facts(facts, strict)}
    rows = guard_needs_backing(tight, {VID: facts}, strict)
    # Strict: the seed is no backing, so KilowattApp is withheld; the seed value stays alone.
    assert [r["source_id"] for r in rows] == ["kilowatt-openev"]
    assert tight[VID]["dc_peak_kw"].source_ids == ["seed-manual"]
    assert tight[VID]["dc_peak_kw"].confidence == "low"


# --- F2: the impossible guard respects citations -------------------------------------------


def test_impossible_guard_never_brings_back_what_a_citation_overruled() -> None:
    """Both halves cited (equal footing) and both taken out: the OpenEV 82 that the cited 88
    overruled must not come back as the usable value."""
    facts = [
        _mf("openev", "battery_kwh_net", 82),
        _mf("seed-manual", "battery_kwh_net", 88, cited=True),
        _mf("openev", "battery_kwh_gross", 99),
        _mf("seed-manual", "battery_kwh_gross", 85, cited=True),
    ]
    merged = _merged(facts)
    assert merged[VID]["battery_kwh_net"].rule == "cited"
    assert merged[VID]["battery_kwh_gross"].rule == "cited"
    guard_impossible(merged, {VID: facts}, REPO_POLICIES)
    net_ = merged[VID].get("battery_kwh_net")
    assert net_ is None or net_.value != 82


def test_run_guards_does_not_mutate_the_callers_facts_and_dedupes() -> None:
    facts = [_mf("openev", "battery_kwh_net", 82)]
    pool = {VID: facts}
    merged = _merged(facts)
    ev = {VID: [_blocked_cite("battery_kwh_net", 88)]}
    rows = run_guards(merged, pool, REPO_POLICIES, ev)
    assert pool[VID] is facts and len(facts) == 1
    assert len(rows) == 1


def test_run_guards_rechecks_a_value_another_guard_set() -> None:
    """L1: the impossible guard replaces the usable value with a KilowattApp figure equal to
    the AC power; the mix-up guard (run again) must see the new value."""
    facts = [
        _mf("openev", "battery_kwh_net", 60),
        _mf("openev", "battery_kwh_gross", 50),
        _mf("kilowatt-openev", "battery_kwh_gross", 50),
        _mf("kilowatt-openev", "battery_kwh_net", 22),
        _mf("kilowatt-openev", "ac_kw", 22),
    ]
    merged = _merged(facts)
    assert merged[VID]["battery_kwh_net"].value == 60  # OpenEV first in a median field
    run_guards(merged, {VID: facts}, REPO_POLICIES)
    assert merged[VID]["battery_kwh_net"].value == 22
    assert "ac_kw" not in merged[VID]


# --- F6, F8: independence ----------------------------------------------------------------


def test_maker_docs_is_not_an_independent_confirmation_either() -> None:
    mg = merge_facts(
        [_mf("openev", "battery_kwh_net", 88), _mf("maker-docs", "battery_kwh_net", 88)],
        REPO_POLICIES.for_field("battery_kwh_net"),
    )
    assert mg.independent_agreeing == 1 and mg.confidence != "high"


def test_openev_epa_range_is_fueleconomy_origin() -> None:
    """F8: an EPA rating comes only from EPA; OpenEV cites fueleconomy.gov for it."""
    from ev_pipeline.match.matcher import MatchedFact, priority_of
    from ev_pipeline.schema_models import Fact

    def epa(source: str, km: float, n: int) -> MatchedFact:
        lic = {"openev": "CDLA-Permissive-2.0", "fueleconomy": "US-PD"}[source]
        f = Fact(
            id=f"{source}:r{n}:epa_range_km",
            subject_type="variant",
            subject_id=VID,
            field="epa_range_km",
            value=km,
            unit="km",
            source={"id": source, "name": source, "licence": lic},
            source_record=f"r{n}",
            retrieved_at=date(2026, 11, 15),
            confidence="medium",
        )
        return MatchedFact(f, source, priority_of(source), 2023)

    pol = REPO_POLICIES.for_field("epa_range_km")
    assert pol.origin("openev") == "fueleconomy"
    mg = merge_facts([epa("fueleconomy", 400, 1), epa("openev", 400, 2)], pol)
    assert mg.independent_agreeing == 1 and mg.confidence == "medium"
    # ...so OpenEV + an agreeing fueleconomy record no longer outvote the priority value.
    mg = merge_facts([epa("fueleconomy", 490, 3), epa("fueleconomy", 580, 4),
                      epa("openev", 580, 5)], pol)  # fmt: skip
    assert mg.rule == "priority"


# --- L4: git isolation --------------------------------------------------------------------


def test_git_runs_without_user_or_system_gitconfig(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIT_CONFIG", "/home/someone/.gitconfig")
    env = net.git_env()
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert "GIT_CONFIG" not in env
    callers = (
        "snapshot/probe.py",
        "sources/openev/adapter.py",
        "sources/kilowatt_openev/adapter.py",
    )
    for f in callers:
        src = (REPO / "pipeline" / "ev_pipeline" / f).read_text(encoding="utf-8")
        assert src.count("subprocess.run(") == src.count("env=net.git_env()"), f


def test_citation_values_lists_blocked_and_low_citations_only() -> None:
    blocked = _blocked_cite("battery_kwh_net", 66.5)
    low = _mf("seed-manual", "battery_kwh_net", 70.5, cited=True, confidence="low", url=FORD)
    plain = _mf("openev", "battery_kwh_net", 60)
    out = citation_values({VID: [blocked]}, {VID: [low, plain]})
    assert sorted(out[VID]["battery_kwh_net"]) == [66.5, 70.5]
