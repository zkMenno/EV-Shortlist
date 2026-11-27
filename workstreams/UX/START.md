# UX lane brief: brand and design

For any batch chat whose prompt touches this lane. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3; rules: [rules.md](../../docs/process/rules.md). Brand decisions live in `docs/design/brand-design-decisions.md`; the repo design system in `docs/design/` (start at [SOURCE.md](../../docs/design/SOURCE.md)) is the source of truth in Antigravity (Decision 089; historical Claude artifacts are not reachable).

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`.
2. Read `AGENTS.md`, `REVIEW.md` (from `origin/main`), `docs/process/README.md`, your task files, this brief, `docs/design/brand-design-decisions.md`.
3. Before each task: check open PRs and `git ls-remote --heads origin | grep <task-id>`; stop if another chat has it (G-41).

## What the lane owns
`docs/design/` and `workstreams/UX/tools/`. Builds happen in WS2 (`apps/web/`): hand a signed-off design over with one line in `workstreams/WS0/INBOX.md`; WS2's batch asks for a design check on staging the same way.

## Lane rules
- Go slower on brand work: explore → show → let Menno pick → refine. Don't push to the design system before he approves a direction. Send rendered PNGs of options; ask with popups (max 4).
- Breathing room: backgrounds never touch or crowd text. WCAG 2.2 AA contrast (`workstreams/UX/tools/contrast.py`), light "Day trip" and dark "Night drive" themes, colour-blind safe.
- Fonts: Bitter headings + logo, Atkinson Hyperlegible body and numbers, Patrick Hand notes; self-hosted OFL.
- Charging: no charger map of our own, no point-level charger data (Decisions 012, 013).
- Artifacts: always `list_files` / read before republishing the design system or board.

## Verify before every push
- Contrast check on changed tokens; preview renders (`tools/harness.py`, Chrome headless) at 360 and 1280 px, light + dark.
- Commits end with `Verified: <how>`.

## Gotchas
- `tools/` generators (board.py, logo, icons, textures, scenes) expect fonts from npm `@fontsource/*` and paths under /home/claude: adapt paths per session.
- Illustration layers: order and depth per scene in `docs/design/assets/Illustrations/layers/manifest.json`; WS2 re-copies scenes after every change, so say which files changed.

## Done (per task)
Design signed off by Menno (or the reversible default noted) · `docs/design/` updated · PR with renders · Status + Handoff notes in the task file · WS2 told via one WS0 INBOX line.

## Finish the batch
State lives in task files and PRs, not here. When the batch is done or blocked: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · …`, with the four retro answers), then stop. No STATUS or HANDOFF files.

## Open lane threads (current queue lives in BOARD.md and workstreams/WS0/HANDOFF.md)
- T-147: accept/adjust WS2's `--line-strong` values (#158), widen `contrast.py` UI pairs to all 4 grounds, update `docs/design/README.md` contrast line, add `OFL.txt` to `docs/design/fonts/`.
- Design check on staging after T-157 + T-146; variant finder differences-only highlight; EV-media logo audit; logo round 2 after the name is final.
