# AGENTS.md — EV Finder

A free, independent finder for used (and new) electric cars: one canonical EV catalogue (Make → Model → Generation → Variant), our own real-world range and charging stats, and used prices per country. A finder, not a marketplace: we link out and never host listings.

Read this file in full at the start of every session. Then read your task file. If something here conflicts with your task file, this file wins; tell WS0 in its INBOX. On Antigravity, also read [GEMINI.md](GEMINI.md), which translates the Claude-era mechanics in this repo's docs (Decision 089).

## Project identity

- **Name:** EV Shortlist (working title since 2026-11-15, Decision 018; repo and code ids stay `ev-finder`; the final brand is still open, so never hard-code the name in code: use config)
- **Owner:** Menno (solo maintainer). Agents do most of the building.
- **Stack:** Next.js + TypeScript (`apps/web`), its own database in the shared Postgres 17 + PostGIS server, Python jobs scheduled through pg-boss (`pipeline`), JSON Schema as the single source of types (`packages/schema`). Hosted on Menno's shared AppInfra server (Hetzner Arm, next to GardenLayer and Dungeon Tracker): Caddy, CI → Arm image → SSH deploy (`infra`). See DECISIONS.md 006.
- **Source of truth for product scope:** the Master spec v2 (link in DECISIONS.md). This repo holds the engineering rules; the spec holds what to build.

## Directory structure

```
AGENTS.md            this file: shared rules for every agent
CLAUDE.md            thin wrapper for Claude hosts → points here
GEMINI.md            Antigravity adapter: translates Claude-era mechanics (Decision 089)
.agents/             Antigravity rules and workflows (/start-coordinator, /start-batch, /fresh-review, /merge-pr, /handoff)
BOARD.md             Now / Next / Blocked / Done (coordinator only)
QUESTIONS.md         only what Menno must answer; he answers inline
DECISIONS.md         numbered decisions with context and reasons
ROADMAP.md           phases, ideas, parking lot
CHANGELOG.md         what shipped, per wave
tasks/               one file per task (see tasks/TEMPLATE.md)
research/            R-xx-slug.md research notes
audits/              A-xx-slug.md audit reports
apps/web/            Next.js app (Phase 0)
pipeline/            Python data pipeline (Phase 0)
packages/schema/     JSON Schema → generated TS + Python types (Phase 0)
infra/               deploy config for the AppInfra server (Phase 0)
.github/             CI, issue templates, Dependabot
_archive/            retired files: never read unless Menno asks
```

Folders under `apps/`, `pipeline/`, `packages/` and `infra/` get their own nested `AGENTS.md` once they hold code. Lane-specific rules go there, not here.

## Roles and lanes

How chats, workstreams, ownership, review and retros work: [docs/process/README.md](docs/process/README.md). This file holds the engineering rules.

| Role | Does | Writes |
|---|---|---|
| Coordinator | Turns the spec into tasks, plans waves, keeps the board, merges, owns the schema | `BOARD.md`, `tasks/`, `DECISIONS.md`, `QUESTIONS.md`, `packages/schema` |
| Researcher | Answers one research question; no code | `research/R-xx-slug.md` |
| Builder | One task in one lane on one branch; opens a pull request | Code in its lane + handoff notes in the task file |
| Reviewer / tester | Fresh agent (no build context); runs the items in `REVIEW.md` **read from `origin/main`** that the diff triggers, against acceptance criteria, with evidence | Review notes in the task file (`## Review`: SHA + item ids + verdicts) |
| Auditor | Security, dependency, load and data-quality checks | `audits/A-xx-slug.md` + new tasks for findings |

**Lanes:** each builder owns one folder (e.g. `pipeline/sources/rdw`, `apps/web/explore`). Never edit files outside your lane. If you must, flag the one-line cross-lane change in your PR and in the coordinator's INBOX (`workstreams/WS0/INBOX.md`). Only the coordinator changes `packages/schema`.

## Task lifecycle

`todo` → builder claims it (writes name + date in Status) → `doing` → PR opened → `review` → reviewer passes → coordinator merges → `done`.

**Unsure?** Engineering judgement calls are yours: take the reversible default, write it in the task's Handoff notes (or DECISIONS for anything architectural) and carry on. **Blocked** only on something Menno must decide (money, legal or licence risk, public or irreversible steps, his accounts, scope; see docs/process/README.md §1): set `blocked`, add it to WS0's INBOX with the task id, and take the next unblocked task. Never guess facts or data.

One task = one branch = one session. Keep tasks to roughly half a day of agent work.

## Key conventions

### Branches and commits
- Branch: `t-012-short-slug` (task id first). Fixes outside a task: `fix/short-slug`.
- Commit messages: imperative, focused on why. Reference the task (`T-012`) and decisions (`per Decision 004`) when relevant.
- `main` is always deployable. Never force-push to `main`.

### Review
- Reviews follow `REVIEW.md` (Decision 062). Read it from `origin/main` (`git show origin/main:REVIEW.md`), never from the PR branch.
- One review is for one commit: record the head SHA; if the head moves, re-run R0 and the triggered items.
- Evidence, not opinion: every verdict cites a command result, screenshot or number.
- A PR that changes gate files (`config/gate-files.yaml`: CI, REVIEW.md, AGENTS.md, test config, QA thresholds) and other files at once is stopped by `gate-guard` (T-121); split the gate change into its own PR.

### Pull requests
- Small. One task per PR. Fill in the PR template.
- Start of every session: check open PRs and your task files' Status / Handoff notes before new work (one coordinator chat; every other chat is a batch chat, docs/process/README.md §3).
- Never rebase a pushed branch; merge `main` in. Grep for conflict markers before every push (`.githooks/pre-push` does it: `git config core.hooksPath .githooks`).
- After a push from a Claude session, CI may not start: trigger it with `workflow_dispatch` and trust only the run on the PR head commit.
- If `gh pr create` fails, use `gh api repos/zkMenno/EV-Shortlist/pulls -f title=… -f head=… -f base=main -f body=…`.
- `workstreams/WS0/HANDOFF.md` and INBOX lines may go straight to `main` (log files, docs only), so task PRs don't collide on them.
- CI must be green before review. A failing test means the PR doesn't reach a reviewer.
- Run the gate locally first (lint, types, tests, build for the lanes you touched) and open the PR only when it's green. CI stays the independent check; it isn't your test runner. See docs/process/ci-budget.md.
- Merges go one at a time, each PR up to date with the latest `main` (merge `main` in, re-run CI).
- **Dependabot PRs** (Decision 039): patch and minor updates merge themselves once every check is green. Majors get the `dependabot-major` label: the coordinator reviews the breaking changes, fixes workflow inputs if needed, merges and logs it. Don't send these to Menno.

### Versioning
- The website deploys continuously from `main`. No semver for the app.
- **Catalogue data is versioned.** The pipeline publishes numbered data releases that swap in atomically and can be rolled back (spec §12). The numbering scheme is set in the schema lane and logged in DECISIONS.md.
- Published open datasets carry their release number and date.

### Documentation
- README.md is for humans; keep it short and current.
- AGENTS.md (this file) is for agents; update it when conventions change and log the change in DECISIONS.md.
- Log a decision in DECISIONS.md **before** implementing anything architectural.
- Update CHANGELOG.md at the end of each wave, not per commit.
- Ideas go in ROADMAP.md, not into code.

## Data rules (non-negotiable)

1. **Every number is traceable.** Every fact stores source, retrieval date, confidence and the source's licence. No untraced values in published data.
2. **Derived, not copied.** We compute our own figures. Never republish another site's database or tables wholesale.
3. **Licences stay separate.** ODbL inputs (e.g. OpenStreetMap) never get mixed into CC BY output. The pipeline records each source's licence and required attribution.
4. **Raw data is not committed.** Raw fetches go to object storage. Only small, licence-clean sample files go into the repo for tests (`**/fixtures/`).
5. **AI proposes, rules decide.** Language models may extract or suggest; rule checks validate; anything uncertain goes to the review queue.
6. **Units:** metric internally (km, kWh, Wh/km, kW, °C, €). Convert only at display time.

## Security and privacy

- **Never commit secrets.** Use `.env` (git-ignored) locally, and server env files / GitHub secrets in deployment. Add new variables to `.env.example` with a dummy value.
- **This repo is public.** Marketplace sampling targets, rates and partner/affiliate credentials never go in it (Decision 004). Code reads them from config at runtime.
- User data lives in its own schema, never mixed with catalogue data. GDPR export and delete must keep working.
- Privacy-friendly analytics only; nothing that needs a cookie banner.

## Web access

Pre-approved by Menno (2026-11-15): read, search and fetch any public website, documentation, registry, open-data portal, API or download your task needs, without asking. Still ask first (QUESTIONS.md): logging in or creating accounts, submitting forms, paying, posting or sending anything in his name. Respect robots.txt and site terms; never scrape marketplaces (Decision 004). Tests still never call the network.

## Agent boundaries

### Do
- Read this file and your task file first.
- Stay in your lane; follow the acceptance criteria.
- Write tests for every data rule and every bug you fix.
- Write handoff notes in the task file before you finish.
- Take the reversible default when unsure, and write down which one you took.

### Don't
- Touch files outside your lane or change the schema (unless you're the coordinator).
- Add a dependency without saying why in the PR.
- Add features that aren't in your task. The scope guard is strict: only what docs/spec/launch-scope.md lists ships at launch (Decision 051); new ideas go to ROADMAP.md.
- Call external services or scrape sites in tests. Use fixtures.
- Delete or rewrite DECISIONS.md entries. Supersede them with a new one.
- Read, search or cite `_archive/` (unless Menno asks), or delete docs: retire them with `git mv` into `_archive/`.

## Stack conventions

**TypeScript / Next.js (`apps/web`)**
- Strict TypeScript; no `any` without a comment explaining why.
- ESM, named exports. Server components by default; client components only where interaction needs them.
- Tests: Vitest for units, Playwright for key flows (Explore, compare tray).
- Format and lint with the repo config (added with the app). CI runs lint, type check, tests and build.

**Python (`pipeline`)**
- Python 3.12+, type hints everywhere, `ruff` for lint and format, `pytest` for tests.
- Jobs are small, idempotent Python steps queued and scheduled through pg-boss. Each step records its inputs and outputs in the run log, and every Fact carries its own source and date: that is our provenance, so never write a value without it.
- **Respect the shared server.** Jobs run at night at low priority inside their memory limit (Decision 006). Big one-off imports go to a temporary machine, not the shared server.
- Source adapters live in `pipeline/ev_pipeline/sources/<name>/`, with fixtures in `pipeline/tests/fixtures/<name>/` (see pipeline/AGENTS.md).

**Schema (`packages/schema`)**
- JSON Schema is the single source. TypeScript and Python types are generated from it, never hand-written.
- Stable IDs never change; slugs may.

## Design principles

1. **Models first, listings second.** The canonical vehicle database is the core asset.
2. **Instant before clever.** The Explore table loads fast and works without sign-up.
3. **State never gets lost.** Filters and comparisons live in the URL; accounts make them permanent.
4. **Boring tech, sharp product.** One person with AI agents must be able to understand, run and fix all of it.
5. **Progressive disclosure.** Add files, tools and structure only when they're needed.
6. **Rules live at the narrowest scope.** Lane rules go in that folder's `AGENTS.md`.

## References

- [docs/process/README.md](docs/process/README.md): how we work (workstreams, ownership, verify + learn)
- [DECISIONS.md](DECISIONS.md): decisions and the link to the spec
- [docs/spec/product-decisions.md](docs/spec/product-decisions.md): product decisions in one list
- [ROADMAP.md](ROADMAP.md): phases and the Phase 0 checklist
- [BOARD.md](BOARD.md): current work
- [tasks/TEMPLATE.md](tasks/TEMPLATE.md): task file format

<!-- Agentic Scaffold v0.8.0 | https://github.com/montymerlin/agentic-scaffold-plugin -->
