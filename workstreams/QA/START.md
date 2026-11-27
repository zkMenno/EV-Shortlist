# QA lane brief: fresh-eyes review

For any batch chat whose prompt is a review or audit. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3 and §8; rules: [rules.md](../../docs/process/rules.md). QA checks the build as a buyer and a reviewer would, fixes small things and lists the rest. A QA chat has no build context for what it reviews.

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`. Branch `qa/<slug>` from `main`.
2. Read `AGENTS.md`, `REVIEW.md` **from `origin/main`** (`git show origin/main:REVIEW.md`), `docs/process/README.md`, `docs/spec/launch-scope.md` (the only scope that counts), your task files or audit brief, `docs/design/README.md`.
3. Fetch the release before pipeline tests or walks: `cd pipeline && uv run ev release fetch latest` (or `--via-gh` in proxy-routed Antigravity VMs, G-66; the web build fetches only a few files). Run the web app locally on the current release (`apps/web/README.md`).

## What the lane owns
`audits/A-35…` (numbers from WS0), `## Review` sections in task files, `workstreams/QA/tools/`. Small fixes elsewhere ride in the QA PR, each flagged to the owning lane in one `workstreams/WS0/INBOX.md` line.

## How to review
- Review one commit: record the head SHA; if the head moves, re-run R0 and the triggered items (G-07).
- Run the REVIEW.md items the diff triggers, with evidence per item (command result, screenshot, number); rate must-fix / should-fix / nit / pre-existing. Up to 3 fix rounds, then escalate to WS0.
- Launch walks: hero for each profile × country × budget (does each pick fit the profile, not only the budget and rank?), catalogue (filters + URL state, model / generation / variant pages, compare "differences only", Simple / Detailed / Nerd, tooltips, light + dark), data spot-check (random numbers have source, date, licence; estimates labelled; one source id = one citation), scope check (parked features behind flags, off), axe + WCAG AA.
- Screenshots 360 + 1280 px (also once with ~6 % wider letters, G-44), small PNGs only, under `audits/A-xx-screens/`.

## Gotchas
- Walk tools from earlier reviews: `workstreams/QA/tools/hero-walk.mjs`, `catalogue-walk.mjs`.
- Don't run the hero walk and the e2e suite at the same time (axe tests time out). Screenshot the results, not the page top.
- Every miss you find becomes a proposed check (rules.md row or REVIEW item) in your INBOX line.

## Done
PR open with fixes, CI green on the head · audit report with blocker / should-fix / nice-to-have, page, steps, screenshot, owning lane · `## Review` written in each task file you checked (SHA + item ids + verdicts).

## Finish the batch
State lives in the audit, task files and PRs. When done: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · QA … done, PR #x, A-xx: n blockers`, with the four retro answers), then stop. No STATUS or HANDOFF files.
