# REVIEW.md — what a reviewer checks (Decision 062, T-120)

Reviewers (fresh agent, QA chat or `/review`) read this file **from `main`, never from the PR branch**. A PR that changes this file is a gate change (T-121) and gets its own PR.

## How to use
1. List the changed paths (`git diff --name-only origin/main...HEAD`).
2. Run only the items whose trigger matches. Usually 3–10.
3. For each: pass / fail, plus the evidence (command output, screenshot, number). "Looks fine" is not evidence.
4. Rate each finding: **must-fix** (blocks merge), **should-fix** (before public), **nit**, **pre-existing** (not the author's fault; log it, don't block).
5. Fix rounds: up to 3. Still failing → stop, write it in the task's `## Review`, ping WS0 INBOX.
6. **One review = one commit.** Note the head SHA you reviewed. If the head moves during review, re-run R0 and the triggered items on the new head.
7. Write the result under `## Review` in the task file: reviewer, date, head SHA, item ids and verdicts, e.g. `R0–R3, D1, D3: pass (abc1234)`.

Read this file with `git show origin/main:REVIEW.md`, so a PR can't change the rules it is judged by.

## Always
| # | Check | Why (incident) |
|---|---|---|
| R0 | CI green **on the PR head commit** (start with workflow_dispatch if the push didn't trigger it); review is for that commit only. Exception (G-47): if main moved only by log files (`workstreams/WS0/INBOX.md`, `workstreams/WS0/HANDOFF.md`, `CHATS.md`) and the PR's own files are byte-identical to the reviewed SHA, the review stands; R0 still runs on the new head | WS2 retro: pushes from sessions don't start CI |
| R1 | No merge-conflict markers (lines starting with seven `<`, `=` or `>`) anywhere | WS2 retro: markers left after a merge |
| R2 | PR body has an evidence pack: how it was verified (commands + results, screenshots, back-test numbers; the `Verified:` stamp lands with T-128); claims in MORNING/STATUS match what the code/release does | A-20 B1: MORNING.md reported MG4 8→6, the release didn't contain it |
| R3 | The PR doesn't change its own checks (tests weakened/deleted, thresholds raised, CI steps removed, AGENTS/REVIEW edited) | Article: checks out of reach of the change |
| R4 | Launch or deploy PRs: `latest` release is newer than the last merge into its inputs (`data/seed/**`, `data/manual/**`, `pipeline/ev_pipeline/derive/**`); any launch-scope sentence the PR touches has an acceptance test on the **published** release, not only fixtures | A-35 B1 (release 1 older than every launch data task), B2 (budget did nothing on real data) |

## Triggered by the diff
| # | Trigger (path or pattern) | Check | Why (incident) |
|---|---|---|---|
| D1 | `data/seed/**`, `pipeline/ev_pipeline/merge/**`, matcher code | Release rebuilt from the same inputs and committed/published; `pytest` green; release diff (T-123) reviewed | A-20 B1 stale release |
| D2 | `data/sources.yaml`, new source adapter, `pipeline/ev_pipeline/images/**` (licence parsing in `photos.py`, `store.py`) | Licence line + terms note; status gate correct; attribution wording follows open Q (e.g. Q-037 RDW); no ODbL into release; a licence-parser change is tested on ≥10 real cached file pages plus every refusal / deletion template name (G-55) | A-20 S1/S2 RDW + KBA |
| D3 | New or changed derived score/model/band (`derive/**`, `*_params.yaml`, `*_rules.yaml`) | Dry run on latest release rows; back-test section in qa.json with median error; units stated per threshold; **the back-test runs the ranking the visitor sees** (one implementation per rule, Decision 065) | WS1 retros; A-35 B3 (web scored a different basis than the back-test) |
| D4 | Matching/attachment rules (`pipeline/ev_pipeline/match/**`, `pipeline/ev_pipeline/merge/**`), seed or manual spec figures (EPA, registrations, picks importer, `data/seed/**`) | Spot-check 5 known tricky cars (EV6, Ioniq 5, MG4, Model Y LR vs Juniper, P7+); the qa.json plausibility gate (T-111: km per kWh and DC km/20 min outliers) passes; **a matching or merge-logic change** (`pipeline/ev_pipeline/match/**`, `merge/**`) quotes a same-data rebuild diff in the PR body: old vs new code on freshly fetched staging, changed ids, changed rows, ± facts (recipe: #135; G-43) | A-30 EPA range class; T-068 tokenising; A-35 B4 (Model Y 719 km, #1 pick); WS1 8th retro |
| D5 | `packages/schema/**` | Additive only, or a migration note; generated types regenerated; old release (N-1) still loads in the web app | Releases are read by older and newer code |
| D6 | User-visible strings (`apps/web/**/i18n/**`, `apps/web/**/messages*`, `content/**`) | **Until languages return (Decision 082): English only.** Every public key exists in English; every launch country serves `/{country}/en/`; hidden-language URLs redirect to `/{country}/en/` and are not linked, in the sitemap or in hreflang; existing NL/DE/FR/ES/IT strings are kept, not deleted. Glossary id + ⓘ tooltip for any new term. When a language returns, this item again requires that language for every public key (`i18n.test.ts`) | Product principle; T-093; A-35 B5 (DE/FR 172 of 736 keys, ES/IT not served); Decision 082 |
| D7 | Any new number on a page | Source + date + licence visible in Nerd mode; estimates labelled | Product principle |
| D8 | UI components/styles | Screenshots 360 px + 1280 px, light + dark; axe clean; WCAG AA contrast (workstreams/UX/tools/contrast.py); every 360 px check also runs once with wider letters (`letter-spacing: 0.06em`, ~6 % wider, since CI fonts run wider; G-44) | UX hard rule; WS2 5th retro (db62961) |
| D9 | Feature flags, routes, nav | Parked features (Decision 051) stay behind flags, off | Launch scope |
| D10 | `apps/web` bundle-affecting changes | Explore first load stays under the budget in audits/A-03 | Perf budget |
| D11 | `.github/workflows/**`, `infra/**`, deploy | Gate change → separate PR, WS0 approves; least-privilege permissions; actions pinned to SHA | CI security baseline (A-02) |
| D12 | `DECISIONS.md` | Number is inside the writer's own block; no duplicate numbers; **a de-dupe keeps the union of both texts** (never drop the newer one) | Clashes 052–056, duplicate 060; A-35 S1 (e885fa0 dropped Decision 060's 17 Nov checks) |
| D13 | Network code in tests | Tests never call the network (fixtures only) | AGENTS.md |

## Keeping this file alive
- Each item names the incident behind it. A miss found after merge (QA, back-test, Menno, a revert) adds or sharpens an item here (T-122 rule register).
- Prune each phase: drop items that never fire or never catch anything; merge duplicates.
