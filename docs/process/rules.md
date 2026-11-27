# Rule register (T-122, Decision 062)

Every rule we work by, the incident behind it, and **where it is enforced**. A rule that lives only in prose is marked *prose* and is a candidate for a real check. Add a row when a miss is found after merge (QA, back-test, Menno, a revert): the miss + the check added. Prune once per phase: rules that never fire get merged or dropped, with a note.

Find unverified work: `git log --grep="Verified: none" --oneline` (stamp lands with T-128).

| Id | Rule | Incident behind it | Enforced by | Owner | Added | Last fired |
|---|---|---|---|---|---|---|
| G-01 | Raw data never in git (5 MB cap); release files 25 MB cap | catalogue.json 7.1 MB turned main red (15 Nov) | CI repo-checks | WS0 | 2026-11-15 | 2026-11-15 |
| G-02 | No `.env` files committed | baseline | CI repo-checks | WS0 | 2026-11-14 | — |
| G-03 | No merge-conflict markers in tracked files | WS2 retro: markers left after a messy merge (15 Nov) | CI repo-checks + optional `.githooks/pre-push` | WS0 | 2026-11-17 | — |
| G-04 | Decision numbers unique | duplicate 019 (15 Nov), 039, 053/054, 060 | CI repo-checks | WS0 | 2026-11-17 | — |
| G-05 | Decision numbers come from the writer's own block (table at the top of DECISIONS.md) | WS2 retro: 053/054 taken by other chats | REVIEW D12 (+ G-04) | WS0 | 2026-11-17 | — |
| G-06 | A change can't edit the checks that judge it (gate files in their own PR) | article: gates out of reach of the change | CI `gate-guard` (observe → enforce, T-121) + REVIEW R3 | WS0 | 2026-11-17 | — |
| G-07 | Reviewers read REVIEW.md from `origin/main`; one review per commit (head SHA) | launch tasks merged without review (QA, 17 Nov) | REVIEW.md + AGENTS.md *prose* until T-128 | WS0 | 2026-11-17 | — |
| G-08 | Trust only the CI run on the PR head commit; start with `workflow_dispatch` after a session push | WS2 retro: session pushes don't start CI | REVIEW R0 | WS0 | 2026-11-17 | — |
| G-09 | Never rebase a pushed branch; merge main in | WS2 retro: rebase + blocked force-push | *prose* (AGENTS.md); force-push is blocked by the host anyway | WS0 | 2026-11-17 | — |
| G-10 | Every derived score/band/model: dry run on latest release rows before tests; back-test section in qa.json | WS1 retros: thresholds on a different data basis; 22 % rung inconsistency and wrong EPA matches found only by back-test | REVIEW D3 + pipeline/AGENTS.md | WS1 | 2026-11-17 | — |
| G-11 | Matching/attachment rule changes spot-check 5 tricky cars | A-30 EPA range class; T-068 '+' tokenising | REVIEW D4 | WS1 | 2026-11-17 | — |
| G-12 | Tests never call the network | baseline | REVIEW D13; *prose* otherwise (candidate: socket-blocking fixture) | WS1/WS2 | 2026-11-14 | — |
| G-13 | Every user-visible string in every served language (EN only until languages return, Decision 082; drafts allowed) + glossary tooltip for new terms | T-093 shipped unreviewed strings | REVIEW D6 | WS2/WS3 | 2026-11-17 | — |
| G-14 | Parked features (Decision 051) behind flags, off | launch scope | REVIEW D9; parked e2e only in `PARKED=1` builds | WS2 | 2026-11-17 | — |
| G-15 | Start of a batch: check open PRs and your task files (Status, Handoff notes, `## Review`) first; only the coordinator reads a HANDOFF (`workstreams/WS0/HANDOFF.md`). Updated 2026-11-18 for one coordinator + batch chats (docs/process §3) | WS1 (3rd session) retro; 18 Nov: per-lane HANDOFFs retired | docs/process §2 + lane briefs *prose* | all | 2026-11-17 | 2026-11-18 |
| G-16 | Only `workstreams/WS0/HANDOFF.md` (coordinator) and lines appended to `workstreams/WS0/INBOX.md` may go straight to main (docs only); everything else goes through a PR. Updated 2026-11-18: per-lane STATUS/HANDOFF/INBOX retired | WS1 retro: two PRs appending to the same logs | AGENTS.md + docs/process §2 *prose* | all | 2026-11-17 | 2026-11-18 |
| G-17 | Use `gh api …/pulls` when `gh pr create` fails | WS1 retro: GraphQL blocked in sessions | AGENTS.md *prose* (tip) | all | 2026-11-17 | — |
| G-18 | WS0 merges green + reviewed PRs at least once a day, in one pass; small housekeeping rides in its task PR | WS1 retro: 9-PR chain waiting on WS0 | *prose* (WS0 STATUS) | WS0 | 2026-11-17 | — |
| G-19 | Parked-feature e2e runs nightly in a `PARKED=1` build | WS2 retro: parked e2e only run by hand | to build: WS2 follow-up (T-095) | WS2 | 2026-11-17 | — |
| G-20 | Every number visible on a page has source + date + licence in Nerd mode | product principle | REVIEW D7 | WS2 | 2026-11-15 | — |
| G-21 | One owner per file; read right before writing; small edits (was P-01) | Two chats nearly overwrote the decisions file (15 Nov) | *prose* (docs/process/README.md) | all | 2026-11-15 | — |
| G-22 | Spec mirrored in docs/spec/; repo copy wins for builders (was P-02) | Overnight build couldn't read the claude.ai spec | *prose* | WS0 | 2026-11-15 | — |
| G-23 | Chats talk through the coordinator's INBOX (`workstreams/WS0/INBOX.md`), never via Menno; cross-lane requests go there and the coordinator puts them in the next brief (was P-03; one inbox since 2026-11-18) | Menno relayed AppInfra answers by hand | *prose* (docs/process §2) | all | 2026-11-15 | 2026-11-18 |
| G-24 | Measure before sizing (server, memory) (was P-04) | Server facts guessed before measured | *prose* | WS4 | 2026-11-15 | — |
| G-25 | Project instructions live in a versioned file (was P-05) | Instructions lived only in a chat message | *prose* (docs/process/project-instructions.md) | WS0 | 2026-11-15 | — |
| G-26 | QUESTIONS.md holds only what Menno must answer (was P-06) | 83 "open" questions, ~76 engineering defaults (17 Nov) | *prose*; candidate: CI warns when > 10 open | WS0 | 2026-11-17 | — |
| G-27 | Release must match its inputs; reports must match the release (was P-13) | A-20 B1: stale release; MORNING.md quoted numbers it didn't contain | CI pytest (test_real_release); T-123, T-127 | WS1 | 2026-11-17 | — |
| G-28 | Every commit ends with `Verified: <how>` (was P-16) | Unverified work wasn't findable | to build: T-128 | WS0 | 2026-11-17 | — |
| G-29 | Flaky tests: no skip/sleep/retry; fix or delete + log (was P-17) | Article: flaky tests teach rerunning | CI `gate-guard` (observe) + T-128 | WS0 | 2026-11-17 | — |
| G-30 | Chat mentions: direct link + paste-ready code block every time (was P-18) | Menno had to ask twice (17 Nov) | *prose* (project instructions) | all | 2026-11-17 | — |
| G-31 | One process doc, one decisions log per kind; project docs are pointers (was P-19) | Workflow described in 5 places, decisions in 2 (17 Nov) | *prose* | WS0 | 2026-11-17 | — |
| G-32 | Retire docs into `_archive/` (git mv + row in `_archive/README.md`), never delete; chats never read, search or cite `_archive/` unless Menno asks | Menno (17 Nov): move, don't delete; keep old docs out of every chat's context | `.rgignore` (Grep skips it) + AGENTS.md, docs/process §2, project instructions v1.6 *prose* | WS0 | 2026-11-17 | — |
| G-33 | Run the full local gate in the session before opening or updating a PR; one PR per batch; no "just to check" CI runs (was P-21) | GardenLayer burned ~2,900 Actions min in 17 days (#813), mostly re-running red PRs | *prose* (AGENTS.md, docs/process/ci-budget.md); candidate: ci-ok warns if a PR gets > 3 pushes | WS0 | 2026-11-17 | — |
| G-34 | Launch/deploy needs a fresh release: `latest` newer than the last merge into release inputs | A-35 B1: release 1 predated every launch data task; build log hid it | REVIEW R4; fetch-release warns on missing files (#46); to build: CI launch gate | WS1/WS0 | 2026-11-17 | — |
| G-35 | Each launch-scope sentence has an acceptance test on the published release | A-35 B2: €15k and €35k gave the same top 10 | REVIEW R4; T-115 e2e | WS2 | 2026-11-17 | — |
| G-36 | One implementation per rule; the back-test runs the ranking visitors see | A-35 B3: web and pipeline scored different bases | REVIEW D3; Decision 065; T-114 | WS0 | 2026-11-17 | — |
| G-37 | Implausible spec figures go to review, not the release | A-35 B4: Model Y LR 719 km WLTP was the #1 pick | to build: qa.json plausibility gate (T-111); REVIEW D4 | WS1 | 2026-11-17 | — |
| G-38 | Every public string exists in every served language (EN only, Decision 082); every launch country is served at `/{country}/en/` | A-35 B5 | to build: `i18n.test.ts` all six (T-117); REVIEW D6 | WS2 | 2026-11-17 | — |
| G-39 | A decision de-dupe keeps the union of both texts | A-35 S1: e885fa0 dropped the newer Decision 060 text | REVIEW D12 | WS0 | 2026-11-17 | 2026-11-17 |
| G-40 | Note-only commits must not trigger image builds (or deploys) | 17 Nov: main's image build broke (release 2 catalogue missing) and every handoff/inbox commit re-ran it, ~20 failure emails to Menno in an evening | `paths-ignore` on the push trigger in `.github/workflows/images.yml` | WS0 | 2026-11-17 | — |
| G-41 | One owner per task id. The coordinator writes the owning chat (link) in the task file's Status before it hands out a prompt. Before starting a task and again before its first push, a chat checks open PRs and `git ls-remote --heads origin \| grep <task-id>` and stops if another chat has it | WS2 6th + WS3 4th retros (18 Nov): T-130 and T-136 were built twice by parallel chats | *prose* (docs/process §3, lane briefs); candidate: CI warns when two open PRs name the same task id | WS0 / all | 2026-11-18 | 2026-11-18 |
| G-42 | Merge chats claim before merging: comment "Merging (<chat link>)" on the PR before touching it; skip a PR that already has such a comment from another chat in the last 2 hours | Merge batch 2 retro (18 Nov): two merge chats raced on #124/#125 | *prose* (merge-chat prompts) | WS0 / merge chats | 2026-11-18 | 2026-11-18 |
| G-43 | A matching or merge-logic change (`pipeline/ev_pipeline/match/**`, `pipeline/ev_pipeline/merge/**`, attachment rules) quotes a same-data rebuild diff in the PR body: old vs new code on freshly fetched staging, listing changed ids, changed rows and ± facts (recipe: PR #135) | WS1 8th retro (18 Nov): CI fixtures can't show a matching change's effect on real data; recipe in #135 | REVIEW D4 | WS1 | 2026-11-18 | — |
| G-44 | Every 360 px check also runs once with letters ~6 % wider (CI fonts are wider than local ones) | WS2 5th retro (18 Nov): a "nit" layout fix passed locally and broke CI at 360 px (db62961) | REVIEW D8; `catalogue.spec` "wider text" test (lands with #126) | WS2 | 2026-11-18 | — |
| G-45 | WS3 lane: run `sh data/seed/data_qa.sh` (runs CI's data-qa seed steps; merged with #130) before every push | WS3 retro: data-qa failures found only in CI | *prose* (WS3 lane brief); CI data-qa job stays the independent check | WS3 | 2026-11-18 | — |
| G-46 | Local e2e / verify refuse to reuse a running server whose build differs from `.next/BUILD_ID` (kill it or start a fresh one) | Web batch retro (18 Nov): a stale `next start` on port 3100 made one e2e run test an old build | the web verify and e2e scripts (WS2 adds the check in its next batch) | WS2 | 2026-11-18 | — |
| G-47 | An open PR keeps its passing fresh review when main moved only by log files (`workstreams/WS0/INBOX.md`, `workstreams/WS0/HANDOFF.md`, `CHATS.md`) and the PR's own files are byte-identical to the reviewed head (`git diff <reviewed-sha> HEAD -- <PR files>` is empty); CI on the new head (R0) still has to pass | Merge batch 4 retro (18 Nov): main moved 3× under #129 by inbox lines, each move cost a re-review | REVIEW R0 note; merge chats check with that `git diff` | all | 2026-11-18 | — |
| G-48 | `ev verify` flags a seed variant whose built drivetrain differs from its seed, or whose built WLTP is >10 % off its own cited WLTP | Variant queue retro (18 Nov): a reviewer caught Kia EV3 built as AWD / 583 km twice by hand | `ev verify` (T-153) | WS1 | 2026-11-19 | — |
| G-49 | `ev verify` refuses to run while `ev refresh` holds the staging directory | Catalogue retro (18 Nov): verified on a half-written staging while a refresh ran | `ev verify` lock check (T-153) | WS1 | 2026-11-19 | — |
| G-50 | `validate_variants.py` warns when a seed `cited:` block uses a `blocked` source (those values never ship; use data/manual) | Catalogue retro (18 Nov): maker-docs `cited:` values never shipped and nothing said so | `data/seed/validate_variants.py` (T-153, cross-lane) | WS1 + WS3 | 2026-11-19 | — |
| G-51 | A task brief that names a data-dependent rule includes a one-line repro on the current release (expected before / after) | T-152 retro (19 Nov): the WS0 rule as briefed passed its own tests and left the bug on release 3 | *prose* (WS0 briefs) | WS0 | 2026-11-19 | — |
| G-52 | Merge only from a step that fails on its own when `compare main...branch` shows behind_by > 0, run separately before the merge command (exception: G-59) | T-151 retro (19 Nov): #178 merged while main was 5 commits ahead; the check sat in the same command as the merge | `sh scripts/merge_ready.sh <pr>` (T-158, #195) | WS0 | 2026-11-19 | — |
| G-53 | `ev verify --keep <dir>` keeps its scratch build so a builder can trace where a value came from | T-151 retro (19 Nov): needed a separate scratch build because verify deletes it | `ev verify --keep <dir>` (T-158, #195) | WS1 | 2026-11-19 | — |
| G-54 | `approved_changes` validation warns when an entry's `release` is ≤ the latest published release when its PR merges | T-151 retro (19 Nov): an approval scoped to an already-built release blocked main's next build | `ev release approvals` (in data_qa.sh) + `merge_ready.sh` at merge (T-158, #195) | WS1 | 2026-11-19 | — |
| G-55 | A licence-parser change is tested on ≥10 real cached file pages plus every refusal / deletion template name | Batch #171/T-149/T-150 retro (19 Nov): a deletion-template bug passed tests that only had `{{delete}}`; the reviewer caught it | REVIEW D2 (trigger: `pipeline/ev_pipeline/images/**`) | WS1 | 2026-11-19 | — |
| G-56 | `ev verify --base-release-from <ref>` builds the base ref on the same staging and diffs against it | T-154 retro (19 Nov): a fresh staging diffed against committed release 3 gave ~10k blocking lines | `ev verify --base-release-from <ref>` (T-158, #195) | WS1 | 2026-11-19 | — |
| G-57 | `data_qa.sh` loads `config/approved_changes.yaml` with `load_config`, so a bad `approved_by` fails there | T-154 retro (19 Nov): found only when the loader failed | `ev release approvals` in `data_qa.sh` (T-158, #195) | WS1 | 2026-11-19 | — |
| G-58 | A pause goes into HANDOFF **and** an INBOX line **and** the Status of every open task; batch chats re-read the newest INBOX lines and their task Status before opening a PR | T-156 retro (19 Nov): the pause landed mid-batch and nothing told the running chat | *prose* (WS0 + batch chats) | WS0 | 2026-11-19 | — |
| G-59 | G-52 also passes when every commit main is ahead by touches only `workstreams/WS0/INBOX.md`, `workstreams/WS0/HANDOFF.md` or `CHATS.md` and GitHub says `mergeable_state: clean` (same idea as G-47) | T-153 retro (19 Nov): main moved 6× by log lines → 5 extra merge + CI rounds | `sh scripts/merge_ready.sh <pr>` (T-158, #195) | WS0 | 2026-11-19 | — |
| G-60 | A task that adds a `source_holds` entry "remove once T-xxx merges" writes the exact follow-up change into T-xxx's file, or (if T-xxx isn't its own task) into an INBOX line for WS0 | T-153 retro (19 Nov): the Elroq hold removal alone would have shipped a wrong 150 kW | *prose* (builders, WS0 briefs) | WS0 | 2026-11-19 | — |
| G-61 | `data_qa.sh` runs the tests that pin seed state (`pytest -m seed`, marker registered in `pipeline/pyproject.toml`) | T-160 retro (19 Nov): a seed change broke `test_t153_split` / `test_t159_split`, found only in CI | `data_qa.sh` + `pyproject.toml` (T-165, #210/#211) | WS1 + WS3 | 2026-11-19 | — |
| G-62 | `ev verify` lists rows whose derived flags change only because an input is missing, naming the input | T-161 retro (19 Nov): 22 rows lost a version flag only for missing `power_kw`; the reviewer found it | `ev verify` `missing_input_flag_changes` (T-165, #211) | WS1 | 2026-11-19 | — |
| G-63 | `merge_ready.sh` treats a check run with a `conclusion` and `completed_at` as completed, and says so | T-158 retro (19 Nov): a check run stuck at `in_progress` with `conclusion: success` blocked #195 | `merge_ready.sh` (T-165, #211) | WS1 | 2026-11-19 | — |
| G-64 | Antigravity sessions read `GEMINI.md` alongside `AGENTS.md` and `docs/process/README.md`; `GEMINI.md` translates Claude-era mechanics while `AGENTS.md` and `docs/` remain canonical (Decision 089) | Migration from Claude to Antigravity (26 Nov 2026): Claude-era mechanics and project docs needed a repo-tracked adapter | *prose* (`GEMINI.md`, `AGENTS.md`, `.agents/workflows/`) | WS0 | 2026-11-26 | — |
| G-65 | An automated fixture test scans `pipeline/tests/test_*.py` for reads of committed `data/seed/*.yaml` and asserts they carry `@pytest.mark.seed`, so new seed-pinned tests cannot skip `data_qa.sh` | T-165 retro (26 Nov): initial grep missed 36 real-seed tests in `test_scoped_aliases.py` (`REAL_SEED` variable); caught by round-1 fresh reviewer | `pipeline/tests/test_seed_marker_audit.py` (T-166, #221) | WS1 | 2026-11-26 | — |
| G-66 | `ev release fetch --via-gh` fallback downloads release assets via `gh release download` and places + sha256-checks every file from `manifest.json`, so local `ev verify` works cleanly in proxy-routed VMs | T-165 + T-162 + T-163 retros (26 Nov): Antigravity VM proxy triggered `ev_pipeline.net` SSRF refusal on `github.com` release downloads in all three batches | `ev release fetch --via-gh` (T-166, #221) | WS1 | 2026-11-26 | — |
| G-67 | Before adding a bare TGK variant code to `pipeline/ev_pipeline/match/tgk_split.yaml`, group staging records by `(variant, uitvoering, wltp_range_km)` to check for sub-trim splits (e.g. `_B_` vs `_P_`) | T-163 retro (26 Nov): bare `SA3` initially mixed Raven Performance (593 km) into Raven LR (610 km); caught by round-1 fresh reviewer | *prose* (`docs/process/rules.md`; REVIEW D4 check) | WS1 | 2026-11-26 | — |
| G-68 | When citing a manufacturer-submitted filing hosted on a US government portal (e.g. `dis.epa.gov`, CARB), check the PDF's own copyright stamp before attributing `17 U.S.C. 105` public domain; EPA-compiled tables (`www.epa.gov` `tstcar`) are US Gov PD, whereas OEM application PDFs are `maker-docs` cited under Decisions 068 / 087 | T-164 retro (27 Nov): Tesla's copyrighted 2017 EPA/CARB application PDF on `dis.epa.gov` was initially labelled US Gov PD; caught by round-1 fresh reviewer | *prose* (`docs/process/rules.md`; REVIEW D2 check) | WS3 | 2026-11-27 | — |

**Old P-ids** (verification chat's seed list, 17 Nov) map here: P-07→G-04/G-05 · P-08→G-09 · P-09→G-03 · P-10→G-08 · P-11→G-15/G-16 · P-12→G-10 · P-14→G-07 · P-15→G-06 · P-20→G-17 · P-21 (CI budget)→G-33; the rest became G-21–G-31.

## Pruned
_None yet._

## Retro proposals processed (17 Nov 2026)

| From | Proposal | Verdict |
|---|---|---|
| WS1 | Dry run on latest release rows before tests for any derived score | Accepted → G-10 |
| WS1 | Back-test section in qa.json for every derived model | Accepted → G-10 |
| WS1 | WS0 merges WS1 PRs as soon as green, or WS1 batches housekeeping | Accepted with a change: green **and reviewed** (T-128) → G-18 |
| WS1 | STATUS/HANDOFF only in a session's last PR, or straight to main | Accepted: straight to main → G-16 |
| WS1 | Use `gh api` when `gh pr create` fails | Accepted → G-17 |
| WS1 (3rd) | START.md says "check open PRs and their HANDOFF first" | Accepted → G-15 (all START files) |
| WS2 | Fixed Decision block per workstream listed in DECISIONS.md | Accepted → G-05 + G-04 |
| WS2 | Never rebase a pushed branch | Accepted → G-09 |
| WS2 | Grep for conflict markers before every push | Accepted → G-03 (CI + hook) |
| WS2 | `workflow_dispatch` after a session push; trust the PR-head run | Accepted → G-08 |
| WS2 | Nightly `PARKED=1` e2e job | Accepted, to build → G-19 |

## Retro proposals processed (18 Nov 2026)

| From | Proposal | Verdict |
|---|---|---|
| Menno / WS0 (#122) | One coordinator chat, every other chat a batch; one inbox; lane START files become lane briefs | Accepted 2026-11-18 → G-15, G-16, G-23 updated |
| WS2 6th + WS3 4th, WS1 4th | Check open PRs + remote branches for the task id before starting and before the first push; coordinator names the owning chat in the task file | Accepted 2026-11-18 → G-41 |
| Merge batch 2 | Merge chats claim a PR with a comment before merging; skip recently claimed PRs | Accepted 2026-11-18 → G-42 |
| WS1 8th | Same-data rebuild diff in the PR body for any matching change | Accepted 2026-11-18 → G-43 (REVIEW D4) |
| WS2 5th | Run the 360 px check with ~6 % wider letters too | Accepted 2026-11-18 → G-44 (REVIEW D8) |
| WS3 (retro 1b) | `data/seed/data_qa.sh` before every push | Accepted 2026-11-18 → G-45 |

Added later on 18 Nov: web batch → G-46 accepted; merge batch 4 → G-47 accepted (coordinator).

## Retro proposals processed (19 Nov 2026)

| From | Proposal | Verdict |
|---|---|---|
| Batch: variant queue | `ev verify` flags seed variants whose built drivetrain or WLTP disagree with the seed / cited values | Accepted 2026-11-19 → G-48 (T-153) |
| Batch: catalogue | `ev verify` refuses to run while `ev refresh` holds staging | Accepted 2026-11-19 → G-49 (T-153) |
| Batch: catalogue | `validate_variants` warns when a `cited:` block uses a blocked source | Accepted 2026-11-19 → G-50 (T-153) |
| Batch: T-152 | Briefs for data-dependent rules carry a repro on the current release | Accepted → G-51 |
| Batch: T-151 | Merge only after a separate behind_by = 0 check | Accepted → G-52 (script in T-158) |
| Batch: T-151 | `ev verify --keep <dir>` | Accepted → G-53 (T-158) |
| Batch: T-151 | `approved_changes` warns on a release already built | Accepted → G-54 (T-158) |
| Batch: #171/T-149/T-150 | Licence parser tested on real file pages + every refusal template | Accepted → G-55 (REVIEW D2) |

## Retro proposals processed (19 Nov 2026, lines 09:15–10:54 UTC)

| From | Proposal | Verdict |
|---|---|---|
| Batch: catalogue T-154 | `ev verify --base-release-from <ref>` | Accepted → G-56 (T-158) |
| Batch: catalogue T-154 | data_qa loads approved_changes.yaml | Accepted → G-57 (T-158) |
| Batch: catalogue T-156 | Pause notice in INBOX + task Status; batch chats re-read newest INBOX lines + task Status before PRs | Accepted → G-58 |
| Batch: data T-153 | G-52 passes when ahead commits are log-only and `clean` | Accepted → G-59 |
| Batch: data T-153 | Hold "remove once T-xxx" names the exact follow-up in T-xxx | Accepted → G-60 |
| Batch: data T-155 | `ev verify --keep` scratch builds for reviewers | Exists → G-53 (T-158) |
| Batch: data T-155 | `ev verify` lists value_guard.py as a changed rule | Accepted → T-158 item (no new rule) |
| Batch: data T-155 | PR-body checker recounts "main has N" claims | Parked (cost > benefit now; reviewers recount) |

## Retro proposals processed (19 Nov 2026, lines 14:25–16:05 UTC)

| From | Proposal | Verdict |
|---|---|---|
| Batch: data T-161 | `ev verify` lists flag changes caused by a missing input | Accepted → G-62 (T-165) |
| Batch: data T-158 | merge_ready treats conclusion + completed_at as completed | Accepted → G-63 (T-165) |
| Batch: catalogue T-160 | data_qa.sh runs the seed-pinned split tests | Accepted → G-61 (T-165) |
| Batch: catalogue T-160 | Approvals measured with `ev verify` against the latest release, not only a same-staging main build | Covered: plain `ev verify` diffs against the latest published release; T-162–T-164 ask for it next to `--base-release-from` (G-56 is the code diff) |

## Retro proposals processed (26 Nov 2026)

| From | Proposal | Verdict |
|---|---|---|
| Batch: data T-159 | Brief templates say `-F body=@file` (or reject `@/` comment bodies) | Superseded on Antigravity (`gh pr comment --body-file` works natively without Claude proxy) |
| Batch: data T-159 | `merge_ready.sh` reports when main changed `config/approved_changes.yaml` | Covered by G-52: `config/approved_changes.yaml` is not in `LOG_FILES`, so `merge_ready.sh` already blocks and names it |
| Batch: T-165 | Fixture test scanning `pipeline/tests/test_*.py` for committed `data/seed/*.yaml` reads asserts `@pytest.mark.seed` | Accepted → G-65 (T-166) |
| Batch: catalogue T-162 (+ T-165, T-163) | `ev release fetch --via-gh` fallback so local `ev verify` works cleanly in proxy-routed VMs | Accepted → G-66 (T-166) |
| Batch: data T-163 | Run `test_match`, `test_tgk_attach`, `test_seed_cited` before pushing any `matcher.py` edit | Covered by G-33 (run full local gate before opening or updating a PR) |
| Batch: data T-163 | Group staging records by `(variant, uitvoering, wltp_range_km)` before adding a bare TGK variant code to `tgk_split.yaml` | Accepted → G-67 |

## Retro proposals processed (27 Nov 2026)

| From | Proposal | Verdict |
|---|---|---|
| Batch: catalogue T-164 | Check PDF copyright stamp on OEM filings hosted on US gov portals (`dis.epa.gov`, CARB) before claiming `17 U.S.C. 105` PD | Accepted → G-68 |
| Batch: T-166 | Synthetic multi-segment literal & edge-case checklist for new static-analysis / AST audit tests | Covered for G-65 in `pipeline/tests/test_seed_marker_audit.py` (#221) |
| Batch: T-166 | Note `ev release fetch --via-gh` in `workstreams/WS1/START.md` so VM batches don't rediscover the proxy workaround | Accepted (added in companion note-only PR) |

## Retro questions (every session end)
1. What slowed us down? 2. What did Menno have to do by hand? 3. Which rule would have prevented it? **4. What did a check miss, and which check would have caught it?** (answer 4 adds or sharpens a row here or a REVIEW.md item).
