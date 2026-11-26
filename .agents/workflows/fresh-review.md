---
description: Independent review of an EV Shortlist PR by an agent that did not build it
---

Run this in a **new** agent or conversation that has not seen the work.

1. `gh pr view <PR> --repo zkMenno/EV-Shortlist` and `gh pr diff <PR>`.
2. Read `REVIEW.md` and apply every check that fits (R0: CI green on the PR head commit only).
3. Verify the PR's claims yourself: run the tests / scripts it cites, open the files, check data against cited sources. Never trust "Verified:" lines without re-running.
4. Write the result into the task file's `## Review` section only (PASS / CHANGES with reasons, the commit SHA reviewed), and as a PR comment.
5. Any miss the builder should have caught → propose a rule in `workstreams/WS0/INBOX.md` (docs/process/rules.md is WS0's).
