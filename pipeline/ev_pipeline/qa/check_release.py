"""Re-run the blocking release QA on a COMMITTED release folder (T-057, CI `data-qa` job).

Staging is git-ignored, so CI cannot rebuild a release; it can re-check the published one:
catalogue.json + facts.parquet (+ charging_stats.json) against today's data/sources.yaml.

    uv run python -m ev_pipeline.qa check-release ../data/releases/latest
    uv run python -m ev_pipeline.qa check-release ../data/releases/1 --data-dir ../data --json

`latest` may be the pointer file (it holds the release number) or a folder. The blocking
checks are the same functions the release step runs: provenance completeness and the licence
gate (so a source later moved to blocked / ODbL in sources.yaml fails CI). Impossible values
are reported, never blocking. Exit code: 0 pass, 1 a blocking check failed, 2 bad input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from ev_pipeline.images.qa import check_images
from ev_pipeline.qa.checks import Check, check_licence_gate, check_provenance, impossible_values
from ev_pipeline.release.gate import load_registry

REQUIRED_FILES = ("catalogue.json", "facts.parquet")
CHARGING_STATS_FILE = "charging_stats.json"


class ReleaseInputError(Exception):
    """The release folder or the registry is missing or unreadable."""


def resolve_release_dir(path: Path) -> Path:
    """A release folder, or the `latest` pointer file -> the folder it names."""
    if path.is_file():
        n = path.read_text(encoding="utf-8").strip()
        if not n.isdigit():
            raise ReleaseInputError(f"{path}: pointer must hold a release number, got {n!r}")
        path = path.parent / n
    if not path.is_dir():
        raise ReleaseInputError(f"release folder not found: {path}")
    missing = [f for f in REQUIRED_FILES if not (path / f).exists()]
    if missing:
        raise ReleaseInputError(f"{path}: missing {', '.join(missing)}")
    return path


def fact_from_parquet(row: dict[str, Any]) -> dict[str, Any]:
    """facts.parquet row (release.build._flat_facts) -> the fact dict the checks expect."""
    value = row.get("value_num")
    if value is None:
        value = row.get("value_text")
    fact: dict[str, Any] = {
        "id": row.get("id"),
        "subject_type": row.get("subject_type"),
        "subject_id": row.get("subject_id"),
        "field": row.get("field"),
        "value": value,
        "unit": row.get("unit"),
        "source": {
            "id": row.get("source_id"),
            "name": row.get("source_name"),
            "licence": row.get("source_licence"),
            **({"url": row["source_url"]} if row.get("source_url") else {}),
        },
        "retrieved_at": row.get("retrieved_at"),
        "confidence": row.get("confidence"),
    }
    for k in ("country", "source_record"):
        if row.get(k) is not None:
            fact[k] = row[k]
    return fact


def load_release(release_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Any]:
    try:
        catalogue = json.loads((release_dir / "catalogue.json").read_text(encoding="utf-8"))
        facts = [
            fact_from_parquet(r) for r in pq.read_table(release_dir / "facts.parquet").to_pylist()
        ]
    except (OSError, ValueError) as e:  # json / parquet errors are ValueError subclasses
        raise ReleaseInputError(f"{release_dir}: cannot read release files: {e}") from e
    cs = release_dir / CHARGING_STATS_FILE
    charging = json.loads(cs.read_text(encoding="utf-8")) if cs.exists() else None
    return catalogue, facts, charging


def check_release(release_dir: Path, data_dir: Path) -> dict[str, Any]:
    """Run the blocking checks; returns a small report (status pass | fail)."""
    release_dir = resolve_release_dir(release_dir)
    sources = data_dir / "sources.yaml"
    if not sources.exists():
        raise ReleaseInputError(f"registry not found: {sources}")
    registry = load_registry(sources)
    catalogue, facts, charging = load_release(release_dir)
    checks: list[Check] = [
        check_provenance(catalogue, facts),
        check_licence_gate(catalogue, facts, registry, charging),
        check_images(catalogue, release_dir),
    ]
    # T-123: the committed release against N-1 under today's approved_changes.yaml.
    from ev_pipeline.release.differ import release_diff_check

    n = catalogue.get("release")
    if isinstance(n, int):
        diff_check, _ = release_diff_check(
            data_dir, release_dir, n, write_review=False, fetch_new=True
        )
        checks.append(diff_check)
    failed = [c.id for c in checks if c.blocking and c.status == "fail"]
    impossible = impossible_values(catalogue, facts)
    return {
        "release": catalogue.get("release"),
        "release_dir": str(release_dir),
        "status": "fail" if failed else "pass",
        "blocking_failures": failed,
        "checks": {
            c.id: {
                "status": c.status,
                "summary": c.summary,
                "errors": c.details.get("errors", []),
            }
            for c in checks
        },
        "impossible_values": impossible,  # report only (non-blocking outlier check)
    }


def render(report: dict[str, Any]) -> str:
    lines = [f"Release {report['release']} ({report['release_dir']}): {report['status']}"]
    for cid, c in report["checks"].items():
        lines.append(f"  {cid}: {c['status']} ({c['summary']})")
        lines += [f"    - {e}" for e in c["errors"][:20]]
    imp = report["impossible_values"]
    if imp:
        lines.append(f"  impossible values (not blocking): {len(imp)}")
        lines += [f"    - {i['variant_id']}: {i['detail']}" for i in imp[:10]]
    return "\n".join(lines)
