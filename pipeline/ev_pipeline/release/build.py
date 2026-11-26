"""`ev release`: match -> range-check -> merge -> derive -> validate -> publish (T-006).

Inputs:  data/staging/*.records.jsonl (SourceRecord per line), data/seed/models.yaml,
         data/seed/variants.yaml (optional, source `seed-manual`).
         data/sources.yaml (licence gate), data/field_sources.yaml (merge policy per field).
Outputs: data/review/{unmatched,validation,conflicts}.csv,
         data/releases/<n>/{catalogue.json, catalogue.parquet, facts.parquet, diff.json,
         coverage.md, README.md, run_log.json} and data/releases/latest (holds n).

n = highest existing release number + 1 (Decision 008). The folder is written under a
temporary name and renamed at the end, so a failed run never leaves a half release.
`--dry-run` computes everything and prints the summary but writes nothing.
Licence gate (Decision 009): records from a source that data/sources.yaml does not list as
`active` with a named licence are dropped on load and guarded again before writing; `nyland`
(permission pending) is always excluded.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ev_pipeline.derive.known_issues import build_known_issues, read_defects
from ev_pipeline.derive.links import (
    apply_rule_links,
    catalogue_parts,
    finish_voltage,
    id_errors,
    inherited_for,
    link_coverage,
    load_links,
    pack_facts,
)
from ev_pipeline.derive.rows import ESTIMATE_SOURCE, build_rows
from ev_pipeline.manual.facts import attach_manual_facts, issue_problems, load_manual_dir
from ev_pipeline.match.matcher import (
    EXCLUDED_SOURCES,
    MatchedFact,
    MatchResult,
    Problem,
    UnmatchedRow,
    aggregate_counts,
    match_records,
    registration_entries,
)
from ev_pipeline.match.review import unmatched_rows, write_unmatched
from ev_pipeline.match.seed import (
    ManualVariant,
    Seed,
    SourceHold,
    load_manual_variants,
    load_seed,
    load_source_holds,
)
from ev_pipeline.merge.ac_route import route_optional_ac
from ev_pipeline.merge.corroborate import apply_corroboration
from ev_pipeline.merge.generation_years import corroborate_years
from ev_pipeline.merge.merge import Merged, has_citation, merge_variant_facts
from ev_pipeline.merge.policy import load_policies
from ev_pipeline.qa.pack_guard import fill_winning_values, guard_usable_vs_pack
from ev_pipeline.qa.value_guard import citation_values, run_guards
from ev_pipeline.records import SourceRecord
from ev_pipeline.release.charging_stats import FILE_NAME as CHARGING_STATS_FILE
from ev_pipeline.release.charging_stats import REVIEW_COLUMNS as CHARGING_REVIEW_COLUMNS
from ev_pipeline.release.charging_stats import REVIEW_FILE as CHARGING_REVIEW_FILE
from ev_pipeline.release.charging_stats import build_charging_stats, charging_review_rows
from ev_pipeline.release.gate import MISSING_REGISTRY, load_registry
from ev_pipeline.release.taxonomy import load_optional_taxonomy, optional_taxonomy_errors
from ev_pipeline.release.validate import (
    ROW_NUMBER_FIELDS,
    ReleaseError,
    _schema,
    check_fact_ranges,
    enum_fact_errors,
    excluded_source_errors,
    licence_errors,
    provenance_errors,
    schema_errors,
    write_validation,
)
from ev_pipeline.review_queue import annotate_review_dir, snapshot_statuses
from ev_pipeline.sources._common import rel

REPO_ROOT = Path(__file__).resolve().parents[3]
DIFF_IGNORE = {"release", "provenance"}


def config_dir(data_dir: Path) -> Path:
    """The repo's config/ next to data_dir; a scratch data dir (ev verify, a temp machine) falls
    back to the repo's own config/, like publish.load_config does for publish.yaml."""
    here = data_dir.parent / "config"
    return here if here.is_dir() else Path(__file__).resolve().parents[3] / "config"


def default_data_dir() -> Path:
    return Path(os.environ.get("EV_DATA_DIR", REPO_ROOT / "data"))


@dataclass
class ReleaseResult:
    release: int
    catalogue: dict[str, Any]
    facts: list[dict[str, Any]]
    fact_years: list[int | None]
    diff: dict[str, Any]
    match: MatchResult
    problems: list[Problem]
    unmatched_count: int
    inputs: list[dict[str, Any]] = field(default_factory=list)
    unmatched_rows: list[UnmatchedRow] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    gated: dict[str, dict[str, Any]] = field(default_factory=dict)
    out_dir: Path | None = None
    catalogue_bytes: int = 0
    catalogue_gzip_bytes: int = 0
    taxonomy_tables: dict[str, int] = field(default_factory=dict)
    taxonomy_held_back: dict[str, dict[str, str]] = field(default_factory=dict)
    # T-059: charging_stats.json (None = not shipped) and the run-log lines of the sections.
    charging_stats: dict[str, Any] | None = None
    sections: dict[str, Any] = field(default_factory=dict)
    # T-025: charging figures for review (big step, fall, revision, gone since last release).
    charging_review: list[dict[str, str]] = field(default_factory=list)
    # T-034: towns + January climate per country (towns/<cc>.json), empty = not shipped.
    towns: dict[str, dict[str, Any]] = field(default_factory=dict)
    # T-033: per-variant consumption matrix (consumption_matrix.json), None = not shipped.
    consumption: dict[str, Any] | None = None
    # T-062: retired variant ids -> successor (or None); never loses an entry.
    retired_ids: dict[str, str | None] = field(default_factory=dict)
    # T-069: per-variant shortlist scores (shortlist_scores.json), None = not shipped.
    shortlist: dict[str, Any] | None = None
    shortlist_backtest: dict[str, Any] | None = None
    # T-081: used price bands per variant, build year and country (used_prices.json).
    used_prices: dict[str, Any] | None = None
    # T-111: values the plausibility gate took out of the rows (Issue dicts, qa.json).
    plausibility_withheld: list[dict[str, Any]] = field(default_factory=list)
    # T-134: resized car photos (release-relative path -> WebP bytes), published as assets.
    image_files: dict[str, bytes] = field(default_factory=dict)


# --- loading -----------------------------------------------------------------------------


def load_staging(staging: Path) -> tuple[list[SourceRecord], list[dict[str, Any]], list[Problem]]:
    records: list[SourceRecord] = []
    inputs: list[dict[str, Any]] = []
    problems: list[Problem] = []
    if not staging.is_dir():
        return records, inputs, problems
    for path in sorted(staging.glob("*.records.jsonl")):
        name = path.name.removesuffix(".records.jsonl")
        if name in EXCLUDED_SOURCES:
            inputs.append({"path": str(path), "skipped": "excluded source (permission pending)"})
            continue
        n = 0
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    rec = SourceRecord.model_validate_json(line)
                except Exception as exc:
                    problems.append(
                        Problem(
                            "parse", name, f"{path.name}:{lineno}", "", "", "", "", str(exc)[:200]
                        )
                    )
                    continue
                records.append(rec)
                n += 1
        inputs.append({"path": str(path), "records": n, "modified": _mtime(path)})
    return records, inputs, problems


def log_path(path: Path | str, data_dir: Path) -> str:
    """A machine-independent path for the run log: repo-relative (sources._common.rel), else
    relative to the data folder as `data/...`, else just the file name. Never an absolute
    host path (T-006 review)."""
    p = Path(path)
    r = rel(p)
    if not Path(r).is_absolute():
        return r
    try:
        return str(Path("data") / p.resolve().relative_to(data_dir.resolve()))
    except ValueError:
        return p.name


def generation_pack_kwh(links: Any, manual: list[ManualVariant]) -> dict[str, set[float]]:
    """Battery sizes per generation from battery_packs.yaml via variant_links.yaml (generation
    links, and variant links of seed-manual variants). Evidence for shared-year matching."""
    gen_of = {mv.id: mv.generation_id for mv in manual}
    out: dict[str, set[float]] = {}

    def add(gid: str | None, link: dict[str, Any]) -> None:
        if not gid:
            return
        ids = [link.get("battery_pack_id"), *(link.get("battery_pack_options") or [])]
        for pid in ids:
            pack = links.packs.get(pid) if pid else None
            for k in ("gross_kwh", "usable_kwh"):
                v = (pack or {}).get(k)
                if isinstance(v, int | float) and not isinstance(v, bool):
                    out.setdefault(gid, set()).add(float(v))

    for gid, link in links.by_generation.items():
        add(gid, link)
    for vid, link in links.by_variant.items():
        add(gen_of.get(vid), link)
    return out


def _merged_number(merged: dict[str, Any], field: str) -> float | None:
    mg = merged.get(field)
    v = getattr(mg, "value", None)
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")


def existing_releases(releases: Path) -> list[int]:
    if not releases.is_dir():
        return []
    return sorted(int(p.name) for p in releases.iterdir() if p.is_dir() and p.name.isdigit())


def next_release_number(releases: Path) -> int:
    nums = existing_releases(releases)
    return (nums[-1] + 1) if nums else 1


# --- building ----------------------------------------------------------------------------


def _fact_dict(mf: MatchedFact) -> dict[str, Any]:
    return mf.fact.model_dump(mode="json", exclude_none=True)


def _generation_dicts(seed: Seed) -> list[dict[str, Any]]:
    out = []
    for gid in sorted(seed.generations):
        g = seed.generations[gid]
        d: dict[str, Any] = {
            "id": g.id,
            "model_id": g.model_id,
            "name": g.name,
            "slug": g.id,
            "year_start": g.year_start,
            "year_end": g.year_end,
            "uncertain": g.uncertain,
        }
        if g.change_markers:
            d["change_markers"] = [
                {"year": int(c["year"]), "text": str(c["text"])} for c in g.change_markers
            ]
        out.append(d)
    return out


def compute_diff(prev: dict[str, Any] | None, cur: dict[str, Any]) -> dict[str, Any]:
    cur_rows = {r["variant_id"]: r for r in cur["rows"]}
    prev_rows = {r["variant_id"]: r for r in (prev or {}).get("rows", [])}
    added = sorted(set(cur_rows) - set(prev_rows))
    removed = sorted(set(prev_rows) - set(cur_rows))
    changed: dict[str, dict[str, dict[str, Any]]] = {}
    for vid in sorted(set(cur_rows) & set(prev_rows)):
        a, b = prev_rows[vid], cur_rows[vid]
        fields = {}
        for k in sorted((set(a) | set(b)) - DIFF_IGNORE):
            if a.get(k) != b.get(k):
                fields[k] = {"old": a.get(k), "new": b.get(k)}
        if fields:
            changed[vid] = fields
    return {
        "release": cur["release"],
        "previous_release": prev["release"] if prev else None,
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {
            "rows_previous": len(prev_rows),
            "rows": len(cur_rows),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def generation_has_image(schema: dict[str, Any]) -> bool:
    """T-134: attach `generations[].image` only once packages/schema defines it (WS0)."""
    gen = schema.get("$defs", {}).get("Generation", {})
    return "image" in gen.get("properties", {})


def attach_images(
    catalogue: dict[str, Any], data_dir: Path, today: date
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Car photos (T-134, Decision 081): validated photos.yaml entries whose original is in
    data/cache/images get resized WebP files and a `generations[].image` field. Returns the
    files to write and the run-log section. Nothing is fetched here (`ev images fetch`)."""
    from ev_pipeline.images.photos import load_photos
    from ev_pipeline.images.store import CACHE_DIR, build_release_images

    gens = catalogue["generations"]
    photos, problems = load_photos(data_dir, {g["id"] for g in gens}, today)
    log: dict[str, Any] = {
        "photos": len(photos),
        "problems": [{"generation_id": p.generation_id, "reason": p.reason} for p in problems],
    }
    pf = data_dir / "images" / "photos.yaml"
    if pf.exists():
        log["photos_file"] = {"records": len(photos) + len(problems), "modified": _mtime(pf)}
    if not photos:
        log["status"] = "no photos"
        return {}, log
    if not generation_has_image(_schema()):
        log["status"] = "held back: packages/schema has no Generation.image yet (WS0)"
        return {}, log
    rel = build_release_images(photos, data_dir / CACHE_DIR)
    for g in gens:
        if g["id"] in rel.fields:
            g["image"] = rel.fields[g["id"]]
    log.update(rel.log(), status="attached")
    return rel.files, log


def build_release(
    data_dir: Path,
    now: datetime | None = None,
    release: int | None = None,
) -> ReleaseResult:
    now = now or datetime.now(UTC)
    today = now.date()
    seed_path = data_dir / "seed" / "models.yaml"
    if not seed_path.exists():
        raise ReleaseError(f"seed not found: {seed_path}")
    seed = load_seed(seed_path)
    manual: list[ManualVariant] = []
    holds: list[SourceHold] = []
    problems: list[Problem] = []
    records, inputs, parse_problems = load_staging(data_dir / "staging")
    problems += parse_problems
    variants_path = data_dir / "seed" / "variants.yaml"
    if variants_path.exists():
        manual, manual_problems = load_manual_variants(variants_path)
        holds = load_source_holds(variants_path)
        problems += [Problem("seed", "seed-manual", "", "", "", "", "", p) for p in manual_problems]
        inputs.append(
            {"path": str(variants_path), "records": len(manual), "modified": _mtime(variants_path)}
        )
    inputs.insert(0, {"path": str(seed_path), "modified": _mtime(seed_path)})

    registry = load_registry(data_dir / "sources.yaml")
    if not registry.loaded:
        # Fail closed (T-006 review): without the registry nothing proves a licence.
        raise ReleaseError(MISSING_REGISTRY)
    policies = load_policies(data_dir / "field_sources.yaml")
    gated: dict[str, dict[str, Any]] = {}

    def gate(sid: str, url: str | None = None) -> bool:
        why = registry.fact_blocked(sid, url) if url is not None else registry.reason_blocked(sid)
        if why is not None:
            g = gated.setdefault(sid, {"reason": why, "records": 0})
            g["records"] += 1
            return False
        return True

    records = [r for r in records if gate(r.source.id.root)]
    manual = [mv for mv in manual if gate(mv.record.source.id.root)]
    # P7: hand-entered facts (data/manual/) and seed `cited:` values (source maker-docs, A-06 F3).
    # Gated per fact after matching below: maker-hosted cited facts ship under Decisions 068 / 087
    # (`use: cited-facts` + `cited_hosts`); blocked sources and third-party / dealer copies never
    # ship, and are kept as evidence for guard_contradicted.
    hand = load_manual_dir(data_dir, today, registry)
    problems += issue_problems(hand.issues)
    inputs += [{"path": str(data_dir / Path(p).relative_to("data"))} for p in hand.files]
    hand_facts = list(hand.facts)

    links = load_links(data_dir)
    result = match_records(records, seed, manual, generation_pack_kwh(links, manual), holds=holds)
    problems += result.problems
    hand_matched, hand_problems = attach_manual_facts(hand_facts, result, seed)
    result.spec_facts += hand_matched
    problems += hand_problems
    spec_facts, dropped = check_fact_ranges(result.spec_facts)
    problems += dropped
    # A-06 F3 / Decisions 068, 087: citations from a blocked source or a URL outside the source's
    # `cited_hosts` are evidence only, never published values; anything else unreleasable here
    # would be a bug: drop it.
    evidence: dict[str, list[MatchedFact]] = {}
    shipping: list[MatchedFact] = []
    for mf in spec_facts:
        if gate(mf.source_id, mf.fact.source.url or ""):
            shipping.append(mf)
        elif has_citation(mf):
            evidence.setdefault(mf.fact.subject_id.root, []).append(mf)
    spec_facts = shipping
    for info in result.variants.values():
        info.source_ids = {s for s in info.source_ids if registry.releasable(s)}

    by_variant: dict[str, list[MatchedFact]] = {}
    for mf in spec_facts:
        by_variant.setdefault(mf.fact.subject_id.root, []).append(mf)
    # T-063 (Decision 034): a source ac_kw that a citation names as the optional charger
    # moves to ac_kw_optional before merging; without a citation nothing moves.
    by_variant, ac_routed, ac_route_problems = route_optional_ac(
        by_variant, evidence, policies.for_field("ac_kw")
    )
    problems += [
        Problem("merge", "-", "-", rp.variant_id, "ac_kw_optional", "", "kW", rp.message)
        for rp in ac_route_problems
    ]
    # T-057: usable kWh above the linked pack's gross never merges; it goes to conflicts.csv.
    by_variant, pack_conflicts = guard_usable_vs_pack(
        by_variant, links, {vid: info.generation_id for vid, info in result.variants.items()}
    )
    merged = {vid: merge_variant_facts(fs, policies) for vid, fs in by_variant.items()}
    # A-05 F9 / F7, A-06: contradicted, mixed-up, unbacked values and impossible pairs go to
    # review, not into rows (qa/value_guard.run_guards repeats them until nothing changes).
    pack_conflicts += run_guards(merged, by_variant, policies, evidence)
    fill_winning_values(pack_conflicts, merged)
    # Q-019 (a): generation averages may confirm a merged value, never set one (flag-gated).
    corro_facts, corro_dropped = check_fact_ranges(result.corroboration_facts)
    problems += corro_dropped
    corro_used, result.corroboration_log = apply_corroboration(
        merged, result.variants, corro_facts, policies
    )
    conflicts = conflict_rows(merged) + pack_conflicts
    nl_counts = aggregate_counts(result.count_facts, seed, "rdw", "NL")
    registrations = registration_entries(result.count_facts, seed)

    n = release or next_release_number(data_dir / "releases")
    inputs += [{"path": p} for p in links.inputs]
    # T-060: rows the file leaves without a pack or platform get one by rule (same generation,
    # capacity fit); everything else is reported in coverage.md and the run log.
    link_report = apply_rule_links(
        links,
        {vid: info.generation_id for vid, info in result.variants.items()},
        {vid: _merged_number(merged.get(vid, {}), "battery_kwh_net") for vid in result.variants},
    )
    inherited = {
        vid: inherited_for(
            links,
            vid,
            info.generation_id,
            {f: mg.value for f, mg in merged.get(vid, {}).items()},
        )
        for vid, info in result.variants.items()
    }
    rows, row_problems = build_rows(
        result.variants,
        merged,
        seed,
        nl_counts,
        today,
        n,
        policies=policies,
        inherited=inherited,
        registrations=registrations,
        citations=citation_values(evidence, by_variant),
    )
    for row in rows:
        finish_voltage(links, row, row.get("platform_id"))
        if links.taxonomy is None:
            # Ids cannot be checked without the taxonomy files: do not publish them.
            for f in ("chemistry_id", "cooling_id"):
                row.pop(f, None)
                row["provenance"].pop(f, None)
    problems += row_problems
    # T-111 (A-35 B4): implausible values go to review, out of the rows, before anything is
    # derived from the rows (matrix, shortlist, used prices).
    from ev_pipeline.qa.plausibility import WITHHOLD, apply_gate
    from ev_pipeline.qa.plausibility import load_config as load_plausibility

    plaus = apply_gate(rows, load_plausibility())
    conflicts_plausibility = plaus.review_rows

    all_facts = spec_facts + result.count_facts + corro_used
    sources: dict[str, dict[str, Any]] = {}
    for mf in all_facts:
        sources.setdefault(mf.source_id, mf.fact.source.model_dump(mode="json", exclude_none=True))
    if any(ESTIMATE_SOURCE in p["source_ids"] for r in rows for p in r["provenance"].values()):
        est = registry.source_object(ESTIMATE_SOURCE) or {
            "id": ESTIMATE_SOURCE,
            "name": "EV Finder estimate models",
            "licence": "CC-BY-4.0",
        }
        sources.setdefault(ESTIMATE_SOURCE, est)
    # T-059: Wikidata years corroborate generations; RDW APK defects -> known_issues.
    years = corroborate_years(result.year_records, seed)
    generations = _generation_dicts(seed)
    for g in generations:
        if g["id"] in years.by_generation:
            g["years_corroboration"] = years.by_generation[g["id"]]
    for sid, src in years.sources.items():
        sources.setdefault(sid, src)
    defects = read_defects(data_dir / "staging")
    if defects:
        inputs.append({"path": str(data_dir / "staging" / "rdw-defects.defects.jsonl"),
                       "records": len(defects)})  # fmt: skip
    known = build_known_issues(
        defects, seed, {r["generation_id"] for r in rows}, registry.releasable,
        result.scoped_aliases,
    )  # fmt: skip
    if known.source is not None:
        sources.setdefault(known.source["id"], known.source)
    catalogue = {
        "release": n,
        "generated_at": now.isoformat(timespec="seconds"),
        "sources": [sources[k] for k in sorted(sources)],
        "generations": generations,
        "rows": rows,
        **catalogue_parts(links),
    }
    if known.section is not None:
        catalogue["known_issues"] = known.section
    # Optional taxonomy tables (T-024, T-019): only next to the base four, which Taxonomy requires.
    optional = load_optional_taxonomy(data_dir, registry.reason_blocked)
    taxonomy_errs: list[str] = []
    if "taxonomy" in catalogue and optional.tables:
        catalogue["taxonomy"] = {**catalogue["taxonomy"], **optional.tables}
        inputs += [{"path": p} for p in optional.inputs]
        taxonomy_errs = optional_taxonomy_errors(optional.tables, set(links.platforms))
    elif optional.tables:
        optional.held_back["(all)"] = {
            t: "base taxonomy files missing, so no Taxonomy object ships" for t in optional.tables
        }
        optional.tables = {}
    if links.packs and links.retrieved_at:
        sources.setdefault(links.source["id"], links.source)
        catalogue["sources"] = [sources[k] for k in sorted(sources)]
    charging = build_charging_stats(
        data_dir / "staging",
        registry,
        catalogue.get("taxonomy"),
        n,
        catalogue["generated_at"],
        manual_dir=data_dir / "manual" / "charging",  # T-025: staff figures, WS3 writes
    )
    inputs += charging.inputs
    from ev_pipeline.release.towns import build_towns

    towns = build_towns(data_dir / "staging", registry, n, catalogue["generated_at"])
    inputs += towns.inputs
    facts = [_fact_dict(mf) for mf in all_facts]
    pfacts = pack_facts(links)
    facts += pfacts
    from ev_pipeline.derive.consumption import build_matrix

    # Rows whose WLTP / usable kWh / consumption the gate withheld get no range estimate:
    # no matrix entry, so no winter range and no derived shortlist values (PR #91 review).
    no_range = plaus.range_withheld
    matrix = build_matrix(
        [r for r in rows if r["variant_id"] not in no_range],
        facts,
        data_dir / "staging",
        registry.releasable,
        {s["id"]: s for s in catalogue["sources"]},
        n,
        catalogue["generated_at"],
        taxonomy_dir=data_dir / "taxonomy",
    )
    inputs += matrix.inputs
    # T-072: winter range on each row, same numbers the shortlist scores with.
    from ev_pipeline.derive.winter import attach_winter_range, band_labels

    winter_log = attach_winter_range(
        rows, matrix.document, band_labels=band_labels(data_dir / "taxonomy")
    )
    from ev_pipeline.derive.shortlist import build_shortlist

    shortlist = build_shortlist(rows, matrix.document, data_dir, n, catalogue["generated_at"])
    inputs += shortlist.inputs
    from ev_pipeline.derive.used_price import build_used_prices

    used = build_used_prices(
        rows,
        facts,
        [mf.year for mf in all_facts] + [None] * len(pfacts),
        data_dir,
        n,
        catalogue["generated_at"],
    )
    inputs += used.inputs
    images, images_log = attach_images(catalogue, data_dir, today)
    # T-149: popularity per generation from this release's own registration facts.
    from ev_pipeline.derive.popularity import attach_popularity

    popularity_log, pop_inputs = attach_popularity(catalogue, config_dir(data_dir), data_dir)
    inputs += pop_inputs
    if images_log.get("photos_file"):
        inputs.append(
            {"path": str(data_dir / "images" / "photos.yaml"), **images_log["photos_file"]}
        )

    for inp in inputs:
        inp["path"] = log_path(inp["path"], data_dir)

    errors = (
        schema_errors(catalogue, facts)
        + provenance_errors(rows)
        + excluded_source_errors(catalogue, facts, registry.releasable)
        + licence_errors(catalogue["sources"])
        + id_errors(links, catalogue)
        + taxonomy_errs
        + enum_fact_errors(facts)
        + section_gate_errors(catalogue, charging.document, registry.releasable)
    )
    if errors:
        raise ReleaseError("release failed validation:\n  " + "\n  ".join(errors[:50]))

    prev = None
    prev_nums = [x for x in existing_releases(data_dir / "releases") if x < n]
    if prev_nums:
        prev_path = data_dir / "releases" / str(prev_nums[-1]) / "catalogue.json"
        if not prev_path.exists() and (prev_path.parent / "manifest.json").exists():
            # T-064: the previous release lives outside git; fetch it by manifest so the diff
            # (and the >15 % / drop review rules) compare against real data, never nothing.
            from ev_pipeline.release.publish import PublishError, ensure_local

            try:
                ensure_local(
                    data_dir,
                    prev_nums[-1],
                    only=frozenset({"catalogue.json", CHARGING_STATS_FILE, "retired_ids.json"}),
                )
            except PublishError as e:
                raise ReleaseError(f"previous release {prev_nums[-1]} unavailable: {e}") from e
        if prev_path.exists():
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
    prev_charging = None
    if prev_nums:
        cs_path = data_dir / "releases" / str(prev_nums[-1]) / CHARGING_STATS_FILE
        if cs_path.exists():
            prev_charging = json.loads(cs_path.read_text(encoding="utf-8"))
    from ev_pipeline.release.retired import FILE_NAME as RETIRED_FILE
    from ev_pipeline.release.retired import compute_retired, has_catalogue_field, load_hand_kept

    prev_retired: dict[str, str | None] = dict((prev or {}).get("retired_ids") or {})
    if prev_nums:
        rp = data_dir / "releases" / str(prev_nums[-1]) / RETIRED_FILE
        if rp.exists():
            prev_retired.update(json.loads(rp.read_text(encoding="utf-8")).get("retired_ids") or {})
    try:
        hand_kept = load_hand_kept(data_dir / "seed")
    except ValueError as e:
        raise ReleaseError(str(e)) from e
    retired = compute_retired(
        prev, prev_retired, {str(r["variant_id"]) for r in catalogue["rows"]}, hand_kept
    )
    if retired.ids and has_catalogue_field(_schema()):
        catalogue["retired_ids"] = retired.ids
    charging_review = charging_review_rows(prev_charging if prev_nums else None, charging.document)
    charging.log["review_rows"] = len(charging_review)
    diff = compute_diff(prev, catalogue)
    unmatched = unmatched_rows(result)
    res = ReleaseResult(
        release=n,
        catalogue=catalogue,
        facts=facts,
        fact_years=[mf.year for mf in all_facts] + [None] * len(pfacts),
        diff=diff,
        match=result,
        problems=problems,
        unmatched_count=len(result.unmatched) + sum(result.other_makes.values()),
        inputs=inputs,
        unmatched_rows=unmatched,
        conflicts=conflicts + conflicts_plausibility,
        gated=gated,
        taxonomy_tables=optional.counts(),
        taxonomy_held_back=optional.held_back,
        charging_stats=charging.document,
        charging_review=charging_review,
        retired_ids=retired.ids,
        towns=towns.documents,
        consumption=matrix.document,
        shortlist=shortlist.document,
        shortlist_backtest=shortlist.backtest,
        used_prices=used.document,
        plausibility_withheld=[i.to_dict() for i in plaus.issues if i.action == WITHHOLD],
        image_files=images,
        sections={
            "epa_range_km": epa_summary(rows),
            "generation_years": years.log,
            "known_issues": known.log,
            "charging_stats": charging.log,
            "towns": towns.log,
            "consumption_matrix": matrix.log,
            "retired_ids": retired.log,
            "shortlist_scores": shortlist.log,
            "used_prices": used.log,
            "images": images_log,
            "popularity": popularity_log,
            "real_range_winter_km": winter_log,
            "plausibility": plaus.log(),
            "pack_links": link_coverage(link_report),
            "ac_kw_optional": {
                "routed": [asdict(r) for r in ac_routed],
                "problems": [asdict(r) for r in ac_route_problems],
            },
        },
    )
    raw = catalogue_bytes(catalogue)
    res.catalogue_bytes = len(raw)
    res.catalogue_gzip_bytes = len(gzip.compress(raw, mtime=0))
    return res


def section_gate_errors(
    catalogue: dict[str, Any], charging: dict[str, Any] | None, releasable: Any
) -> list[str]:
    """T-059 last guard: the known_issues source, generation year checks and every charging
    stat come from a releasable source (aliases resolve through data/sources.yaml)."""
    errors: list[str] = []
    ki = catalogue.get("known_issues")
    if ki is not None and not releasable(ki["source_id"]):
        errors.append(f"known_issues uses blocked source {ki['source_id']}")
    for g in catalogue.get("generations", []):
        for c in (g.get("years_corroboration") or {}).get("checks", []):
            if not releasable(c["source_id"]):
                errors.append(f"{g['id']}: years_corroboration uses blocked {c['source_id']}")
    for s in (charging or {}).get("sources", []):
        if not releasable(s["id"]):
            errors.append(f"charging_stats lists blocked source {s['id']}")
    bad = Counter(
        st["source_id"]
        for st in (charging or {}).get("stats", [])
        if not releasable(st["source_id"])
    )
    errors += [f"charging_stats: {k} rows from blocked {s}" for s, k in sorted(bad.items())]
    return errors


def epa_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """EPA range rows (T-059): how many, and how many have a second agreeing EPA source."""
    out = Counter()
    for r in rows:
        p = (r.get("provenance") or {}).get("epa_range_km")
        if r.get("epa_range_km") is None or p is None:
            continue
        src = set(p.get("source_ids") or [])
        out["rows"] += 1
        out["with_fueleconomy"] += "fueleconomy" in src
        out["fueleconomy_only"] += src == {"fueleconomy"}
        if p.get("agreeing_sources", 1) >= 2:
            out["two_plus_agreeing"] += 1
            out["second_source_via_fueleconomy"] += "fueleconomy" in src
    return dict(sorted(out.items()))


CONFLICT_COLUMNS = [
    "variant_id",
    "field",
    "source_id",
    "value",
    "unit",
    "winning_value",
    "tolerance",
    "fact_id",
]


def conflict_rows(merged: dict[str, dict[str, Merged]]) -> list[dict[str, Any]]:
    """Facts outside the field tolerance of the winning value. Never averaged in."""
    out = []
    for vid in sorted(merged):
        for fname, mg in merged[vid].items():
            for c in mg.conflicts:
                out.append(
                    {
                        "variant_id": vid,
                        "field": fname,
                        "source_id": c.source_id,
                        "value": c.fact.value,
                        "unit": c.fact.unit,
                        "winning_value": mg.value,
                        "tolerance": mg.tolerance,
                        "fact_id": c.fact.id,
                    }
                )
    return out


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def write_conflicts(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CONFLICT_COLUMNS)
        w.writeheader()
        w.writerows(rows)


COVERAGE_BUCKETS = ("2+ agreeing sources", "1 source", "estimate only", "missing")


def coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per row field: how many variants have 2+ agreeing sources, 1, an estimate, nothing."""
    out: dict[str, dict[str, int]] = {}
    for f in ROW_NUMBER_FIELDS:
        c = dict.fromkeys(COVERAGE_BUCKETS, 0)
        for r in rows:
            p = (r.get("provenance") or {}).get(f)
            if r.get(f) is None or p is None:
                c["missing"] += 1
            elif p.get("estimate"):
                c["estimate only"] += 1
            elif p.get("agreeing_sources", 1) >= 2:
                c["2+ agreeing sources"] += 1
            else:
                c["1 source"] += 1
        out[f] = c
    return out


def coverage_md(res: ReleaseResult) -> str:
    rows = res.catalogue["rows"]
    n = len(rows) or 1
    lines = [
        f"# Coverage, release {res.release}",
        "",
        f"{len(rows)} variants. Share of variants per field (count in brackets). 'estimate only'"
        " = our model or ratio, no source; derived values count by their weakest input.",
        "",
        "| Field | " + " | ".join(COVERAGE_BUCKETS) + " |",
        "|---|" + "---|" * len(COVERAGE_BUCKETS),
    ]
    for f, c in coverage(rows).items():
        cells = [f"{100 * c[b] / n:.0f}% ({c[b]})" for b in COVERAGE_BUCKETS]
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    lines += pack_links_md(res.sections.get("pack_links"))
    lines += sections_md(res.sections)
    from ev_pipeline.derive.shortlist import coverage_lines

    lines += coverage_lines(res.sections.get("shortlist_scores") or {})
    from ev_pipeline.derive.used_price import coverage_lines as used_price_lines

    lines += used_price_lines(res.sections.get("used_prices") or {})
    return "\n".join(lines) + "\n"


def pack_links_md(cov: dict[str, Any] | None) -> list[str]:
    """coverage.md lines for battery pack / platform links per row (T-060)."""
    if not cov:
        return []
    n = cov["rows"] or 1
    lines = [
        "",
        "## Battery pack and platform links",
        "",
        "Per row: linked in data/seed/variant_links.yaml, linked by rule (same generation;"
        " for packs, usable kWh fits exactly one of the generation's packs), or missing.",
        "",
        "| Link | variant_links.yaml | rule | missing |",
        "|---|---|---|---|",
    ]
    for key in ("battery_pack_id", "platform_id"):
        c = cov[key]
        cells = [f"{100 * c[b] / n:.0f}% ({c[b]})" for b in ("file", "rule", "missing")]
        lines.append(f"| {key} | " + " | ".join(cells) + " |")
    if cov["unlinked"]:
        lines += ["", f"Rows missing a link ({len(cov['unlinked'])}):", ""]
        lines += [f"- `{u['variant_id']}`: {u['reason']}" for u in cov["unlinked"]]
    return lines


def sections_md(sections: dict[str, Any]) -> list[str]:
    """coverage.md lines for the T-059 sections (EPA, generation years, known issues, charging)."""
    if not sections:
        return []
    epa = sections.get("epa_range_km") or {}
    gy = sections.get("generation_years") or {}
    ki = sections.get("known_issues") or {}
    cs = sections.get("charging_stats") or {}
    lines = [
        "",
        "## Other sections",
        "",
        f"- **EPA range** (`epa_range_km`, compared with EPA figures only): {epa.get('rows', 0)}"
        f" variants; {epa.get('two_plus_agreeing', 0)} with 2+ agreeing sources, of which"
        f" {epa.get('second_source_via_fueleconomy', 0)} through fueleconomy.gov.",
        f"- **Generation years vs Wikidata** (corroboration only, +/-1 year):"
        f" {gy.get('generations_checked', 0)} generations checked,"
        f" {gy.get('generations_corroborated', 0)} corroborated; {gy.get('agree', 0)} of"
        f" {gy.get('checks', 0)} years agree.",
    ]
    if ki.get("status") == "shipped":
        lines.append(
            f"- **Known issues** (RDW APK defects, NL): {ki['generations']} generations,"
            f" {ki['cohorts']} first-registration-year cohorts ({ki['cohorts_few_reports']}"
            f" marked few reports), {ki['codes']} defect codes."
        )
    else:
        lines.append(f"- **Known issues**: not shipped ({ki.get('status', 'no input')}).")
    for name, f in sorted((cs.get("files") or {}).items()):
        state = f"gated: {f['gated']}" if f.get("gated") else f"{f['shipped']} rows shipped"
        lines.append(f"- **Charging stats** `{name}`: {f['rows_in']} rows in, {state}.")
    cm = sections.get("consumption_matrix") or {}
    if cm.get("status") == "shipped":
        rungs = ", ".join(f"{k} {v}" for k, v in (cm.get("cells_by_rung") or {}).items())
        lines.append(
            f"- **Consumption matrix** (Trip fit, all estimates): {cm['variants']} variants"
            f" ({cm['variants_skipped']} without a WLTP or test figure), cells by rung: {rungs};"
            f" {cm['tests_used']} tests; {cm['gzip_bytes'] / 1024:.0f} KB gzip."
        )
    tw = sections.get("towns") or {}
    if tw.get("status") == "shipped":
        n_towns = sum(v for k, v in tw.items() if k.startswith("towns "))
        lines.append(
            f"- **Towns + climate** (GeoNames, Meteostat): {n_towns} towns,"
            f" {tw.get('with climate', 0)} with January climate"
            f" ({tw.get('climate without P10', 0)} without P10),"
            f" {tw.get('no station in range', 0)} without a station in range."
        )
    if cs.get("review_rows"):
        lines.append(
            f"- **Charging stats to review**: {cs['review_rows']} figures (step over 15 %, fall,"
            " revision or gone since the last release) in `data/review/charging_changes.csv`."
        )
    return lines


# --- writing -----------------------------------------------------------------------------


def catalogue_bytes(catalogue: dict[str, Any]) -> bytes:
    return json.dumps(catalogue, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _flat_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    countries = sorted({cc for r in rows for cc in (r.get("price_new") or {})})
    out = []
    for r in rows:
        flat = {
            k: v for k, v in r.items() if k not in ("price_new", "change_markers", "provenance")
        }
        for cc in countries:
            money = (r.get("price_new") or {}).get(cc)
            flat[f"price_new_{cc.lower()}"] = money["amount"] if money else None
            flat[f"price_new_{cc.lower()}_currency"] = money["currency"] if money else None
        flat["change_markers_json"] = json.dumps(r.get("change_markers") or [], ensure_ascii=False)
        flat["provenance_json"] = json.dumps(r["provenance"], separators=(",", ":"))
        out.append(flat)
    return out


def _flat_facts(facts: list[dict[str, Any]], years: list[int | None]) -> list[dict[str, Any]]:
    out = []
    for f, y in zip(facts, years, strict=True):
        v = f["value"]
        num = isinstance(v, int | float) and not isinstance(v, bool)
        out.append(
            {
                "id": f["id"],
                "subject_type": f["subject_type"],
                "subject_id": f["subject_id"],
                "field": f["field"],
                "value_num": float(v) if num else None,
                "value_text": None if num else str(v),
                "unit": f["unit"],
                "country": f.get("country"),
                "source_id": f["source"]["id"],
                "source_name": f["source"]["name"],
                "source_licence": f["source"]["licence"],
                "source_url": f["source"].get("url"),
                "source_record": f.get("source_record"),
                "retrieved_at": f["retrieved_at"],
                "confidence": f["confidence"],
                "record_year": y,
            }
        )
    return out


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def release_readme(res: ReleaseResult) -> str:
    cat = res.catalogue
    rows = cat["rows"]
    tiers = Counter(r["quality_tier"] for r in rows)
    rungs = Counter(r.get("real_range_rung") or "none" for r in rows)
    lines = [
        f"# EV Finder catalogue release {res.release}",
        "",
        f"Generated {cat['generated_at']} by `ev release`. Data licence: CC BY 4.0"
        " (see DATA_LICENSE.md); third-party inputs keep their own licences, listed below.",
        "",
        "## Counts",
        "",
        f"- Variants (rows): {len(rows)}",
        f"- Generations with rows: {len({r['generation_id'] for r in rows})}"
        f" of {len(cat['generations'])} in the seed",
        f"- Facts: {len(res.facts)}",
        "- Quality tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(tiers.items())),
        "- Real-range rungs: " + ", ".join(f"{k} {v}" for k, v in sorted(rungs.items())),
        f"- Changes vs previous: +{res.diff['counts']['added']} / -{res.diff['counts']['removed']}"
        f" / ~{res.diff['counts']['changed']}",
        "",
        "## Sources and licences",
        "",
        "| Source | Licence | Attribution |",
        "|---|---|---|",
    ]
    for s in cat["sources"]:
        attribution = s.get("attribution") or s["name"]
        lines.append(f"| {s['id']} ({s['name']}) | {s['licence']} | {attribution} |")
    lines += [
        "",
        "## Attribution",
        "",
        *[
            f"- Contains data from {s['name']}"
            + (f" ({s['url']})" if s.get("url") else "")
            + f", licensed {s['licence']}."
            + (f" {s['attribution']}" if s.get("attribution") else "")
            for s in cat["sources"]
        ],
        "",
        "## Caveats",
        "",
        "- Real-range figures on the `body-ratio` rung are PROVISIONAL generic ratios"
        " (mild-weather mixed driving), not measurements.",
        "- `seed-manual` values are hand-entered and unchecked (confidence low).",
        "- `registered_count_nl` is per generation: every variant of a generation shows the"
        " same RDW total (also in `registrations.NL`, kind fleet).",
        "- `registrations` holds official counts per country, one per source and period:"
        " `fleet` = cars on the road (RDW NL, DfT UK), `new_registrations` = first registrations"
        " in the period (KBA DE year-to-date, EEA NL/DE/FR/BE per year). They are never added"
        " together. `level: model` (DfT has no model year) repeats the whole model's count on"
        " every generation.",
        "- Charge curves from KilowattApp are `estimated` (upstream does not say how they were"
        " obtained); km-in-N-minutes also uses an estimated motorway consumption.",
        "- `shortlist_scores.json` is editorial: one owner's selection rules"
        " (data/editorial/shortlist_rules.yaml) applied to our own fields. Opinion, not fact.",
        "- `used_prices.json`: method `model` bands are estimates (list price at registration"
        " x share of value kept at that age, research/R-40), `samples: 0`. Asking prices, not"
        " transaction prices.",
        "",
    ]
    from ev_pipeline.derive.shortlist import readme_lines

    lines += readme_lines(res.shortlist_backtest)
    return "\n".join(lines)


def write_latest(releases: Path, n: int) -> None:
    """Point `latest` at release n atomically: write a temp file, then rename over it, so a
    reader sees the old number or the new one, never an empty file (addendum 6 P2)."""
    tmp = releases / f".latest.tmp-{os.getpid()}"
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(f"{n}\n")
        fh.flush()
        os.fsync(fh.fileno())  # A-05 L2: the bytes are on disk before the rename
    os.replace(tmp, releases / "latest")
    fsync_dir(releases)  # ...and the rename itself survives a power loss


def fsync_dir(path: Path) -> None:
    """fsync a directory so a rename inside it is durable (no-op where unsupported)."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return  # e.g. Windows cannot open directories
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _default_extras(res: ReleaseResult, data_dir: Path) -> dict[str, Any]:
    """sources.json (source health, addendum 6 P3) for releases made by plain `ev release`."""
    from ev_pipeline.health.state import release_sources_doc
    from ev_pipeline.refresh.plan import registry_entries

    return {
        "sources.json": release_sources_doc(
            data_dir, res.catalogue, registry_entries(data_dir), res.charging_stats
        )
    }


def write_release(res: ReleaseResult, data_dir: Path, extras: dict[str, Any] | None = None) -> Path:
    """`extras`: more JSON files for the release folder (name -> document), written before QA
    so they move into place with everything else. Default: sources.json."""
    releases = data_dir / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    final = releases / str(res.release)
    if final.exists():
        raise ReleaseError(f"release folder already exists: {final}")
    tmp = releases / f".tmp-{res.release}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    (tmp / "catalogue.json").write_bytes(catalogue_bytes(res.catalogue))
    _write_parquet(tmp / "catalogue.parquet", _flat_rows(res.catalogue["rows"]))
    _write_parquet(tmp / "facts.parquet", _flat_facts(res.facts, res.fact_years))
    (tmp / "diff.json").write_text(
        json.dumps(res.diff, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (tmp / "README.md").write_text(release_readme(res), encoding="utf-8")
    (tmp / "coverage.md").write_text(coverage_md(res), encoding="utf-8")
    (tmp / "run_log.json").write_text(
        json.dumps(run_log(res, "published"), indent=1) + "\n", encoding="utf-8"
    )
    if res.charging_stats is not None:  # T-059, Decision 012: aggregates only
        (tmp / CHARGING_STATS_FILE).write_text(
            json.dumps(res.charging_stats, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if res.retired_ids and "retired_ids" not in res.catalogue:  # T-062, until the schema has it
        from ev_pipeline.release.retired import FILE_NAME as RETIRED_FILE

        (tmp / RETIRED_FILE).write_text(
            json.dumps(
                {"release": res.release, "generated_at": res.catalogue["generated_at"],
                 "retired_ids": dict(sorted(res.retired_ids.items()))},
                indent=1, ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )  # fmt: skip
    if res.consumption is not None:  # T-033: static JSON for the Trip fit browser model
        from ev_pipeline.derive.consumption import FILE_NAME as MATRIX_FILE

        (tmp / MATRIX_FILE).write_text(
            json.dumps(res.consumption, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if res.shortlist is not None:  # T-069: editorial scores for the hero shortlist
        from ev_pipeline.derive.shortlist import FILE_NAME as SHORTLIST_FILE

        (tmp / SHORTLIST_FILE).write_text(
            json.dumps(res.shortlist, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if res.used_prices is not None:  # T-081: used price bands for the hero budget filter
        from ev_pipeline.derive.used_price import FILE_NAME as USED_PRICES_FILE

        (tmp / USED_PRICES_FILE).write_text(
            json.dumps(res.used_prices, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if res.towns:  # T-034: one file per country, loaded on demand by the trip module
        (tmp / "towns").mkdir()
        for cc, doc in sorted(res.towns.items()):
            (tmp / "towns" / f"{cc}.json").write_text(
                json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    for rel_path, data in sorted(res.image_files.items()):
        dest = tmp / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    for name, doc in (_default_extras(res, data_dir) if extras is None else extras).items():
        if "/" in name or name.startswith("."):
            raise ReleaseError(f"bad extra file name: {name!r}")
        (tmp / name).write_text(
            json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    # Release QA + back-test (qa.json, qa.md) and open data bundle (open/); a blocking QA
    # failure raises ReleaseError and removes tmp (R-05 §1, T-035, Decision 016).
    from ev_pipeline.qa.release_step import finish_release

    finish_release(res.catalogue, res.facts, tmp, data_dir, res.plausibility_withheld)
    # T-064: per-generation split + manifest.json (sizes, sha256) before the folder goes live.
    from ev_pipeline.release.publish import PublishError, load_config, package

    try:
        package(tmp, load_config(data_dir))
    except PublishError as e:
        shutil.rmtree(tmp)
        raise ReleaseError(f"packaging failed: {e}") from e
    tmp.rename(final)
    write_latest(releases, res.release)
    review = data_dir / "review"
    previous_status = snapshot_statuses(review)  # P7: keep staff decisions
    write_unmatched(review / "unmatched.csv", res.unmatched_rows)
    write_validation(review / "validation.csv", res.problems)
    write_conflicts(review / "conflicts.csv", res.conflicts)
    write_csv(review / CHARGING_REVIEW_FILE, CHARGING_REVIEW_COLUMNS, res.charging_review)
    annotate_review_dir(
        review, previous_status, date.fromisoformat(res.catalogue["generated_at"][:10])
    )
    res.out_dir = final
    return final


def summary(res: ReleaseResult) -> dict[str, Any]:
    rows = res.catalogue["rows"]
    return {
        "release": res.release,
        "rows": len(rows),
        "generations_with_rows": len({r["generation_id"] for r in rows}),
        "facts": len(res.facts),
        "sources": [s["id"] for s in res.catalogue["sources"]],
        "matched_records": res.match.matched_records,
        "excluded_records": dict(res.match.excluded),
        "count_only_spec_records_skipped": dict(res.match.count_only_skipped),
        "match_flags": {
            "scoped_aliases": res.match.scoped_aliases,
            "eea_corroboration": res.match.eea_corroboration,
        },
        "corroboration": {
            "skipped": dict(res.match.corroboration_skipped),
            **res.match.corroboration_log,
        },
        "attach_only_records_attached": dict(res.match.attached),
        "ignored_fields": dict(res.match.ignored_fields),
        "registrations_coverage": registrations_coverage(rows),
        "dc_curve_status": dict(Counter(r.get("dc_curve_status") or "none" for r in rows)),
        "price_new_coverage": dict(
            sorted(Counter(cc for r in rows for cc in (r.get("price_new") or {})).items())
        ),
        "year_bands": res.match.year_bands,
        "unmatched_records": res.unmatched_count,
        "unmatched_seed_makes": len(res.match.unmatched),
        "validation_problems": len(res.problems),
        "conflicts": len(res.conflicts),
        "gated_sources": res.gated,
        "real_range_rungs": dict(Counter(r.get("real_range_rung") or "none" for r in rows)),
        "quality_tiers": dict(Counter(r["quality_tier"] for r in rows)),
        "optional_taxonomy_rows": res.taxonomy_tables,
        "taxonomy_rows_held_back": res.taxonomy_held_back,
        "sections": res.sections,
        "catalogue_json_bytes": res.catalogue_bytes,
        "catalogue_json_gzip_bytes": res.catalogue_gzip_bytes,
        "diff": res.diff["counts"],
    }


def registrations_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per country: variants with any count, and per source+kind how many variants have one."""
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        for cc, entries in (r.get("registrations") or {}).items():
            c = out.setdefault(cc, {"variants": 0})
            c["variants"] += 1
            for key in sorted({f"{e['source_id']}:{e['kind']}:{e['level']}" for e in entries}):
                c[key] = c.get(key, 0) + 1
    return dict(sorted(out.items()))


def run_log(res: ReleaseResult, outcome: str) -> dict[str, Any]:
    return {
        "step": "release",
        "at": res.catalogue["generated_at"],
        "inputs": res.inputs,
        "outputs": summary(res),
        "outcome": outcome,
    }


def release_cmd(
    dry_run: bool,
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
    today: date | None = None,
) -> int:
    data_dir = data_dir or default_data_dir()
    if today is not None and now is None:
        now = datetime(today.year, today.month, today.day, tzinfo=UTC)
    try:
        res = build_release(data_dir, now=now)
    except ReleaseError as exc:
        print(f"release failed: {exc}", file=sys.stderr)
        return 1
    if dry_run:
        print(json.dumps(run_log(res, "dry-run (nothing written)"), indent=1))
        return 0
    try:
        out = write_release(res, data_dir)
    except ReleaseError as exc:
        print(f"release failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(run_log(res, f"published {log_path(out, data_dir)}"), indent=1))
    return 0
