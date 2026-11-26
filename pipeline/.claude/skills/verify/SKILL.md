---
name: verify-pipeline
description: Use before any commit or PR that changes data, matching, merge, derive rules, params, seed, taxonomy, editorial rules or config/approved_changes.yaml in EV Finder. Rebuilds the release from recorded staging, runs tests, the release diff, back-tests and tricky-car spot checks, and checks the numbers quoted in the PR body.
---

# verify-pipeline (T-127)

Prove a data change before you claim it. "Looks fine" is not evidence (REVIEW.md).

## When
Any change under `pipeline/ev_pipeline/{match,merge,derive,release,qa}/`, `*_params.yaml`,
`*_rules.yaml`, `data/seed/`, `data/taxonomy/`, `data/editorial/`, `data/manual/`,
`data/sources.yaml`, `data/field_sources.yaml` or `config/approved_changes.yaml`.

## Steps
1. **Staging.** `ev verify` rebuilds from `data/staging/` and never fetches. With no staging,
   record it once (network, ~10 min, < 300 MB): `cd pipeline && uv run ev refresh --no-release`.
   Use a scratch `EV_DATA_DIR` when you don't want to touch your checkout's data/.
2. **Run** `cd pipeline && uv run ev verify` (it refuses while `ev refresh` is writing
   staging, G-49: wait for the refresh) (add `--data-dir` for a scratch data dir).
   Fresh staging but the committed N-1 is older? Add `--base-release-from origin/main`: it builds
   main on the same staging and diffs against that, so only this branch's changes show (G-56).
   Add `--keep <new dir>` to keep the scratch build and trace where a value came from (G-53).
   It writes `pipeline/verify-report.md` (git-ignored) and exits 1 on any failure:
   rebuild failed, tests failed, release diff blocking, or a PR body claim that doesn't match.
3. **Read the report**, in this order:
   - Release diff: every blocking line is either a bug (fix it) or intended. If it's
     intended, add a release-scoped entry to `config/approved_changes.yaml` with the reason
     and `PR #n` / `Decision nnn`. Don't raise a threshold to make a line go away (REVIEW.md R3:
     that is a gate change, its own PR).
   - Back-tests: compare each median with its gate and with the previous release. A flag
     doesn't block, but say it in the PR.
   - Changed rules: the dry run is the release diff. Check that the moves are the ones the
     rule change was meant to make, and nothing else.
   - Seed vs built (G-48): a seed variant built with another drivetrain, or a WLTP > 10 %
     off its own cited WLTP. New ones fail the run; ones the previous release already had
     are listed for the seed's owner (WS3).
   - Derived flag changes from missing inputs (G-62): rows whose derived shortlist flags
     changed solely because an input is missing (e.g. `power_kw` under Decision 088), with
     the missing input named. Report only, so "unknown -> no flag" rules show their data cost.
   - Spot checks: EV6, Ioniq 5, MG4, Model Y LR vs Juniper, P7+. Bold cells moved. Look
     at every bold cell and every note ("real range > WLTP x 1.1", "no battery", "gone").
4. **PR body.** Paste the report's Numbers block, then run
   `uv run ev verify --skip-tests --pr-body <file with the PR body>` once more. A number
   quoted in the body (`key: value`) that the release doesn't have fails the run (A-20 B1).
   Quote numbers in MORNING/STATUS from the report too, never from memory.
5. **Commit stamp:** end the commit message with `Verified: verify-pipeline` plus one line
   of what it showed (e.g. `0 blocking, 3 approved; EPA proxy 8.9 % < 10 %`).

## Don't
- Don't commit `verify-report.md` or anything from the scratch build.
- Don't run it on the shared server in the daytime (Decision 006): it builds a full release.
