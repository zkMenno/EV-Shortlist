"""EEA CO2 monitoring of new passenger cars, Regulation (EU) 2019/631 (CC BY 4.0).

Pulls new battery-electric registrations (Ft = 'electric') per country x make x commercial
name for NL/DE/FR/BE (the UK is not in the EU data), aggregated server-side through the
Discodata SQL endpoint: one grouped query per data year in TABLES, FETCH_SLEEP_S apart.

**History (T-053).** TABLES lists the *final* dataset of every year from 2018 to 2024 plus the
newest provisional year. Each row keeps its table and its `Year`, so every record is one
country x model x year (`registrations[]` gets one entry per year; years are never summed).
2018 and 2019 have no table of their own on Discodata: their SDI records point to the
all-years table `[co2cars]` filtered on `Year`, `Status = 'F'` and `Version_file` (v18, v20);
`[co2cars]` stops at 2022 provisional, so 2020-2024 use their own final tables. Table names
come from each year's SDI metadata record (`METADATA_UUID` per table), checked 2026-11-15.
Each table's licence is checked in its own SDI record. Final datasets are confidence high,
provisional ones medium.

**Counts only (T-004 review).** The grouped query also returns registration-weighted averages
of mass (M), consumption (Z) and range (Zr) over *every* type approval under one commercial
name: all battery sizes, wheels and trims blended into a number that may match no real car.
Decision 009 says conflicts are never averaged, so these are NOT emitted as spec facts. `M`
is also mass in running order (curb weight + 75 kg driver), which must never merge with curb
weight. Per-type-approval (TAN/Va/Ve) spec rows are an open question (QUESTIONS.md Q-039).

**Corroboration records (Q-019 option a).** The range (Zr) and consumption (Z) averages are also
emitted as `kind="corroboration"` records (never mass). The matcher ignores them unless
`EV_EEA_CORROBORATION=1`; then merge may use one to count EEA as an agreeing source when it
is within the field tolerance of a variant's merged value. It never sets a value.

Discodata sits behind an Azure WAF that rejects many GET queries (e.g. `... AND ...` with
quoted literals) with HTTP 403; POSTing the same query as a form body works.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from ev_pipeline import net
from ev_pipeline.records import SourceRecord, SpecValue
from ev_pipeline.schema_models import Confidence, Country, FactField, Source
from ev_pipeline.sources import _common as c

NAME = "eea"
SQL_URL = "https://discodata.eea.europa.eu/sql"
SDI_SEARCH = "https://sdi.eea.europa.eu/catalogue/srv/api/search/records/_search"
DATAHUB_URL = (
    "https://www.eea.europa.eu/en/datahub/datahubitem-view/fa8b1229-3db6-495d-b18e-9c9b3267c02b"
)
COUNTRIES = ("NL", "DE", "FR", "BE")
PAGE_SIZE = 1000
FETCH_SLEEP_S = 2.0
"""Pause between Discodata / SDI requests (fair use; one request at a time)."""


@dataclass(frozen=True)
class EeaTable:
    """One data year on Discodata: its table, the filter that picks the year's release, and
    the SDI metadata record (licence and table name)."""

    year: int
    table: str
    status: str  # F = final, P = provisional
    metadata_uuid: str
    version_file: str | None = None  # only for the all-years [co2cars] table

    @property
    def where(self) -> str:
        extra = f" AND Status = '{self.status}' AND Version_file = '{self.version_file}'"
        return f"Year = {self.year}" + (extra if self.version_file else "")


ALL_YEARS = "[CO2Emission].[latest].[co2cars]"
TABLES: tuple[EeaTable, ...] = (
    EeaTable(2018, ALL_YEARS, "F", "b319cb95-2c93-4635-8177-e5e0e4f48c1b", "v18"),
    EeaTable(2019, ALL_YEARS, "F", "a0da862c-0bed-460f-808a-0bae489b12b9", "v20"),
    EeaTable(2020, "[CO2Emission].[latest].[co2cars_2020Fv22]", "F",
             "47a7277f-d111-47ba-8438-d669b1057b6d"),
    EeaTable(2021, "[CO2Emission].[latest].[co2cars_2021Fv24]", "F",
             "0172c621-9e03-4756-ac5f-47cc3e241201"),
    EeaTable(2022, "[CO2Emission].[latest].[co2cars_2022Fv26]", "F",
             "992616f8-158f-4ecc-b978-814b81629db6"),
    EeaTable(2023, "[CO2Emission].[latest].[co2cars_2023Fv28]", "F",
             "87fd2bce-6ad5-46d8-af41-f27cfd2e45a8"),
    EeaTable(2024, "[CO2Emission].[latest].[co2cars_2024Fv30]", "F",
             "5018ec17-2348-4c92-8761-6f2377bbd1c0"),
    # Newest: 2025 provisional (v31, published 2026-06-25). When the final 2025 table or the
    # provisional 2026 table appears, add or replace a line here.
    EeaTable(2025, "[CO2Emission].[latest].[co2cars_2025Pv31]", "P",
             "b4044b06-2e6b-4f8e-a6e6-66e0e98bb0dd"),
)  # fmt: skip
TABLE = TABLES[-1].table
"""The newest table (kept for callers and old raw pages without a `table` key)."""
METADATA_UUID = TABLES[-1].metadata_uuid


def _wavg(column: str) -> str:
    return (
        f"SUM(CAST(R AS float) * {column}) / "
        f"NULLIF(SUM(CASE WHEN {column} IS NOT NULL THEN R END), 0)"
    )


def query_for(t: EeaTable) -> str:
    return (
        "SELECT MS, Mk, Cn, Year, SUM(R) AS registrations, "
        f"{_wavg('[M (kg)]')} AS mass_kg, "
        f"{_wavg('[Z (Wh/km)]')} AS z_wh_km, "
        f"{_wavg('Zr')} AS zr_km "
        f"FROM {t.table} "
        "WHERE Ft = 'electric' AND MS IN (" + ", ".join(f"'{m}'" for m in COUNTRIES) + ") "
        f"AND {t.where} "
        "GROUP BY MS, Mk, Cn, Year ORDER BY MS, Mk, Cn, Year"
    )


QUERY = query_for(TABLES[-1])

SOURCE = Source(
    id="eea",
    name="EEA CO2 monitoring of new cars (Reg. 2019/631)",
    url=DATAHUB_URL,
    licence="CC-BY-4.0",
    attribution=(
        "Contains data from the European Environment Agency, CO2 emissions from new "
        "passenger cars (Regulation (EU) 2019/631). Copyright holder: Directorate-General "
        "for Climate Action (DG CLIMA). CC BY 4.0."
    ),
)


def fetch_licence(client: httpx.Client, uuid: str = METADATA_UUID) -> str | None:
    """Use-limitation text of a dataset's SDI metadata record (where the licence lives)."""
    resp = client.post(
        SDI_SEARCH,
        json={"query": {"term": {"uuid": uuid}}, "size": 1},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    if not hits:
        return None
    limits = hits[0]["_source"].get("MD_ConstraintsUseLimitationObject", [])
    return limits[0].get("default") if limits else None


def fetch(
    client: httpx.Client,
    target: Path,
    tables: tuple[EeaTable, ...] = TABLES,
    sleep_s: float = FETCH_SLEEP_S,
) -> int:
    """Licence per table, then one grouped query per table (paged). Every row gets a `table`
    key. Pages are numbered across tables (`page-001.json` ...). Returns the row count."""
    calls = 0

    def pause() -> None:
        nonlocal calls
        if calls and sleep_s:
            time.sleep(sleep_s)
        calls += 1

    licences: dict[str, str] = {}
    for t in tables:
        if t.metadata_uuid in licences:
            continue
        pause()
        text = fetch_licence(client, t.metadata_uuid)
        if not text or "CC-BY 4.0" not in text:
            raise RuntimeError(f"EEA {t.year} licence not confirmed in metadata: {text!r}")
        licences[t.metadata_uuid] = text
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("page-*.json"):
        old.unlink()
    rows = page_no = 0
    per_table: list[dict[str, object]] = []
    for t in tables:
        query = query_for(t)
        t_rows = page = 0
        while True:
            page += 1
            pause()
            resp = client.post(
                SQL_URL, data={"query": query, "p": str(page), "nrOfHits": str(PAGE_SIZE)}
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise RuntimeError(f"Discodata error ({t.year}): {body['errors']}")
            batch = [{**r, "table": t.table} for r in body.get("results", [])]
            page_no += 1
            (target / f"page-{page_no:03d}.json").write_text(
                json.dumps(batch, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
            )
            t_rows += len(batch)
            if len(batch) < PAGE_SIZE:
                break
        rows += t_rows
        per_table.append(
            {
                "year": t.year,
                "table": t.table,
                "status": t.status,
                "where": t.where,
                "metadata_record": t.metadata_uuid,
                "pages": page,
                "rows": t_rows,
            }
        )
    newest = tables[-1]
    c.write_fetch_meta(
        target,
        {
            "url": SQL_URL,
            "table": newest.table,  # newest table; every table is under `tables`
            "query": query_for(newest),
            "metadata_record": newest.metadata_uuid,
            "licence_metadata": licences[newest.metadata_uuid],
            "licence_metadata_by_record": licences,
            "tables": per_table,
            "pages": page_no,
            "rows": rows,
        },
    )
    return rows


def normalise(raw_dir: Path, retrieved_at: date) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for page in sorted(raw_dir.glob("page-*.json")):
        for row in json.loads(page.read_text(encoding="utf-8")):
            ms, make, model = row.get("MS"), row.get("Mk"), row.get("Cn")
            count = int(row.get("registrations") or 0)
            if ms not in COUNTRIES or not make or not model or count <= 0:
                continue
            year = int(row["Year"]) if row.get("Year") else None
            table = str(row.get("table") or TABLE)
            key = f"{table}:{ms}|{make}|{model}|{year or ''}"
            common = {
                "source": SOURCE,
                "make": make,
                "model": model,
                "year": year,
                "country": Country(ms),
                "retrieved_at": retrieved_at,
            }
            # Counts are the official monitoring data: final tables high, provisional medium.
            records.append(
                SourceRecord(
                    record_key=key,
                    kind="registration_count",
                    specs={FactField.registered_count: SpecValue(value=count, unit="count")},
                    confidence=Confidence.high if table in FINAL_TABLES else Confidence.medium,
                    **common,
                )
            )
            # No spec record: see the module docstring (averages across different cars).
            corro: dict[FactField, SpecValue] = {}
            if _positive(row.get("zr_km")):
                corro[FactField.wltp_range_km] = SpecValue(value=float(row["zr_km"]), unit="km")
            if _positive(row.get("z_wh_km")):
                corro[FactField.consumption_kwh_100km] = SpecValue(
                    value=float(row["z_wh_km"]), unit="Wh/km"
                )
            if corro:
                # The count is the average's weight: merge uses the best-supported average.
                corro[FactField.registered_count] = SpecValue(value=count, unit="count")
                records.append(
                    SourceRecord(
                        record_key=f"{key}#corroboration",
                        kind="corroboration",
                        specs=corro,
                        confidence=Confidence.low,  # registration-weighted average
                        **common,
                    )
                )
    return records


FINAL_TABLES = frozenset(t.table for t in TABLES if t.status == "F")
"""Tables holding only final data (the all-years table is filtered to F rows in the query)."""


def _positive(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and v > 0


def restore_from_release(data_dir: Path, release_num: int) -> list[SourceRecord]:
    """Reconstruct cached EEA registration_count staging records from a published release's
    `facts.parquet` when Discodata / SDI are unreachable on a fresh runner (preserving each
    fact's original `retrieved_at` date, confidence, country, year and record key).

    EEA tables 2018-2024 are final and the provisional year updates yearly, so keeping the
    previous release's facts matches the on-disk keep-previous behaviour of a persistent host.
    """
    import pyarrow.parquet as pq

    from ev_pipeline.release.publish import PublishError, ensure_local, read_manifest

    release_dir = data_dir / "releases" / str(release_num)
    facts_path = release_dir / "facts.parquet"
    if not facts_path.exists() or read_manifest(release_dir) is not None:
        try:
            ensure_local(data_dir, release_num, only=frozenset({"facts.parquet"}))
        except PublishError:
            return []
    if not facts_path.exists():
        return []
    table = pq.read_table(facts_path)
    records: list[SourceRecord] = []
    seen: set[str] = set()
    for row in table.to_pylist():
        if row.get("source_id") != NAME or row.get("field") != FactField.registered_count.value:
            continue
        key = row.get("source_record")
        if not isinstance(key, str) or ":" not in key or key in seen:
            continue
        _, rest = key.split(":", 1)
        head = rest.split("|", 2)
        if len(head) != 3 or "|" not in head[2]:
            continue
        ms, make, tail = head
        model, year_s = tail.rsplit("|", 1)
        if ms not in COUNTRIES or not make or not model:
            continue
        val = row.get("value_num")
        if not isinstance(val, int | float) or isinstance(val, bool) or val <= 0:
            continue
        year = int(year_s) if year_s.isdigit() else row.get("record_year")
        if not isinstance(year, int) or isinstance(year, bool):
            continue
        retrieved = row.get("retrieved_at")
        if not isinstance(retrieved, str):
            continue
        try:
            retrieved_date = date.fromisoformat(retrieved)
            conf = Confidence(str(row.get("confidence")))
        except ValueError:
            continue
        seen.add(key)
        records.append(
            SourceRecord(
                source=SOURCE,
                record_key=key,
                kind="registration_count",
                make=make,
                model=model,
                year=year,
                country=Country(ms),
                specs={FactField.registered_count: SpecValue(value=int(round(val)), unit="count")},
                retrieved_at=retrieved_date,
                confidence=conf,
            )
        )
    return records


def fetch_cmd(client: httpx.Client | None = None) -> int:
    target = c.raw_dir(NAME)
    own = client is None
    client = client or net.safe_client(NAME, timeout=300)
    try:
        rows = fetch(client, target)
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"fetch {NAME}: failed: {exc}")
        return 1
    finally:
        if own:
            client.close()
    c.log_step(
        step="fetch",
        source=NAME,
        input_=f"{SQL_URL} {len(TABLES)} tables {TABLES[0].year}-{TABLES[-1].year} (grouped SQL)",
        output=c.rel(target),
        rows_out=rows,
    )
    return 0


def normalise_cmd(from_fixtures: bool) -> int:
    src = c.FIXTURES_DIR / NAME if from_fixtures else c.raw_dir(NAME)
    if not any(src.glob("page-*.json")):
        print(f"normalise {NAME}: no data in {src} (run `ev fetch {NAME}` first)")
        return 1
    records = normalise(src, c.retrieved_at_for(src))
    out = c.staging_dir() / f"{NAME}.records.jsonl"
    rows = c.write_records(records, out)
    per_year: dict[str, dict[str, int]] = {}
    for r in records:
        if r.kind == "registration_count":
            slot = per_year.setdefault(str(r.year), {"records": 0, "registrations": 0})
            slot["records"] += 1
            slot["registrations"] += int(r.specs[FactField.registered_count].value)
    c.log_step(
        step="normalise",
        source=NAME,
        input_=c.rel(src),
        output=c.rel(out),
        rows_out=rows,
        from_fixtures=from_fixtures,
        count_records_per_year=dict(sorted(per_year.items())),
    )
    return 0
