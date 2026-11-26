---
description: Start a throwaway batch conversation for one or more EV Shortlist tasks
---

1. `git checkout main && git pull`.
2. Read `GEMINI.md`, `AGENTS.md`, `docs/process/README.md`, and `workstreams/<lane>/START.md` for every lane the brief touches. UI work: also `docs/design/brand-design-decisions.md` and `docs/design/SOURCE.md`.
3. Add a `batch: <what>` row to `CHATS.md` in your first commit.
4. For each task in the brief: read `tasks/T-xxx-*.md`, check open PRs for it, claim it (name + date, status `doing`).
5. One task = one branch = one PR. Plan first, work in chunks. Every ~30 min: commit, push, update the task file's Status / Handoff notes.
6. Every commit message ends with `Verified: <how>`. Put evidence in the PR body.
7. Loop guard: same error 3× or 30 min without progress → stop that path, log it, try one alternative, else park it (task file + one INBOX line) and take the next task.
8. Before merge: get a fresh review via `/fresh-review <PR>` in a new agent. If the brief allows merging, run `/merge-pr <PR>`.
9. When done, blocked, or context is getting heavy: write state into the task files, append one line to `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from batch:<what> · message`), stop.
