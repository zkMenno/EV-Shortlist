"""Load the hand-curated seed: data/seed/models.yaml (+ optional data/seed/variants.yaml)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from ev_pipeline.match.normalise import key, tokens
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.schema_models import Confidence, FactField, Source

# Make spellings seen in registration data that the seed cannot know about. Keys are
# normalised (see normalise.key). Kept tiny on purpose: add a line when unmatched.csv shows one.
MAKE_ALIASES: dict[str, str] = {
    "vw": "volkswagen",
    "mercedesbenz": "mercedes",
    "vauxhall": "opel",
    "bmwi": "bmw",
    "teslamotors": "tesla",
    "mgroewe": "mg",  # KBA FZ10 files MG as "MG ROEWE"
    "opelvauxhall": "opel",  # KilowattApp
}

SEED_MANUAL_SOURCE_ID = "seed-manual"
# A-06 F3 / Decisions 068, 087: a seed `cited:` value is a fact from the document it cites,
# not hand-entered seed data, so it carries that document's source (`maker-docs` by default)
# unless the entry names another registered `source_id`. It goes through the licence gate and
# `cited_hosts` check like any other fact, never under the seed's CC BY licence.
CITED_DEFAULT_SOURCE_ID = "maker-docs"
CITED_SOURCE_NAMES = {"maker-docs": "Maker documents and price lists"}
CITED_LICENCE = "facts cited, no licence"


@dataclass
class SeedGeneration:
    id: str
    model_id: str
    name: str
    year_start: int
    year_end: int | None
    uncertain: bool = False
    notes: str | None = None
    change_markers: list[dict[str, Any]] = field(default_factory=list)

    def covers(self, year: int) -> bool:
        return self.year_start <= year and (self.year_end is None or year <= self.year_end)


@dataclass
class SeedModel:
    id: str
    make_id: str
    name: str
    segment: str | None
    body: str | None
    aliases: list[str]
    generations: list[SeedGeneration]
    # Names that start like this model but are a different car ("e-tron GT" vs "e-tron").
    # A record whose name contains one of these (as whole tokens) never matches this model.
    name_excludes: list[str] = field(default_factory=list)
    # Bare trade names ("KONA", "208") that mean this electric model only in sources that hold
    # nothing but BEVs (matcher.BEV_FILTERED_SOURCES). Exact whole-name match, never a prefix.
    bev_only_aliases: list[str] = field(default_factory=list)
    # Names one source uses for this model, valid for that source only (`source_aliases:
    # {kba-fz10: ["4ER", {name: "ID.4, ID.5", note: "..."}]}`). Prefix match like
    # `name_aliases`; an alias may start with a make the seed lacks ("SEAT BORN"). A `note`
    # travels with the matched counts into the release provenance.
    source_aliases: dict[str, list[SourceAlias]] = field(default_factory=dict)
    # Q-021: one explicit, general list of names per source (`aliases_by_source`), used when
    # scoped aliases are on (matcher.scoped_aliases_enabled). Replaces `bev_only_aliases` and
    # `source_aliases` for a model that has it; a model without it keeps the legacy keys.
    # Keys are source ids, or several joined by commas ("rdw,eea"). Entries: a bare string
    # (whole-name match) or {name, match: exact|prefix, note}. `None` = key absent.
    aliases_by_source: dict[str, list[SourceAlias]] | None = None


ALIAS_MATCH_MODES = ("exact", "prefix")

# Model-year span (start, end); either bound None = open.
YearSpan = tuple[int | None, int | None]


@dataclass(frozen=True)
class SourceAlias:
    name: str
    note: str | None = None
    match: str = "prefix"  # exact: whole name only; prefix: leading tokens (like name_aliases)


@dataclass
class SeedMake:
    id: str
    name: str
    models: list[SeedModel]


@dataclass
class Seed:
    makes: dict[str, SeedMake]
    make_keys: dict[str, str]  # normalised make key -> make id
    models: dict[str, SeedModel]
    generations: dict[str, SeedGeneration]
    # Q-021: make spellings one source uses (`make_aliases_by_source` on a make in models.yaml,
    # e.g. EEA "VOLKSWAGEN, VW", OpenEV "MG Motor"): source id -> normalised key -> make id.
    # Used only when scoped aliases are on.
    make_source_keys: dict[str, dict[str, str]] = field(default_factory=dict)

    def make_id_for(
        self, make: str, source_id: str | None = None, scoped: bool = False
    ) -> str | None:
        k = key(make)
        if k in self.make_keys:
            return self.make_keys[k]
        if scoped and source_id is not None:
            hit = self.make_source_keys.get(source_id, {}).get(k)
            if hit is not None:
                return hit
        return self.make_keys.get(MAKE_ALIASES.get(k, ""))


def parse_seed(data: dict[str, Any]) -> Seed:
    makes: dict[str, SeedMake] = {}
    make_keys: dict[str, str] = {}
    models: dict[str, SeedModel] = {}
    gens: dict[str, SeedGeneration] = {}
    make_source_keys: dict[str, dict[str, str]] = {}
    for mk in data.get("makes", []):
        for sids, names in (mk.get("make_aliases_by_source") or {}).items():
            for sid in [x.strip() for x in str(sids).split(",") if x.strip()]:
                for n in names or []:
                    k = key(str(n))
                    prev = make_source_keys.setdefault(sid, {}).get(k)
                    if not k or (prev is not None and prev != mk["id"]):
                        raise ValueError(f"make alias {n!r} for {sid}: empty or on two makes")
                    make_source_keys[sid][k] = mk["id"]
        make_models: list[SeedModel] = []
        for md in mk.get("models", []):
            mgens: list[SeedGeneration] = []
            for g in md.get("generations", []):
                years = g.get("years") or [None, None]
                sg = SeedGeneration(
                    id=g["id"],
                    model_id=md["id"],
                    name=g.get("name", g["id"]),
                    year_start=int(years[0]),
                    year_end=None if years[1] is None else int(years[1]),
                    uncertain=bool(g.get("uncertain", False)),
                    notes=g.get("notes"),
                    change_markers=list(g.get("change_markers") or []),
                )
                mgens.append(sg)
                gens[sg.id] = sg
            sm = SeedModel(
                id=md["id"],
                make_id=mk["id"],
                name=md["name"],
                segment=md.get("segment"),
                body=md.get("body"),
                aliases=list(md.get("name_aliases") or []),
                generations=sorted(mgens, key=lambda g: g.year_start),
                name_excludes=list(md.get("name_excludes") or []),
                bev_only_aliases=list(md.get("bev_only_aliases") or []),
                source_aliases=_parse_source_aliases(md.get("source_aliases")),
                aliases_by_source=(
                    _parse_aliases_by_source(md["aliases_by_source"], md["id"])
                    if "aliases_by_source" in md
                    else None
                ),
            )
            make_models.append(sm)
            models[sm.id] = sm
        makes[mk["id"]] = SeedMake(id=mk["id"], name=mk["name"], models=make_models)
        make_keys[key(mk["name"])] = mk["id"]
        make_keys[key(mk["id"])] = mk["id"]
    return Seed(
        makes=makes,
        make_keys=make_keys,
        models=models,
        generations=gens,
        make_source_keys=make_source_keys,
    )


def _parse_source_aliases(raw: Any) -> dict[str, list[SourceAlias]]:
    out: dict[str, list[SourceAlias]] = {}
    for sid, items in (raw or {}).items():
        for it in items or []:
            if isinstance(it, str):
                out.setdefault(str(sid), []).append(SourceAlias(it))
            elif isinstance(it, dict) and it.get("name"):
                out.setdefault(str(sid), []).append(SourceAlias(str(it["name"]), it.get("note")))
            else:
                raise ValueError(f"bad source_aliases entry for {sid}: {it!r}")
    return out


def _parse_aliases_by_source(raw: Any, model_id: str) -> dict[str, list[SourceAlias]]:
    """`aliases_by_source` (Q-021). A bare string is a whole-name (exact) alias, the safe
    default for bare trade names like "KONA"; a dict may ask for `match: prefix`."""
    out: dict[str, list[SourceAlias]] = {}
    for keys, items in (raw or {}).items():
        sids = [s.strip() for s in str(keys).split(",") if s.strip()]
        if not sids:
            raise ValueError(f"{model_id}: aliases_by_source has an empty source key")
        for it in items or []:
            if isinstance(it, str | int | float) and not isinstance(it, bool):
                alias = SourceAlias(str(it), None, "exact")
            elif isinstance(it, dict) and it.get("name") is not None:
                mode = str(it.get("match", "exact"))
                if mode not in ALIAS_MATCH_MODES:
                    raise ValueError(f"{model_id}: aliases_by_source match {mode!r} unknown")
                alias = SourceAlias(str(it["name"]), it.get("note"), mode)
            else:
                raise ValueError(f"{model_id}: bad aliases_by_source entry for {keys}: {it!r}")
            for sid in sids:
                out.setdefault(sid, []).append(alias)
    return out


def load_seed(path: Path) -> Seed:
    return parse_seed(yaml.safe_load(path.read_text(encoding="utf-8")))


# --- seed-manual variants (data/seed/variants.yaml) ------------------------------------

# Units implied by field name in variants.yaml (metric, see AGENTS.md data rule 6).
CANONICAL_UNITS: dict[str, str] = {
    "battery_kwh_net": "kWh",
    "battery_kwh_gross": "kWh",
    "wltp_range_km": "km",
    "epa_range_km": "km",
    "real_range_km": "km",
    "consumption_kwh_100km": "kWh/100km",
    "ac_kw": "kW",
    "ac_kw_optional": "kW",
    "dc_peak_kw": "kW",
    "dc_avg_10_80_kw": "kW",
    "power_kw": "kW",
    "accel_0_100_s": "s",
    "top_speed_kmh": "km/h",
    "boot_l": "l",
    "frunk_l": "l",
    "length_mm": "mm",
    "width_mm": "mm",
    "height_mm": "mm",
    "wheelbase_mm": "mm",
    "weight_kg": "kg",
    "towing_kg": "kg",
    "seats": "count",
    "registered_count": "count",
    "dc_curve": "kW",
    "dc_minutes_10_80": "min",
    "dc_peak_kw_claim": "kW",
    "consumption_motorway_kwh_100km": "kWh/100km",
    "real_range_summer_km": "km",
    "real_range_motorway_km": "km",
    "real_range_winter_km": "km",
    "voltage_nominal_v": "V",
    "voltage_max_v": "V",
    "warranty_years": "years",
    "warranty_km": "km",
    # Decision 023: separate fields, never used to fill WLTP / kerb weight / peak power.
    "nedc_range_km": "km",
    "nedc_consumption_kwh_100km": "kWh/100km",
    "wltp_range_km_worst": "km",
    "wltp_consumption_kwh_100km_worst": "kWh/100km",
    "mass_running_order_kg": "kg",
    "power_30min_kw": "kW",
    # id-valued fields (Decision 010): values are taxonomy ids, unit "id".
    "chemistry_id": "id",
    "cooling_id": "id",
    "cell_format": "id",
    "charger_400v_behaviour": "id",
    # price_new: unit is the currency code, so it cannot be implied.
}


@dataclass
class ManualVariant:
    """A hand-entered variant: id and generation are given, so it skips name matching."""

    id: str
    generation_id: str
    name: str
    year_start: int | None
    year_end: int | None
    record: SourceRecord
    # Q-062: the names other sources give this same car (`source_names: {openev: [Standard,
    # "Standard Range"]}` in variants.yaml; keys may be "a,b"). Source id -> normalised keys.
    # A record of that source with that variant name in this generation joins this variant
    # instead of making a near-duplicate row of its own.
    source_names: dict[str, set[str]] = field(default_factory=dict)
    # `cited:` values (field -> value + its own public source URL, retrieval date and
    # confidence): one record each, so every cited value carries its own provenance.
    cited_records: list[SourceRecord] = field(default_factory=list)
    # Year-scoped source names (`{name: Base, years: [2024, null]}`): (source id, name key)
    # -> the model years that name means this variant. Names not listed here mean it in
    # every year. Lets one source name ("Base") join different seed variants by model year.
    source_name_years: dict[tuple[str, str], YearSpan] = field(default_factory=dict)

    @property
    def records(self) -> list[SourceRecord]:
        return [self.record, *self.cited_records]


def parse_cited(
    raw: Any, vid: str, v: dict[str, Any], source: Source
) -> tuple[list[SourceRecord], list[str]]:
    """`cited:` of one seed-manual variant -> one SourceRecord per value (see validate_variants)."""
    out: list[SourceRecord] = []
    problems: list[str] = []
    if raw is None:
        return out, problems
    if not isinstance(raw, dict):
        return out, [f"{vid}: cited must map fields to cited values"]
    valid_fields = {f.value for f in FactField}
    years = v.get("years") or [None, None]
    for fname, c in raw.items():
        if fname not in valid_fields or fname not in CANONICAL_UNITS or fname == "dc_curve":
            problems.append(f"{vid}: cited {fname}: unknown or unsupported field; skipped")
            continue
        if not isinstance(c, dict):
            problems.append(f"{vid}: cited {fname}: must be a mapping; skipped")
            continue
        value, url, got = c.get("value"), c.get("source_url"), c.get("retrieved")
        conf = c.get("confidence")
        if isinstance(value, bool) or not isinstance(value, int | float):
            problems.append(f"{vid}: cited {fname}: value is not a number; skipped")
            continue
        if not isinstance(url, str) or not url.startswith("https://"):
            problems.append(f"{vid}: cited {fname}: no https source_url; skipped")
            continue
        if isinstance(got, str):
            try:
                got = date.fromisoformat(got)
            except ValueError:
                got = None
        if not isinstance(got, date) or isinstance(got, datetime):
            problems.append(f"{vid}: cited {fname}: no retrieved date; skipped")
            continue
        if conf not in {c_.value for c_ in Confidence}:
            problems.append(f"{vid}: cited {fname}: no valid confidence; skipped")
            continue
        if not (c.get("quote") or c.get("locator")):
            problems.append(f"{vid}: cited {fname}: needs a quote or locator; skipped")
            continue
        sid = c.get("source_id") or CITED_DEFAULT_SOURCE_ID
        if not isinstance(sid, str) or sid == source.id.root:
            problems.append(f"{vid}: cited {fname}: source_id must be the cited document's source")
            continue
        label = CITED_SOURCE_NAMES.get(sid, sid)
        cited_source = Source(
            id=sid,
            name=f"{label}: {c.get('source_name') or url}",
            licence=CITED_LICENCE,
            url=url,
        )
        out.append(
            SourceRecord(
                source=cited_source,
                record_key=f"{vid}#cited:{fname}",
                kind="spec",
                make="",
                model="",
                variant_name=v.get("name"),
                year=years[0],
                drivetrain=v.get("drivetrain"),
                specs={
                    FactField(fname): SpecValue(value=float(value), unit=CANONICAL_UNITS[fname])
                },
                retrieved_at=got,
                confidence=Confidence(conf),
            )
        )
    return out, problems


def parse_year_span(raw: Any, where: str) -> YearSpan:
    """`[start, end]` with either bound null (open). Raises ValueError on anything else."""
    if (
        not isinstance(raw, list)
        or len(raw) != 2
        or not all(y is None or (isinstance(y, int) and not isinstance(y, bool)) for y in raw)
        or raw == [None, None]
    ):
        raise ValueError(f"{where}: years must be [start, end] (one bound may be null)")
    start, end = raw
    if start is not None and end is not None and end < start:
        raise ValueError(f"{where}: years end before start")
    return (start, end)


def span_covers(span: YearSpan | None, year: int | None) -> bool:
    """True when `span` (None = every year) includes `year`. A record without a year fits only
    an unscoped name: a scoped name is a claim about model years we can't check."""
    if span is None:
        return True
    if year is None:
        return False
    start, end = span
    return (start is None or start <= year) and (end is None or year <= end)


def spans_overlap(a: YearSpan | None, b: YearSpan | None) -> bool:
    if a is None or b is None:
        return True
    lo = max(x for x in (a[0], b[0], -(10**6)) if x is not None)
    hi = min(x for x in (a[1], b[1], 10**6) if x is not None)
    return lo <= hi


def parse_source_name_entries(
    raw: Any, vid: str
) -> tuple[dict[str, set[str]], dict[tuple[str, str], YearSpan]]:
    """`source_names` of one seed-manual variant -> (source id -> normalised name keys,
    (source id, name key) -> year span for the year-scoped entries).

    An entry is a name, or `{name, years: [start, end]}` (either bound null) when the source
    uses that name for this car only in those model years (OpenEV e-208 "Base" is the 50 kWh
    car up to MY2023 and the 51 kWh car from MY2024)."""
    out: dict[str, set[str]] = {}
    years: dict[tuple[str, str], YearSpan] = {}
    if raw is None:
        return out, years
    if not isinstance(raw, dict):
        raise ValueError(f"{vid}: source_names must map source ids to lists of names")
    for keys, names in raw.items():
        sids = [x.strip() for x in str(keys).split(",") if x.strip()]
        if not sids or not isinstance(names, list):
            raise ValueError(f"{vid}: bad source_names entry {keys!r}: {names!r}")
        for n in names:
            span: YearSpan | None = None
            if isinstance(n, dict):
                extra = set(n) - {"name", "years", "note"}
                if extra or "name" not in n:
                    raise ValueError(f"{vid}: source_names entry {n!r}: keys name, years, note")
                if "years" in n:
                    span = parse_year_span(n["years"], f"{vid}: source_names {n['name']!r}")
                n = n["name"]
            k = key(str(n))
            if not k:
                raise ValueError(f"{vid}: empty name in source_names for {keys}")
            for sid in sids:
                if k in out.get(sid, set()):
                    raise ValueError(f"{vid}: source name {sid} {n!r} listed twice")
                out.setdefault(sid, set()).add(k)
                if span is not None:
                    years[(sid, k)] = span
    return out, years


def parse_source_names(raw: Any, vid: str) -> dict[str, set[str]]:
    """`source_names` of one seed-manual variant -> source id -> normalised name keys."""
    return parse_source_name_entries(raw, vid)[0]


@dataclass(frozen=True)
class SourceHold:
    """`source_holds` in variants.yaml: records of one source, with one of these variant names,
    in one generation and model-year span, go to review with `reason` instead of making or
    joining a row. For source records whose figures fit no real variant of those years (OpenEV
    Q4 e-tron MY2024-25 records repeat the MY2023 lineup). Never sets or changes a value."""

    generation_id: str
    source_id: str
    name_key: str
    years: YearSpan | None
    reason: str

    def holds(self, generation_id: str, source_id: str, name: str | None, year: int | None) -> bool:
        return (
            generation_id == self.generation_id
            and source_id == self.source_id
            and key(name or "") == self.name_key
            and span_covers(self.years, year)
        )


def parse_source_holds(data: dict[str, Any]) -> list[SourceHold]:
    """Top-level `source_holds:` of variants.yaml. Raises ValueError on a malformed entry."""
    out: list[SourceHold] = []
    raw = data.get("source_holds")
    if raw is None:
        return out
    if not isinstance(raw, list):
        raise ValueError("source_holds must be a list")
    for i, h in enumerate(raw):
        where = f"source_holds[{i}]"
        if not isinstance(h, dict):
            raise ValueError(f"{where}: must be a mapping")
        extra = set(h) - {"generation_id", "source", "names", "years", "reason"}
        if extra:
            raise ValueError(f"{where}: unknown keys {sorted(extra)}")
        gid, sid, names, reason = (
            h.get("generation_id"),
            h.get("source"),
            h.get("names"),
            h.get("reason"),
        )
        if not isinstance(gid, str) or not isinstance(sid, str) or not gid or not sid:
            raise ValueError(f"{where}: needs generation_id and source")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{where}: needs a reason")
        if not isinstance(names, list) or not names:
            raise ValueError(f"{where}: names must be a non-empty list")
        span = parse_year_span(h["years"], where) if "years" in h else None
        for n in names:
            k = key(str(n))
            if not k:
                raise ValueError(f"{where}: empty name")
            out.append(SourceHold(gid, sid, k, span, reason.strip()))
    return out


def load_source_holds(path: Path) -> list[SourceHold]:
    return parse_source_holds(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def parse_manual_variants(
    data: dict[str, Any], retrieved_at: date
) -> tuple[list[ManualVariant], list[str]]:
    """Returns (variants, problems). Problems are human-readable and go to validation.csv."""
    src = data.get("source") or {}
    source = Source(
        id=src.get("id", SEED_MANUAL_SOURCE_ID),
        name=src.get("name", "EV Finder seed (hand-entered, unchecked)"),
        licence=src.get("licence", "CC-BY-4.0"),
        url=src.get("url"),
        attribution=src.get("attribution"),
    )
    out: list[ManualVariant] = []
    problems: list[str] = []
    valid_fields = {f.value for f in FactField}
    for v in data.get("variants") or []:
        vid = v.get("id")
        gid = v.get("generation_id")
        if not vid or not gid:
            problems.append(f"variant without id/generation_id: {v!r:.80}")
            continue
        years = v.get("years") or [None, None]
        specs: dict[FactField, SpecValue] = {}
        for fname, value in (v.get("specs") or {}).items():
            if value is None:
                continue
            if fname not in valid_fields:
                problems.append(f"{vid}: unknown field {fname}")
                continue
            if fname == "price_new" or fname not in CANONICAL_UNITS:
                problems.append(f"{vid}: {fname} needs an explicit unit; skipped")
                continue
            if fname == "dc_curve" and isinstance(value, list):
                curve = {"points": value, "status": "estimated"}
                specs[FactField(fname)] = SpecValue(value=json.dumps(curve), unit="kW")
                continue
            if isinstance(value, bool) or not isinstance(value, int | float):
                problems.append(f"{vid}: {fname} is not a number ({value!r})")
                continue
            specs[FactField(fname)] = SpecValue(value=float(value), unit=CANONICAL_UNITS[fname])
        cited, cited_problems = parse_cited(v.get("cited"), vid, v, source)
        problems += cited_problems
        for cr in cited:
            for f in cr.specs:
                if f in specs:
                    problems.append(f"{vid}: {f.value} is both in specs and cited; cited wins")
                    del specs[f]
        conf = v.get("confidence", "low")
        names, name_years = parse_source_name_entries(v.get("source_names"), vid)
        record = SourceRecord(
            source=source,
            record_key=vid,
            kind="spec",
            make="",
            model="",
            variant_name=v.get("name"),
            year=years[0],
            drivetrain=v.get("drivetrain"),
            specs=specs,
            retrieved_at=retrieved_at,
            confidence=Confidence(conf),
        )
        out.append(
            ManualVariant(
                id=vid,
                generation_id=gid,
                name=v.get("name") or vid,
                year_start=years[0],
                year_end=years[1] if len(years) > 1 else None,
                record=record,
                source_names=names,
                cited_records=cited,
                source_name_years=name_years,
            )
        )
    return out, problems


def load_manual_variants(path: Path) -> tuple[list[ManualVariant], list[str]]:
    # No retrieval date in the file: use its modification date (stable while the file is).
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date()
    return parse_manual_variants(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, mtime)


def _with_and_without_make(model: SeedModel, names: list[str]) -> set[str]:
    make_toks = tokens(model.make_id)
    out: set[str] = set()
    for name in names:
        toks = tokens(name)
        if not toks:
            continue
        out.add("".join(toks))
        if toks[: len(make_toks)] == make_toks and len(toks) > len(make_toks):
            out.add("".join(toks[len(make_toks) :]))
    return out


def model_bev_only_keys(model: SeedModel) -> set[str]:
    """Normalised whole-name keys of `bev_only_aliases` (with and without the make name)."""
    return _with_and_without_make(model, model.bev_only_aliases)


def model_exclude_tokens(model: SeedModel) -> list[list[str]]:
    """Token lists of `name_excludes`; matched as a contiguous run anywhere in a name."""
    return [t for t in (tokens(n) for n in model.name_excludes) if t]


def model_source_alias_keys(model: SeedModel, source_id: str) -> dict[str, SourceAlias]:
    """Normalised keys of this model's aliases for one source (with and without the make)."""
    out: dict[str, SourceAlias] = {}
    for a in model.source_aliases.get(source_id, []):
        for k in _with_and_without_make(model, [a.name]):
            out[k] = a
    return out


def model_scoped_alias_keys(
    model: SeedModel, source_id: str
) -> tuple[dict[str, SourceAlias], dict[str, SourceAlias]]:
    """(prefix keys, exact keys) of this model's `aliases_by_source` for one source, with and
    without the make name. Empty when the model has no `aliases_by_source`."""
    prefix: dict[str, SourceAlias] = {}
    exact: dict[str, SourceAlias] = {}
    for a in (model.aliases_by_source or {}).get(source_id, []):
        target = exact if a.match == "exact" else prefix
        for k in _with_and_without_make(model, [a.name]):
            target[k] = a
    return prefix, exact


def model_alias_keys(model: SeedModel) -> set[str]:
    """Normalised keys a source may use for this model, with and without the make name."""
    return _with_and_without_make(model, [model.name, *model.aliases])
