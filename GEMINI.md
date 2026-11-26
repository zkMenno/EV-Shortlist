# GEMINI.md — EV Shortlist (Antigravity adapter)

Read `AGENTS.md` in full first. It is the canonical engineering rule set. Then `docs/process/README.md` (how we work). This file only translates the Claude-era mechanics in those docs to Antigravity. Where they conflict on *mechanics*, this file wins; on *rules and product*, AGENTS.md and docs/ win.

Project: a used-EV finder, a better EV Database. Owner: Menno, not a developer. He wants autonomy, few questions, plain language. Repo: github.com/zkMenno/EV-Shortlist.

## Translation table: Claude-era → Antigravity

| Docs say | In Antigravity, do |
|---|---|
| "Attach the repo with push access (`add_repo …`)" | Work in the local clone opened as the workspace. `git pull` main first. Push with Menno's normal GitHub auth (`gh` / git credentials). |
| "chat" / "session" | An Antigravity conversation (or an agent in Agent Manager). |
| Coordinator chat (WS0) | One named conversation, title starting `WS0 coordinator`. Start it with `/start-coordinator`. |
| Throwaway batch chat | A fresh conversation per batch. Start it with `/start-batch`. |
| Row in `CHATS.md` with a `claude.ai/code/session_…` link | Add a row with link `Antigravity: <conversation title>` and the date. Old claude.ai links are history. |
| "Popup, max 4, recommended option first" | Ask in the conversation: numbered options, max 4, recommended first, one plain sentence of why. Or a short entry in `QUESTIONS.md` if Menno is away. |
| "Fresh subagent review before merge" | A reviewer that has **not** seen the build: a new Antigravity agent/conversation running `/fresh-review <PR>`. Never self-review. |
| "After a push from a Claude session, start CI with `workflow_dispatch`" | Claude-proxy quirk. Normal pushes trigger CI. Only use `workflow_dispatch` if the PR head has no run. Rule R0 still holds: trust only the CI run on the PR head commit. |
| "Proxy blocks GraphQL / branch deletion" | No longer applies. You may delete merged branches yourself. |
| Project doc `claude/brand-design-decisions.md` | `docs/design/brand-design-decisions.md` in the repo (added at migration). |
| claude.ai artifact links (design system, board, architecture) | Not reachable. Use `docs/design/` (tokens.json, components, assets) — it is the source of truth for code. |
| "Before a chat gets long … successor prompt" | Same idea: before context gets heavy, run `/handoff`. |
| Claude skills (unslop etc.) | Not available. For anything in Menno's name: plain, human writing, no filler; he approves before it is sent. |

## Always
- Decide, do, log (DECISIONS.md). Ask Menno only for: money over €50/month or €200 one-off; legal or licence risk; public or irreversible steps; anything sent in his name; scope.
- Reading public websites is pre-approved. Logins, forms, payments and posting need him. **Never scrape marketplaces.**
- Done = proven: evidence in the PR, `Verified: <how>` on every commit, fresh review before merge, `sh scripts/merge_ready.sh <pr>` says READY right before merging. Every miss becomes a check (docs/process/rules.md).
- Only tasks in **Launch** on BOARD.md get built (Decision 051). New ideas go to ROADMAP.md.
- Never read `_archive/` unless Menno asks. Retire files there with `git mv`, never delete.
- Never invent data. Flag licences and uncertainty.
- Antigravity "Review" / auto-run settings: terminal and browser actions for code, tests and public reading may run; anything touching accounts, payments, posting, DNS, AppInfra production or deleting data waits for Menno.

## Talking to Menno
See `.agents/rules/talking-to-menno.md`.
