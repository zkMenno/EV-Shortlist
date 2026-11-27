"""Tests for EEA release fallback (`eea.adapter.restore_from_release` + `runner` hook)."""

from __future__ import annotations

import json
import types
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.refresh.plan import PlannedSource
from ev_pipeline.refresh.runner import Deps, RefreshOptions, refresh_source
from ev_pipeline.schema_models import Confidence, Country, FactField
from ev_pipeline.snapshot.store import open_store
from ev_pipeline.sources.eea import adapter as eea


def _write_facts(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("id", pa.string()),
            ("subject_type", pa.string()),
            ("subject_id", pa.string()),
            ("field", pa.string()),
            ("value_num", pa.float64()),
            ("value_text", pa.string()),
            ("unit", pa.string()),
            ("country", pa.string()),
            ("source_id", pa.string()),
            ("source_name", pa.string()),
            ("source_licence", pa.string()),
            ("source_url", pa.string()),
            ("source_record", pa.string()),
            ("retrieved_at", pa.string()),
            ("confidence", pa.string()),
            ("record_year", pa.int64()),
        ]
    )
    cols = {f.name: [r.get(f.name) for r in rows] for f in schema}
    pq.write_table(pa.table(cols, schema=schema), path)


def _fact(
    source_record: str,
    *,
    source_id: str = "eea",
    field: str = "registered_count",
    value_num: float = 42.0,
    country: str = "NL",
    retrieved_at: str = "2026-11-18",
    confidence: str = "high",
    record_year: int = 2024,
) -> dict[str, object]:
    return {
        "id": f"{source_id}:{source_record}:{field}",
        "subject_type": "generation",
        "subject_id": "tesla-model-y-gen1",
        "field": field,
        "value_num": value_num,
        "value_text": None,
        "unit": "count",
        "country": country,
        "source_id": source_id,
        "source_name": "EEA",
        "source_licence": "CC-BY-4.0",
        "source_url": eea.DATAHUB_URL,
        "source_record": source_record,
        "retrieved_at": retrieved_at,
        "confidence": confidence,
        "record_year": record_year,
    }


def test_restore_from_release_reconstructs_exact_provenance_and_handles_pipes(
    tmp_path: Path,
) -> None:
    facts_path = tmp_path / "releases" / "3" / "facts.parquet"
    _write_facts(
        facts_path,
        [
            _fact(
                "[CO2Emission].[latest].[co2cars_2024Fv30]:NL|TESLA|MODEL Y|2024",
                value_num=1234.0,
                retrieved_at="2026-11-18",
                confidence="high",
                record_year=2024,
            ),
            # Duplicate source_record (matched to two subjects or repeated) -> deduplicated
            _fact(
                "[CO2Emission].[latest].[co2cars_2024Fv30]:NL|TESLA|MODEL Y|2024",
                value_num=1234.0,
                retrieved_at="2026-11-18",
                confidence="high",
                record_year=2024,
            ),
            # Pipe inside commercial name Cn + provisional medium confidence
            _fact(
                "[CO2Emission].[latest].[co2cars_2025Pv31]:BE|MG|MG4 | ELECTRIC|2025",
                value_num=88.0,
                country="BE",
                retrieved_at="2026-11-18",
                confidence="medium",
                record_year=2025,
            ),
            # Non-EEA row -> ignored
            _fact(
                "m9d7-ebf2:TESLA|MODEL Y|2024",
                source_id="rdw",
                value_num=500.0,
            ),
            # Non-registration field -> ignored
            _fact(
                "[CO2Emission].[latest].[co2cars_2024Fv30]:DE|AUDI|Q4|2024",
                field="wltp_range_km",
                value_num=500.0,
                country="DE",
            ),
            # Unsupported country -> ignored
            _fact(
                "[CO2Emission].[latest].[co2cars_2024Fv30]:UK|TESLA|MODEL Y|2024",
                country="UK",
            ),
            # Bad retrieved_at -> ignored
            _fact(
                "[CO2Emission].[latest].[co2cars_2024Fv30]:FR|RENAULT|ZOE|2024",
                country="FR",
                retrieved_at="not-a-date",
            ),
        ],
    )

    records = eea.restore_from_release(tmp_path, 3)
    assert len(records) == 2

    first, second = records
    assert first.kind == "registration_count"
    assert first.source == eea.SOURCE
    assert first.record_key == "[CO2Emission].[latest].[co2cars_2024Fv30]:NL|TESLA|MODEL Y|2024"
    assert (first.make, first.model, first.year, first.country) == (
        "TESLA",
        "MODEL Y",
        2024,
        Country.NL,
    )
    assert first.specs[FactField.registered_count].value == 1234
    assert first.retrieved_at == date(2026, 11, 18)
    assert first.confidence == Confidence.high

    assert (second.make, second.model, second.year, second.country) == (
        "MG",
        "MG4 | ELECTRIC",
        2025,
        Country.BE,
    )
    assert second.specs[FactField.registered_count].value == 88
    assert second.confidence == Confidence.medium


def test_restore_from_release_missing_release_returns_empty(tmp_path: Path) -> None:
    assert eea.restore_from_release(tmp_path, 99) == []


def test_refresh_source_restores_staging_on_fetch_failure_when_missing(tmp_path: Path) -> None:
    (tmp_path / "releases").mkdir(parents=True)
    (tmp_path / "releases" / "latest").write_text("3\n", encoding="utf-8")

    sample_rec = SourceRecord(
        source=eea.SOURCE,
        record_key="[CO2Emission].[latest].[co2cars_2024Fv30]:NL|TESLA|MODEL Y|2024",
        kind="registration_count",
        make="TESLA",
        model="MODEL Y",
        year=2024,
        country=Country.NL,
        specs={FactField.registered_count: SpecValue(value=1234, unit="count")},
        retrieved_at=date(2026, 11, 18),
        confidence=Confidence.high,
    )
    called: list[int] = []

    def restore_from_release(data_dir: Path, release_num: int) -> list[SourceRecord]:
        called.append(release_num)
        return [sample_rec]

    fake_adapter = types.SimpleNamespace(
        NAME="eea",
        fetch_cmd=lambda: 1,
        normalise_cmd=lambda from_fixtures=False: 0,
        restore_from_release=restore_from_release,
    )
    ps = PlannedSource(
        id="eea",
        action="fetch",
        reason="forced",
        cadence="yearly",
        registry={"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"},
        adapter=fake_adapter,
    )
    store = open_store({"SNAPSHOT_DIR": str(tmp_path / "snapshots")})
    run, entry = refresh_source(ps, {}, tmp_path, store, RefreshOptions(force=True), Deps())

    assert called == [3]
    assert run.status == "failed"
    assert "restored 1 cached records from release 3" in run.message
    assert entry["status"] == "failed"
    staging = tmp_path / "staging" / "eea.records.jsonl"
    assert staging.exists()
    rows = [json.loads(line) for line in staging.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    assert rows[0]["retrieved_at"] == "2026-11-18"
    assert rows[0]["specs"]["registered_count"]["value"] == 1234


def test_refresh_source_does_not_overwrite_existing_staging_on_fetch_failure(
    tmp_path: Path,
) -> None:
    (tmp_path / "releases").mkdir(parents=True)
    (tmp_path / "releases" / "latest").write_text("3\n", encoding="utf-8")
    staging = tmp_path / "staging" / "eea.records.jsonl"
    staging.parent.mkdir(parents=True)
    staging.write_text('{"existing": true}\n', encoding="utf-8")

    called: list[int] = []
    fake_adapter = types.SimpleNamespace(
        NAME="eea",
        fetch_cmd=lambda: 1,
        normalise_cmd=lambda from_fixtures=False: 0,
        restore_from_release=lambda d, n: called.append(n) or [],
    )
    ps = PlannedSource(
        id="eea",
        action="fetch",
        reason="forced",
        cadence="yearly",
        registry={"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"},
        adapter=fake_adapter,
    )
    store = open_store({"SNAPSHOT_DIR": str(tmp_path / "snapshots")})
    run, _ = refresh_source(ps, {}, tmp_path, store, RefreshOptions(force=True), Deps())

    assert called == []
    assert run.status == "failed"
    assert staging.read_text(encoding="utf-8") == '{"existing": true}\n'


def test_refresh_source_catches_restore_hook_exception(tmp_path: Path) -> None:
    (tmp_path / "releases").mkdir(parents=True)
    (tmp_path / "releases" / "latest").write_text("3\n", encoding="utf-8")

    def boom(data_dir: Path, release_num: int) -> list[SourceRecord]:
        raise RuntimeError("corrupt parquet")

    fake_adapter = types.SimpleNamespace(
        NAME="eea",
        fetch_cmd=lambda: 1,
        normalise_cmd=lambda from_fixtures=False: 0,
        restore_from_release=boom,
    )
    ps = PlannedSource(
        id="eea",
        action="fetch",
        reason="forced",
        cadence="yearly",
        registry={"id": "eea", "name": "EEA", "licence": "CC-BY-4.0"},
        adapter=fake_adapter,
    )
    store = open_store({"SNAPSHOT_DIR": str(tmp_path / "snapshots")})
    run, _ = refresh_source(ps, {}, tmp_path, store, RefreshOptions(force=True), Deps())

    assert run.status == "failed"
    assert any(s["step"] == "restore_from_release" and s["outcome"] == "failed" for s in run.steps)
    assert not (tmp_path / "staging" / "eea.records.jsonl").exists()
