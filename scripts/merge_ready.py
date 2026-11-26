#!/usr/bin/env python3
"""merge_ready (T-158, T-165; rules G-52, G-59, G-54, G-63): is PR <n> safe to merge right now?

Usage:  sh scripts/merge_ready.sh <pr>          (or python3 scripts/merge_ready.py <pr>)
        python3 scripts/merge_ready.py --from-json facts.json   (offline: tests, dry runs)

Run it as its own step, right before the merge command, never in the same command (G-52). Exit 0 =
ready; 1 = not ready (every reason printed in plain words); 2 = could not ask GitHub.

Checks:
1. G-52: the PR branch is not behind main (`compare main...head`, behind_by = 0).
   G-59: behind is still fine when every commit main is ahead by touches only log files
   (workstreams/WS0/INBOX.md, workstreams/WS0/HANDOFF.md, CHATS.md) and GitHub says
   `mergeable_state: clean`.
2. CI on the PR head is green: every check run (latest per name) completed with success /
   neutral / skipped, at least one exists, and no commit status is failing or pending.
   G-63: a check run with both `conclusion` and `completed_at` counts as completed even if
   GitHub left its `status` at `in_progress` (noted in output).
3. G-54: when the PR changes config/approved_changes.yaml, no entry it adds is scoped to a
   release main has already published (`data/releases/latest` on main). Needs the pipeline env
   (uv); skipped with a note when uv is missing.

Stdlib only; GitHub calls go through `gh api` (REST; GraphQL is blocked in Claude sessions).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = os.environ.get("MERGE_READY_REPO", "zkMenno/EV-Shortlist")
ROOT = Path(__file__).resolve().parent.parent
LOG_FILES = {"workstreams/WS0/INBOX.md", "workstreams/WS0/HANDOFF.md", "CHATS.md"}
APPROVALS = "config/approved_changes.yaml"
OK_CONCLUSIONS = {"success", "neutral", "skipped"}


class GitHubError(RuntimeError):
    pass


def gh(path: str) -> Any:
    cp = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if cp.returncode != 0:
        raise GitHubError(f"gh api {path}: {(cp.stderr or cp.stdout).strip()[:300]}")
    return json.loads(cp.stdout)


def _content(path: str, ref: str, api: Callable[[str], Any]) -> str | None:
    try:
        doc = api(f"repos/{REPO}/contents/{path}?ref={ref}")
    except GitHubError:
        return None
    return base64.b64decode(doc.get("content") or "").decode("utf-8")


def gather(pr: int, api: Callable[[str], Any] = gh) -> dict[str, Any]:
    """Everything evaluate() needs, from GitHub's REST API."""
    p = api(f"repos/{REPO}/pulls/{pr}")
    head, base = p["head"]["sha"], p["base"]["ref"]
    behind = api(f"repos/{REPO}/compare/{base}...{head}")
    ahead = api(f"repos/{REPO}/compare/{head}...{base}") if behind.get("behind_by") else {}
    runs = api(f"repos/{REPO}/commits/{head}/check-runs?per_page=100")
    status = api(f"repos/{REPO}/commits/{head}/status")
    files: list[dict[str, Any]] = []
    for page in range(1, 31):  # GitHub lists at most 3000 files; 100 per page
        batch = api(f"repos/{REPO}/pulls/{pr}/files?per_page=100&page={page}")
        files += batch
        if len(batch) < 100:
            break
    facts: dict[str, Any] = {
        "pr": pr,
        "state": p.get("state"),
        "merged": bool(p.get("merged")),
        "base": base,
        "head_sha": head,
        "mergeable_state": p.get("mergeable_state"),
        "behind_by": int(behind.get("behind_by") or 0),
        "ahead_files": sorted({f["filename"] for f in ahead.get("files") or []}),
        "check_runs": [
            {"id": r.get("id"), "name": r.get("name"), "status": r.get("status"),
             "conclusion": r.get("conclusion"), "completed_at": r.get("completed_at")}
            for r in runs.get("check_runs") or []
        ],  # fmt: skip
        "statuses": [
            {"context": s.get("context"), "state": s.get("state")}
            for s in status.get("statuses") or []
        ],
        "pr_files": sorted(f["filename"] for f in files),
    }
    if APPROVALS in facts["pr_files"]:
        facts["approvals"] = {
            "head": _content(APPROVALS, head, api),
            "base": _content(APPROVALS, base, api),
            "latest": (_content("data/releases/latest", base, api) or "").strip() or None,
        }
    return facts


def approvals_check(head: str, base: str | None, latest: int) -> tuple[list[str], str | None]:
    """(problems, note) via the pipeline's own check (`ev release approvals`, G-54 / G-57)."""
    uv = shutil.which("uv")
    if uv is None:
        return [], "approvals check skipped: uv not found (run `uv run ev release approvals`)"
    with tempfile.TemporaryDirectory(prefix="merge-ready-") as tmp:
        hp, bp = Path(tmp) / "head.yaml", Path(tmp) / "base.yaml"
        hp.write_text(head, encoding="utf-8")
        args = [uv, "run", "-q", "--project", str(ROOT / "pipeline"), "ev", "release",
                "approvals", "--file", str(hp), "--latest", str(latest), "--strict"]  # fmt: skip
        if base is not None:
            bp.write_text(base, encoding="utf-8")
            args += ["--base-file", str(bp)]
        else:
            args += ["--base", ""]
        cp = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT / "pipeline"))
    lines = [ln for ln in cp.stdout.splitlines() if "ERROR" in ln or "WARNING" in ln]
    if cp.returncode != 0 and not lines:
        lines = [f"approvals check failed: {(cp.stderr or cp.stdout).strip()[-300:]}"]
    return lines, None


def latest_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The newest run per check name (a re-run or a workflow_dispatch run replaces older ones)."""
    best: dict[str, dict[str, Any]] = {}
    for r in runs:
        name = str(r.get("name"))
        if name not in best or (r.get("id") or 0) > (best[name].get("id") or 0):
            best[name] = r
    return [best[k] for k in sorted(best)]


def evaluate(
    f: dict[str, Any],
    check_approvals: Callable[[str, str | None, int], tuple[list[str], str | None]] = approvals_check,
) -> tuple[list[str], list[str]]:
    """(problems, notes). No problems = ready to merge."""
    problems: list[str] = []
    notes: list[str] = []
    if f.get("merged") or f.get("state") != "open":
        problems.append(f"PR #{f['pr']} is not open (state {f.get('state')}).")
        return problems, notes
    behind = int(f.get("behind_by") or 0)
    if behind:
        others = [p for p in f.get("ahead_files") or [] if p not in LOG_FILES]
        if not others and f.get("ahead_files") and f.get("mergeable_state") == "clean":
            notes.append(
                f"behind {f['base']} by {behind} commit(s), log files only"
                f" ({', '.join(f['ahead_files'])}) and mergeable_state clean: allowed (G-59)."
            )
        else:
            why = (
                f"it changes {', '.join(others[:5])}" + (f" and {len(others) - 5} more" if len(others) > 5 else "")
                if others
                else f"mergeable_state is {f.get('mergeable_state')!r}, not 'clean'"
            )
            problems.append(
                f"The branch is {behind} commit(s) behind {f['base']} and {why}. Merge"
                f" {f['base']} into the branch, wait for CI on the new head, then run this again"
                " (G-52)."
            )
    runs = latest_runs(f.get("check_runs") or [])
    if not runs:
        problems.append(
            f"No CI has run on the head commit {str(f.get('head_sha'))[:10]}. Start it with"
            " workflow_dispatch and wait for it to finish."
        )
    for r in runs:
        status = r.get("status")
        conclusion = r.get("conclusion")
        completed_at = r.get("completed_at")
        has_conclusion = isinstance(conclusion, str) and bool(conclusion.strip())
        has_completed_at = isinstance(completed_at, str) and bool(completed_at.strip())
        completed = status == "completed"
        if not completed and has_conclusion and has_completed_at:
            completed = True
            notes.append(
                f"CI check '{r['name']}' reports status {status!r} with conclusion"
                f" '{conclusion}' and completed_at {completed_at}: treated as completed (G-63)."
            )
        if not completed:
            problems.append(f"CI check '{r['name']}' is still {status} on the head.")
        elif conclusion not in OK_CONCLUSIONS:
            problems.append(f"CI check '{r['name']}' ended {conclusion} on the head.")
    for s in f.get("statuses") or []:
        if s.get("state") != "success":
            problems.append(f"Commit status '{s.get('context')}' is {s.get('state')} on the head.")
    ap = f.get("approvals")
    if ap is not None:
        latest = str(ap.get("latest") or "")
        if ap.get("head") is None:
            problems.append(f"Could not read {APPROVALS} at the PR head.")
        elif not latest.isdigit():
            notes.append(f"approvals check skipped: main has no data/releases/latest ({latest!r}).")
        else:
            bad, note = check_approvals(ap["head"], ap.get("base"), int(latest))
            problems += bad
            if note:
                notes.append(note)
    return problems, notes


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--from-json":
        src = sys.stdin.read() if argv[1] == "-" else Path(argv[1]).read_text(encoding="utf-8")
        facts = json.loads(src)
    elif len(argv) == 1 and argv[0].lstrip("#").isdigit():
        try:
            facts = gather(int(argv[0].lstrip("#")))
        except (GitHubError, KeyError, ValueError) as e:
            print(f"merge_ready: could not ask GitHub: {e}")
            return 2
    else:
        print("usage: merge_ready.sh <pr number>   |   merge_ready.py --from-json <file|->")
        return 2
    problems, notes = evaluate(facts)
    for n in notes:
        print(f"note: {n}")
    if problems:
        print(f"NOT READY: PR #{facts.get('pr')} — do not merge yet:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"READY: PR #{facts.get('pr')} is up to date with {facts.get('base')} (or log-only behind)"
        f" and CI is green on {str(facts.get('head_sha'))[:10]}. Merge it now, as the next step."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
