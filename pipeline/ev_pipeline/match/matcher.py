"""Rules-first matching of SourceRecords to seed models, generations and variants (T-005).

1. Make: normalised key of the record's make against seed make names/ids (+ MAKE_ALIASES).
2. Model: the longest token prefix of the record's model name (with or without a leading
   make name) that equals a seed model name or one of its `name_aliases`. A tie between two
   seed models is ambiguous and goes to review. Two seed-level guards (T-005 review):
   - `name_excludes`: a model never matches a record whose name contains one of these phrases
     as whole tokens ("e-tron GT" is not an "e-tron"); a shorter, non-excluded match may still
     win, otherwise the record goes to review.
   - `bev_only_aliases`: bare trade names ("KONA", "208", "CORSA") that mean the electric model
     only in sources holding nothing but BEVs (BEV_FILTERED_SOURCES: RDW is BEV-proxy-filtered,
     EEA is filtered on Ft = electric). Whole-name match only, never a prefix, so "GOLF GTI"
     or "500 1.4 16V" never ride on them.
3. Generation: the record's year within [start, end] (end null = open). When two generations
   share a year (a facelift or overlap year), evidence decides (T-005 review, supersedes the
   plain "newer wins" of Q-014):
   a. a generation whose known variant names equal the record's variant name, or whose known
      battery sizes (variant kWh, pack kWh, kWh in variant names) are within 1 kWh of a kWh
      figure in the record ("NISSAN LEAF 40KWH", battery_kwh_net 39) is preferred;
      evidence for several generations -> the newest of those;
   b. no evidence -> the newer generation, unless two or more of the candidate generations
      already have variants: then it is a guess, and the record goes to review with reason
      `ambiguous-generation`.
   Known variants/batteries come from a pre-pass over seed-manual variants and records whose
   year falls in exactly one generation. A record without a year only matches a model with
   exactly one generation.
4. Variant (spec records): `<generation_id>-<slug(variant_name or 'base')>`. Records of one
   source with the same normalised variant name in one generation share a variant, whatever
   their year; years seen become the variant's year span. A seed-manual variant with the same
   normalised name in the same generation lends its id, so the two merge.
   Battery gate (as in 9 below): a record whose battery figures are all outside the gate
   tolerance of the seed-manual variant it would join (by name, `source_names`, or because its
   `<generation_id>-<slug>` id equals the seed variant's id: OpenEV "Q4 e-tron 40" MY2023+
   at 48 kWh vs the seed "40 e-tron" at 77 kWh) goes to review instead of merging.
   Seed power gate: a record that would join a seed-manual variant through `source_names`
   (an alias, not its own name) and whose power_kw (or "<n> kW" in its name) is more than
   5 % from every power figure of that variant goes to review ("power contradicts the seed
   variant"); unknown power on either side rules nothing out. Same-name and same-id joins
   are not power-gated (a later model year may get a stronger motor: Enyaq 60 132 -> 150 kW
   becomes a year band, see below).
   A `source_names` entry may be year-scoped (`{name: Base, years: [2024, null]}`): the name
   then joins that seed variant only for records of those model years, so one source name
   can mean different seed variants by year (OpenEV e-208 "Base": 50 kWh to MY2023, 51 kWh
   from MY2024). Two variants may share a name only with non-overlapping years.
   Source holds (`source_holds` in variants.yaml): records of a named source, variant name,
   generation and model-year span go to review with the hold's reason before any variant is
   made or joined (OpenEV Q4 e-tron MY2024-25 records repeat MY2023 figures under names
   that fit no MY2024+ car). A hold never sets or changes a value.
   Year bands (`split_year_bands`): when a variant's records for a later model year differ from
   its earliest year by more than WLTP 5% or DC peak 10%, that is a real change, so the later
   years become their own variant `<variant_id>-<first year>` (the earliest band keeps the
   original id and ends the year before). Smaller differences stay in one variant; merge then
   prefers the earliest model year and lists the rest in conflicts.csv.
5. Registration counts are kept as facts on the generation, or on the model when the record
   has no year (DfT fleet) or, for MODEL_LEVEL_FALLBACK sources (KBA), when the year cannot
   pick one generation. Each count fact carries its period (KBA "2025-01..12", DfT "2026-Q2").
   Aggregation: `aggregate_counts` (RDW -> registered_count_nl) and `registration_entries`
   (every source -> PublishedVariant.registrations). Counts of different sources, periods or
   kinds (fleet / new registrations) are never added together.
6. Count-only sources (COUNT_ONLY_SOURCES, EEA): their spec records are dropped and counted,
   never matched: the EEA averages blend different cars (T-004 review, Q-039).
   Corroboration records (Q-019 option a, flag `EV_EEA_CORROBORATION`, default off): EEA's
   generation-level range/consumption averages become generation facts in
   `result.corroboration_facts` (one per generation and field: the average with the most
   registrations behind it). Merge (`merge/corroborate.py`) may count them as an agreeing
   source; they never set a value. Flag off, or unplaceable: counted, never unmatched.csv.
7. Source-scoped aliases (`source_aliases` in models.yaml): names one source uses for a model
   (KBA "4ER" = the BEV column of the BMW 4 series = i4). They may start with a make the seed
   lacks ("SEAT BORN" -> Cupra Born). Their optional note goes into the count's provenance.
   Scoped aliases (Q-021, flag `EV_SCOPED_ALIASES`, see `scoped_aliases_enabled`): a model's
   `aliases_by_source` is then the one explicit list of extra names per source (exact or
   prefix, each with an optional note) and replaces its `bev_only_aliases` and
   `source_aliases`; a model without `aliases_by_source` keeps the legacy keys.
8. MATCH_ON_VARIANT_NAME (DfT): the model column is coarse (GenModel "HYUNDAI IONIQ" holds
   the Ioniq 5, 6 and 9 too), so the variant column (DfT "Model") is matched instead.
9. ATTACH_ONLY_SOURCES (ADEME, KilowattApp): their names never equal ours ("e-208 (57Kw)",
   "LR"), so they never make variants of their own. After the main pass each record is
   attached to one existing variant of its generation: same name, else the generation's
   only variant, else the single variant with the most evidence (battery kWh, power kW,
   WLTP km, shared distinctive name words; on equal evidence the name with the fewest words
   the record lacks, but only when every tied name shares a word with the record); a tie or
   no evidence goes to review. A-05: a record without a variant name (RDW year groups, EPA
   rows) names no variant, so it is never a "same name" match for a variant called "base";
   it attaches only to a generation's only variant or by unique evidence. Generic trim words
   (long, standard, extended, plus, max) count only next to a distinctive shared word or
   numeric evidence; "range" is a stop word and "long range" / "standard range" /
   "extended range" are joined into one token each (F8). Year bands of one variant count
   as one candidate; the record's year then picks the band. A record without a year uses
   battery/name evidence to pick the generation, else goes to review.
   Power gate (Q-086, POWER_GATE_SOURCES): when such a record carries power evidence (RDW
   writes its median kW as variant_name "<kW> kW"; a power_kw spec counts too), candidates
   whose known power_kw (seed-manual or any merged source) differs by more than
   max(2 %, 3 kW) are ruled out. Candidates that match the power are preferred; with none,
   only candidates of unknown power stay, and one of them needs positive evidence (kWh,
   WLTP, name words) to be chosen. No candidate left -> review, reason
   "no variant with matching power". Year bands whose own power contradicts the record are
   skipped when the year picks the band. For these sources a tie whose only evidence is
   WLTP within tolerance of 2+ candidates goes to review ("ambiguous evidence") instead of
   the fewest-words tie-break. Price is not used as evidence (list prices move by trim and
   year). Only RDW is gated for now (2026-11-15: gating ADEME and KilowattApp too would
   send 28 + 27 more records to review, not yet checked one by one; ADEME's "(57Kw)" in
   names may not be peak power).
   Battery gate (BATTERY_GATE_REL, every attach-only source): a record that carries battery
   evidence (battery_kwh_net / _gross, or "<n> kWh" in its names) never attaches to a
   candidate whose seed battery (the seed-manual variant's net / gross kWh, its cited kWh
   and any kWh in its name) is more than 15 % away from every one of the record's figures
   (20 % between net and gross or against a figure in a name)
   (KilowattApp "Zoe R90 Entry" 23.3 kWh is not the R90 Z.E. 40 at 41 kWh). Candidates of
   unknown seed battery stay. Once the gate has ruled any candidate out, the pick needs
   positive evidence: the "only variant left" shortcut does not apply, and the pick needs
   numeric evidence (kWh within 1 kWh, power, WLTP) or a distinctive shared name word no
   ruled-out candidate shares (KilowattApp "Enyaq iV 50" at 52 kWh is not the "60 (iV 60)" just
   because the 80 and 85 are out). Nothing left -> review, reason "battery contradicts the seed
   variant". The gate applies before the "same name" and "only variant" shortcuts.
   TGK evidence (TGK_EVIDENCE_SOURCES, rdw-tgk; see `tgk_pick`): a type-approval version
   names no battery, so the variant is picked from the version's own figures: years (+-1),
   the battery its range x consumption implies, trade-name words, a range number in the
   variant name ("R240") and WLTP. Only a single fitting variant is chosen; ties and
   misfits go to review ("tgk: several variants fit" / "tgk: no variant fits"). A TGK year
   shared by two generations (e-Golf 2017) is decided the same way across both generations'
   variants.
   Split evidence (T-153, match/tgk_split.yaml): variants that share a pack (e-208 50 vs
   51 kWh, Model Y LR vs Performance, ID.4 Pro vs GTX) are told apart by the values their
   TGK versions carry per seed variant: type code, 30-minute power, top speed, and
   `motors: 2` (versions that state a 30-minute power are not that variant). A candidate is
   only ruled out by its own listed value; all ruled out -> review. See `tgk_split_pool`.
   Cited power wins (T-153, Decision 068 / 087): an aliased record whose power contradicts
   the seed's cited maker power, but whose battery agrees, joins the seed variant and its
   power_kw is withheld (validation.csv, "power contradicts the cited maker power").

Nothing here decides values: that is merge's job.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ev_pipeline.match.normalise import key, prefix_keys, slug, tokens
from ev_pipeline.match.seed import (
    CANONICAL_UNITS,
    ManualVariant,
    Seed,
    SeedGeneration,
    SeedModel,
    SourceAlias,
    SourceHold,
    YearSpan,
    model_alias_keys,
    model_bev_only_keys,
    model_exclude_tokens,
    model_scoped_alias_keys,
    model_source_alias_keys,
    span_covers,
    spans_overlap,
)
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.schema_models import ChargeCurve, Fact, FactField, Id

EXCLUDED_SOURCES = frozenset({"nyland"})  # permission pending: never in a release (hard floor)

# Sources that hold battery-electric cars only, so a bare trade name ("KONA") means the BEV.
# RDW: server-side BEV proxy (no displacement, see sources/rdw); EEA: Ft = 'electric'.
# KBA FZ10: the "mit Elektroantrieb (BEV)" column; DfT VEH0120: Fuel = battery electric;
# ADEME: Energie = ELECTRIC; KilowattApp: an electric-car database (no PHEVs; the smallest
# car pack is 14.4 kWh, checked 2026-11-15).
BEV_FILTERED_SOURCES = frozenset(
    {"rdw", "rdw-tgk", "eea", "kba-fz10", "dft-veh", "ademe", "kilowatt-openev"}
)

# Sources whose model column is coarse; their variant column names the car (see 8 above).
MATCH_ON_VARIANT_NAME = frozenset({"dft-veh"})

# Sources that only add facts to variants made by other sources (see 9 above).
# rdw: registration names never define variants (Q-068); fueleconomy: US market names.
ATTACH_ONLY_SOURCES = frozenset({"ademe", "kilowatt-openev", "rdw", "fueleconomy", "rdw-tgk"})

# Fields a source emits that we do not use, with the reason (counted in the run log).
IGNORED_FIELDS: dict[str, dict[str, str]] = {
    # Our consumption_kwh_100km is a WLTP figure (motorway = x 1.30, AC km/h); KilowattApp's
    # "energy_consumption" is an app average of unknown cycle (Q-048 item 5).
    "kilowatt-openev": {"consumption_kwh_100km": "not a WLTP figure"},
    # EPA consumption is measured on the US test cycle, not WLTP (Q-075).
    "fueleconomy": {"consumption_kwh_100km": "EPA cycle, not WLTP"},
}

# What a source's registration count is (RegistrationCount.kind).
COUNT_KIND: dict[str, str] = {
    "rdw": "fleet",
    "dft-veh": "fleet",
    "kba-fz10": "new_registrations",
    "eea": "new_registrations",
}
# Count sources placed at model level (not sent to review) when their year is shared by two
# generations without evidence (`ambiguous-generation`): the cars are counted for the model
# without guessing the generation, and never split between generations by a ratio. RDW
# joined on 2026-11-15 (coverage-gaps finding 6: about 10,400 NL cars of Niro 2022, Zoe 2019,
# Kona 2023, Model S 2016, e-Golf 2017, Soul 2019). A year outside every generation
# (KBA 2025 "GOLF" BEV: the e-Golf ended in 2020) still goes to review. EEA still sends a
# shared year to review (no such EEA year in the 2025/2026 files).
MODEL_LEVEL_FALLBACK = frozenset({"kba-fz10", "rdw"})
SHARED_YEAR_NOTE = "shared year, generation unknown"
_KBA_PERIOD_RE = re.compile(r"YTD (\d{4}-\d{2}\.\.\d{2})")
_DFT_PERIOD_RE = re.compile(r"(\d{4}) Q([1-4])")

# Sources used for registration counts only; their spec records never become facts (Q-039).
COUNT_ONLY_SOURCES = frozenset({"eea"})

# Q-019 option (a): sources whose `corroboration` records may confirm (never set) a value.
# T-059: wikidata corroborates generation *years* only (no specs); its records are collected
# in `MatchResult.year_records` whatever the EEA flag says, because they never touch a value
# (merge/generation_years.py).
YEAR_CORROBORATION_SOURCES = frozenset({"wikidata"})
CORROBORATION_SOURCES = frozenset({"eea"}) | YEAR_CORROBORATION_SOURCES
EEA_CORROBORATION_ENV = "EV_EEA_CORROBORATION"
EEA_CORROBORATION_DEFAULT = False  # Q-019 is open: off until Menno picks option (a)

AMBIGUOUS_GENERATION = "ambiguous-generation"

# Q-021 source-scoped aliases. Env EV_SCOPED_ALIASES=1/0 overrides the default; the default
# was set by measuring the 2026-11-15 staging data with the flag off and on (QUESTIONS Q-021).
SCOPED_ALIASES_ENV = "EV_SCOPED_ALIASES"
SCOPED_ALIASES_DEFAULT = True
_ON = {"1", "true", "yes", "on"}
_OFF = {"0", "false", "no", "off"}


def scoped_aliases_enabled(value: bool | None = None) -> bool:
    """The scoped-alias flag: an explicit value, else the env var, else the default."""
    if value is not None:
        return value
    raw = os.environ.get(SCOPED_ALIASES_ENV, "").strip().lower()
    if raw in _ON:
        return True
    if raw in _OFF:
        return False
    if raw:
        raise ValueError(f"{SCOPED_ALIASES_ENV}={raw!r}: use 1 or 0")
    return SCOPED_ALIASES_DEFAULT


def eea_corroboration_enabled(value: bool | None = None) -> bool:
    """The Q-019 corroboration flag: an explicit value, else the env var, else the default."""
    if value is not None:
        return value
    raw = os.environ.get(EEA_CORROBORATION_ENV, "").strip().lower()
    if raw in _ON:
        return True
    if raw in _OFF:
        return False
    if raw:
        raise ValueError(f"{EEA_CORROBORATION_ENV}={raw!r}: use 1 or 0")
    return EEA_CORROBORATION_DEFAULT


KWH_TOLERANCE = 1.0  # "40KWH" in a name vs 39 kWh net / 40 kWh gross
# Battery gate (see 4 and 9 above): wide enough for net vs gross of one pack (Kona 64 / 67,
# e-tron 86.5 / 95, Leaf 39 / 40) and a "22 kWh" name on an 18.8 kWh-net i3; narrow enough
# to keep 22 vs 41 (Zoe), 52 vs 77 (Q4) or 58 vs 77 (ID.3) apart.
BATTERY_GATE_REL = 0.15
# Net vs gross of one pack, or a name figure that may be either, differ more on small and
# older packs (e-Golf 24.2 gross / 20.5 net, i3 22 / 18.8): 20 % across bases.
BATTERY_GATE_CROSS_REL = 0.20
NO_BATTERY_MATCH = "battery contradicts the seed variant"
# Seed power gate (main pass, see 4 above): a record joining a seed-manual variant through a
# `source_names` alias whose power differs from the seed's by more than 5 % is another car.
SEED_POWER_GATE_REL = 0.05
NO_SEED_POWER_MATCH = "power contradicts the seed variant"
# T-153 (Decision 068 / 087): a power figure the seed cites from a maker document beats a
# record's contradicting power. An aliased record whose battery agrees with the seed then
# joins, and its own power_kw is withheld (validation.csv), never published.
CITED_POWER_WINS = "power contradicts the cited maker power: withheld"
# `source_holds` in variants.yaml (see 4 above): records sent to review by name and year.
SOURCE_HOLD = "source hold"
# Year-band split thresholds (relative difference to the band's first year).
BAND_THRESHOLDS: dict[str, float] = {"wltp_range_km": 0.05, "dc_peak_kw": 0.10}
_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*-?\s*kwh", re.IGNORECASE)

# Sources whose figures are maker claims rather than measurements (Decision 009: OpenEV and
# seed values count as claims tonight).
CLAIM_SOURCES = frozenset({"openev", "seed-manual", "maker-docs"})

# Spec priority (higher wins). "checked" seed overrides will sit above openev later.
SOURCE_PRIORITY: dict[str, int] = {"openev": 30, "eea": 20, "seed-manual": 10}
DEFAULT_PRIORITY = 0

# Unit conversions to the canonical unit per field: (field, unit_lowercase) -> factor.
_UNIT_ALIASES = {"kwh": "kWh", "km": "km", "kw": "kW", "kwh/100km": "kWh/100km", "s": "s"}
_UNIT_ALIASES |= {"km/h": "km/h", "kph": "km/h", "l": "l", "litre": "l", "liter": "l"}
_UNIT_ALIASES |= {"min": "min", "minutes": "min", "v": "V", "id": "id"}
_UNIT_ALIASES |= {"years": "years", "year": "years", "y": "years"}
_UNIT_ALIASES |= {"mm": "mm", "kg": "kg", "count": "count", "seats": "count", "": "count"}
_CONVERSIONS: dict[tuple[str, str], float] = {
    ("consumption_kwh_100km", "wh/km"): 0.1,
    ("wltp_range_km", "mi"): 1.609344,
    ("epa_range_km", "mi"): 1.609344,
    ("real_range_km", "mi"): 1.609344,
    ("wltp_range_km", "miles"): 1.609344,
    ("epa_range_km", "miles"): 1.609344,
    ("real_range_km", "miles"): 1.609344,
    ("length_mm", "cm"): 10.0,
    ("length_mm", "m"): 1000.0,
}
CURRENCIES = {"EUR", "GBP"}


@dataclass
class MatchedFact:
    fact: Fact
    source_id: str
    priority: int
    year: int | None
    generation_id: str | None = None
    model_id: str | None = None
    period: str | None = None  # registration counts: the period the count covers
    note: str | None = None  # e.g. a source alias note ("KBA joins ID.4 and ID.5")
    weight: int | None = None  # corroboration: registrations behind the average


@dataclass
class VariantInfo:
    id: str
    generation_id: str
    name: str
    years: set[int] = field(default_factory=set)
    explicit_end: int | None = None  # seed-manual gives an end year directly
    open_end: bool = False  # seed-manual years [start, null]
    drivetrains: list[tuple[int, str, str]] = field(default_factory=list)  # (prio, value, src)
    source_ids: set[str] = field(default_factory=set)
    # Q-062: names other sources use for this variant (seed-manual `source_names`).
    source_names: dict[str, set[str]] = field(default_factory=dict)
    # Year-scoped source names: (source id, name key) -> model years the name means this car.
    source_name_years: dict[tuple[str, str], YearSpan] = field(default_factory=dict)

    def named(self, source_id: str, name: str | None, year: int | None = None) -> bool:
        """True when `name` is this variant's name or one of `source_id`'s names for it
        (a year-scoped source name only for a record of those model years).

        A record without a variant name names no variant (A-05 F1): it is never an exact
        match for a variant called "base" (RDW year groups and EPA rows blend every trim)."""
        k = key(name or "")
        if not k:
            return False
        if k == key(self.name):
            return True
        if k not in self.source_names.get(source_id, set()):
            return False
        return span_covers(self.source_name_years.get((source_id, k)), year)


@dataclass
class UnmatchedRow:
    source_id: str
    record_key: str
    make: str
    model: str
    variant_name: str
    year: str
    reason: str


@dataclass
class Problem:
    """A value we could not use; written to data/review/validation.csv."""

    stage: str
    source_id: str
    record_key: str
    subject_id: str
    field: str
    value: str
    unit: str
    reason: str


@dataclass
class MatchResult:
    variants: dict[str, VariantInfo] = field(default_factory=dict)
    spec_facts: list[MatchedFact] = field(default_factory=list)
    count_facts: list[MatchedFact] = field(default_factory=list)
    unmatched: list[UnmatchedRow] = field(default_factory=list)
    other_makes: Counter[tuple[str, str]] = field(default_factory=Counter)
    problems: list[Problem] = field(default_factory=list)
    excluded: Counter[str] = field(default_factory=Counter)
    count_only_skipped: Counter[str] = field(default_factory=Counter)
    year_bands: list[dict[str, object]] = field(default_factory=list)
    attached: Counter[str] = field(default_factory=Counter)  # attach-only records placed
    ignored_fields: Counter[str] = field(default_factory=Counter)  # "source:field" dropped
    matched_records: int = 0
    scoped_aliases: bool = False  # Q-021 flag value used for this run
    eea_corroboration: bool = False  # Q-019 flag value used for this run
    # Q-019: generation-level facts that may only confirm a merged value (never set one).
    corroboration_facts: list[MatchedFact] = field(default_factory=list)
    corroboration_skipped: Counter[str] = field(default_factory=Counter)  # reason -> records
    corroboration_log: dict[str, object] = field(default_factory=dict)  # set by the release step
    # T-059: production-year records (wikidata) for merge/generation_years.py.
    year_records: list[SourceRecord] = field(default_factory=list)
    # Battery gate: seed-manual variant id -> its battery figures (net, gross, cited, name).
    seed_kwh: dict[str, set[tuple[float, str]]] = field(default_factory=dict)
    # Seed power gate: seed-manual variant id -> its power_kw figures (spec or cited).
    seed_power: dict[str, set[float]] = field(default_factory=dict)
    # Seed-manual variants that a source record joined through a `source_names` alias, and
    # the record keys of the seed's own records (variant + cited): `split_year_bands` does
    # not let those seed facts anchor a year band on such a variant.
    aliased: set[str] = field(default_factory=set)
    seed_record_keys: set[str] = field(default_factory=set)
    # T-153: seed-manual variant id -> power_kw it cites from a maker document (`cited:`).
    seed_cited_power: dict[str, set[float]] = field(default_factory=dict)
    # T-153: TGK split evidence per variant id (match/tgk_split.yaml, `load_tgk_split`).
    tgk_split: dict[str, dict[str, set[str]]] = field(default_factory=dict)


def priority_of(source_id: str) -> int:
    return SOURCE_PRIORITY.get(source_id, DEFAULT_PRIORITY)


def _contains_run(toks: list[str], run: list[str]) -> bool:
    n = len(run)
    return any(toks[i : i + n] == run for i in range(len(toks) - n + 1))


def find_model(
    seed: Seed, make_id: str, record: SourceRecord, scoped: bool = False
) -> tuple[SeedModel | None, str]:
    model, why, _ = find_model_noted(seed, make_id, record, scoped)
    return model, why


def _extra_alias_keys(
    m: SeedModel, sid: str, scoped: bool
) -> tuple[dict[str, SourceAlias], dict[str, SourceAlias | None]]:
    """(prefix keys, exact keys) a source may use for `m` beyond its name and name_aliases."""
    if scoped and m.aliases_by_source is not None:
        prefix, exact = model_scoped_alias_keys(m, sid)
        return prefix, dict(exact)
    legacy_exact: dict[str, SourceAlias | None] = {}
    if sid in BEV_FILTERED_SOURCES:
        legacy_exact = dict.fromkeys(model_bev_only_keys(m))
    return model_source_alias_keys(m, sid), legacy_exact


def find_model_noted(
    seed: Seed, make_id: str, record: SourceRecord, scoped: bool = False
) -> tuple[SeedModel | None, str, str | None]:
    """find_model plus the note of the source alias that matched (if any)."""
    make = seed.makes[make_id]
    sid = record.source.id.root
    alias_index: dict[str, set[str]] = {}
    exact_index: dict[str, set[str]] = {}
    notes: dict[tuple[str, str], str] = {}  # (model id, key) -> source alias note
    for m in make.models:
        for k in model_alias_keys(m):
            alias_index.setdefault(k, set()).add(m.id)
        prefix, exact = _extra_alias_keys(m, sid, scoped)
        for k, a in prefix.items():
            alias_index.setdefault(k, set()).add(m.id)
            if a.note:
                notes[(m.id, k)] = a.note
        for k, ea in exact.items():
            exact_index.setdefault(k, set()).add(m.id)
            if ea is not None and ea.note:
                notes[(m.id, k)] = ea.note
    toks = tokens(record.model)
    variants_of_toks = [toks]
    for strip in (tokens(record.make), tokens(make.name), tokens(make_id)):
        if strip and toks[: len(strip)] == strip and len(toks) > len(strip):
            variants_of_toks.append(toks[len(strip) :])
    # Every (match length, model) candidate; the longest non-excluded one wins.
    candidates: dict[str, int] = {}
    cand_key: dict[str, str] = {}
    for tl in variants_of_toks:
        hits = [(pk, alias_index[pk]) for pk in prefix_keys(tl) if pk in alias_index]
        full = "".join(tl)
        if full in exact_index:
            hits.append((full, exact_index[full]))
        for pk, ids in hits:
            for mid in ids:
                if len(pk) > candidates.get(mid, 0):
                    candidates[mid] = len(pk)
                    cand_key[mid] = pk
    excluded: list[str] = []
    for mid in list(candidates):
        runs = model_exclude_tokens(seed.models[mid])
        if any(_contains_run(tl, run) for tl in variants_of_toks for run in runs):
            excluded.append(mid)
            del candidates[mid]
    if not candidates:
        if excluded:
            why = f"model not in seed (name excluded from {', '.join(sorted(excluded))})"
            return None, why, None
        return None, "model not in seed", None
    best_len = max(candidates.values())
    best = {mid for mid, n in candidates.items() if n == best_len}
    if len(best) > 1:
        return None, f"ambiguous model: {', '.join(sorted(best))}", None
    mid = best.pop()
    return seed.models[mid], "", notes.get((mid, cand_key[mid]))


def find_by_source_alias(
    seed: Seed, record: SourceRecord, scoped: bool = False
) -> tuple[SeedModel | None, str | None]:
    """For a make the seed lacks: a source alias written with its make ("SEAT BORN")."""
    sid = record.source.id.root
    toks = tokens(record.make) + tokens(record.model)
    pks = set(prefix_keys(toks))
    full = "".join(toks)
    found: dict[str, str | None] = {}
    for m in seed.models.values():
        if scoped and m.aliases_by_source is not None:
            for a in m.aliases_by_source.get(sid, []):
                k = key(a.name)
                if (a.match == "exact" and k == full) or (a.match == "prefix" and k in pks):
                    found[m.id] = a.note
            continue
        for a in m.source_aliases.get(sid, []):
            if key(a.name) in pks:
                found[m.id] = a.note
    if len(found) != 1:
        return None, None
    mid, note = found.popitem()
    if any(_contains_run(toks, run) for run in model_exclude_tokens(seed.models[mid])):
        return None, None
    return seed.models[mid], note


def find_record_model(
    seed: Seed, view: SourceRecord, scoped: bool = False
) -> tuple[SeedModel | None, str, str | None, bool]:
    """(model, why not, source alias note, make known) for one record, as match_records sees it.

    Make in the seed: its models by name and aliases; when none matches ("model not in seed"),
    a source alias written with its make still applies (T-136c: KBA "SEAT BORN" is the Cupra
    Born although SEAT itself is in the seed for the Mii electric). Make not in the seed: only
    such source aliases."""
    sid = view.source.id.root
    make_id = seed.make_id_for(view.make, sid, scoped)
    if make_id is None:
        model, note = find_by_source_alias(seed, view, scoped)
        return model, ("" if model else "make not in seed"), note, False
    model, why, note = find_model_noted(seed, make_id, view, scoped)
    if model is None and why == "model not in seed":
        alias, alias_note = find_by_source_alias(seed, view, scoped)
        if alias is not None:
            return alias, "", alias_note, True
    return model, why, note, True


def match_view(record: SourceRecord) -> SourceRecord:
    """The record as matching sees it: DfT is matched on its variant column (see 8 above)."""
    if record.source.id.root in MATCH_ON_VARIANT_NAME and record.variant_name:
        return record.model_copy(update={"model": record.variant_name})
    return record


def kwh_in_text(*texts: str | None) -> set[float]:
    """kWh figures written in names: "40KWH", "62 kWh", "e+ 62-kWh" -> {40.0, 62.0}."""
    out: set[float] = set()
    for t in texts:
        for m in _KWH_RE.finditer(t or ""):
            out.add(float(m.group(1).replace(",", ".")))
    return out


def record_kwh(record: SourceRecord) -> set[float]:
    out = kwh_in_text(record.model, record.variant_name)
    for f in (FactField.battery_kwh_net, FactField.battery_kwh_gross):
        sv = record.specs.get(f)
        if sv is not None and isinstance(sv.value, int | float) and not isinstance(sv.value, bool):
            out.add(float(sv.value))
    return out


def battery_figures(record: SourceRecord, *names: str | None) -> set[tuple[float, str]]:
    """Battery evidence as (kWh, basis): basis net / gross from the specs, "name" for kWh
    written in the record's model / variant name (and in `names`)."""
    out = {(v, "name") for v in kwh_in_text(record.model, record.variant_name, *names)}
    for f, basis in ((FactField.battery_kwh_net, "net"), (FactField.battery_kwh_gross, "gross")):
        sv = record.specs.get(f)
        if sv is not None and isinstance(sv.value, int | float) and not isinstance(sv.value, bool):
            out.add((float(sv.value), basis))
    return out


def battery_close(a: tuple[float, str], b: tuple[float, str]) -> bool:
    """Battery gate tolerance, relative to the larger figure: BATTERY_GATE_REL on the same
    basis, BATTERY_GATE_CROSS_REL between net and gross or against a name figure."""
    tol = BATTERY_GATE_REL if a[1] == b[1] else BATTERY_GATE_CROSS_REL
    return abs(a[0] - b[0]) <= tol * max(abs(a[0]), abs(b[0]))


def battery_contradicts(rec: set[tuple[float, str]], seed: set[tuple[float, str]]) -> bool:
    """True when both sides know a battery and no record figure is close to a seed figure.
    Unknown on either side is no contradiction."""
    if not rec or not seed:
        return False
    return not any(battery_close(a, b) for a in rec for b in seed)


def _source_name_vid(
    targets: list[tuple[YearSpan | None, str]] | None, year: int | None
) -> str | None:
    """The seed-manual variant a source name means for a record of this model year."""
    for span, vid in targets or []:
        if span_covers(span, year):
            return vid
    return None


def _num_text(values: set[float]) -> str:
    return "/".join(f"{v:g}" for v in sorted(values))


def _kwh_text(values: set[tuple[float, str]]) -> str:
    return "/".join(f"{v:g}" for v in sorted({v for v, _ in values}))


@dataclass
class GenerationEvidence:
    """What we already know per generation, used to place records from a shared year."""

    names: dict[str, set[str]] = field(default_factory=dict)  # gen id -> variant name keys
    kwh: dict[str, set[float]] = field(default_factory=dict)  # gen id -> battery sizes
    with_variants: set[str] = field(default_factory=set)
    # Seed `source_names` (staff decisions): (source id, name key) -> (gen id, model-year span)
    # of the seed variant that name means. In a shared year it picks the generation first.
    pins: dict[tuple[str, str], list[tuple[str, YearSpan | None]]] = field(default_factory=dict)

    def pinned(self, source_id: str, name_key: str, year: int) -> set[str]:
        """Generations whose seed variant claims this source name for this model year."""
        return {
            g for g, span in self.pins.get((source_id, name_key), []) if span_covers(span, year)
        }

    def add_variant(
        self, gen_id: str, name: str | None, kwh: set[float], makes_variant: bool = True
    ) -> None:
        # Attach-only records (RDW, TGK, ADEME, ...) never make a variant, so they add name and
        # battery evidence but do not count as "this generation has variants": otherwise a
        # generation with no published row (Kia EV6 / XPeng G6 facelift, T-068) turns its
        # shared year ambiguous and RDW parks the cars at model level on the other one.
        if makes_variant:
            self.with_variants.add(gen_id)
        if name:
            self.names.setdefault(gen_id, set()).add(key(name))
        self.kwh.setdefault(gen_id, set()).update(kwh | kwh_in_text(name))

    def supports(self, gen_id: str, name_key: str, kwh: set[float]) -> bool:
        if name_key and name_key in self.names.get(gen_id, set()):
            return True
        known = self.kwh.get(gen_id, set())
        return any(abs(a - b) <= KWH_TOLERANCE for a in kwh for b in known)


def find_generation(
    model: SeedModel,
    year: int | None,
    evidence: GenerationEvidence | None = None,
    record: SourceRecord | None = None,
) -> tuple[SeedGeneration | None, str]:
    if year is None:
        if len(model.generations) == 1:
            return model.generations[0], ""
        if evidence is not None and record is not None:
            # No year (ADEME): battery/name evidence may still single out one generation.
            nk, kwh = key(record.variant_name), record_kwh(record)
            backed = [g for g in model.generations if evidence.supports(g.id, nk, kwh)]
            if len(backed) == 1:
                return backed[0], ""
        return None, f"no year and model has {len(model.generations)} generations"
    hits = [g for g in model.generations if g.covers(year)]
    if not hits:
        return None, f"year {year} outside every generation of {model.id}"
    newest = max(hits, key=lambda g: g.year_start)
    if len(hits) == 1 or evidence is None:
        return newest, ""  # no evidence index: plain "newer wins" (Q-014)
    name_key = key(record.variant_name) if record is not None else ""
    if record is not None and name_key:
        # A seed source name scoped to these model years (`source_names`) is a staff decision:
        # it outranks name/kWh evidence, which would send the shared year to the newest
        # generation (T-068: OpenEV Ioniq 5 MY2024 "Base" is the gen1 77.4 kWh car, T-110).
        pinned = [g for g in hits if g.id in evidence.pinned(record.source.id.root, name_key, year)]
        if len(pinned) == 1:
            return pinned[0], ""
    kwh = record_kwh(record) if record is not None else set()
    backed = [g for g in hits if evidence.supports(g.id, name_key, kwh)]
    if backed:
        return max(backed, key=lambda g: g.year_start), ""
    if sum(1 for g in hits if g.id in evidence.with_variants) >= 2:
        ids = ", ".join(g.id for g in sorted(hits, key=lambda g: g.year_start))
        return None, f"{AMBIGUOUS_GENERATION}: {year} is shared by {ids}; no name/battery evidence"
    return newest, ""


def normalise_unit(fname: str, sv: SpecValue) -> tuple[object, str, str]:
    """Return (value, canonical unit, problem). Problem is '' when the value is usable."""
    value = sv.value
    unit = sv.unit.strip()
    if fname == "price_new":
        cur = unit.upper()
        if cur not in CURRENCIES:
            return value, unit, f"unsupported currency {unit!r}"
        return value, cur, ""
    if fname == "dc_curve":
        try:
            raw = json.loads(value) if isinstance(value, str) else value
            return ChargeCurve.model_validate(raw), "kW", ""
        except Exception as exc:
            return value, unit, f"invalid charge curve: {str(exc)[:80]}"
    canonical = CANONICAL_UNITS.get(fname)
    if canonical is None:
        return value, unit, f"no canonical unit for {fname}"
    low = unit.lower()
    if _UNIT_ALIASES.get(low) == canonical or unit == canonical:
        return value, canonical, ""
    factor = _CONVERSIONS.get((fname, low))
    if factor is not None and isinstance(value, int | float) and not isinstance(value, bool):
        return float(value) * factor, canonical, ""
    return value, unit, f"unit {unit!r} not convertible to {canonical}"


def _make_fact(
    record: SourceRecord,
    fname: str,
    sv: SpecValue,
    subject_type: str,
    subject_id: str,
    result: MatchResult,
) -> Fact | None:
    value, unit, problem = normalise_unit(fname, sv)
    if problem:
        result.problems.append(
            Problem(
                "unit",
                record.source.id.root,
                record.record_key,
                subject_id,
                fname,
                str(sv.value),
                sv.unit,
                problem,
            )
        )
        return None
    return Fact(
        id=f"{record.source.id.root}:{record.record_key}:{fname}",
        subject_type=subject_type,
        subject_id=subject_id,
        field=FactField(fname),
        value=value,
        unit=unit,
        country=record.country,
        source=record.source,
        source_record=record.record_key,
        retrieved_at=record.retrieved_at,
        confidence=record.confidence,
        claim=True
        if record.source.id.root in CLAIM_SOURCES and fname != "registered_count"
        else None,
    )


def _unmatched(record: SourceRecord, reason: str) -> UnmatchedRow:
    return UnmatchedRow(
        source_id=record.source.id.root,
        record_key=record.record_key,
        make=record.make,
        model=record.model,
        variant_name=record.variant_name or "",
        year="" if record.year is None else str(record.year),
        reason=reason,
    )


def build_evidence(
    records: list[SourceRecord],
    seed: Seed,
    manual: list[ManualVariant],
    generation_kwh: dict[str, set[float]] | None = None,
    scoped: bool = False,
) -> GenerationEvidence:
    """Pre-pass: variant names and battery sizes per generation from seed-manual variants and
    spec records whose year falls in exactly one generation (no circular guessing)."""
    ev = GenerationEvidence()
    for gid, kwhs in (generation_kwh or {}).items():
        ev.kwh.setdefault(gid, set()).update(kwhs)
    for mv in manual:
        if mv.record.source.id.root in EXCLUDED_SOURCES or mv.generation_id not in seed.generations:
            continue
        ev.add_variant(mv.generation_id, mv.name, set().union(*(record_kwh(r) for r in mv.records)))
        for sid_, keys in mv.source_names.items():
            ev.names.setdefault(mv.generation_id, set()).update(keys)
            for k in keys:
                span = mv.source_name_years.get((sid_, k))
                ev.pins.setdefault((sid_, k), []).append((mv.generation_id, span))
    for rec in records:
        sid = rec.source.id.root
        if rec.kind != "spec" or sid in EXCLUDED_SOURCES or sid in COUNT_ONLY_SOURCES:
            continue
        make_id = seed.make_id_for(rec.make, sid, scoped)
        if make_id is None or rec.year is None:
            continue
        model, _ = find_model(seed, make_id, match_view(rec), scoped)
        if model is None:
            continue
        hits = [g for g in model.generations if g.covers(rec.year)]
        if len(hits) == 1:
            ev.add_variant(hits[0].id, rec.variant_name or "base", record_kwh(rec),
                           makes_variant=sid not in ATTACH_ONLY_SOURCES)  # fmt: skip
    return ev


def match_records(
    records: list[SourceRecord],
    seed: Seed,
    manual: list[ManualVariant] | None = None,
    generation_kwh: dict[str, set[float]] | None = None,
    scoped_aliases: bool | None = None,
    eea_corroboration: bool | None = None,
    holds: list[SourceHold] | None = None,
    tgk_split: dict[str, dict[str, set[str]]] | None = None,
) -> MatchResult:
    """`generation_kwh`: optional battery sizes per generation (e.g. from battery_packs.yaml
    via variant_links.yaml), used as evidence for shared-year records. `scoped_aliases`:
    None = env EV_SCOPED_ALIASES / default (see `scoped_aliases_enabled`); `eea_corroboration`
    likewise (EV_EEA_CORROBORATION, `eea_corroboration_enabled`). `holds`: `source_holds`
    from variants.yaml (records that go to review by name and model year). `tgk_split`: TGK
    split evidence per variant (None = match/tgk_split.yaml, see `load_tgk_split`)."""
    result = MatchResult()
    result.tgk_split = load_tgk_split() if tgk_split is None else tgk_split
    scoped = scoped_aliases_enabled(scoped_aliases)
    result.scoped_aliases = scoped
    corroborate = eea_corroboration_enabled(eea_corroboration)
    result.eea_corroboration = corroborate
    manual = manual or []
    evidence = build_evidence(records, seed, manual, generation_kwh, scoped)
    # (generation_id, variant name key) -> variant id
    variant_ids: dict[tuple[str, str], str] = {}
    # Q-062: (generation_id, source id, variant name key) -> [(model years or None = all,
    # seed-manual variant id)]; year-scoped names may point one name at several variants.
    source_name_ids: dict[tuple[str, str, str], list[tuple[YearSpan | None, str]]] = {}
    holds = holds or []

    for mv in manual:
        if mv.record.source.id.root in EXCLUDED_SOURCES:
            result.excluded[mv.record.source.id.root] += 1
            continue
        gen = seed.generations.get(mv.generation_id)
        if gen is None:
            result.unmatched.append(
                _unmatched(mv.record, f"seed-manual generation {mv.generation_id} not in seed")
            )
            continue
        variant_ids[(gen.id, key(mv.name))] = mv.id
        for sid_, keys in mv.source_names.items():
            for k in keys:
                span = mv.source_name_years.get((sid_, k))
                targets = source_name_ids.setdefault((gen.id, sid_, k), [])
                for prev_span, prev in targets:
                    if prev != mv.id and spans_overlap(prev_span, span):
                        raise ValueError(f"source_names: {sid_} {k!r} on {prev} and {mv.id}")
                targets.append((span, mv.id))
        info = result.variants.setdefault(mv.id, VariantInfo(mv.id, gen.id, mv.name))
        for sid_, keys in mv.source_names.items():
            info.source_names.setdefault(sid_, set()).update(keys)
        info.source_name_years.update(mv.source_name_years)
        if mv.year_start is not None:
            info.years.add(int(mv.year_start))
        if mv.year_end is not None:
            info.explicit_end = int(mv.year_end)
        elif mv.year_start is not None:
            info.open_end = True
        for rec in mv.records:  # the variant's own record, then one per cited value
            _add_spec_facts(rec, gen, mv.id, info, result)
            result.seed_record_keys.add(rec.record_key)
        kwhs = set().union(*(battery_figures(r, mv.name) for r in mv.records))
        if kwhs:
            result.seed_kwh[mv.id] = kwhs
        power = set().union(*(_spec_num(r, "power_kw") for r in mv.records))
        if power:
            result.seed_power[mv.id] = power
        cited_power = set().union(*(_spec_num(r, "power_kw") for r in mv.cited_records))
        if cited_power:
            result.seed_cited_power[mv.id] = cited_power
        result.matched_records += 1

    ordered = sorted(
        records, key=lambda r: (-priority_of(r.source.id.root), r.source.id.root, r.record_key)
    )
    deferred: list[tuple[SourceRecord, SeedGeneration]] = []
    # TGK records whose year two generations share: (source, record key) -> those generations.
    multi_gen: dict[tuple[str, str], list[SeedGeneration]] = {}
    for rec in ordered:
        sid = rec.source.id.root
        if sid in EXCLUDED_SOURCES:
            result.excluded[sid] += 1
            continue
        if rec.kind == "corroboration":
            if sid in YEAR_CORROBORATION_SOURCES:
                result.year_records.append(rec)
            elif not corroborate:
                result.corroboration_skipped["flag off"] += 1
            elif sid not in CORROBORATION_SOURCES:
                result.corroboration_skipped[f"{sid}: not a corroboration source"] += 1
            else:
                _add_corroboration(rec, seed, evidence, result, scoped)
            continue
        if sid in COUNT_ONLY_SOURCES and rec.kind != "registration_count":
            result.count_only_skipped[sid] += 1
            continue
        view = match_view(rec)
        model, why, note, make_known = find_record_model(seed, view, scoped)
        if model is None:
            if make_known:
                result.unmatched.append(_unmatched(rec, why))
            else:
                result.other_makes[(sid, rec.make.strip().upper())] += 1
            continue
        if rec.kind == "registration_count":
            _add_count(rec, model, result, evidence, note)
            continue
        gen, why = find_generation(model, rec.year, evidence, rec)
        if gen is None and sid in TGK_EVIDENCE_SOURCES and why.startswith(AMBIGUOUS_GENERATION):
            # TGK figures (battery fit, years) can tell the generations apart: attach decides
            # among the variants of every generation sharing the year (see 9 above).
            shared = sorted(
                (g for g in model.generations if g.covers(rec.year)), key=lambda g: g.year_start
            )
            deferred.append((rec, shared[-1]))
            multi_gen[(sid, rec.record_key)] = shared
            continue
        if gen is None:
            result.unmatched.append(_unmatched(rec, why))
            continue
        hold = next((h for h in holds if h.holds(gen.id, sid, rec.variant_name, rec.year)), None)
        if hold is not None:
            result.unmatched.append(_unmatched(rec, f"{SOURCE_HOLD}: {hold.reason}"))
            continue
        if sid in ATTACH_ONLY_SOURCES:
            deferred.append((rec, gen))
            continue
        name = rec.variant_name or "base"
        vkey = (gen.id, key(name) or "base")
        vid = _source_name_vid(source_name_ids.get((gen.id, sid, vkey[1])), rec.year)
        aliased = vid is not None
        vid = vid or variant_ids.get(vkey)
        new_vid = vid is None
        if vid is None:
            vid = f"{gen.id}-{slug(name) or 'base'}"
        rk = battery_figures(rec)
        if battery_contradicts(rk, result.seed_kwh.get(vid, set())):
            # Battery gate (see 4 above): a different car under the seed variant's name/id.
            result.unmatched.append(
                _unmatched(
                    rec,
                    f"{NO_BATTERY_MATCH} {vid} ({_kwh_text(rk)} vs "
                    f"{_kwh_text(result.seed_kwh[vid])} kWh)",
                )
            )
            continue
        rp, sp = record_power(rec), result.seed_power.get(vid, set())
        if (
            aliased
            and rp
            and sp
            and not _close_rel(rp, sp, SEED_POWER_GATE_REL)
            and _cited_power_wins(rec, vid, rp, rk, result)
        ):
            rec = _without_power(rec, vid, result)
            rp = set()
        if aliased and rp and sp and not _close_rel(rp, sp, SEED_POWER_GATE_REL):
            # Seed power gate (see 4 above): same name or alias, different motor.
            result.unmatched.append(
                _unmatched(
                    rec,
                    f"{NO_SEED_POWER_MATCH} {vid} ({_num_text(rp)} vs {_num_text(sp)} kW)",
                )
            )
            continue
        if new_vid:
            variant_ids[vkey] = vid
        if aliased:
            result.aliased.add(vid)
        info = result.variants.setdefault(vid, VariantInfo(vid, gen.id, rec.variant_name or "Base"))
        if rec.year is not None:
            info.years.add(rec.year)
        _add_spec_facts(rec, gen, vid, info, result)
        result.matched_records += 1
    split_year_bands(result)
    attach_records(deferred, result, multi_gen)
    result.corroboration_facts = _best_corroboration(result.corroboration_facts)
    return result


def _cited_power_wins(
    rec: SourceRecord, vid: str, rp: set[float], rk: set[tuple[float, str]], result: MatchResult
) -> bool:
    """T-153: the seed's cited maker power overrules the record's power when the record's
    battery positively agrees with the seed (a different motor on the same name stays out:
    without battery evidence the seed power gate still applies). The record's power only
    lifts the gate when it differs from the cited figure itself, not just from a spec one."""
    cited = result.seed_cited_power.get(vid)
    seed_kwh = result.seed_kwh.get(vid)
    if not cited or not rk or not seed_kwh or battery_contradicts(rk, seed_kwh):
        return False
    return not _close_rel(rp, cited, SEED_POWER_GATE_REL)


def _without_power(rec: SourceRecord, vid: str, result: MatchResult) -> SourceRecord:
    """The record with its power_kw spec left out (it never becomes a Fact), logged."""
    sv = rec.specs.get(FactField.power_kw)
    cited = _num_text(result.seed_cited_power[vid])
    shown = _num_text(record_power(rec))
    result.problems.append(
        Problem(
            "match", rec.source.id.root, rec.record_key, vid, FactField.power_kw.value,
            shown, sv.unit if sv else "kW", f"{CITED_POWER_WINS} ({shown} vs {cited} kW cited)",
        )
    )  # fmt: skip
    specs = {k: v for k, v in rec.specs.items() if k != FactField.power_kw}
    return rec.model_copy(update={"specs": specs})


def _add_corroboration(
    rec: SourceRecord,
    seed: Seed,
    evidence: GenerationEvidence,
    result: MatchResult,
    scoped: bool,
) -> None:
    """A corroboration record becomes generation facts (Q-019); never a variant fact."""
    model, _, _, _ = find_record_model(seed, match_view(rec), scoped)
    if model is None:
        result.corroboration_skipped["model not in seed"] += 1
        return
    gen, why = find_generation(model, rec.year, evidence, rec)
    if gen is None:
        reason = AMBIGUOUS_GENERATION if why.startswith(AMBIGUOUS_GENERATION) else "no generation"
        result.corroboration_skipped[reason] += 1
        return
    weight_sv = rec.specs.get(FactField.registered_count)
    weight = int(weight_sv.value) if weight_sv and isinstance(weight_sv.value, int | float) else 0
    for f, sv in rec.specs.items():
        fname = f.value if isinstance(f, FactField) else str(f)
        if fname == "registered_count":
            continue
        fact = _make_fact(rec, fname, sv, "generation", gen.id, result)
        if fact is not None:
            result.corroboration_facts.append(
                MatchedFact(
                    fact,
                    rec.source.id.root,
                    priority_of(rec.source.id.root),
                    rec.year,
                    gen.id,
                    gen.model_id,
                    weight=weight,
                )
            )


def _best_corroboration(facts: list[MatchedFact]) -> list[MatchedFact]:
    """One per (source, generation, field, year): the average with the most registrations
    behind it (then the lowest fact id). Several countries or commercial names ("KONA",
    "KONA ELECTRIC") never give several chances to agree."""
    best: dict[tuple[str, str, str, int | None], MatchedFact] = {}
    for mf in sorted(facts, key=lambda m: (-(m.weight or 0), m.fact.id)):
        k = (mf.source_id, str(mf.generation_id), mf.fact.field.value, mf.year)
        best.setdefault(k, mf)
    return sorted(best.values(), key=lambda m: m.fact.id)


# --- attach-only sources -------------------------------------------------------------------

# Words that say nothing about which variant a name means.
_STOP_TOKENS = frozenset(
    [
        "electric",
        "electrique",
        "elettrica",
        "ev",
        "bev",
        "moteur",
        "motor",
        "kw",
        "kwh",
        "ch",
        "hp",
        "ps",
        "auto",
        "automatic",
        "base",
        "edition",
        "new",
        "version",
        "e",
        "range",  # A-05 F8: "Standard Range" and "Long Range" share it; see _PHRASES
    ]
)
# A-05 F8: trim-neutral words. They count as name evidence only next to a distinctive shared
# word or numeric evidence (kWh, kW, WLTP), never on their own.
_GENERIC_TOKENS = frozenset({"long", "standard", "extended", "plus", "max", "std"})
# Two-word trim phrases kept as one token, so "standard range" never shares a word with
# "long range" ("range" alone is a stop word). The joined token is distinctive evidence.
_PHRASES: dict[tuple[str, str], str] = {
    ("long", "range"): "longrange",
    ("standard", "range"): "standardrange",
    ("std", "range"): "standardrange",
    ("extended", "range"): "extendedrange",
}
_KW_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kw(?!h)", re.IGNORECASE)
POWER_TOLERANCE = 0.02
WLTP_TOLERANCE = 0.02

# Q-086 power gate (see 9 above). The absolute floor keeps rounding of small motors
# (RDW 100 kW vs a 102 kW maker figure) from counting as a contradiction.
POWER_GATE_SOURCES = frozenset({"rdw"})
POWER_GATE_REL = 0.02
POWER_GATE_ABS_KW = 3.0
NO_POWER_MATCH = "no variant with matching power"
AMBIGUOUS_EVIDENCE = "ambiguous evidence"
NO_EVIDENCE = "no variant evidence (name, kWh, kW, WLTP)"


# T-159: RDW model-year aggregates (record key `...[merk|handelsbenaming|jaar]...`: one value
# for every car of a trade name and first-admission year) say nothing about a variant except
# its year and the trade-name words. Two rules (year_aggregate_pick):
# - Own WLTP: a pick whose only evidence is the aggregate's own WLTP, while 2+ candidates' years
#   hold its year, goes to review. The aggregate mixes every variant of that year (the 2021
#   Model Y aggregate, 507 km = the 2021 Long Range, sat on the Performance row because 507 was
#   within 2 % of the Performance's WLTP).
# - Year only: no evidence at all, and the candidates' years don't overlap (rows split only by
#   year, e.g. E-Tourneo Courier 2025 vs the 2026 update): the one whose years hold it gets it.
YEAR_AGGREGATE_SOURCES = frozenset({"rdw"})
YEAR_AGGREGATE_KEY = "[merk|handelsbenaming|jaar]"
YEAR_AGG_OWN_WLTP = "model-year aggregate: only its own WLTP fits; several variants hold its year"
YEAR_ONLY_NONE = "no variant's years hold"


def is_year_aggregate(rec: SourceRecord) -> bool:
    return rec.source.id.root in YEAR_AGGREGATE_SOURCES and YEAR_AGGREGATE_KEY in rec.record_key


# A-30 follow-up: a record whose own text says "Long Range" / "Standard Range" may only attach
# to a candidate above / below the biggest step in the pool's known pack sizes (EPA rows
# carry no kWh, so a US Long Range row could land on the EU 58 kWh car). It only rules out
# candidates of the other half; unknown-battery candidates stay. One pack size = no rule.
RANGE_CLASS_SOURCES = frozenset({"fueleconomy"})
RANGE_CLASS_TOKENS = {"longrange": "max", "extendedrange": "max", "standardrange": "min"}
NO_RANGE_CLASS_MATCH = "no variant with the named range class"
RANGE_CLASS_GAP = 0.10


def range_class_pool(rec: SourceRecord, pool: list[_Candidate]) -> tuple[list[_Candidate], str]:
    """(pool, applied class) for RANGE_CLASS_SOURCES; class "" = rule not applied."""
    toks = set(_joined_tokens(f"{rec.model} {rec.variant_name or ''}"))
    cls = {RANGE_CLASS_TOKENS[t] for t in toks if t in RANGE_CLASS_TOKENS}
    if len(cls) != 1:
        return pool, ""
    sizes = sorted({max(c.kwh) for c in pool if c.kwh})
    # Split the pack sizes at their biggest step, and only when that step is a real class gap
    # (>= RANGE_CLASS_GAP): 75 vs 79 kWh are both "long range" (Model Y), 63 vs 77 are not.
    gaps = [(b / a, a, b) for a, b in zip(sizes, sizes[1:], strict=False)]
    if not gaps or max(gaps)[0] < 1 + RANGE_CLASS_GAP:
        return pool, ""
    _, low, high = max(gaps)
    if cls == {"max"}:
        return [c for c in pool if not c.kwh or max(c.kwh) >= high], "max"
    return [c for c in pool if not c.kwh or max(c.kwh) <= low], "min"


def power_close(a: float, b: float) -> bool:
    """Q-086 tolerance: within 2 % of the larger figure or 3 kW, whichever is larger."""
    return abs(a - b) <= max(POWER_GATE_ABS_KW, POWER_GATE_REL * max(abs(a), abs(b)))


def record_power(rec: SourceRecord) -> set[float]:
    """Power evidence of a record: "<kW> kW" in its variant name, or a power_kw spec."""
    power = {float(m.group(1).replace(",", ".")) for m in _KW_RE.finditer(rec.variant_name or "")}
    return power | _spec_num(rec, "power_kw")


def _numbers(mfs: list[MatchedFact], fname: str) -> set[float]:
    out: set[float] = set()
    for mf in mfs:
        v = mf.fact.value
        if mf.fact.field.value == fname and isinstance(v, int | float) and not isinstance(v, bool):
            out.add(float(v))
    return out


def _close_rel(a: set[float], b: set[float], tol: float) -> bool:
    return any(abs(x - y) <= tol * max(abs(x), abs(y)) for x in a for y in b)


def _spec_num(rec: SourceRecord, fname: str) -> set[float]:
    sv = rec.specs.get(FactField(fname))
    if sv is None or isinstance(sv.value, bool) or not isinstance(sv.value, int | float):
        return set()
    return {float(sv.value)}


@dataclass
class _Candidate:
    root: str
    members: list[str]  # the root variant id and its year-band ids
    name_tokens: set[str]
    kwh: set[float]
    power: set[float]
    wltp: set[float]
    # TGK: the defining (kWh, basis) figures, basis net / gross / name (see tgk_pick)
    battery: set[tuple[float, str]] = field(default_factory=set)


def _joined_tokens(text: str | None) -> list[str]:
    """tokens() with the two-word trim phrases of _PHRASES joined into one token."""
    toks = tokens(text)
    out: list[str] = []
    i = 0
    while i < len(toks):
        pair = (toks[i], toks[i + 1]) if i + 1 < len(toks) else None
        if pair in _PHRASES:
            out.append(_PHRASES[pair])  # type: ignore[index]
            i += 2
        else:
            out.append(toks[i])
            i += 1
    return out


def _distinct_tokens(text: str | None, drop: set[str]) -> set[str]:
    return {t for t in _joined_tokens(text) if t not in _STOP_TOKENS and t not in drop}


def name_score(words: set[str], cand: set[str], numeric: int = 0) -> int:
    """Shared name words as evidence (A-05 F8): generic words count only next to a
    distinctive shared word or numeric evidence."""
    shared = words & cand
    distinct = shared - _GENERIC_TOKENS
    if distinct or numeric > 0:
        return len(shared)
    return 0


def attach_records(
    deferred: list[tuple[SourceRecord, SeedGeneration]],
    result: MatchResult,
    multi_gen: dict[tuple[str, str], list[SeedGeneration]] | None = None,
) -> None:
    """Place attach-only records (ADEME, KilowattApp, RDW, TGK) on existing variants (see 9
    above). `multi_gen`: TGK records whose year two generations share; their candidates are
    the variants of all those generations."""
    if not deferred:
        return
    multi_gen = multi_gen or {}
    band_root: dict[str, str] = {}
    for b in result.year_bands:
        for nid in b["new_ids"]:  # type: ignore[union-attr]
            band_root[str(nid)] = str(b["variant_id"])
    facts_of: dict[str, list[MatchedFact]] = {}
    for mf in result.spec_facts:
        facts_of.setdefault(mf.fact.subject_id.root, []).append(mf)
    by_gen: dict[str, dict[str, list[str]]] = {}
    for vid, info in result.variants.items():
        root = band_root.get(vid, vid)
        by_gen.setdefault(info.generation_id, {}).setdefault(root, []).append(vid)

    for rec, gen in deferred:
        sid = rec.source.id.root
        gens = multi_gen.get((sid, rec.record_key), [gen])
        where = " / ".join(g.id for g in gens)
        roots = {r: m for g in gens for r, m in by_gen.get(g.id, {}).items()}
        if not roots:
            result.unmatched.append(_unmatched(rec, f"no variant in {where} to attach to"))
            continue
        # Words of the make and the seed model name say nothing about the variant.
        drop = set(tokens(rec.make)) | set(tokens(gen.model_id))
        cands: list[_Candidate] = []
        for root, members in sorted(roots.items()):
            mfs = [mf for v in members for mf in facts_of.get(v, [])]
            info = result.variants[root]
            cands.append(
                _Candidate(
                    root,
                    sorted(members),
                    _distinct_tokens(info.name, drop),
                    _numbers(mfs, "battery_kwh_net")
                    | _numbers(mfs, "battery_kwh_gross")
                    | kwh_in_text(info.name),
                    _numbers(mfs, "power_kw"),
                    _numbers(mfs, "wltp_range_km"),
                    _defining_kwh(mfs, info.name),
                )
            )
        rec_name = rec.variant_name or ""
        gated = sid in POWER_GATE_SOURCES
        pool, need_evidence = cands, False
        power = record_power(rec) if gated else set()
        if power:
            pool, need_evidence = _power_pool(power, cands)
            if not pool:
                kw = ", ".join(f"{p:g}" for p in sorted(power))
                result.unmatched.append(
                    _unmatched(rec, f"attach-only: {NO_POWER_MATCH} ({kw} kW) in {where}")
                )
                continue
        if sid in RANGE_CLASS_SOURCES:
            pool, rclass = range_class_pool(rec, pool)
            if rclass and not pool:
                result.unmatched.append(
                    _unmatched(rec, f"attach-only: {NO_RANGE_CLASS_MATCH} in {where}")
                )
                continue
        rk = battery_figures(rec)
        ruled_out: list[_Candidate] = []
        if rk:
            # Battery gate (see 9 above): rule out candidates whose seed battery contradicts.
            known = [c for c in pool if result.seed_kwh.get(c.root)]
            fit = [c for c in known if not battery_contradicts(rk, result.seed_kwh[c.root])]
            if len(fit) < len(known):
                unknown = [c for c in pool if not result.seed_kwh.get(c.root)]
                if not fit and not unknown:
                    seeds = set().union(*(result.seed_kwh[c.root] for c in known))
                    result.unmatched.append(
                        _unmatched(
                            rec,
                            f"attach-only: {NO_BATTERY_MATCH} ({_kwh_text(rk)} vs "
                            f"{_kwh_text(seeds)} kWh) in {where}",
                        )
                    )
                    continue
                ruled_out = [c for c in known if c not in fit]
                pool = fit + unknown
                # The gate only rules out: "within tolerance" is no evidence for what is left
                # (Model S "70" at 69 kWh is not the "60" just because the "85" is out).
                need_evidence = True
        exact = [c for c in pool if result.variants[c.root].named(sid, rec_name, rec.year)]
        if len(exact) == 1:
            chosen, why = exact[0], ""
        elif is_year_aggregate(rec) and len(pool) > 1:
            chosen, why = year_aggregate_pick(rec, pool, drop, result)
            if (
                chosen is not None
                and ruled_out
                and not _beats_ruled_out(rec, chosen, ruled_out, drop)
            ):  # the same battery-gate check as the general path below (review #204)
                why = f"{NO_BATTERY_MATCH}: name points at a ruled-out variant, not {chosen.root}"
                chosen = None
        elif sid in TGK_EVIDENCE_SOURCES:
            chosen, why = tgk_pick(rec, pool, drop, result)
        elif len(pool) == 1 and not need_evidence:
            chosen, why = pool[0], ""  # the generation's only variant, or the only power match
        else:
            chosen, why = _best_candidate(rec, pool, drop, strict=gated)
            if (
                chosen is not None
                and ruled_out
                and not _beats_ruled_out(rec, chosen, ruled_out, drop)
            ):
                why = f"{NO_BATTERY_MATCH}: name points at a ruled-out variant, not {chosen.root}"
                chosen = None
        if chosen is None:
            if ruled_out:
                why += "; battery gate ruled out " + ", ".join(c.root for c in ruled_out)
            result.unmatched.append(_unmatched(rec, f"attach-only: {why} in {where}"))
            continue
        members = chosen.members
        if power and len(members) > 1:
            # A year band whose own power contradicts the record is not its band (an RDW
            # 2024 e-208 at 100 kW is the old 50 kWh car, not the 115 kW 2024 band).
            fits = [
                v
                for v in members
                if not (vp := _numbers(facts_of.get(v, []), "power_kw"))
                or any(power_close(p, q) for p in power for q in vp)
            ]
            members = fits or members
        vid = _band_for_year(members, rec.year, result)
        info = result.variants[vid]
        target = next((g for g in gens if g.id == info.generation_id), gen)
        _add_spec_facts(rec, target, vid, info, result)
        result.attached[sid] += 1
        result.matched_records += 1


# --- TGK evidence (rdw-tgk): pick the variant inside a generation -------------------------
#
# A type-approval version names no battery, so the variant is chosen by what the version's
# own figures imply, and only when exactly one candidate fits (ties and misfits -> review):
# 1. Years: the version's first-admission year within the candidate's years, +-1 year
#    (first admission lags or leads the model year).
# 2. Battery: range x consumption of the same cycle (NEDC pair; WLTP best pair) is the
#    energy the test drew from the wall: usable kWh x 1.03-1.45, gross kWh x 1.0-1.25 on
#    the 2026-11-15 TGK rows of Golf, i3, Zoe, Leaf, Ioniq, Kona, Niro, Soul, Model 3/S,
#    e-208, Mini, Honda e, I-Pace, e-tron and EQC. A candidate fits when every such energy
#    is within TGK_ENERGY_RATIO of one of its defining battery figures (seed-manual's when
#    it has one, else the highest-priority source's; kWh in its name only when no source
#    has one). Candidates of unknown battery stay only when no candidate fits (then they
#    need name evidence). Battery fits next to name-only candidates of unknown battery is a
#    tie for review (A-05 F12), never decided by the name count.
# 0. Range in the name: a 3-digit number in a candidate name equal to the version's NEDC or
#    WLTP range ("Q210", "R240") limits the choice to those candidates (checked first; the
#    year and battery checks still apply, so a contradiction goes to review).
# 3. Name: distinctive words of the maker trade names ("I3S", "E-TRON 55"), and a kWh figure
#    in the plate name ("NISSAN LEAF 24KWH") within 1 kWh of the candidate's.
# 4. WLTP: the version's best-case WLTP within 2 % of the candidate's known WLTP.
# 5. Drivetrain: OFF (A-05 F12, TGK_AWD_TIE_BREAK). TGK leaves 30-minute power out on
#    multi-motor versions, but a missing field is not evidence; such ties go to review.
# 6. Trade name (still tied): a candidate whose name extends the model name by up to two
#    characters ("i3s" for model i3) is dropped when the version's trade name lacks that
#    word (a plain "I3" version is not an i3s), if another candidate stays.
# Running-order mass is not used: seed kerb weights are sparse and not on the same basis.
TGK_EVIDENCE_SOURCES = frozenset({"rdw-tgk"})
# Energy drawn on the test / battery kWh, per basis of the battery figure (see 2 above).
TGK_ENERGY_RATIO: dict[str, tuple[float, float]] = {
    "net": (1.0, 1.5),
    "gross": (0.95, 1.3),
    "name": (0.95, 1.5),  # kWh in a variant name: net or gross, unknown
}
TGK_YEAR_SLACK = 1
# A-05 F12: "no 30-minute power -> prefer AWD" infers from a missing field, so it is off;
# such ties go to review. Kept as a switch so its effect can be measured.
TGK_AWD_TIE_BREAK = False
TGK_SPLIT_FILE = Path(__file__).with_name("tgk_split.yaml")
TGK_SPLIT_FIELDS = ("type_codes", "power_30min_kw", "top_speed_kmh")  # order applied (T-153)
TGK_TIE = "tgk: several variants fit"
TGK_MISFIT = "tgk: no variant fits"
_RANGE_NUM_RE = re.compile(r"(?<!\d)(\d{3})(?!\d)(?!\s*(?:kw|ah|v\b|nm|ps|hp|km/h))", re.I)


def load_tgk_split(path: Path = TGK_SPLIT_FILE) -> dict[str, dict[str, set[str]]]:
    """match/tgk_split.yaml -> {variant id: {field: values as text}} (see the file)."""
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if doc.get("schema") != "tgk-split/v1":
        raise ValueError(f"{path}: schema must be tgk-split/v1")
    out: dict[str, dict[str, set[str]]] = {}
    for vid, entry in (doc.get("variants") or {}).items():
        unknown = set(entry) - set(TGK_SPLIT_FIELDS) - {"basis", "motors"}
        if unknown or not entry.get("basis"):
            raise ValueError(f"{path}: {vid}: needs a basis; unknown keys {sorted(unknown)}")
        if entry.get("motors") not in (None, 1, 2):
            raise ValueError(f"{path}: {vid}: motors must be 1 or 2")
        out[str(vid)] = {
            f: {_split_text(v) for v in entry[f]} for f in TGK_SPLIT_FIELDS if entry.get(f)
        }
        if entry.get("motors"):
            out[str(vid)]["motors"] = {_split_text(entry["motors"])}
    return out


def _split_text(v: object) -> str:
    """One form per value: numbers as "%g" (57, 57.0 -> "57"), codes upper-case."""
    if isinstance(v, int | float) and not isinstance(v, bool):
        return f"{float(v):g}"
    return str(v).strip().upper()


def tgk_type_codes(rec: SourceRecord) -> set[str]:
    """The version's TGK variant code and its uitvoering prefix (before "-"), e.g. Model Y
    "Y5LD" / Stellantis "ZKXZ" of "ZKXZ-J0A000", from the record key (sources/rdw_tgk)."""
    parts = rec.record_key.rsplit(":", 1)[-1].split("|")
    if len(parts) < 3:
        return set()
    return {_split_text(parts[1]), _split_text(parts[2].split("-")[0])} - {""}


def tgk_split_pool(
    rec: SourceRecord, pool: list[_Candidate], result: MatchResult
) -> tuple[list[_Candidate], str]:
    """T-153 split evidence for variants that share a pack, applied in TGK_SPLIT_FIELDS
    order, then `motors`. Each step only rules out candidates whose known value contradicts
    the version's; unknowns stay. (pool, "") or ([], misfit reason)."""
    evidence = {
        "type_codes": tgk_type_codes(rec),
        "power_30min_kw": {_split_text(v) for v in _spec_num(rec, "power_30min_kw")},
        "top_speed_kmh": {_split_text(v) for v in _spec_num(rec, "top_speed_kmh")},
    }
    for f in TGK_SPLIT_FIELDS:
        have = evidence[f]
        if not have:
            continue
        out = [
            c for c in pool
            if f in (known := result.tgk_split.get(c.root, {})) and not _split_fits(known[f], have)
        ]  # fmt: skip
        if out:
            pool = [c for c in pool if c not in out]
            if not pool:
                return [], f"{TGK_MISFIT} the {f} ({'/'.join(sorted(have))})"
    if evidence["power_30min_kw"]:
        # `motors: 2` in the table: that variant's TGK versions never state a 30-minute power
        # (one drivetrain row per motor), so a version that states one is not it (ID.4 GTX).
        # Not a general rule: a missing figure says nothing, and some dual-motor versions
        # carry a single row (I-Pace, A-05 F12), so only listed variants are ruled out.
        out = [c for c in pool if result.tgk_split.get(c.root, {}).get("motors") == {"2"}]
        if out:
            pool = [c for c in pool if c not in out]
            if not pool:
                return [], f"{TGK_MISFIT} the motors (30-min power stated, only dual-motor left)"
    return pool, ""


def _split_fits(known: set[str], have: set[str]) -> bool:
    """A listed value fits the version's: equal, or for a type code "A+B" (T-159) both the
    variant code and the uitvoering code (Taycan JA12 + 1040000: base car, smaller pack)."""
    return any(set(k.split("+")) <= have for k in known)


def tgk_energies(rec: SourceRecord) -> list[float]:
    """kWh drawn on the test: range x consumption / 100 per cycle (NEDC; WLTP best case)."""
    out = []
    for rng, cons in (
        ("nedc_range_km", "nedc_consumption_kwh_100km"),
        ("wltp_range_km", "consumption_kwh_100km"),
    ):
        r, c = _spec_num(rec, rng), _spec_num(rec, cons)
        if r and c:
            out.append(round(next(iter(r)) * next(iter(c)) / 100, 1))
    return out


def _defining_kwh(mfs: list[MatchedFact], name: str) -> set[tuple[float, str]]:
    """The battery figures that define a variant, as (kWh, basis): seed-manual's, else the
    highest-priority source's (other sources' kWh may be wrong or another pack's); kWh in
    the variant name (basis unknown) only when no source gives one."""
    by_src: dict[str, set[tuple[float, str]]] = {}
    for f, basis in (("battery_kwh_net", "net"), ("battery_kwh_gross", "gross")):
        for mf in mfs:
            for v in _numbers([mf], f):
                by_src.setdefault(mf.source_id, set()).add((v, basis))
    if not by_src:
        return {(v, "name") for v in kwh_in_text(name)}
    if "seed-manual" in by_src:
        return by_src["seed-manual"]
    return by_src[max(by_src, key=lambda s: (priority_of(s), s))]


def _span(c: _Candidate, result: MatchResult) -> tuple[int | None, int | None, bool]:
    """(first year, last year, open end) over the candidate's year bands."""
    years: set[int] = set()
    end: int | None = None
    open_end = False
    for v in c.members:
        info = result.variants[v]
        years |= info.years
        open_end = open_end or info.open_end
        if info.explicit_end is not None:
            end = max(end or info.explicit_end, info.explicit_end)
    if not years:
        return None, None, open_end
    return min(years), (None if open_end else max(end or max(years), max(years))), open_end


def _year_fits(c: _Candidate, year: int, result: MatchResult) -> bool:
    lo, hi, _ = _span(c, result)
    if lo is None:
        return True  # unknown years: no evidence either way
    return lo - TGK_YEAR_SLACK <= year and (hi is None or year <= hi + TGK_YEAR_SLACK)


def _battery_fits(energies: list[float], kwh: set[tuple[float, str]]) -> bool:
    def ok(e: float, b: float, basis: str) -> bool:
        lo, hi = TGK_ENERGY_RATIO[basis]
        return b > 0 and lo <= e / b <= hi

    return all(any(ok(e, b, basis) for b, basis in kwh) for e in energies)


def _tgk_words(rec: SourceRecord, drop: set[str]) -> set[str]:
    """Distinctive words of the trade-name part of the TGK name (before " · ") and model."""
    trade = (rec.variant_name or "").split(" · ")[0]
    return _distinct_tokens(trade, drop) | _distinct_tokens(rec.model, drop)


def _range_named(rec: SourceRecord, name: str) -> bool:
    """A 3-digit number in the variant name equals the version's NEDC or WLTP range."""
    ranges = {round(x) for f in ("nedc_range_km", "wltp_range_km") for x in _spec_num(rec, f)}
    return bool(ranges & {int(m.group(1)) for m in _RANGE_NUM_RE.finditer(name)})


def _has_type_code_match(rec: SourceRecord, c: _Candidate, result: MatchResult) -> bool:
    """T-163: True when `tgk_split.yaml` lists `type_codes` for `c` and the version matches one.
    Explicit type-approval variant-code evidence stands in when pack kWh is missing on the row
    (Tesla Model S 75R / 75D, Model X 60X / 75X / 90X / 100X)."""
    have = tgk_type_codes(rec)
    known = result.tgk_split.get(c.root, {}).get("type_codes")
    return bool(have and known and _split_fits(known, have))


def tgk_pick(
    rec: SourceRecord, cands: list[_Candidate], drop: set[str], result: MatchResult
) -> tuple[_Candidate | None, str]:
    """TGK evidence (see above): the one candidate that fits, else (None, reason)."""
    pool = list(cands)

    def ids(cs: list[_Candidate]) -> str:
        return ", ".join(c.root for c in cs)

    # A variant named after this range ("R240") is the only one it can be, whatever the years
    # say; if the years then disagree, that is a misfit for review, not another variant.
    by_range = [c for c in pool if _range_named(rec, result.variants[c.root].name)]
    if by_range:
        pool = by_range
    if rec.year is not None:
        pool = [c for c in pool if _year_fits(c, rec.year, result)]
        if not pool:
            return None, f"{TGK_MISFIT} year {rec.year} (+-{TGK_YEAR_SLACK})"
    pool, why = tgk_split_pool(rec, pool, result)
    if not pool:
        return None, why
    words = _tgk_words(rec, drop)
    rec_kwh = kwh_in_text(rec.model, rec.variant_name)  # "NISSAN LEAF 24KWH"
    named = {}
    for c in pool:
        kwh_hit = 1 if any(abs(a - b) <= KWH_TOLERANCE for a in rec_kwh for b in c.kwh) else 0
        named[c.root] = name_score(words, c.name_tokens, kwh_hit) + kwh_hit
    coded = {c.root for c in pool if _has_type_code_match(rec, c, result)}
    energies = tgk_energies(rec)
    need_evidence = False
    if energies:
        fit = [c for c in pool if c.battery and _battery_fits(energies, c.battery)]
        unknown = [c for c in pool if not c.battery]
        e_txt = "/".join(f"{e:g}" for e in energies)
        evidenced_unknown = [c for c in unknown if named[c.root] > 0 or c.root in coded]
        if fit and evidenced_unknown:
            # A-05 F12: battery evidence for some, name or type-code evidence for others.
            has_name = any(named[c.root] > 0 for c in evidenced_unknown)
            has_code = any(c.root in coded for c in evidenced_unknown)
            how = "name/code" if (has_name and has_code) else ("code" if has_code else "name")
            return None, f"{TGK_TIE}: battery fits {ids(fit)}, {how} only {ids(evidenced_unknown)}"
        if fit:
            pool = fit
        elif unknown:
            pool = unknown
            need_evidence = len(cands) > 1 and not all(c.root in coded for c in unknown)
        else:
            return None, f"{TGK_MISFIT} the battery (range x consumption {e_txt} kWh)"
    top = max(named[c.root] for c in pool)
    if top > 0:
        pool = [c for c in pool if named[c.root] == top]
    elif need_evidence:
        return None, f"{TGK_MISFIT}: battery unknown and no name evidence ({ids(pool)})"
    if len(pool) > 1:
        wltp = _spec_num(rec, "wltp_range_km")
        close = [c for c in pool if _close_rel(wltp, c.wltp, WLTP_TOLERANCE)]
        if close:
            pool = close
    if (
        TGK_AWD_TIE_BREAK
        and len(pool) > 1
        and energies
        and FactField.power_30min_kw not in rec.specs
    ):
        awd = [c for c in pool if "awd" in _drivetrains(c, result)]
        if awd:
            pool = awd
    if len(pool) > 1:
        # A candidate named after a longer trade name of the model ("i3s" next to model
        # "i3") is contradicted by a version whose trade name lacks that word.
        trade = set(tokens((rec.variant_name or "").split(" · ")[0])) | set(tokens(rec.model))
        # `drop` = the make and seed model tokens ("bmw", "i3").
        kept = [c for c in pool if not _trade_word_missing(c.name_tokens, trade, drop)]
        if kept:
            pool = kept
    if len(pool) == 1:
        return pool[0], ""
    return None, f"{TGK_TIE} ({ids(pool)})"


def year_aggregate_pick(
    rec: SourceRecord, pool: list[_Candidate], drop: set[str], result: MatchResult
) -> tuple[_Candidate | None, str]:
    """T-159 (see YEAR_AGGREGATE_SOURCES): the usual evidence pick, except that (1) a pick
    resting only on the aggregate's own WLTP, with 2+ candidates whose years hold the record's
    year, goes to review; (2) with no evidence at all, the year decides when the candidates'
    years don't overlap (rows split only by year) and exactly one holds it."""
    chosen, why = _best_candidate(rec, pool, drop, strict=True)
    year = rec.year
    holds = [c for c in pool if year is not None and _year_holds(c, year, result)]
    if chosen is not None:
        if _wltp_only(rec, chosen, drop) and len(holds) > 1:
            ids = ", ".join(c.root for c in holds)
            return None, f"{YEAR_AGG_OWN_WLTP} ({chosen.root}; {year}: {ids})"
        return chosen, why
    if not why.startswith(NO_EVIDENCE) or year is None or not _years_disjoint(pool, result):
        return None, why
    if len(holds) == 1:
        return holds[0], ""
    return None, f"{why}; {YEAR_ONLY_NONE} {year}"


def _wltp_only(rec: SourceRecord, c: _Candidate, drop: set[str]) -> bool:
    """The record's only evidence for `c` is its own WLTP (no name word, kWh or power)."""
    words = _distinct_tokens(rec.variant_name, drop) | _distinct_tokens(rec.model, drop)
    if name_score(words, c.name_tokens) > 0:
        return False
    if any(abs(a - b) <= KWH_TOLERANCE for a in record_kwh(rec) for b in c.kwh):
        return False
    if any(power_close(p, q) for p in record_power(rec) for q in c.power):
        return False
    return _close_rel(_spec_num(rec, "wltp_range_km"), c.wltp, WLTP_TOLERANCE)


def _year_holds(c: _Candidate, year: int, result: MatchResult) -> bool:
    """The candidate's own years hold `year` (no TGK slack); unknown years never do."""
    lo, hi, _ = _span(c, result)
    return lo is not None and lo <= year and (hi is None or year <= hi)


def _years_disjoint(pool: list[_Candidate], result: MatchResult) -> bool:
    """Every candidate has known years and no two overlap: the rows are split only by year."""
    spans = [_span(c, result)[:2] for c in pool]
    if any(lo is None for lo, _ in spans):
        return False
    spans.sort(key=lambda s: s[0] or 0)
    for (_, hi), (lo2, _) in zip(spans, spans[1:], strict=False):
        if hi is None or (lo2 or 0) <= hi:
            return False
    return True


def _trade_word_missing(cand: set[str], trade: set[str], model_toks: set[str]) -> bool:
    """True when the candidate name has a model-name extension ("i3s" for model "i3": the
    model token plus at most 2 characters) that the record's trade name does not carry."""
    for t in cand - trade:
        for m in model_toks:
            if len(m) >= 2 and t != m and t.startswith(m) and len(t) - len(m) <= 2:
                return True
    return False


def _drivetrains(c: _Candidate, result: MatchResult) -> set[str]:
    return {d for v in c.members for _, d, _ in result.variants[v].drivetrains}


def _power_pool(power: set[float], cands: list[_Candidate]) -> tuple[list[_Candidate], bool]:
    """Q-086: (candidates left after the power gate, whether the pick needs other evidence).
    Power matches win; otherwise only candidates of unknown power stay (unconfirmed)."""
    matching = [c for c in cands if any(power_close(p, q) for p in power for q in c.power)]
    if matching:
        return matching, False
    return [c for c in cands if not c.power], True


def _numeric_evidence(rec: SourceRecord, c: _Candidate) -> bool:
    """kWh within KWH_TOLERANCE, power or WLTP within tolerance of the candidate's."""
    kwh = record_kwh(rec)
    if any(abs(a - b) <= KWH_TOLERANCE for a in kwh for b in c.kwh):
        return True
    if _close_rel(record_power(rec), c.power, POWER_TOLERANCE):
        return True
    return _close_rel(_spec_num(rec, "wltp_range_km"), c.wltp, WLTP_TOLERANCE)


def _beats_ruled_out(
    rec: SourceRecord, chosen: _Candidate, ruled_out: list[_Candidate], drop: set[str]
) -> bool:
    """Battery gate: a pick made after the gate ruled candidates out needs numeric evidence,
    or a distinctive name word that no ruled-out candidate shares with the record (and no
    ruled-out candidate sharing more words). Words the ruled-out candidates share just as
    well ("iV" on Enyaq 60 and 80, "quattro" on e-tron 50 and 55) say nothing about which
    of the rest it is: name and battery disagree -> review."""
    if _numeric_evidence(rec, chosen):
        return True
    words = _distinct_tokens(rec.variant_name, drop) | _distinct_tokens(rec.model, drop)
    if name_score(words, chosen.name_tokens) < max(
        name_score(words, c.name_tokens) for c in ruled_out
    ):
        return False
    out_words = set().union(*(words & c.name_tokens for c in ruled_out))
    return bool((words & chosen.name_tokens) - out_words - _GENERIC_TOKENS)


def _best_candidate(
    rec: SourceRecord, cands: list[_Candidate], drop: set[str], strict: bool = False
) -> tuple[_Candidate | None, str]:
    """`strict` (POWER_GATE_SOURCES): a tie whose only evidence is WLTP goes to review."""
    words = _distinct_tokens(rec.variant_name, drop) | _distinct_tokens(rec.model, drop)
    kwh = record_kwh(rec)
    power = record_power(rec)
    wltp = _spec_num(rec, "wltp_range_km")
    scored: list[tuple[int, int, _Candidate]] = []  # (score, score without name words, c)
    for c in cands:
        numeric = 2 if any(abs(a - b) <= KWH_TOLERANCE for a in kwh for b in c.kwh) else 0
        if strict:
            numeric += 2 if any(power_close(p, q) for p in power for q in c.power) else 0
        else:
            numeric += 2 if _close_rel(power, c.power, POWER_TOLERANCE) else 0
        numeric += 1 if _close_rel(wltp, c.wltp, WLTP_TOLERANCE) else 0
        scored.append((name_score(words, c.name_tokens, numeric) + numeric, numeric, c))
    top = max(s for s, _, _ in scored)
    if top == 0:
        return None, NO_EVIDENCE
    best = [c for s, _, c in scored if s == top]
    if strict and len(best) > 1 and all(s == n == 1 for s, n, c in scored if c in best):
        # Only WLTP within tolerance, for 2+ candidates: the name-length tie-break below
        # would be a guess (Q-086).
        return None, f"{AMBIGUOUS_EVIDENCE}: WLTP fits " + ", ".join(c.root for c in best)
    # Same evidence: the variant whose name has the fewest words the record lacks, but only
    # when every tied candidate shares a name word with the record (A-05 F1): a variant with
    # no words ("base") would otherwise win every tie on no evidence at all.
    if len(best) > 1 and all(name_score(words, c.name_tokens, 0) > 0 for c in best):
        extra = {c.root: len(c.name_tokens - words) for c in best}
        fewest = min(extra.values())
        best = [c for c in best if extra[c.root] == fewest]
    if len(best) > 1:
        return None, "tie between " + ", ".join(c.root for c in best)
    return best[0], ""


def _band_for_year(members: list[str], year: int | None, result: MatchResult) -> str:
    """The year band of a variant that holds `year` (else the first band)."""
    if year is None or len(members) == 1:
        return members[0] if len(members) == 1 else min(members, key=len)
    starts = []
    for vid in members:
        ys = result.variants[vid].years
        starts.append((min(ys) if ys else 0, vid))
    starts.sort()
    pick = starts[0][1]
    for start, vid in starts:
        if start <= year:
            pick = vid
    return pick


def _add_spec_facts(
    rec: SourceRecord, gen: SeedGeneration, vid: str, info: VariantInfo, result: MatchResult
) -> None:
    sid = rec.source.id.root
    info.source_ids.add(sid)
    if rec.drivetrain:
        info.drivetrains.append((priority_of(sid), rec.drivetrain, sid))
    for f, sv in rec.specs.items():
        fname = f.value if isinstance(f, FactField) else str(f)
        if fname == "registered_count":
            continue
        if fname in IGNORED_FIELDS.get(sid, {}):
            result.ignored_fields[f"{sid}:{fname}"] += 1
            continue
        if fname == "price_new" and rec.country is None:
            result.problems.append(
                Problem(
                    "unit", sid, rec.record_key, vid, fname, str(sv.value), sv.unit, "no country"
                )
            )
            continue
        fact = _make_fact(rec, fname, sv, "variant", vid, result)
        if fact is not None:
            result.spec_facts.append(
                MatchedFact(fact, sid, priority_of(sid), rec.year, gen.id, gen.model_id)
            )


def count_period(rec: SourceRecord) -> str:
    """The period a count covers: KBA "2025-01..12" (YTD), DfT "2026-Q2" (quarter end),
    RDW the fetch date (fleet snapshot), else the record's year."""
    sid = rec.source.id.root
    if sid == "kba-fz10" and (m := _KBA_PERIOD_RE.search(rec.record_key)):
        return m.group(1)
    if sid == "dft-veh" and (m := _DFT_PERIOD_RE.search(rec.record_key)):
        return f"{m.group(1)}-Q{m.group(2)}"
    if COUNT_KIND.get(sid) == "fleet" or rec.year is None:
        return rec.retrieved_at.isoformat()
    return str(rec.year)


def _add_count(
    rec: SourceRecord,
    model: SeedModel,
    result: MatchResult,
    evidence: GenerationEvidence | None = None,
    note: str | None = None,
) -> None:
    sv = rec.specs.get(FactField.registered_count)
    if sv is None:
        result.unmatched.append(_unmatched(rec, "registration record without registered_count"))
        return
    if rec.year is None:
        subject_type, subject_id, gen_id = "model", model.id, None
    else:
        gen, why = find_generation(model, rec.year, evidence, rec)
        if (
            gen is None
            and rec.source.id.root in MODEL_LEVEL_FALLBACK
            and why.startswith(AMBIGUOUS_GENERATION)
        ):
            subject_type, subject_id, gen_id = "model", model.id, None
            note = "; ".join(x for x in (note, f"model level: {SHARED_YEAR_NOTE} ({why})") if x)
        elif gen is None:
            result.unmatched.append(_unmatched(rec, why))
            return
        else:
            subject_type, subject_id, gen_id = "generation", gen.id, gen.id
    fact = _make_fact(rec, "registered_count", sv, subject_type, subject_id, result)
    if fact is not None:
        result.count_facts.append(
            MatchedFact(
                fact,
                rec.source.id.root,
                priority_of(rec.source.id.root),
                rec.year,
                gen_id,
                model.id,
                period=count_period(rec),
                note=note,
            )
        )
        result.matched_records += 1


def _band_values(facts: list[MatchedFact]) -> dict[str, float]:
    """Per band field, the value of the highest-priority fact (then lowest fact id)."""
    out: dict[str, float] = {}
    for fname in BAND_THRESHOLDS:
        cands = [
            mf
            for mf in facts
            if mf.fact.field.value == fname
            and isinstance(mf.fact.value, int | float)
            and not isinstance(mf.fact.value, bool)
        ]
        if cands:
            best = sorted(cands, key=lambda m: (-m.priority, m.fact.id))[0]
            out[fname] = float(best.fact.value)
    return out


def _differs(a: dict[str, float], b: dict[str, float]) -> str:
    for fname, limit in BAND_THRESHOLDS.items():
        if fname in a and fname in b:
            scale = max(abs(a[fname]), abs(b[fname])) or 1.0
            if abs(a[fname] - b[fname]) / scale > limit + 1e-9:
                return f"{fname} {a[fname]:g} -> {b[fname]:g} (> {limit:.0%})"
    return ""


def split_year_bands(result: MatchResult) -> None:
    """Split a variant whose later model years differ a lot from its first year (T-005 review).

    Walk the model years in order; a year whose WLTP range differs from the current band's
    first year by more than 5%, or whose DC peak differs by more than 10%, starts a new band.
    Facts without a year stay in the first band. The first band keeps the variant id; later
    bands get `<variant_id>-<first year>` and the name "<name> (<first year>+)". Each split is
    recorded in `result.year_bands` (written to the run log).

    On a seed-manual variant that a source joined through a `source_names` alias, the seed's
    own facts (variant record and cited values) don't anchor bands: the alias says the
    source's records are this car, so a seed-vs-source difference is a disagreement for merge
    (conflicts.csv), not a model-year change. Bands then come from the source's own years only;
    the seed facts stay in the first band. Same-name and same-id joins keep the seed anchor."""
    by_variant: dict[str, list[MatchedFact]] = {}
    for mf in result.spec_facts:
        by_variant.setdefault(mf.fact.subject_id.root, []).append(mf)
    for vid in sorted(by_variant):
        facts = by_variant[vid]
        banding = facts
        if vid in result.aliased:
            banding = [mf for mf in facts if mf.fact.source_record not in result.seed_record_keys]
        years = sorted({mf.year for mf in banding if mf.year is not None})
        if len(years) < 2:
            continue
        per_year = {y: _band_values([mf for mf in banding if mf.year == y]) for y in years}
        bands: list[list[int]] = [[years[0]]]
        anchor = per_year[years[0]]
        reasons: list[str] = []
        for y in years[1:]:
            why = _differs(anchor, per_year[y])
            if why:
                bands.append([y])
                anchor = per_year[y]
                reasons.append(f"{y}: {why}")
            else:
                bands[-1].append(y)
                for k, v in per_year[y].items():
                    anchor.setdefault(k, v)
        if len(bands) == 1:
            continue
        info = result.variants[vid]
        orig_end, orig_open = info.explicit_end, info.open_end
        for i, band in enumerate(bands):
            start = band[0]
            next_start = bands[i + 1][0] if i + 1 < len(bands) else None
            if i == 0:
                target = info
            else:
                new_id = f"{vid}-{start}"
                target = VariantInfo(
                    new_id,
                    info.generation_id,
                    f"{info.name} ({start}+)",
                    drivetrains=list(info.drivetrains),
                )
                result.variants[new_id] = target
                for mf in facts:
                    if mf.year in band:
                        mf.fact = mf.fact.model_copy(update={"subject_id": Id(new_id)})
                        target.source_ids.add(mf.source_id)
            target.years = set(band) if i else {y for y in info.years if y < bands[1][0]}
            if next_start is not None:
                target.explicit_end, target.open_end = next_start - 1, False
            else:
                target.explicit_end, target.open_end = orig_end, orig_open
        info.source_ids = {
            mf.source_id for mf in facts if mf.fact.subject_id.root == vid
        } or info.source_ids
        result.year_bands.append(
            {
                "variant_id": vid,
                "bands": [f"{b[0]}-{b[-1]}" for b in bands],
                "new_ids": [f"{vid}-{b[0]}" for b in bands[1:]],
                "reasons": reasons,
            }
        )


@dataclass
class CountAggregate:
    value: int
    fact_ids: list[str]
    source_ids: list[str]
    level: str  # "generation" or "model"


def aggregate_counts(
    count_facts: list[MatchedFact], seed: Seed, source_id: str, country: str
) -> dict[str, CountAggregate]:
    """Sum registration counts per generation for one source+country.

    Year-level records sum into their generation. A model-level record (no year) is used
    only when that source has no year-level record for the model, and only for a model with
    exactly one generation (otherwise we cannot split it); this avoids double counting.
    """
    mine = [
        mf
        for mf in count_facts
        if mf.source_id == source_id
        and (mf.fact.country.value if mf.fact.country else None) == country
        and isinstance(mf.fact.value, int | float)
    ]
    models_with_years = {mf.model_id for mf in mine if mf.generation_id}
    out: dict[str, CountAggregate] = {}
    for mf in sorted(mine, key=lambda m: m.fact.id):
        if mf.generation_id:
            gid = mf.generation_id
            level = "generation"
        else:
            if mf.model_id in models_with_years:
                continue
            gens = seed.models[mf.model_id].generations
            if len(gens) != 1:
                continue
            gid = gens[0].id
            level = "model"
        agg = out.setdefault(gid, CountAggregate(0, [], [source_id], level))
        agg.value += int(mf.fact.value)
        agg.fact_ids.append(mf.fact.id)
    return out


@dataclass
class RegistrationEntry:
    """One count for PublishedVariant.registrations[country] (one source, period and kind)."""

    count: int
    kind: str  # fleet | new_registrations
    period: str | None
    level: str  # generation | model
    source_id: str
    fact_ids: list[str]
    confidence: str
    notes: list[str] = field(default_factory=list)


_CONF_ORDER = {"low": 0, "medium": 1, "high": 2}


def _conf_of(mf: MatchedFact) -> str:
    c = mf.fact.confidence
    return c.value if hasattr(c, "value") else str(c)


def registration_entries(
    count_facts: list[MatchedFact], seed: Seed
) -> dict[str, dict[str, list[RegistrationEntry]]]:
    """generation id -> country -> entries.

    One entry per (source, country, period). Generation-level facts sum into their generation.
    When a model has any model-level fact in a group (DfT has no year; KBA years that pick no
    generation), the whole group's count for that model is one model-level entry, repeated
    on every generation of the model (level "model"; "generation" for a one-generation
    model). Nothing is summed across sources, periods or kinds. RDW keeps `aggregate_counts`
    so its NL fleet equals registered_count_nl; its shared-year cars (model-level facts that
    `aggregate_counts` leaves out) become one extra entry per model with level "model",
    repeated on every generation and never added to the generation entry."""
    out: dict[str, dict[str, list[RegistrationEntry]]] = {}
    groups: dict[tuple[str, str, str], list[MatchedFact]] = {}
    for mf in count_facts:
        kind = COUNT_KIND.get(mf.source_id)
        cc = mf.fact.country.value if mf.fact.country else None
        if kind is None or cc is None or not isinstance(mf.fact.value, int | float):
            continue
        groups.setdefault((mf.source_id, cc, mf.period or ""), []).append(mf)

    def add(gid: str, cc: str, entry: RegistrationEntry) -> None:
        out.setdefault(gid, {}).setdefault(cc, []).append(entry)

    for (sid, cc, period), mfs in sorted(groups.items()):
        kind = COUNT_KIND[sid]
        if sid == "rdw":
            by_id = {mf.fact.id: mf for mf in mfs}
            taken: set[str] = set()
            for gid, agg in aggregate_counts(mfs, seed, sid, cc).items():
                used = [by_id[f] for f in agg.fact_ids]
                taken.update(agg.fact_ids)
                conf = min((_conf_of(m) for m in used), key=lambda c: _CONF_ORDER[c])
                add(gid, cc, RegistrationEntry(
                    agg.value, kind, period or None, agg.level, sid, agg.fact_ids, conf,
                    sorted({m.note for m in used if m.note}),
                ))  # fmt: skip
            _add_rdw_model_level(mfs, taken, seed, cc, kind, period, add)
            continue
        by_model: dict[str, list[MatchedFact]] = {}
        for mf in mfs:
            by_model.setdefault(str(mf.model_id), []).append(mf)
        for model_id, items in sorted(by_model.items()):
            items = sorted(items, key=lambda m: m.fact.id)
            gens = seed.models[model_id].generations
            if any(m.generation_id is None for m in items):
                buckets = {g.id: items for g in gens}
                level = "generation" if len(gens) == 1 else "model"
            else:
                buckets = {}
                for m in items:
                    buckets.setdefault(str(m.generation_id), []).append(m)
                level = "generation"
            for gid, used in buckets.items():
                conf = min((_conf_of(m) for m in used), key=lambda c: _CONF_ORDER[c])
                add(gid, cc, RegistrationEntry(
                    sum(int(m.fact.value) for m in used), kind, period or None, level, sid,
                    [m.fact.id for m in used], conf, sorted({m.note for m in used if m.note}),
                ))  # fmt: skip
    return out


def _add_rdw_model_level(
    mfs: list[MatchedFact],
    taken: set[str],
    seed: Seed,
    cc: str,
    kind: str,
    period: str,
    add: Callable[[str, str, RegistrationEntry], None],
) -> None:
    """RDW shared-year cars (MODEL_LEVEL_FALLBACK): one model-level entry per model, repeated
    on every generation of a multi-generation model. Never split, never summed into the
    generation entry (registered_count_nl stays the generation-level fleet)."""
    by_model: dict[str, list[MatchedFact]] = {}
    for mf in mfs:
        if mf.generation_id is None and mf.year is not None and mf.fact.id not in taken:
            by_model.setdefault(str(mf.model_id), []).append(mf)
    for model_id, items in sorted(by_model.items()):
        gens = seed.models[model_id].generations
        if len(gens) < 2:
            continue  # a shared year needs two generations; nothing to place
        items = sorted(items, key=lambda m: m.fact.id)
        conf = min((_conf_of(m) for m in items), key=lambda c: _CONF_ORDER[c])
        notes = sorted({m.note for m in items if m.note})
        for g in gens:
            add(g.id, cc, RegistrationEntry(
                sum(int(m.fact.value) for m in items), kind, period or None, "model", "rdw",
                [m.fact.id for m in items], conf, notes,
            ))  # fmt: skip
