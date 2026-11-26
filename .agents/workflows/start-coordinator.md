---
description: Start or resume the WS0 coordinator conversation for EV Shortlist
---

1. `git checkout main && git pull`.
2. Read `GEMINI.md`, `AGENTS.md`, `docs/process/README.md`, then `workstreams/WS0/HANDOFF.md` and `workstreams/WS0/INBOX.md` (items without `→ done`).
3. Check open PRs (`gh pr list --repo zkMenno/EV-Shortlist`) — newest state may not be on main yet.
4. Add or update the coordinator row in `CHATS.md` (`Antigravity: WS0 coordinator <date>`), mark the previous coordinator row as history.
5. Process the INBOX: decide, log in DECISIONS.md (next free number is in HANDOFF), append `→ done` to handled lines.
6. Refresh BOARD.md "Now" if stale.
7. Write briefs for the next batches. For each: give Menno a code block he pastes into a new conversation, starting with `/start-batch` and listing task ids, lanes, done criteria and whether the batch may merge.
8. Reply to Menno in one screen: what he must do, then one next step.
