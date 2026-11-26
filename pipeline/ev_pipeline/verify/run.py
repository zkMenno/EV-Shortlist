"""T-127: `ev verify`: before a commit that changes data, prove the release still matches its
inputs and the numbers still make sense on real rows.

Steps (each one a section in verify-report.md):
1. rebuild: the next release from the recorded staging in a scratch copy of data/ (no
   network; data/releases/<latest> is the N-1 it is compared with). Its QA runs as in a real
   build, including the T-123 release diff.
2. tests: `pytest -q` for the pipeline (skip with --skip-tests).
3. release diff: the scratch release against latest (counts, blocking list, biggest moves).
4. back-tests: every back-test section in the scratch qa.json with its median error and gate.
5. changed rules: rule/parameter files changed against the base ref; their effect on the
   latest rows is the release diff in step 3 (the dry run).
6. spot checks: the tricky cars (tricky_cars.yaml) with old -> new headline numbers.
7. claims: every `key: number` line in the PR body (--pr-body) whose key is one of the
   report's numbers must equal the report (A-20 B1: MORNING.md quoted a number the release
   didn't have).
8. seed check (G-48, T-153): a seed variant built with another drivetrain than its seed, or
   with a WLTP more than 10 % off its own cited WLTP: listed; a mismatch the previous
   release did not have fails the run.
9. missing-input flag changes (G-62, T-165): rows whose derived shortlist flags change solely
   because an input is missing (e.g. `power_kw` under Decision 088), naming the missing input
   (report only, so "unknown -> no flag" rules show their data cost).
G-49 (T-153): while `ev refresh` holds data/staging (refresh/lock.py) verify refuses to run;
a refresh that ran during the rebuild, even a short one that already finished, fails the run
(T-158: the `.refresh.last` stamp changed).
T-158: `--keep <dir>` keeps the scratch build (G-53) so a value can be traced afterwards;
`--base-release-from <ref>` (G-56) builds <ref>'s code and inputs on the same staging and diffs
against that build instead of the committed release N-1, so a fresh staging shows only what the
branch changes (that base build has no N-1 of its own: retired ids and review-only carry-overs
are not part of the comparison).
Plus the memory peak. Exit 0 = pass, 1 = fail. Back-test flags are reported, not failures
(they don't block a release either).
"""

from __future__ import annotations

import fnmatch
import json
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ev_pipeline.release.build import REPO_ROOT

TRICKY_FILE = Path(__file__).with_name("tricky_cars.yaml")
SPOT_FIELDS = (
    "battery_kwh_net", "wltp_range_km", "real_range_km", "epa_range_km",
    "consumption_kwh_100km", "dc_km_per_20min",
)  # fmt: skip
RULE_GLOBS = (
    "pipeline/ev_pipeline/derive/*", "pipeline/ev_pipeline/match/*", "pipeline/ev_pipeline/merge/*",
    "pipeline/ev_pipeline/qa/value_guard.py", "pipeline/ev_pipeline/backtest/*",
    "*_params.yaml", "*_rules.yaml", "data/editorial/*", "data/taxonomy/*", "data/seed/*",
    "data/manual/*", "data/sources.yaml", "data/field_sources.yaml",
    "config/approved_changes.yaml", "config/popularity.yaml",
)  # fmt: skip
BACKTEST_KEYS = ("backtest", "backtest_epa", "backtest_used_prices", "backtest_popularity")
SKIP_COPY = {"releases", "raw", "runs", "review", "local", "staging"}
CLAIM = re.compile(r"^[\s>*-]*`?([a-z][a-z0-9_]*)`?\s*[:=]\s*(-?\d+(?:\.\d+)?)\b", re.M)


@dataclass
class Report:
    status: str = "pass"
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    numbers: dict[str, float | int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    release_diff_csv: str | None = None  # the scratch build's data/review/release_diff.csv

    def fail(self, why: str) -> None:
        self.status = "fail"
        self.failures.append(why)


# --- steps -------------------------------------------------------------------------------


def latest_number(data_dir: Path) -> int | None:
    p = data_dir / "releases" / "latest"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8").strip()
    return int(t) if t.isdigit() else None


def scratch_copy(
    data_dir: Path, dest: Path, latest: int | None, base_release: Path | None = None
) -> Path:
    """A copy of data/ that a build may write into: inputs copied, staging linked (read
    only by the build), and only the latest release (the N-1). With `base_release` (G-56) that
    folder stands in for release N-1 instead of the committed one."""
    d = dest / "data"
    d.mkdir(parents=True)
    for p in data_dir.iterdir():
        if p.name in SKIP_COPY:
            continue
        if p.is_dir():
            shutil.copytree(p, d / p.name)
        else:
            shutil.copy2(p, d / p.name)
    if (data_dir / "staging").is_dir():
        (d / "staging").symlink_to((data_dir / "staging").resolve(), target_is_directory=True)
    rel = d / "releases"
    rel.mkdir()
    pub = data_dir / "releases" / "publish.yaml"
    if pub.exists():
        shutil.copy2(pub, rel / "publish.yaml")
    if base_release is not None and latest is not None:
        shutil.copytree(base_release, rel / str(latest))
        (rel / "latest").write_text(f"{latest}\n", encoding="utf-8")
    elif latest is not None:
        from ev_pipeline.release.publish import ensure_local

        ensure_local(data_dir, latest)  # T-064: asset files fetched by sha256 if missing
        shutil.copytree(data_dir / "releases" / str(latest), rel / str(latest))
        (rel / "latest").write_text(f"{latest}\n", encoding="utf-8")
    return d


# G-56: the base ref's own code builds the base release. It runs in a child process with the
# ref's pipeline/ first on sys.path (the venv's editable install is a plain .pth path entry,
# so the ref's ev_pipeline wins). It has no N-1, so no release diff can block it; any other
# QA block in it fails verify with that message.
BASE_BUILD = r"""
import json, shutil, sys
from datetime import datetime
from pathlib import Path
src, data, now, n = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
sys.path.insert(0, str(src / "pipeline"))
import ev_pipeline
assert Path(ev_pipeline.__file__).resolve().is_relative_to(src.resolve()), ev_pipeline.__file__
from ev_pipeline.release.build import build_release, write_release
res = build_release(data, now=datetime.fromisoformat(now), release=n)
out = write_release(res, data, None)
print(json.dumps({"dir": str(out), "release": res.release}))
"""


def base_source(repo: Path, ref: str, dest: Path) -> str:
    """Export `ref`'s tree (minus release folders) into dest; returns its commit sha."""
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    dest.mkdir(parents=True)
    arch = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", sha, "--", ".",
         ":(exclude)data/releases/[0-9]*", ":(exclude)apps", ":(exclude)_archive"],
        capture_output=True, check=True,
    )  # fmt: skip
    subprocess.run(["tar", "-x", "-C", str(dest)], input=arch.stdout, check=True)
    return sha


def build_base(
    repo: Path, ref: str, data_dir: Path, tmp: Path, now: datetime, latest: int | None
) -> dict[str, Any]:
    """G-56: build `ref` on this checkout's staging. Returns {status, sha, dir|error}."""
    try:
        sha = base_source(repo, ref, tmp / "base-src")
    except (subprocess.CalledProcessError, OSError) as e:
        err = getattr(e, "stderr", None)
        msg = (err.decode() if isinstance(err, bytes) else str(err or e)).strip().splitlines()
        return {
            "status": "fail",
            "ref": ref,
            "error": f"cannot export {ref}: {msg[0] if msg else e}",
        }
    src_data = tmp / "base-src" / "data"
    d = tmp / "base" / "data"
    d.mkdir(parents=True)
    for p in src_data.iterdir():
        if p.name in SKIP_COPY:
            continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, d / p.name)
    (d / "staging").symlink_to((data_dir / "staging").resolve(), target_is_directory=True)
    (d / "releases").mkdir()
    pub = src_data / "releases" / "publish.yaml"
    if pub.exists():
        shutil.copy2(pub, d / "releases" / "publish.yaml")
    n = (latest or 0) + 1
    cp = subprocess.run(
        [sys.executable, "-c", BASE_BUILD, str(tmp / "base-src"), str(d), now.isoformat(), str(n)],
        capture_output=True, text=True, cwd=str(tmp),
    )  # fmt: skip
    if cp.returncode != 0:
        lines = (cp.stderr or cp.stdout).strip().splitlines()
        err = [ln for ln in lines if "Error" in ln.split(":")[0]]  # the exception's headline
        why = (err[-1] if err else lines[-1]) if lines else f"exit {cp.returncode}"
        return {"status": "fail", "ref": ref, "sha": sha, "error": f"base build of {ref}: {why}"}
    out = json.loads(cp.stdout.strip().splitlines()[-1])
    return {"status": "pass", "ref": ref, "sha": sha, "dir": out["dir"], "release": out["release"]}


def keep_build(src: Path, dest: Path) -> str | None:
    """G-53: copy the scratch tree to dest (links kept as links). Refuses a non-empty dest."""
    if dest.exists() and any(dest.iterdir()):
        return f"--keep: {dest} exists and is not empty; pick a new folder"
    dest.mkdir(parents=True, exist_ok=True)
    for p in src.iterdir():
        target = dest / p.name
        if p.is_dir() and not p.is_symlink():
            shutil.copytree(p, target, symlinks=True)
        else:
            shutil.copy2(p, target, follow_symlinks=False)
    return None


def rebuild(data_dir: Path, scratch: Path, now: datetime) -> dict[str, Any]:
    from ev_pipeline.release.build import build_release, write_release
    from ev_pipeline.release.validate import ReleaseError

    if not any((data_dir / "staging").glob("*.jsonl")):
        return {
            "status": "fail",
            "error": "no recorded staging in data/staging: run `uv run ev refresh --no-release` "
            "(network) once, then verify again",
        }
    res = None
    try:
        res = build_release(scratch, now=now)
        out = write_release(res, scratch)
    except ReleaseError as e:
        qa = scratch / "review" / "qa.json"
        return {  # a QA block still has a built catalogue: spot checks need it most then
            "status": "fail",
            "error": str(e).splitlines()[0],
            "release": res.release if res else None,
            "qa": json.loads(qa.read_text(encoding="utf-8")) if qa.exists() else None,
            "catalogue": res.catalogue if res else None,
            "shortlist": res.shortlist if res else None,
        }
    qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
    cat = json.loads((out / "catalogue.json").read_text(encoding="utf-8"))
    return {
        "status": "pass",
        "release": res.release,
        "dir": str(out),
        "qa": qa,
        "catalogue": cat,
        "shortlist": res.shortlist,
    }


def run_tests(pipeline_dir: Path) -> dict[str, Any]:
    cp = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=pipeline_dir, capture_output=True, text=True, check=False,
    )  # fmt: skip
    tail = [x for x in cp.stdout.splitlines() if x.strip()][-1:] or [cp.stderr.strip()[-200:]]
    m = re.search(r"(\d+) passed", tail[0])
    f = re.search(r"(\d+) failed", tail[0])
    return {
        "status": "pass" if cp.returncode == 0 else "fail",
        "summary": tail[0],
        "passed": int(m.group(1)) if m else 0,
        "failed": int(f.group(1)) if f else 0,
    }


def backtests(qa: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every back-test in qa.json; sections made of parts (EPA: range, consumption,
    consumption_oos) are listed per part as `name.part`."""
    out = []

    def add(name: str, b: dict[str, Any]) -> None:
        med = {k: v for k, v in b.items() if "median" in k and isinstance(v, int | float)}
        out.append(
            {"name": name, "status": b.get("status"), "gate": b.get("gate"), "medians": med,
             "n": b.get("n"), "note": b.get("note")}
        )  # fmt: skip

    for key in BACKTEST_KEYS:
        b = (qa or {}).get(key)
        if not isinstance(b, dict):
            continue
        parts = {k: v for k, v in b.items() if isinstance(v, dict) and "status" in v}
        if "status" in b or not parts:
            add(key, b)
        for part, v in sorted(parts.items()):
            add(f"{key}.{part}", v)
    return out


def changed_rules(repo: Path, base: str) -> list[str] | None:
    cp = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if cp.returncode != 0:
        return None
    names = [n for n in cp.stdout.splitlines() if n]
    return [n for n in names if any(fnmatch.fnmatchcase(n, g) for g in RULE_GLOBS)]


def load_tricky(path: Path = TRICKY_FILE) -> list[dict[str, str]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if doc.get("schema") != "tricky-cars/v1":
        raise ValueError(f"{path}: schema must be tricky-cars/v1")
    return [{"id": str(c["id"]), "why": str(c.get("why") or "")} for c in doc.get("cars") or []]


def spot_checks(
    new: dict[str, Any] | None, old: dict[str, Any] | None, tricky: list[dict[str, str]]
) -> list[dict[str, Any]]:
    nr = {r["variant_id"]: r for r in (new or {}).get("rows") or []}
    orows = {r["variant_id"]: r for r in (old or {}).get("rows") or []}
    out = []
    for car in tricky:
        ids = sorted(i for i in set(nr) | set(orows) if fnmatch.fnmatchcase(i, car["id"]))
        if not ids:
            out.append({"pattern": car["id"], "variant_id": None, "why": car["why"]})
        for vid in ids:
            a, b = orows.get(vid) or {}, nr.get(vid) or {}
            values = {f: (a.get(f), b.get(f)) for f in SPOT_FIELDS}
            notes = []
            if vid not in nr:
                notes.append("gone")
            elif vid not in orows:
                notes.append("new")
            w, rr = b.get("wltp_range_km"), b.get("real_range_km")
            if isinstance(w, int | float) and isinstance(rr, int | float) and rr > w * 1.1:
                notes.append("real range > WLTP x 1.1")
            if vid in nr and b.get("battery_kwh_net") is None:
                notes.append("no battery")
            changed = [f for f, (x, y) in values.items() if x != y and vid in nr and vid in orows]
            out.append(
                {"pattern": car["id"], "variant_id": vid, "values": values,
                 "changed": changed, "notes": notes}
            )  # fmt: skip
    return out


SEED_WLTP_REL = 0.10  # G-48: built WLTP more than 10 % off the variant's own cited WLTP


def seed_mismatches(new: dict[str, Any] | None, seed_doc: dict[str, Any] | None) -> list[str]:
    """Messages of `seed_mismatch_items` (see there)."""
    return [m for _, m in seed_mismatch_items(new, seed_doc)]


def seed_mismatch_items(
    new: dict[str, Any] | None, seed_doc: dict[str, Any] | None
) -> list[tuple[tuple[str, str], str]]:
    """G-48 (T-153): seed variants whose built row (or year band `<id>-<yyyy>`) disagrees
    with the seed: another drivetrain than the seed's, or a WLTP more than SEED_WLTP_REL off
    the seed's own cited WLTP (a reviewer caught Kia EV3 built as AWD / 583 km twice).
    Each item is ((row id, "drivetrain" | "wltp"), message): the key stays the same when a
    built value drifts with fresh data."""
    rows = (new or {}).get("rows") or []
    out: list[tuple[tuple[str, str], str]] = []
    for v in (seed_doc or {}).get("variants") or []:
        vid = str(v.get("id") or "")
        band = re.compile(rf"^{re.escape(vid)}(-\d{{4}})?$")
        cited = ((v.get("cited") or {}).get("wltp_range_km") or {}).get("value")
        for r in rows:
            rid = str(r.get("variant_id") or "")
            if not band.match(rid):
                continue
            dt, sdt = r.get("drivetrain"), v.get("drivetrain")
            if dt and sdt and dt != sdt:
                out.append(((rid, "drivetrain"), f"{rid}: drivetrain {dt}, seed says {sdt}"))
            w = r.get("wltp_range_km")
            if (
                isinstance(cited, int | float)
                and isinstance(w, int | float)
                and abs(w - cited) > SEED_WLTP_REL * cited
            ):
                msg = f"{rid}: WLTP {w:g} km, its cited WLTP is {cited:g} km (> 10 % off)"
                out.append(((rid, "wltp"), msg))
    return out


FLAG_PREFIXES = ("bonus:", "penalty:")
VERSION_FLAGS = ("newest-version", "older-version")


def _positive_num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, int | float) or v <= 0:
        return None
    return float(v)


def _has_mass(row: dict[str, Any]) -> bool:
    return row.get("kerb_mass_kg") is not None or row.get("mass_running_order_kg") is not None


def _shortlist_flags(
    doc: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, set[str]]], dict[str, set[str]]]:
    """Per variant: ({flag_id -> combos where it fired}, set of non-ruled-out combos)."""
    flags: dict[str, dict[str, set[str]]] = {}
    ok_combos: dict[str, set[str]] = {}
    for v in (doc or {}).get("variants") or []:
        vid = str(v.get("variant_id") or "")
        if not vid:
            continue
        fmap: dict[str, set[str]] = {}
        ok: set[str] = set()
        for combo, sc in (v.get("scores") or {}).items():
            if not isinstance(sc, dict):
                continue
            if sc.get("band") != "ruled-out":
                ok.add(str(combo))
            for reason in sc.get("reasons") or []:
                rs = str(reason)
                for pref in FLAG_PREFIXES:
                    if rs.startswith(pref):
                        fmap.setdefault(rs[len(pref) :], set()).add(str(combo))
        flags[vid] = fmap
        ok_combos[vid] = ok
    return flags, ok_combos


def _version_own_missing(row: dict[str, Any], flag: str, drivetrains: tuple[str, ...]) -> list[str]:
    miss: list[str] = []
    if row.get("year_start") is None:
        miss.append("year_start")
    if row.get("drivetrain") not in drivetrains:
        miss.append("drivetrain")
    if _positive_num(row.get("power_kw")) is None:
        miss.append("power_kw")
    if flag == "older-version" and row.get("dc_km_per_20min") is None:
        miss.append("dc_km_per_20min")
    return miss


def _power_compatible(a: dict[str, Any], b: dict[str, Any], gap: float) -> bool:
    pa, pb = _positive_num(a.get("power_kw")), _positive_num(b.get("power_kw"))
    if pa is None or pb is None:
        return True
    lo, hi = (pa, pb) if pa <= pb else (pb, pa)
    return hi <= lo * (1 + gap)


def _peer_can_trigger_version_flag(
    row: dict[str, Any],
    peer: dict[str, Any],
    old_peer: dict[str, Any] | None,
    flag: str,
    drivetrains: tuple[str, ...],
    gap: float,
) -> bool:
    """True when `peer` could share a trim line with `row` (ignoring missing inputs) and trigger
    `flag` on `row`."""
    rdt = row.get("drivetrain")
    pdt = peer.get("drivetrain")
    if pdt not in drivetrains and old_peer is not None:
        pdt = old_peer.get("drivetrain")
    if rdt in drivetrains and pdt in drivetrains and rdt != pdt:
        return False
    if not _power_compatible(row, peer, gap):
        return False
    ry = row.get("year_start")
    py = peer.get("year_start")
    if py is None and old_peer is not None:
        py = old_peer.get("year_start")
    if py is None:
        return False
    if ry is not None:
        if flag == "newest-version" and int(py) >= int(ry):
            return False
        if flag == "older-version" and int(py) <= int(ry):
            return False
    if flag == "older-version":
        rdc, pdc = row.get("dc_km_per_20min"), peer.get("dc_km_per_20min")
        if rdc is not None and pdc is not None and pdc <= rdc:
            return False
    return True


def missing_input_flag_changes(
    new_cat: dict[str, Any] | None,
    old_cat: dict[str, Any] | None,
    new_scores: dict[str, Any] | None,
    old_scores: dict[str, Any] | None,
    *,
    gap: float | None = None,
) -> list[dict[str, Any]]:
    """G-62 (T-165): rows present in both releases whose derived shortlist flags changed solely
    because an input is missing in the new build (e.g. `power_kw` under Decision 088), naming
    the missing input(s)."""
    if not (new_cat and old_cat and new_scores and old_scores):
        return []
    from ev_pipeline.derive import shortlist as sl

    try:
        params = sl.load_params()
    except OSError:
        params = {}
    if gap is None:
        gap = float(params.get("trim_line_power_gap", sl.TRIM_LINE_POWER_GAP))
    drivetrains = sl.DRIVETRAINS
    lim = params.get("too_big") or {"width_mm": 1950, "kerb_mass_kg": 2300}
    old_rows = {str(r["variant_id"]): r for r in old_cat.get("rows") or [] if r.get("variant_id")}
    new_rows = {str(r["variant_id"]): r for r in new_cat.get("rows") or [] if r.get("variant_id")}
    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in new_rows.values():
        by_model.setdefault(str(r.get("model_id") or ""), []).append(r)
    line_max_year: dict[str, int] = {}
    for line in sl.trim_lines(list(new_rows.values()), gap):
        top = max(int(r["year_start"]) for r in line)
        for r in line:
            line_max_year[str(r["variant_id"])] = top
    old_fc, old_ok = _shortlist_flags(old_scores)
    new_fc, new_ok = _shortlist_flags(new_scores)
    out: list[dict[str, Any]] = []
    for vid in sorted(set(old_rows) & set(new_rows)):
        old_r, new_r = old_rows[vid], new_rows[vid]
        old_f = set(old_fc.get(vid) or ())
        new_f = set(new_fc.get(vid) or ())
        peers = [
            o for o in by_model.get(str(new_r.get("model_id") or ""), []) if o["variant_id"] != vid
        ]
        # 1. Flags lost in the new build (ignoring flags hidden only by becoming ruled-out)
        for flag in sorted(old_f - new_f):
            if not (old_fc[vid][flag] & new_ok.get(vid, set())):
                continue
            if flag in VERSION_FLAGS:
                own = _version_own_missing(new_r, flag, drivetrains)
                if own:
                    if any(
                        _peer_can_trigger_version_flag(
                            new_r, o, old_rows.get(str(o["variant_id"])), flag, drivetrains, gap
                        )
                        for o in peers
                    ):
                        out.append(
                            {"variant_id": vid, "flag": flag, "change": "lost", "missing": own}
                        )
                else:
                    # If a newer complete peer already sits in this row's trim line, the row lost
                    # `newest-version` because it was superseded, not for an older peer's gap.
                    if (
                        flag == "newest-version"
                        and vid in line_max_year
                        and line_max_year[vid] > int(new_r["year_start"])
                    ):
                        continue
                    peer_miss: list[str] = []
                    for o in sorted(peers, key=lambda x: str(x["variant_id"])):
                        oid = str(o["variant_id"])
                        pm = _version_own_missing(o, flag, drivetrains)
                        if pm and _peer_can_trigger_version_flag(
                            new_r, o, old_rows.get(oid), flag, drivetrains, gap
                        ):
                            peer_miss.extend(f"{f} (on {oid})" for f in pm)
                    if peer_miss:
                        out.append(
                            {
                                "variant_id": vid,
                                "flag": flag,
                                "change": "lost",
                                "missing": peer_miss,
                            }
                        )
            elif flag == "lfp-daily-100":
                if new_r.get("charge_100_daily") is None:
                    out.append(
                        {
                            "variant_id": vid,
                            "flag": flag,
                            "change": "lost",
                            "missing": ["charge_100_daily"],
                        }
                    )
            elif flag == "too-big-for-b-roads":
                w_new, m_new = new_r.get("width_mm") is not None, _has_mass(new_r)
                w_old = old_r.get("width_mm")
                m_old = sl.kerb_mass(old_r, params) if params.get("mro_driver_kg") else None
                if m_old is None and old_r.get("kerb_mass_kg") is not None:
                    m_old = float(old_r["kerb_mass_kg"])
                w_over = w_old is not None and float(w_old) > float(lim["width_mm"])
                m_over = m_old is not None and m_old > float(lim["kerb_mass_kg"])
                miss: list[str] = []
                if not w_new and w_over:
                    miss.append("width_mm")
                if not m_new and m_over:
                    miss.append("kerb_mass_kg")
                if not w_new and not m_new and not miss:
                    miss = ["width_mm", "kerb_mass_kg"]
                if miss:
                    out.append({"variant_id": vid, "flag": flag, "change": "lost", "missing": miss})
        # 2. Flags gained solely because a newer peer dropped out due to a missing input
        for flag in sorted(new_f - old_f):
            if flag != "newest-version":
                continue
            if not (new_fc[vid][flag] & old_ok.get(vid, set())):
                continue
            if new_r.get("year_start") is None or new_r.get("drivetrain") not in drivetrains:
                continue
            peer_miss = []
            for o in sorted(peers, key=lambda x: str(x["variant_id"])):
                pm = _version_own_missing(o, "newest-version", drivetrains)
                if not pm:
                    continue
                oid = str(o["variant_id"])
                old_o = old_rows.get(oid) or {}
                oy = (
                    o.get("year_start")
                    if o.get("year_start") is not None
                    else old_o.get("year_start")
                )
                odt = (
                    o.get("drivetrain")
                    if o.get("drivetrain") in drivetrains
                    else old_o.get("drivetrain")
                )
                if oy is None or int(oy) <= int(new_r["year_start"]):
                    continue
                if odt in drivetrains and odt != new_r["drivetrain"]:
                    continue
                if not _power_compatible(new_r, o, gap):
                    continue
                peer_miss.extend(f"{f} (on {oid})" for f in pm)
            if peer_miss:
                out.append(
                    {"variant_id": vid, "flag": flag, "change": "gained", "missing": peer_miss}
                )
    return out


def check_claims(body: str, numbers: dict[str, float | int]) -> list[str]:
    """`key: number` lines in a PR body whose key is a report number must match it."""
    bad = []
    for key, val in CLAIM.findall(body):
        if key in numbers and abs(float(val) - float(numbers[key])) > 1e-9:
            bad.append(f"{key}: PR body says {val}, report says {numbers[key]}")
    return bad


def peak_mb() -> float:
    self_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(max(self_kb, child_kb) / 1024, 1)


# --- the whole run -----------------------------------------------------------------------


def verify(
    data_dir: Path,
    *,
    repo: Path = REPO_ROOT,
    base: str = "origin/main",
    skip_tests: bool = False,
    pr_body: str | None = None,
    tricky: list[dict[str, str]] | None = None,
    now: datetime | None = None,
    keep: Path | None = None,
    base_release_from: str | None = None,
) -> Report:
    rep = Report()
    now = now or datetime.now(UTC)
    from ev_pipeline.refresh.lock import last_run, refusal

    stamp = last_run(data_dir)  # before the busy check: a refresh starting in between counts
    busy = refusal(data_dir)
    if busy is not None:  # G-49: never rebuild from a staging that refresh is still writing
        rep.sections["rebuild"] = {"status": "refused", "error": busy}
        rep.fail(busy)
        return rep
    if keep is not None and keep.exists() and (not keep.is_dir() or any(keep.iterdir())):
        rep.sections["rebuild"] = {"status": "refused", "error": f"--keep: {keep} is not empty"}
        rep.fail(f"--keep: {keep} exists and is not an empty folder; pick a new folder")
        return rep
    if keep is not None and keep.resolve().is_relative_to(data_dir.resolve()):
        rep.sections["rebuild"] = {"status": "refused", "error": f"--keep: {keep} is in data/"}
        rep.fail(f"--keep: {keep} is inside {data_dir}; the next verify would copy it. Pick a"
                 " folder outside data/")  # fmt: skip
        return rep
    latest = latest_number(data_dir)
    old_cat = None
    old_scores = None
    if latest is not None and base_release_from is None:
        from ev_pipeline.release.publish import local_catalogue

        p = local_catalogue(data_dir, latest)
        old_cat = json.loads(p.read_text(encoding="utf-8")) if p else None
    with tempfile.TemporaryDirectory(prefix="ev-verify-") as tmp:
        base_dir = None
        if base_release_from is not None:
            b = build_base(repo, base_release_from, data_dir, Path(tmp), now, latest)
            rep.sections["base_build"] = {k: v for k, v in b.items() if k != "dir"}
            if b["status"] != "pass":
                rep.fail(str(b["error"]))
            else:
                base_dir = Path(b["dir"])
                old_cat = json.loads((base_dir / "catalogue.json").read_text(encoding="utf-8"))
                sp = base_dir / "shortlist_scores.json"
                if sp.exists():
                    old_scores = json.loads(sp.read_text(encoding="utf-8"))
        if base_release_from is None or base_dir is not None:
            scratch = scratch_copy(data_dir, Path(tmp), latest, base_dir)
            if old_scores is None and latest is not None:
                sp = scratch / "releases" / str(latest) / "shortlist_scores.json"
                if sp.exists():
                    old_scores = json.loads(sp.read_text(encoding="utf-8"))
            built = rebuild(data_dir, scratch, now)
        else:
            built = {"status": "fail", "error": "no base build to compare with"}
        csv_path = Path(tmp) / "data" / "review" / "release_diff.csv"
        if csv_path.exists():
            rep.release_diff_csv = csv_path.read_text(encoding="utf-8")
        if keep is not None:
            err = keep_build(Path(tmp), keep)
            if err:
                rep.fail(err)
            else:
                rep.sections["kept"] = {"dir": str(keep)}
    late = refusal(data_dir)
    if late is not None:  # G-49: a refresh started while we rebuilt; the rebuild may be mixed
        rep.fail(f"a refresh started during the rebuild: {late}")
    elif last_run(data_dir) != stamp:  # T-158: a short refresh ran and finished meanwhile
        rep.fail(
            "a refresh ran during the rebuild (data/staging/.refresh.last changed): the rebuild"
            " may mix old and new staging; run ev verify again"
        )
    qa = built.get("qa")
    rep.sections["rebuild"] = {
        k: v for k, v in built.items() if k in ("status", "error", "release")
    } | {"previous_release": latest}
    if built["status"] != "pass":
        rep.fail(f"rebuild: {built.get('error')}")
    if skip_tests:
        rep.sections["tests"] = {"status": "skipped", "summary": "--skip-tests"}
    else:
        t = run_tests(repo / "pipeline")
        rep.sections["tests"] = t
        rep.numbers["tests_passed"] = t["passed"]
        if t["status"] != "pass":
            rep.fail(f"tests: {t['summary']}")
    rd = (qa or {}).get("release_diff") or {}
    rep.sections["release_diff"] = rd
    if rd.get("counts") is not None:
        for k in ("blocking", "approved", "retired", "review"):
            rep.numbers[f"release_diff_{k}"] = int(rd["counts"].get(k, 0))
        if rd.get("status") == "fail":
            rep.fail(f"release diff: {rd['counts'].get('blocking', 0)} blocking change(s)")
    cat = built.get("catalogue")
    if cat is not None:
        rep.numbers["variants"] = len(cat.get("rows") or [])
    if old_cat is not None:
        rep.numbers["variants_previous"] = len(old_cat.get("rows") or [])
    bts = backtests(qa)
    rep.sections["backtests"] = {"items": bts}
    for b in bts:
        for k, v in b["medians"].items():
            rep.numbers[f"{b['name'].replace('.', '_')}_{k}"] = v
    rules = changed_rules(repo, base)
    rep.sections["changed_rules"] = {"files": rules, "base": base}
    rep.sections["spot_checks"] = {"rows": spot_checks(cat, old_cat, tricky or load_tricky())}
    seed_file = data_dir / "seed" / "variants.yaml"
    if cat is not None and seed_file.exists():
        seed_doc = yaml.safe_load(seed_file.read_text(encoding="utf-8"))
        items = seed_mismatch_items(cat, seed_doc)
        bad = [m for _, m in items]
        # Already in the previous release (same row and kind, whatever the value now): listed,
        # not a failure of this change (the owner lane fixes the seed); a mismatch the
        # previous release did not have fails the run. Baseline = release N-1, not main.
        before = {k for k, _ in seed_mismatch_items(old_cat, seed_doc)} if old_cat else set()
        new = [m for k, m in items if k not in before]
        rep.sections["seed_check"] = {
            "status": "fail" if new else "pass", "mismatches": new,
            "pre_existing": [m for k, m in items if k in before], "baseline": latest,
        }  # fmt: skip
        rep.numbers["seed_mismatches"] = len(bad)
        rep.numbers["seed_mismatches_new"] = len(new)
        for b in new:
            rep.fail(f"seed check (G-48): {b}")
    new_scores = built.get("shortlist")
    if (
        cat is not None
        and old_cat is not None
        and new_scores is not None
        and old_scores is not None
    ):
        mi = missing_input_flag_changes(cat, old_cat, new_scores, old_scores)
        rep.sections["missing_input_flags"] = {"items": mi}
        rep.numbers["missing_input_flag_changes"] = len(mi)
    if pr_body is not None:
        bad = check_claims(pr_body, rep.numbers)
        rep.sections["claims"] = {"status": "fail" if bad else "pass", "mismatches": bad}
        for b in bad:
            rep.fail(f"claim: {b}")
    rep.numbers["memory_peak_mb"] = peak_mb()
    return rep


# --- report ------------------------------------------------------------------------------


def _fmt(v: Any) -> str:
    return "-" if v is None else f"{v:g}" if isinstance(v, float) else str(v)


def report_md(rep: Report) -> str:
    s = rep.sections
    out = [f"# verify-pipeline report: **{rep.status}**", ""]
    out += [f"- {f}" for f in rep.failures] + ([""] if rep.failures else [])
    rb = s.get("rebuild", {})
    out += [
        "## Rebuild from recorded staging",
        f"{rb.get('status')}: release {rb.get('release', '-')} against {rb.get('previous_release')}"
        + (f" ({rb['error']})" if rb.get("error") else ""),
    ]
    bb = s.get("base_build")
    if bb:
        out.append(
            f"Base (G-56): {bb.get('ref')} @ {str(bb.get('sha') or '?')[:10]} built on the same"
            f" staging, {bb.get('status')}"
            + (f" ({bb['error']})" if bb.get("error") else "")
            + "; release N-1 in the diff below is that build, not the committed release."
        )
    if s.get("kept"):
        out.append(f"Scratch build kept in `{s['kept']['dir']}` (G-53).")
    out += [
        "",
        "## Tests",
        f"{s.get('tests', {}).get('status')}: {s.get('tests', {}).get('summary')}",
    ]
    from ev_pipeline.release.differ import summary_md

    rd = s.get("release_diff") or {}
    out += summary_md(rd) if rd.get("counts") is not None else ["", "## Release diff", "not run"]
    out += ["", "## Back-tests (report only)", ""]
    items = s.get("backtests", {}).get("items") or []
    if items:
        out += ["| back-test | status | n | medians | gate |", "|---|---|---|---|---|"]
        for b in items:
            med = ", ".join(f"{k} {_fmt(v)}" for k, v in b["medians"].items()) or "-"
            out.append(
                f"| {b['name']} | {b['status']} | {_fmt(b.get('n'))} | {med} | "
                f"{b.get('gate') or '-'} |"
            )
    else:
        out.append("none in qa.json")
    cr = s.get("changed_rules", {})
    out += ["", f"## Changed rules vs {cr.get('base')}", ""]
    files = cr.get("files")
    if files is None:
        out.append("git diff unavailable")
    elif not files:
        out.append("none")
    else:
        out += [f"- `{f}`" for f in files]
        out.append("Dry run: their effect on the latest rows is the release diff above.")
    out += ["", "## Spot checks (tricky cars: old -> new)", ""]
    out.append("| variant | " + " | ".join(SPOT_FIELDS) + " | notes |")
    out.append("|---" * (len(SPOT_FIELDS) + 2) + "|")
    for r in s.get("spot_checks", {}).get("rows") or []:
        if r["variant_id"] is None:
            out.append(f"| `{r['pattern']}`: no rows |" + " |" * (len(SPOT_FIELDS) + 1))
            continue
        cells = []
        for f in SPOT_FIELDS:
            a, b = r["values"][f]
            cells.append(_fmt(b) if a == b else f"**{_fmt(a)} -> {_fmt(b)}**")
        out.append(f"| {r['variant_id']} | " + " | ".join(cells) + f" | {', '.join(r['notes'])} |")
    if "seed_check" in s:
        out += ["", "## Seed vs built (G-48: drivetrain, WLTP vs cited)", ""]
        sc = s["seed_check"]
        out += [f"- **new:** {m}" for m in sc["mismatches"]]
        out += [
            f"- already in release {sc.get('baseline')}: {m}" for m in sc.get("pre_existing") or []
        ]
        if not sc["mismatches"] and not sc.get("pre_existing"):
            out.append("all match")
    if "missing_input_flags" in s:
        out += ["", "## Derived flag changes from missing inputs (G-62)", ""]
        mi_items = s["missing_input_flags"].get("items") or []
        if mi_items:
            out += ["| variant | flag | change | missing input |", "|---|---|---|---|"]
            for m in mi_items:
                miss = ", ".join(m["missing"])
                out.append(f"| {m['variant_id']} | {m['flag']} | {m['change']} | {miss} |")
        else:
            out.append("none")
    if "claims" in s:
        out += ["", "## PR body claims", ""]
        out += [f"- {m}" for m in s["claims"]["mismatches"]] or ["all match"]
    out += ["", "## Numbers (paste into the PR body; `ev verify --pr-body` checks them)", "", "```"]
    out += [f"{k}: {_fmt(v)}" for k, v in sorted(rep.numbers.items())]
    out += ["```", "", "Commit stamp: `Verified: verify-pipeline`", ""]
    return "\n".join(out)
