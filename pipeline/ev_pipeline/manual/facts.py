"""Manual facts: hand-entered, cited values in data/manual/<topic>/*.yaml (addendum 6, P7).

File format (`schema: manual-facts/v1`)::

    schema: manual-facts/v1
    entered_by: menno            # default for every fact in the file (optional)
    fixture: false               # true = example/test file, never loaded by a release
    source: manual               # optional data/sources.yaml id for every fact in the file
                                 # (default `manual`); e.g. a third-party site with its own
                                 # status, so the licence gate decides per site (Decision 080)
    facts:
      - variant_id: vw-id3-pro-58kwh     # or generation_id (exactly one)
        field: warranty_years            # a schema FactField
        value: 8
        unit: years                      # must be the field's canonical unit
        country: NL                      # optional; required for price_new
        year: 2024                       # price_new only: the year the listed price applies to
                                         # (price list date / model year); without it the
                                         # used-price estimate cannot use the price (warning)
        source_url: https://...          # required, http(s)
        source_name: "VW NL warranty terms"   # optional label for the cited document
        retrieved: 2026-11-15            # required, ISO date, not in the future
        quote: "8 jaar of 160.000 km"    # quote and/or locator required
        locator: "p. 4, table 2"
        entered_by: menno                # required here or at file level
        confidence: medium               # high | medium | low
        claim: true                      # optional, default true (maker documents are claims)
        notes: "..."                     # optional
        source: cited-third-party        # optional, overrides the file's source for this fact

Every fact becomes a schema `Fact` with source id `manual` (or the fact's / file's `source`)
and is checked against the JSON Schema `Fact` def plus the extra rules above. The licence gate
decides per source. `manual` is releasable under Decision 068 (`use: cited-facts`): single
facts from maker documents. For such a source the fact's URL host must be in its
`cited_hosts` in data/sources.yaml (fixtures excepted); a press, dealer or review page is an
error until the fact names a blocked source (e.g. `cited-third-party`), so a third-party
figure can never ship as a maker fact. A `cited_hosts` entry is a host or a host/path prefix
(`url_matches`). The file or fact `source:` may only name an `access: manual` source, or a
source whose own `hosts` serve the fact's URL (on a shared host such as github.com: its
`cite_paths` only), so a third-party page can't borrow the id (and licence) of an open source
such as `rdw` or `openev`. Dot segments (also percent-encoded) never match a path prefix.

Folders whose name starts with `_` (e.g. `data/manual/_example/`) and files with
`fixture: true` are validated by `ev manual check` but never loaded by a release.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from ev_pipeline.match.matcher import CURRENCIES, MatchedFact, MatchResult, Problem
from ev_pipeline.match.seed import CANONICAL_UNITS, Seed
from ev_pipeline.release.gate import CITED_FACTS, Registry, url_matches
from ev_pipeline.release.validate import (
    _validator,
    in_range,
    range_reason,
    value_reason,
)
from ev_pipeline.schema_models import ChargeCurve, Confidence, Country, Fact, FactField

MANUAL_SOURCE_ID = "manual"
FORMAT = "manual-facts/v1"
DEFAULT_SOURCE_NAME = "Manual entries (hand-entered, cited by URL)"
DEFAULT_LICENCE = "none (individual facts cited by URL and date)"
# Above seed-manual (10) and below EEA (20) / OpenEV (30): a cited single fact beats an
# unchecked seed value; field_sources.yaml should list `manual` once it is releasable.
MANUAL_PRIORITY = 15

# Units for FactFields that CANONICAL_UNITS (seed) does not cover; schema fixtures use these.
EXTRA_UNITS: dict[str, str] = {
    "iso15118_20_support": "enum",
    "heat_pump": "enum",
    "drag_coefficient": "Cd",
    "frontal_area_m2": "m2",
    "kerb_mass_kg": "kg",
    "wheel_size_in": "in",
}
STRING_UNITS = {"id", "enum"}
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

FILE_KEYS = {"schema", "entered_by", "fixture", "facts", "notes", "source"}
FACT_KEYS = {
    "variant_id",
    "generation_id",
    "field",
    "value",
    "unit",
    "country",
    "year",
    "years",
    "source_url",
    "source_name",
    "retrieved",
    "quote",
    "locator",
    "entered_by",
    "confidence",
    "claim",
    "notes",
    "source",
}


def _years_span(raw: object, today: date) -> tuple[tuple[int, int | None] | None, str]:
    """`years: [from, to]` -> ((from, to), ''); to may be null (still built)."""

    def whole(v: object) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and 2000 <= v <= today.year + 1

    bad = (
        f"years must be [from, to]: whole years 2000-{today.year + 1}, to >= from or null"
        f" (still built), got {raw!r}"
    )
    if not isinstance(raw, list) or len(raw) != 2:
        return None, bad
    lo, hi = raw
    if not whole(lo) or not (hi is None or (whole(hi) and hi >= lo)):
        return None, bad
    return (lo, hi), ""


def expected_unit(fname: str) -> str | None:
    """The one unit a manual fact of this field may use (None = field not allowed)."""
    if fname == "price_new":
        return None  # a currency code, checked separately
    return CANONICAL_UNITS.get(fname) or EXTRA_UNITS.get(fname)


@dataclass
class ManualFact:
    fact: Fact
    path: str  # data/manual/<topic>/<file>.yaml (repo-relative)
    record_key: str
    entered_by: str
    quote: str | None = None
    locator: str | None = None
    notes: str | None = None
    year: int | None = None  # price_new: the year the price applies to (record year)
    # Generation facts only: model years [from, to] (to None = still built) the fact holds
    # for. It applies to the generation's variants whose years lie fully inside (WS3 ask,
    # Decision 059: e.g. Model 3 heat pump from MY2021). A variant that straddles the
    # boundary gets neither value: "not known" beats a wrong one.
    years: tuple[int, int | None] | None = None


@dataclass
class ManualIssue:
    path: str
    index: int | None  # position in `facts` (0-based), None for file-level problems
    record_key: str
    message: str
    subject_id: str = ""
    field: str = ""
    value: str = ""
    unit: str = ""
    warning: bool = False

    def text(self) -> str:
        where = self.path + (f" facts[{self.index}]" if self.index is not None else "")
        kind = "warning" if self.warning else "error"
        return f"{where}: {kind}: {self.message}"


@dataclass
class ManualLoad:
    facts: list[ManualFact] = field(default_factory=list)
    issues: list[ManualIssue] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # fixture/example files (release only)
    fixture_files: set[str] = field(default_factory=set)  # `_`-folders or `fixture: true`

    @property
    def errors(self) -> list[ManualIssue]:
        return [i for i in self.issues if not i.warning]


def _as_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def _url_ok(v: Any) -> bool:
    if not isinstance(v, str) or not v.strip() or any(c.isspace() for c in v.strip()):
        return False
    u = urlparse(v.strip())
    return u.scheme in ("http", "https") and bool(u.netloc)


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _value_problems(fname: str, value: Any, unit: str) -> list[str]:
    """Value checks that need the field: type per unit, enum values, plausible ranges."""
    out: list[str] = []
    if fname == "dc_curve":
        try:
            ChargeCurve.model_validate(value)
        except Exception as exc:
            out.append(f"dc_curve value is not a valid ChargeCurve: {str(exc)[:120]}")
        return out
    if unit in STRING_UNITS:
        if unit == "id" and not (isinstance(value, str) and ID_RE.match(value)):
            out.append(f"{fname} needs a taxonomy id (lowercase-hyphen), got {value!r}")
        if unit == "enum" and not isinstance(value, str):
            out.append(f"{fname} needs a text value, got {value!r}")
    elif fname == "drag_coefficient":
        pass  # value_reason covers numbers and "not-disclosed"
    elif isinstance(value, bool) or not isinstance(value, int | float):
        out.append(f"{fname} needs a number, got {value!r}")
        return out
    why = value_reason(fname, value)
    if why is not None:
        out.append(f"{fname} {why}")
    elif not in_range(fname, value):
        out.append(f"{fname} {range_reason(fname, value)}")
    return out


def _source_dict(
    registry: Registry | None, url: str, name: str | None, source_id: str = MANUAL_SOURCE_ID
) -> dict[str, Any]:
    entry = registry.sources.get(source_id) if registry is not None else None
    base = entry.name if entry is not None else DEFAULT_SOURCE_NAME
    licence = (entry.licence if entry is not None else DEFAULT_LICENCE) or DEFAULT_LICENCE
    src: dict[str, Any] = {
        "id": source_id,
        "name": f"{base}: {name}" if name else base,
        "url": url,
        "licence": licence.split("(")[0].strip() or licence,
    }
    return src


MANUAL_ACCESS = "manual"
# Hosts that serve many owners' content: a source's fetch `hosts` entry for one of these never
# lets a manual fact claim that source; only its `cite_paths` (its own repo or folder) do.
SHARED_HOSTS = frozenset(
    {
        "github.com",
        "raw.githubusercontent.com",
        "gitlab.com",
        "docs.google.com",
        "drive.google.com",
        "*.googleusercontent.com",
        "mb.cision.com",
        "cdn.uc.assets.prezly.com",
    }
)


def _source_claim_problems(registry: Registry | None, source_id: str, url: str) -> list[str]:
    """PR #80 review must-fix 1: a hand-entered fact may only name a hand-entry source
    (`access: manual`: manual, maker-docs, autotijd, cited-third-party), or a source whose own
    `hosts` serve the cited URL (an RDW page may say `source: rdw`). Otherwise a press or review
    figure could borrow an open source's id and licence and reach the release and the CC BY
    bundle. A source on a shared host (SHARED_HOSTS, e.g. github.com) matches only its
    `cite_paths`. Applies to fixtures too: there is no reason to test a laundered label."""
    if registry is None or not registry.loaded:
        return []
    entry = registry.sources.get(registry.canonical(source_id))
    if entry is None or entry.access == MANUAL_ACCESS:
        return []
    allowed = entry.cite_paths or tuple(h for h in entry.hosts if h not in SHARED_HOSTS)
    if any(url_matches(h, url) for h in allowed):
        return []
    host = (urlparse(url.strip()).hostname or "").lower()
    return [
        f"source {source_id!r} is not a hand-entry source (access: {entry.access or 'none'})"
        f" and source_url host {host!r} is not one of its hosts: a manual fact may name"
        " `manual`, `cited-third-party` or another `access: manual` source only"
    ]


def _cited_host_problems(
    registry: Registry | None, source_id: str, url: str, fixture: bool
) -> list[str]:
    """Decision 068: a `use: cited-facts` source ships without a licence, so each fact must
    cite one of its listed maker hosts or host paths (`url_matches`). Fixture files are exempt
    (never released)."""
    if fixture or registry is None or not registry.loaded:
        return []
    entry = registry.sources.get(registry.canonical(source_id))
    if entry is None or entry.use != CITED_FACTS:
        return []
    if any(url_matches(h, url) for h in entry.cited_hosts):
        return []
    host = (urlparse(url.strip()).hostname or "").lower()
    return [
        f"source_url {host!r} is not a maker host or path in `{entry.id}` cited_hosts"
        " (data/sources.yaml, Decision 068): add it there if this is the maker's own document,"
        " else give the fact a blocked source such as `source: cited-third-party`"
    ]


def parse_manual_file(
    path: Path,
    rel: str,
    topic: str,
    today: date,
    registry: Registry | None = None,
) -> tuple[list[ManualFact], list[ManualIssue], bool]:
    """Parse and validate one file. Returns (facts, issues, is_fixture)."""
    issues: list[ManualIssue] = []

    def file_issue(msg: str) -> None:
        issues.append(ManualIssue(rel, None, rel, msg))

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        file_issue(f"not valid YAML: {str(exc)[:160]}")
        return [], issues, False
    if not isinstance(data, dict):
        file_issue("top level must be a mapping with `schema` and `facts`")
        return [], issues, False
    fixture = data.get("fixture") is True
    for k in sorted(set(data) - FILE_KEYS):
        file_issue(f"unknown key {k!r}")
    if data.get("schema") != FORMAT:
        file_issue(f"schema must be {FORMAT!r}, got {data.get('schema')!r}")
    raw_facts = data.get("facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        file_issue("`facts` must be a non-empty list")
        return [], issues, fixture
    file_by = _text(data.get("entered_by"))
    source_id = MANUAL_SOURCE_ID
    if "source" in data:
        sid = _text(data.get("source"))
        if not sid or not ID_RE.match(sid):
            file_issue(f"source must be a data/sources.yaml id, got {data.get('source')!r}")
            return [], issues, fixture
        if registry is not None and registry.loaded and sid not in registry.sources:
            # Fail closed: an unregistered source could never be gated by its own status.
            file_issue(f"source {sid!r} is not in data/sources.yaml")
            return [], issues, fixture
        source_id = sid
    stem = f"{topic}/{path.stem}"
    validator = _validator("Fact")
    out: list[ManualFact] = []
    for i, raw in enumerate(raw_facts):
        if not isinstance(raw, dict):
            issues.append(ManualIssue(rel, i, f"{stem}#{i}", "each fact must be a mapping"))
            continue
        msgs: list[str] = []
        for k in sorted(set(raw) - FACT_KEYS):
            msgs.append(f"unknown key {k!r}")
        fact_source = source_id
        if "source" in raw:
            sid = _text(raw.get("source"))
            if not sid or not ID_RE.match(sid):
                msgs.append(f"source must be a data/sources.yaml id, got {raw.get('source')!r}")
            elif registry is not None and registry.loaded and sid not in registry.sources:
                msgs.append(f"source {sid!r} is not in data/sources.yaml")
            else:
                fact_source = sid
        vid, gid = _text(raw.get("variant_id")), _text(raw.get("generation_id"))
        if bool(vid) == bool(gid):
            msgs.append("give exactly one of variant_id or generation_id")
        subject_type = "variant" if vid else "generation"
        subject_id = vid or gid or ""
        fname = _text(raw.get("field")) or ""
        value = raw.get("value")
        unit = _text(raw.get("unit")) or ""
        country = _text(raw.get("country"))
        record_key = f"{stem}:{subject_id}:{fname}" + (f":{country}" if country else "")
        raw_year = raw.get("year")
        year: int | None = None
        warns: list[str] = []
        if raw_year is not None:
            if fname != "price_new":
                msgs.append("year is only for price_new (the year the price applies to)")
            elif isinstance(raw_year, bool) or not isinstance(raw_year, int):
                msgs.append(f"year must be a whole year, got {raw_year!r}")
            elif not 2000 <= raw_year <= today.year + 1:
                msgs.append(f"year {raw_year} is outside 2000-{today.year + 1}")
            else:
                year = raw_year
                record_key += f":{year}"
        elif fname == "price_new":
            warns.append(
                "price_new has no `year` (the price list's year): it is kept, but the used"
                " price estimate cannot use a list price without a year"
            )

        years: tuple[int, int | None] | None = None
        if raw.get("years") is not None:
            years, why = _years_span(raw.get("years"), today)
            if subject_type != "generation":
                msgs.append("years is only for generation facts (a variant has its own years)")
            elif why:
                msgs.append(why)
            elif years is not None:
                record_key += f":{years[0]}-{'' if years[1] is None else years[1]}"

        if fname not in {f.value for f in FactField}:
            msgs.append(f"unknown field {fname!r} (must be a schema FactField)")
        elif fname == "registered_count":
            msgs.append("registered_count comes from registers, not manual entry")
        elif value is None:
            msgs.append("value is required")
        elif fname == "price_new":
            if unit.upper() not in CURRENCIES or unit != unit.upper():
                msgs.append(
                    f"price_new unit must be a currency code ({', '.join(sorted(CURRENCIES))})"
                )
            if country is None:
                msgs.append("price_new needs a country")
            msgs += _value_problems(fname, value, unit) if not msgs else []
        else:
            want = expected_unit(fname)
            if want is None:
                msgs.append(f"no canonical unit for {fname}")
            elif unit != want:
                msgs.append(f"unit {unit!r} does not match {fname} (use {want!r})")
            else:
                msgs += _value_problems(fname, value, unit)
        if country is not None and country not in {c.value for c in Country}:
            msgs.append(f"country {country!r} unknown")

        url = raw.get("source_url")
        if not _url_ok(url):
            msgs.append("source_url is required and must be an http(s) URL")
        else:
            msgs += _source_claim_problems(registry, fact_source, str(url))
            msgs += _cited_host_problems(registry, fact_source, str(url), fixture)
        retrieved = _as_date(raw.get("retrieved"))
        if raw.get("retrieved") is None:
            msgs.append("retrieved date is required")
        elif retrieved is None:
            msgs.append(f"retrieved must be an ISO date (YYYY-MM-DD), got {raw.get('retrieved')!r}")
        elif retrieved > today:
            msgs.append(f"retrieved {retrieved} is in the future")
        quote, locator = _text(raw.get("quote")), _text(raw.get("locator"))
        if not quote and not locator:
            msgs.append("give a quote or a page locator")
        entered_by = _text(raw.get("entered_by")) or file_by
        if not entered_by:
            msgs.append("entered_by is required (on the fact or the file)")
        conf = _text(raw.get("confidence"))
        if conf not in {c.value for c in Confidence}:
            msgs.append(f"confidence must be high, medium or low, got {conf!r}")
        claim = raw.get("claim", True)
        if not isinstance(claim, bool):
            msgs.append("claim must be true or false")

        fact: Fact | None = None
        if not msgs:
            value_out = value
            if fname != "dc_curve" and isinstance(value, int) and not isinstance(value, bool):
                value_out = float(value)
            fd: dict[str, Any] = {
                "id": f"{fact_source}:{record_key}",
                "subject_type": subject_type,
                "subject_id": subject_id,
                "field": fname,
                "value": value_out,
                "unit": unit,
                "source": _source_dict(
                    registry, str(url).strip(), _text(raw.get("source_name")), fact_source
                ),
                "source_record": f"{rel}#{i}",
                "retrieved_at": retrieved.isoformat() if retrieved else "",
                "confidence": conf,
            }
            if country:
                fd["country"] = country
            if claim:
                fd["claim"] = True
            for e in validator.iter_errors(fd):
                path_s = "/".join(map(str, e.path))
                msgs.append(f"schema Fact {path_s or '(root)'}: {e.message[:160]}")
            if not msgs:
                try:
                    fact = Fact.model_validate(fd)
                except Exception as exc:
                    msgs.append(f"schema Fact: {str(exc)[:160]}")
        if msgs or fact is None:
            for m in msgs:
                issues.append(
                    ManualIssue(rel, i, record_key, m, subject_id, fname, str(value), unit)
                )
            continue
        for m in warns:
            issues.append(
                ManualIssue(
                    rel, i, record_key, m, subject_id, fname, str(value), unit, warning=True
                )
            )
        out.append(
            ManualFact(
                fact=fact,
                path=rel,
                record_key=record_key,
                entered_by=entered_by or "",
                quote=quote,
                locator=locator,
                notes=_text(raw.get("notes")),
                year=year,
                years=years,
            )
        )
    return out, issues, fixture


def _rel(path: Path, data_dir: Path) -> str:
    try:
        return str(Path("data") / path.resolve().relative_to(data_dir.resolve()))
    except ValueError:
        return path.name


# Topic folders with their own format and loader, not manual facts:
# prices/ = used price sample aggregates, read by derive/used_price.py (T-081, Decision 060).
OWN_LOADER_TOPICS = frozenset({"prices"})


def load_manual_dir(
    data_dir: Path,
    today: date,
    registry: Registry | None = None,
    *,
    for_release: bool = True,
) -> ManualLoad:
    """All data/manual/<topic>/*.yaml files. `for_release` skips `_`-folders and fixtures.

    Duplicate (source, subject, field, country, year) entries across files are errors: one
    hand-entered value per fact, source and year, so a second one has to replace the first, not
    compete with it.
    """
    res = ManualLoad()
    root = data_dir / "manual"
    if not root.is_dir():
        return res
    seen: dict[str, str] = {}
    for path in sorted([*root.glob("*/*.yaml"), *root.glob("*/*.yml"), *root.glob("*.yaml")]):
        rel = _rel(path, data_dir)
        if path.parent == root:
            res.issues.append(
                ManualIssue(rel, None, rel, "put manual files in a topic folder: manual/<topic>/")
            )
            continue
        topic = path.parent.name
        if topic in OWN_LOADER_TOPICS:
            continue
        example = topic.startswith("_")
        facts, issues, fixture = parse_manual_file(path, rel, topic, today, registry)
        if example or fixture:
            res.fixture_files.add(rel)
        if for_release and (example or fixture):
            res.skipped.append(rel)
            continue
        if example and not fixture:
            issues.append(ManualIssue(rel, None, rel, "files under _-folders need `fixture: true`"))
        res.files.append(rel)
        res.issues += issues
        for mf in facts:
            f = mf.fact
            # Per source (Decision 080): a held third-party value may sit next to the maker
            # value that replaces it; the licence gate decides which one ships.
            dup = (
                f"{f.source.id.root}|{f.subject_id.root}|{f.field.value}|"
                f"{f.country.value if f.country else ''}|{mf.year or ''}|{mf.years or ''}"
            )
            if dup in seen and not fixture:
                res.issues.append(
                    ManualIssue(
                        rel,
                        None,
                        mf.record_key,
                        f"duplicate of {seen[dup]} (same subject, field, country and year(s))",
                        f.subject_id.root,
                        f.field.value,
                    )
                )
                continue
            seen.setdefault(dup, mf.record_key)
            res.facts.append(mf)
    return res


def issue_problems(issues: list[ManualIssue]) -> list[Problem]:
    """Manual-file errors as validation.csv rows (stage `manual`)."""
    return [
        Problem(
            "manual",
            MANUAL_SOURCE_ID,
            i.record_key,
            i.subject_id,
            i.field,
            i.value,
            i.unit,
            f"{i.path}: {i.message}",
        )
        for i in issues
        if not i.warning
    ]


def attach_manual_facts(
    facts: list[ManualFact], result: MatchResult, seed: Seed
) -> tuple[list[MatchedFact], list[Problem]]:
    """Turn releasable manual facts into MatchedFacts on this release's variants.

    A generation fact applies to every variant of that generation (one copy each, id
    suffixed `@<variant id>`). Ids that this release does not have go to validation.csv.
    """
    by_gen: dict[str, list[str]] = {}
    for vid, info in sorted(result.variants.items()):
        by_gen.setdefault(info.generation_id, []).append(vid)
    out: list[MatchedFact] = []
    problems: list[Problem] = []

    def problem(mf: ManualFact, why: str) -> None:
        f = mf.fact
        problems.append(
            Problem(
                "manual",
                f.source.id.root,
                mf.record_key,
                f.subject_id.root,
                f.field.value,
                str(f.value),
                f.unit,
                why,
            )
        )

    for mf in facts:
        f = mf.fact
        sid = f.subject_id.root
        if f.subject_type.value == "variant":
            info = result.variants.get(sid)
            if info is None:
                problem(mf, "variant not in this release")
                continue
            gen = seed.generations.get(info.generation_id)
            out.append(
                MatchedFact(
                    f,
                    f.source.id.root,
                    MANUAL_PRIORITY,
                    mf.year,  # price_new: the year the price applies to (used price lookup)
                    info.generation_id,
                    gen.model_id if gen else None,
                    note=mf.notes,
                )
            )
            continue
        gen = seed.generations.get(sid)
        if gen is None:
            problem(mf, "generation not in the seed")
            continue
        vids = by_gen.get(sid, [])
        if not vids:
            problem(mf, "generation has no variants in this release")
            continue
        if mf.years is not None:
            lo, hi = mf.years
            vids = [
                v
                for v in vids
                if result.variants[v].years
                and min(result.variants[v].years) >= lo
                and (hi is None or max(result.variants[v].years) <= hi)
            ]
            if not vids:
                problem(
                    mf,
                    f"no variant of the generation lies fully inside years {lo}-{hi or ''}"
                    " (straddling variants get neither value)",
                )
                continue
        for vid in vids:
            fd = f.model_dump(mode="json", exclude_none=True)
            fd.update({"id": f"{f.id}@{vid}", "subject_type": "variant", "subject_id": vid})
            copy = Fact.model_validate(fd)
            out.append(
                MatchedFact(
                    copy,
                    f.source.id.root,
                    MANUAL_PRIORITY,
                    mf.year,
                    sid,
                    gen.model_id,
                    note=mf.notes,
                )
            )
    return out, problems


def gate_reason(registry: Registry) -> str | None:
    """Why manual facts may not reach a public release (None = releasable)."""
    return registry.reason_blocked(MANUAL_SOURCE_ID)
