"""Tests for scripts/merge_ready.py (T-158, G-52 / G-59 / G-54). No network: GitHub answers are
canned dicts. Run: python3 -m unittest discover -s scripts/tests"""
import base64
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merge_ready as mr  # noqa: E402

GREEN = [{"id": 1, "name": "pipeline", "status": "completed", "conclusion": "success"}]


def facts(**kw):
    base = {
        "pr": 7, "state": "open", "merged": False, "base": "main", "head_sha": "abc1234567",
        "mergeable_state": "clean", "behind_by": 0, "ahead_files": [],
        "check_runs": GREEN, "statuses": [], "pr_files": ["pipeline/x.py"],
    }  # fmt: skip
    base.update(kw)
    return base


def never(*a):
    raise AssertionError("approvals check must not run")


class Behind(unittest.TestCase):
    def test_up_to_date_and_green_is_ready(self):
        self.assertEqual(mr.evaluate(facts(), never), ([], []))

    def test_behind_by_code_is_not_ready(self):
        p, _ = mr.evaluate(facts(behind_by=5, ahead_files=["pipeline/a.py", "CHATS.md"]), never)
        self.assertEqual(len(p), 1)
        self.assertIn("5 commit(s) behind main", p[0])
        self.assertIn("pipeline/a.py", p[0])
        self.assertIn("G-52", p[0])

    def test_behind_by_log_files_only_and_clean_passes(self):
        f = facts(behind_by=2, ahead_files=["CHATS.md", "workstreams/WS0/INBOX.md"])
        p, n = mr.evaluate(f, never)
        self.assertEqual(p, [])
        self.assertIn("G-59", n[0])

    def test_log_files_only_but_not_clean_is_not_ready(self):
        f = facts(behind_by=1, ahead_files=["workstreams/WS0/HANDOFF.md"], mergeable_state="blocked")
        p, _ = mr.evaluate(f, never)
        self.assertEqual(len(p), 1)
        self.assertIn("'blocked'", p[0])

    def test_behind_with_unknown_files_is_not_ready(self):
        p, _ = mr.evaluate(facts(behind_by=1, ahead_files=[]), never)
        self.assertEqual(len(p), 1)

    def test_closed_pr(self):
        p, _ = mr.evaluate(facts(state="closed"), never)
        self.assertIn("not open", p[0])


class Checks(unittest.TestCase):
    def test_no_ci_on_head(self):
        p, _ = mr.evaluate(facts(check_runs=[]), never)
        self.assertIn("workflow_dispatch", p[0])

    def test_failed_and_pending_runs(self):
        runs = [
            {"id": 1, "name": "web", "status": "completed", "conclusion": "failure"},
            {"id": 2, "name": "pipeline", "status": "in_progress", "conclusion": None},
            {"id": 3, "name": "lint", "status": "completed", "conclusion": "skipped"},
        ]
        p, _ = mr.evaluate(facts(check_runs=runs), never)
        self.assertEqual(len(p), 2)
        self.assertTrue(any("'web' ended failure" in x for x in p))
        self.assertTrue(any("'pipeline' is still in_progress" in x for x in p))

    def test_newest_run_per_name_wins(self):
        runs = [
            {"id": 5, "name": "data-qa", "status": "completed", "conclusion": "failure"},
            {"id": 9, "name": "data-qa", "status": "completed", "conclusion": "success"},
        ]
        self.assertEqual(mr.evaluate(facts(check_runs=runs), never), ([], []))

    def test_failing_commit_status(self):
        p, _ = mr.evaluate(facts(statuses=[{"context": "ci/x", "state": "pending"}]), never)
        self.assertIn("'ci/x' is pending", p[0])

    def test_stuck_in_progress_with_conclusion_and_completed_at_passes_with_note(self):
        runs = [
            {
                "id": 10,
                "name": "pipeline",
                "status": "in_progress",
                "conclusion": "success",
                "completed_at": "2026-11-19T15:00:00Z",
            }
        ]
        p, n = mr.evaluate(facts(check_runs=runs), never)
        self.assertEqual(p, [])
        self.assertEqual(len(n), 1)
        self.assertIn("'pipeline'", n[0])
        self.assertIn("in_progress", n[0])
        self.assertIn("2026-11-19T15:00:00Z", n[0])
        self.assertIn("G-63", n[0])

    def test_stuck_in_progress_with_failure_still_blocks_with_note(self):
        runs = [
            {
                "id": 11,
                "name": "web",
                "status": "in_progress",
                "conclusion": "failure",
                "completed_at": "2026-11-19T15:00:00Z",
            }
        ]
        p, n = mr.evaluate(facts(check_runs=runs), never)
        self.assertEqual(len(p), 1)
        self.assertIn("'web' ended failure", p[0])
        self.assertEqual(len(n), 1)
        self.assertIn("G-63", n[0])

    def test_in_progress_missing_completed_at_or_conclusion_still_blocks(self):
        runs = [
            {
                "id": 12,
                "name": "no-ts",
                "status": "in_progress",
                "conclusion": "success",
                "completed_at": None,
            },
            {
                "id": 13,
                "name": "no-conclusion",
                "status": "in_progress",
                "conclusion": None,
                "completed_at": "2026-11-19T15:00:00Z",
            },
        ]
        p, n = mr.evaluate(facts(check_runs=runs), never)
        self.assertEqual(n, [])
        self.assertEqual(len(p), 2)
        self.assertTrue(any("'no-ts' is still in_progress" in x for x in p))
        self.assertTrue(any("'no-conclusion' is still in_progress" in x for x in p))


class Approvals(unittest.TestCase):
    def test_runs_when_the_pr_changes_approvals(self):
        seen = []

        def chk(head, base, latest):
            seen.append((head, base, latest))
            return (["approvals: WARNING scoped to release 3"], None)

        ap = {"head": "h", "base": "b", "latest": "3"}
        p, _ = mr.evaluate(facts(approvals=ap), chk)
        self.assertEqual(seen, [("h", "b", 3)])
        self.assertEqual(p, ["approvals: WARNING scoped to release 3"])

    def test_skipped_with_a_note_without_latest(self):
        p, n = mr.evaluate(facts(approvals={"head": "h", "base": None, "latest": None}), never)
        self.assertEqual(p, [])
        self.assertIn("skipped", n[0])


class Gather(unittest.TestCase):
    def test_gather_reads_rest_answers(self):
        def b64(s):
            return {"content": base64.b64encode(s.encode()).decode()}

        runs = [
            {
                "id": 1,
                "name": "pipeline",
                "status": "in_progress",
                "conclusion": "success",
                "completed_at": "2026-11-19T15:00:00Z",
            }
        ]
        answers = {
            f"repos/{mr.REPO}/pulls/7": {
                "state": "open", "merged": False, "mergeable_state": "clean",
                "head": {"sha": "h1"}, "base": {"ref": "main"},
            },
            f"repos/{mr.REPO}/compare/main...h1": {"behind_by": 1},
            f"repos/{mr.REPO}/compare/h1...main": {"files": [{"filename": "CHATS.md"}]},
            f"repos/{mr.REPO}/commits/h1/check-runs?per_page=100": {"check_runs": runs},
            f"repos/{mr.REPO}/commits/h1/status": {"statuses": []},
            f"repos/{mr.REPO}/pulls/7/files?per_page=100&page=1": [{"filename": mr.APPROVALS}],
            f"repos/{mr.REPO}/contents/{mr.APPROVALS}?ref=h1": b64("head"),
            f"repos/{mr.REPO}/contents/{mr.APPROVALS}?ref=main": b64("base"),
            f"repos/{mr.REPO}/contents/data/releases/latest?ref=main": b64("3\n"),
        }  # fmt: skip
        f = mr.gather(7, api=lambda path: answers[path])
        self.assertEqual(f["behind_by"], 1)
        self.assertEqual(f["ahead_files"], ["CHATS.md"])
        self.assertEqual(f["approvals"], {"head": "head", "base": "base", "latest": "3"})
        self.assertEqual(f["check_runs"][0]["completed_at"], "2026-11-19T15:00:00Z")


class Pages(unittest.TestCase):
    def test_pr_files_are_paged(self):
        calls = []

        def api(path):
            calls.append(path)
            if "/files?" in path:
                page = int(path.rsplit("page=", 1)[1])
                n = 100 if page == 1 else 3
                return [{"filename": f"f{page}-{i}"} for i in range(n)] + (
                    [{"filename": mr.APPROVALS}] if page == 2 else []
                )[: 100 - n if page == 1 else None]
            if path.endswith("/pulls/7"):
                return {"state": "open", "head": {"sha": "h"}, "base": {"ref": "main"}}
            if "/compare/" in path:
                return {"behind_by": 0}
            if "check-runs" in path:
                return {"check_runs": GREEN}
            if path.endswith("/status"):
                return {"statuses": []}
            raise mr.GitHubError(path)  # contents: not needed for this test

        f = mr.gather(7, api=api)
        self.assertEqual(len(f["pr_files"]), 104)
        self.assertIn(mr.APPROVALS, f["pr_files"])  # found on page 2
        self.assertIn("approvals", f)


class Main(unittest.TestCase):
    def test_from_json_exit_codes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ok, bad = Path(d) / "ok.json", Path(d) / "bad.json"
            ok.write_text(json.dumps(facts()))
            bad.write_text(json.dumps(facts(behind_by=3, ahead_files=["pipeline/a.py"])))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(mr.main(["--from-json", str(ok)]), 0)
                self.assertEqual(mr.main(["--from-json", str(bad)]), 1)
                self.assertEqual(mr.main([]), 2)
            self.assertIn("READY", out.getvalue())
            self.assertIn("NOT READY", out.getvalue())

    def test_from_json_prints_g63_note_and_ready(self):
        import tempfile

        stuck = [
            {
                "id": 99,
                "name": "ci-ok",
                "status": "in_progress",
                "conclusion": "success",
                "completed_at": "2026-11-19T15:01:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "stuck.json"
            p.write_text(json.dumps(facts(check_runs=stuck)))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(mr.main(["--from-json", str(p)]), 0)
            text = out.getvalue()
            self.assertIn("note: CI check 'ci-ok'", text)
            self.assertIn("G-63", text)
            self.assertIn("READY:", text)


if __name__ == "__main__":
    unittest.main()
