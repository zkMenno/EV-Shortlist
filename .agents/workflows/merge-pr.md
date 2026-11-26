---
description: Merge an EV Shortlist PR safely after a fresh PASS
---

1. Confirm the task file's `## Review` says PASS for the current head SHA (see REVIEW.md G-47 exception for log-only main changes).
2. If behind main: `git merge origin/main` into the branch (never rebase a pushed branch), grep for conflict markers, push, wait for CI on the new head.
3. Run `sh scripts/merge_ready.sh <PR>` as its own step, right before merging. Merge only if it prints READY.
4. Merge, then set the task status to `done`, delete the merged branch, append one line to `workstreams/WS0/INBOX.md`.
