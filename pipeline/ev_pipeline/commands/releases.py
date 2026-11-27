"""`ev release rollback --to <n>`, `ev release diff <a> <b>`, `ev release list` (addendum 6 P2).

These hang under the existing `ev release` command (plain `ev release [--dry-run]` still
builds a release). `latest` is a one-line file holding the current release number; it is
switched atomically (temp file + rename, `release.build.write_latest`), so the web app always
reads a whole number.

Rollback only points `latest` at an existing, QA-passed release: its `qa.json` status must
be `pass` or `review` (A-05 L1: `unknown`, `fail`, `missing` and `unreadable` are refused),
and the blocking checks are run again on it against today's data/sources.yaml
(`qa.check_release`), so a source blocked since that release was built never comes back.
Nothing is deleted: the newer folders stay, and the next `ev release` still takes
the highest number + 1.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ev_pipeline.health.state import latest_release, runs_dir
from ev_pipeline.release.build import (
    compute_diff,
    default_data_dir,
    existing_releases,
    write_latest,
)

SHOW = 15
QA_FILES = frozenset({"catalogue.json", "facts.parquet", "charging_stats.json"})
ROLLBACK_OK = frozenset({"pass", "review"})  # qa/report.overall_status values that may serve


class ReleaseOpError(RuntimeError):
    pass


def _resolve(data_dir: Path, ref: str) -> int:
    if ref == "latest":
        n = latest_release(data_dir)
        if n is None:
            raise ReleaseOpError("data/releases/latest is missing or not a number")
        return n
    if not ref.isdigit():
        raise ReleaseOpError(f"not a release number: {ref!r}")
    return int(ref)


def _catalogue(data_dir: Path, n: int) -> dict[str, Any]:
    from ev_pipeline.release.publish import PublishError, local_catalogue

    try:
        path = local_catalogue(data_dir, n)  # T-064: fetched by manifest if needed
    except PublishError as e:
        raise ReleaseOpError(f"release {n} files unavailable: {e}") from e
    if path is None:
        raise ReleaseOpError(f"release {n} has no catalogue.json ({n}/ missing?)")
    return json.loads(path.read_text(encoding="utf-8"))


def qa_status(data_dir: Path, n: int) -> str:
    path = data_dir / "releases" / str(n) / "qa.json"
    if not path.exists():
        return "missing"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("status") or "unknown")
    except json.JSONDecodeError:
        return "unreadable"


# --- rollback ----------------------------------------------------------------------------


def rollback(data_dir: Path, to: int) -> dict[str, Any]:
    releases = data_dir / "releases"
    if to not in existing_releases(releases):
        raise ReleaseOpError(f"release {to} does not exist in {releases.name}/")
    from ev_pipeline.release.publish import PublishError, ensure_local

    try:
        # T-064: the files the QA re-check reads are fetched and verified first.
        ensure_local(data_dir, to, only=QA_FILES)
    except PublishError as e:
        raise ReleaseOpError(f"release {to} files unavailable: {e}") from e
    _catalogue(data_dir, to)
    qa = qa_status(data_dir, to)
    if qa not in ROLLBACK_OK:
        raise ReleaseOpError(f"release {to} has QA status {qa!r}; refusing to make it latest")
    from ev_pipeline.qa.check_release import ReleaseInputError, check_release

    try:
        recheck = check_release(releases / str(to), data_dir)
    except ReleaseInputError as e:
        raise ReleaseOpError(f"release {to} cannot be re-checked: {e}") from e
    if recheck["status"] != "pass":
        failed = ", ".join(recheck["blocking_failures"])
        raise ReleaseOpError(
            f"release {to} fails today's blocking checks ({failed}); refusing to make it latest"
        )
    before = latest_release(data_dir)
    write_latest(releases, to)
    entry = {
        "step": "release_rollback",
        "at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "from": before,
        "to": to,
        "qa_status": qa,
        "recheck": recheck["status"],
    }
    d = runs_dir(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    with (d / "releases.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


# --- diff --------------------------------------------------------------------------------


def diff_summary(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    d = compute_diff(a, b)
    fields: Counter[str] = Counter()
    for changes in d["changed"].values():
        fields.update(list(changes))
    sa = {s["id"] for s in a.get("sources") or []}
    sb = {s["id"] for s in b.get("sources") or []}
    examples = []
    for vid, changes in list(d["changed"].items())[:SHOW]:
        for f, ch in list(changes.items())[:3]:
            examples.append({"variant_id": vid, "field": f, "old": ch["old"], "new": ch["new"]})
    return {
        "from": a.get("release"),
        "to": b.get("release"),
        "generated_at": {"from": a.get("generated_at"), "to": b.get("generated_at")},
        "counts": d["counts"],
        "changed_fields": dict(fields.most_common()),
        "sources_added": sorted(sb - sa),
        "sources_removed": sorted(sa - sb),
        "examples": examples,
        "diff": d,
    }


def _short(v: Any) -> str:
    text = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return text if len(text) <= 40 else text[:37] + "..."


def diff_text(s: dict[str, Any]) -> str:
    c = s["counts"]
    lines = [
        f"Release {s['from']} -> {s['to']}",
        f"  generated {s['generated_at']['from']} -> {s['generated_at']['to']}",
        f"  variants {c['rows_previous']} -> {c['rows']}: +{c['added']} added, "
        f"-{c['removed']} removed, {c['changed']} changed",
    ]
    d = s["diff"]
    for label, ids in (("added", d["added"]), ("removed", d["removed"])):
        if ids:
            more = f" (+{len(ids) - SHOW} more)" if len(ids) > SHOW else ""
            lines.append(f"  {label}: " + ", ".join(ids[:SHOW]) + more)
    if s["changed_fields"]:
        lines.append("  changed fields (variants):")
        for f, n in list(s["changed_fields"].items())[:20]:
            lines.append(f"    {f:<32} {n}")
    if s["sources_added"] or s["sources_removed"]:
        lines.append(
            f"  sources: +{', '.join(s['sources_added']) or '-'}"
            f" / -{', '.join(s['sources_removed']) or '-'}"
        )
    if s["examples"]:
        lines.append("  examples:")
        for e in s["examples"][:10]:
            lines.append(
                f"    {e['variant_id']} {e['field']}: {_short(e['old'])} -> {_short(e['new'])}"
            )
    return "\n".join(lines)


# --- list --------------------------------------------------------------------------------


def list_releases(data_dir: Path) -> list[dict[str, Any]]:
    cur = latest_release(data_dir)
    out = []
    for n in existing_releases(data_dir / "releases"):
        row: dict[str, Any] = {"release": n, "latest": n == cur, "qa": qa_status(data_dir, n)}
        man = data_dir / "releases" / str(n) / "manifest.json"
        try:
            if man.exists():  # T-064: no download just to list
                m = json.loads(man.read_text(encoding="utf-8"))
                row.update(generated_at=m.get("generated_at"), rows=m["counts"]["rows"])
            else:
                cat = _catalogue(data_dir, n)
                row.update(generated_at=cat.get("generated_at"), rows=len(cat.get("rows") or []))
        except (ReleaseOpError, json.JSONDecodeError, KeyError):
            row.update(generated_at=None, rows=None)
        out.append(row)
    return out


# --- commands ----------------------------------------------------------------------------


def cmd_rollback(args: argparse.Namespace) -> int:
    data_dir = default_data_dir()
    try:
        entry = rollback(data_dir, args.to)
    except ReleaseOpError as exc:
        print(f"rollback refused: {exc}")
        return 1
    print(f"latest: {entry['from']} -> {entry['to']} (QA {entry['qa_status']})")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """`ev release diff N-1 N` or `ev release diff --from N-1 --to N`: the catalogue summary,
    then the T-123 per-file diff with approvals (also written to data/review/release_diff.csv).
    `--check` exits 2 when an unapproved change would block QA."""
    from ev_pipeline.release.differ import (
        REVIEW_FILE,
        DiffConfigError,
        config_path,
        diff_releases,
        load_config,
        summary,
        summary_md,
        write_csv,
    )
    from ev_pipeline.release.publish import PublishError, ensure_local

    data_dir = default_data_dir()
    ra, rb = args.from_ or args.a, args.to or args.b
    if ra is None or rb is None:
        print("diff: give two releases (N-1 N, or --from N-1 --to N)")
        return 1
    try:
        na, nb = _resolve(data_dir, ra), _resolve(data_dir, rb)
        a, b = _catalogue(data_dir, na), _catalogue(data_dir, nb)
        for n in (na, nb):
            ensure_local(data_dir, n)
        res = diff_releases(
            data_dir / "releases" / str(na),
            data_dir / "releases" / str(nb),
            load_config(config_path()),
        )
    except (ReleaseOpError, PublishError, DiffConfigError) as exc:
        print(f"diff: {exc}")
        return 1
    s = diff_summary(a, b)
    full = summary(res)
    write_csv(res, data_dir / "review" / REVIEW_FILE)
    if args.json:
        print(json.dumps({**s, "release_diff": full}, indent=1, ensure_ascii=False))
    else:
        print(diff_text(s))
        print("\n".join(summary_md(full)))
    return 2 if args.check and full["status"] == "fail" else 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = list_releases(default_data_dir())
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    print(f"{'release':>7}  {'latest':<6}  {'qa':<6}  {'rows':>6}  generated")
    for r in rows:
        print(
            f"{r['release']:>7}  {'*' if r['latest'] else '':<6}  {r['qa']:<6}  "
            f"{r['rows'] if r['rows'] is not None else '-':>6}  {r['generated_at'] or '-'}"
        )
    return 0


# --- package / publish / fetch (T-064, Decision 035) ----------------------------------------


def _release_dir(data_dir: Path, ref: str) -> Path:
    return data_dir / "releases" / str(_resolve(data_dir, ref))


def cmd_package(args: argparse.Namespace) -> int:
    from ev_pipeline.release.publish import PublishError, load_config, package

    data_dir = default_data_dir()
    try:
        m = package(_release_dir(data_dir, args.n), load_config(data_dir))
    except (ReleaseOpError, PublishError) as exc:
        print(f"package: {exc}")
        return 1
    c = m["counts"]
    print(f"release {m['release']}: {c['files']} files, {c['bytes']} bytes -> manifest.json")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from ev_pipeline.release.build import REPO_ROOT
    from ev_pipeline.release.publish import (
        PublishError,
        committed_in_git,
        load_config,
        package,
        publisher_for,
        verify,
    )

    data_dir = default_data_dir()
    try:
        cfg = load_config(data_dir)
        rdir = _release_dir(data_dir, args.n)
        m = package(rdir, cfg)
        problems = verify(rdir, m)
        if problems:
            raise PublishError("; ".join(problems[:5]))
        replace = bool(args.replace)
        if replace and committed_in_git(REPO_ROOT, rdir, args.git_ref):
            raise PublishError(
                f"release {m['release']} already has a manifest on {args.git_ref}; "
                "a merged release never changes"
            )
        out = Path(args.out) if args.out else None
        outcome = publisher_for(cfg, target=args.target, out_dir=out).publish(
            rdir, m, replace=replace
        )
    except (ReleaseOpError, PublishError) as exc:
        print(f"publish: {exc}")
        return 1
    print(f"release {m['release']}: {outcome} ({m['storage']['tag']})")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from ev_pipeline.net import FetchBlocked
    from ev_pipeline.release.publish import PublishError, fetch, load_config

    data_dir = default_data_dir()
    try:
        only = frozenset(x for x in (args.only or "").split(",") if x) or None
        stats = fetch(
            _release_dir(data_dir, args.n),
            load_config(data_dir),
            only=only,
            via_gh=bool(args.via_gh),
        )
    except FetchBlocked as exc:
        print(f"fetch: {exc}")
        print(
            f"hint: if direct HTTPS is blocked by a proxy, retry with "
            f"`ev release fetch {args.n} --via-gh`"
        )
        return 1
    except (ReleaseOpError, PublishError) as exc:
        print(f"fetch: {exc}")
        return 1
    extra = f", {stats['unpacked']} unpacked" if stats.get("unpacked") else ""
    print(f"release {args.n}: {stats['downloaded']} downloaded, {stats['kept']} already ok{extra}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from ev_pipeline.release.publish import PublishError, read_manifest, verify

    data_dir = default_data_dir()
    try:
        rdir = _release_dir(data_dir, args.n)
        m = read_manifest(rdir)
        if m is None:
            raise PublishError("no manifest.json")
        problems = verify(rdir, m, only_present=args.present_only)
    except (ReleaseOpError, PublishError) as exc:
        print(f"verify: {exc}")
        return 2
    for p in problems:
        print(p)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


def cmd_approvals(args: argparse.Namespace) -> int:
    """G-57: approved_changes.yaml loads like the build reads it; G-54: new approvals scoped
    to a release that is already published are warned (T-158)."""
    from ev_pipeline.release.approvals import (
        base_doc_from_git,
        check,
        latest_published,
    )
    from ev_pipeline.release.build import REPO_ROOT, default_data_dir
    from ev_pipeline.release.differ import CONFIG_FILE

    path = Path(args.file) if args.file else CONFIG_FILE
    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    latest = args.latest if args.latest is not None else latest_published(data_dir)
    if args.base_file:
        import yaml

        try:
            base = yaml.safe_load(Path(args.base_file).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as e:
            print(f"approvals: ERROR cannot read --base-file: {str(e).splitlines()[0]}")
            return 1
    else:
        base = base_doc_from_git(REPO_ROOT, args.base) if args.base else None
    errors, warnings = check(path, base, latest)
    for e in errors:
        print(f"approvals: ERROR {e}")
    for w in warnings:
        print(f"approvals: WARNING {w}")
    if args.base and not args.base_file and base is None and not errors:
        print(f"approvals: note: {args.base} has no {path.name}; every entry counts as new")
    if not errors and not warnings:
        print(f"approvals: ok ({path.name} loads; latest published release {latest})")
    if errors:
        return 1
    return 1 if warnings and args.strict else 0


def register(sub: argparse._SubParsersAction) -> None:
    rel = sub.choices.get("release")
    if rel is None:
        rel = sub.add_parser("release", help="build or manage catalogue releases")
    actions = rel.add_subparsers(
        dest="release_action",
        required=False,
        metavar="{rollback,diff,list,package,publish,fetch,verify,approvals}",
    )
    p = actions.add_parser("rollback", help="point data/releases/latest at an older release")
    p.add_argument("--to", type=int, required=True, help="release number")
    p.set_defaults(func=cmd_rollback)
    p = actions.add_parser("diff", help="what changed between two releases")
    p.add_argument("a", nargs="?", help="release number or 'latest'")
    p.add_argument("b", nargs="?", help="release number or 'latest'")
    p.add_argument("--from", dest="from_", help="older release (same as a)")
    p.add_argument("--to", help="newer release (same as b)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--check", action="store_true", help="exit 2 if a change would block QA")
    p.set_defaults(func=cmd_diff)
    p = actions.add_parser("list", help="releases, QA status, which one is latest")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)
    p = actions.add_parser("package", help="per-generation split + manifest.json (T-064)")
    p.add_argument("n", help="release number or 'latest'")
    p.set_defaults(func=cmd_package)
    p = actions.add_parser("publish", help="upload a release's files (GitHub Release assets)")
    p.add_argument("n", help="release number or 'latest'")
    p.add_argument("--target", choices=["github", "dir"], help="default: publish.yaml target")
    p.add_argument("--out", help="directory for --target dir")
    p.add_argument("--replace", action="store_true", help="replace an UNMERGED release's assets")
    p.add_argument("--git-ref", default="origin/main", help="ref that marks a release merged")
    p.set_defaults(func=cmd_publish)
    p = actions.add_parser("fetch", help="download a release's files by its manifest")
    p.add_argument("n", help="release number or 'latest'")
    p.add_argument("--only", help="comma-separated paths (a trailing / = a folder); default all")
    p.add_argument(
        "--via-gh",
        action="store_true",
        help="download assets via `gh release download` instead of direct HTTPS (G-66)",
    )
    p.set_defaults(func=cmd_fetch)
    p = actions.add_parser("verify", help="check local release files against manifest.json")
    p.add_argument("n", help="release number or 'latest'")
    p.add_argument("--present-only", action="store_true", help="skip files not on disk")
    p.set_defaults(func=cmd_verify)
    p = actions.add_parser(
        "approvals", help="check config/approved_changes.yaml (loads; new entries not stale)"
    )
    p.add_argument("--file", help="default: config/approved_changes.yaml")
    p.add_argument("--base", default="origin/main", help="ref whose entries are not new")
    p.add_argument("--base-file", help="the base version of the file (instead of --base)")
    p.add_argument("--latest", type=int, help="latest published release (default: data/)")
    p.add_argument("--data-dir", help="default: EV_DATA_DIR or data/")
    p.add_argument("--strict", action="store_true", help="exit 1 on a warning too")
    p.set_defaults(func=cmd_approvals)
