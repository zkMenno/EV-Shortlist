"""T-057 pack guard: usable kWh above the linked pack's gross never merges, goes to conflicts.

Regression for the release-1 QA finding: kia-ev6-gen1-77kwh-awd showed usable 80.0 kWh
(KilowattApp MY2024 facelift record, 84 kWh pack) on pack egmp-77-4 (77.4 kWh gross).
Small hand-built facts plus the committed seed links; no network.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ev_pipeline.derive.links import Links, load_links
from ev_pipeline.match.matcher import MatchedFact, priority_of
from ev_pipeline.merge.merge import merge_variant_facts
from ev_pipeline.merge.policy import load_policies
from ev_pipeline.qa.pack_guard import (
    fill_winning_values,
    guard_usable_vs_pack,
    linked_gross_kwh,
    split_impossible,
)
from ev_pipeline.schema_models import Fact

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
EV6_AWD = "kia-ev6-gen1-77kwh-awd"
EV6_GEN = "kia-ev6-gen1"
_LICENCES = {"kilowatt-openev": "MIT-with-attribution", "seed-manual": "CC-BY-4.0"}


def mf(
    source: str, value: float, year: int, *, vid: str = EV6_AWD, field: str = "battery_kwh_net"
) -> MatchedFact:
    fact = Fact(
        id=f"{source}:{vid}:{year}:{field}",
        subject_type="variant",
        subject_id=vid,
        field=field,
        value=value,
        unit="kW" if field == "dc_peak_kw" else "kWh",
        source={"id": source, "name": source, "licence": _LICENCES[source]},
        retrieved_at=date(2026, 11, 15),
        confidence="low" if source == "seed-manual" else "medium",
    )
    return MatchedFact(fact, source, priority_of(source), year, generation_id=EV6_GEN)


def _links(gross: object = 77.4, **link: object) -> Links:
    return Links(
        packs={"egmp-77-4": {"id": "egmp-77-4", "gross_kwh": gross}},
        by_variant={EV6_AWD: {"variant_id": EV6_AWD, "battery_pack_id": "egmp-77-4", **link}},
    )


def _ev6_facts() -> list[MatchedFact]:
    return [
        mf("seed-manual", 77.4, 2021),
        mf("kilowatt-openev", 80.0, 2024),  # the facelift (84 kWh pack) record
        mf("kilowatt-openev", 263.0, 2024, field="dc_peak_kw"),
    ]


def test_ev6_facelift_usable_is_routed_to_conflicts_not_merged() -> None:
    policies = load_policies(REPO_DATA / "field_sources.yaml")
    facts = _ev6_facts()
    # Without the guard the KilowattApp 80 wins (fallback rank above seed-manual): the bug.
    assert merge_variant_facts(facts, policies)["battery_kwh_net"].value == 80.0

    by_variant, conflicts = guard_usable_vs_pack({EV6_AWD: facts}, _links(), {EV6_AWD: EV6_GEN})
    merged = {v: merge_variant_facts(fs, policies) for v, fs in by_variant.items()}
    fill_winning_values(conflicts, merged)

    assert merged[EV6_AWD]["battery_kwh_net"].value == 77.4
    assert merged[EV6_AWD]["dc_peak_kw"].value == 263.0  # other fields untouched
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["variant_id"] == EV6_AWD and c["source_id"] == "kilowatt-openev"
    assert c["value"] == 80.0 and c["winning_value"] == 77.4
    assert c["tolerance"] == "> pack egmp-77-4 gross 77.4 kWh"
    assert c["fact_id"] == "kilowatt-openev:kia-ev6-gen1-77kwh-awd:2024:battery_kwh_net"


@pytest.mark.seed
def test_committed_ev6_links_point_at_the_pre_facelift_pack() -> None:
    links = load_links(REPO_DATA)
    gross = linked_gross_kwh(links, {EV6_AWD: EV6_GEN, "kia-ev6-gen1-gt": EV6_GEN})
    assert gross[EV6_AWD] == ("egmp-77-4", 77.4)
    assert gross["kia-ev6-gen1-gt"] == ("egmp-77-4", 77.4)
    assert links.packs["egmp-84"]["gross_kwh"] == 84  # the facelift pack the 80 belongs to
    kept, rejected = split_impossible(_ev6_facts(), gross[EV6_AWD][1])
    assert [r.fact.value for r in rejected] == [80.0]
    assert 77.4 in [k.fact.value for k in kept]


def test_value_within_rounding_of_gross_is_kept() -> None:
    kept, rejected = split_impossible(
        [mf("seed-manual", 77.4, 2021), mf("kilowatt-openev", 77.45, 2022)], 77.4
    )
    assert rejected == [] and len(kept) == 2


def test_all_values_impossible_keeps_them_for_qa_to_flag() -> None:
    facts = [
        mf("kilowatt-openev", 80.0, 2024),
        mf("kilowatt-openev", 263.0, 2024, field="dc_peak_kw"),
    ]
    out, conflicts = guard_usable_vs_pack({EV6_AWD: facts}, _links(), {EV6_AWD: EV6_GEN})
    assert out[EV6_AWD] == facts and conflicts == []


def test_variants_without_a_numeric_single_pack_are_untouched() -> None:
    facts = _ev6_facts()
    for links in (
        _links(gross="not-disclosed"),
        Links(by_variant={EV6_AWD: {"variant_id": EV6_AWD, "battery_pack_options": ["egmp-77-4"]}}),
        Links(),
    ):
        out, conflicts = guard_usable_vs_pack({EV6_AWD: facts}, links, {EV6_AWD: EV6_GEN})
        assert out[EV6_AWD] == facts and conflicts == []
    # A variant the matcher does not know (no generation) is passed through as well.
    out, conflicts = guard_usable_vs_pack({EV6_AWD: facts}, _links(), {})
    assert out[EV6_AWD] == facts and conflicts == []


def test_generation_level_link_is_used_when_variant_has_none() -> None:
    links = Links(
        packs={"egmp-77-4": {"id": "egmp-77-4", "gross_kwh": 77.4}},
        by_generation={EV6_GEN: {"generation_id": EV6_GEN, "battery_pack_id": "egmp-77-4"}},
    )
    _, conflicts = guard_usable_vs_pack({EV6_AWD: _ev6_facts()}, links, {EV6_AWD: EV6_GEN})
    assert [c["value"] for c in conflicts] == [80.0]


def test_fill_winning_values_without_merged_field() -> None:
    conflicts = [{"variant_id": "x", "field": "battery_kwh_net", "winning_value": None}]
    fill_winning_values(conflicts, {})
    assert conflicts[0]["winning_value"] is None
