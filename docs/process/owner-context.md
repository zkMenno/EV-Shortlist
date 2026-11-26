# Menno and the project — context that lived outside the repo

Collected from Claude's project memory on 26 Nov 2026. Facts Menno stated; nothing inferred.

## The product (Menno's own goals)
- A better ev-database.org: better UX, a few more features, focus on **used EVs** (ex-lease etc.), cars grouped by generation, second-hand prices across countries.
- Own real-world range stats (owner data / averages, Bjørn Nyland tests as fallback), cross-checked against EV Database. Own multi-source database that adds new cars automatically.
- Finder only: links out, no hosted listings. Simple and clean, no scope creep.
- Markets: Europe, UK, US, Australia first; emerging markets second; China parked.
- Prices both as buy-outright and as monthly lease/loan. He personally buys used, outright.
- Launch scope (strict): EV Database but better UX + more countries. Hero = 3 steps (country → one of 4 profiles → budget + optional filters) → top 10 models/variants/build years, top 5 highlighted, plus browsing the full catalogue. Open data download, tooltips, a few explainer pages. Everything else after launch.
- Catalogue: aim for EV Database's ~1,500 entries; soft launch with fewer is OK if all base models and facelifts are covered. Van-based people carriers in, cargo vans out.
- Data sourcing: maker spec sheets OK as fallback; a paid EV Database licence is last resort only.
- Later: accounts with saved shortlists/comparisons and Top 10 rankings.
- Working title "EV Shortlist" (backup "EV Field Guide"); name and domain still open.
- Solo build with AI coding agents; lean, bootstrapped, mission/community values.
- Repo public (free GitHub Actions minutes). Hosting on his ARM Hetzner server "AppInfra".
- Repo renamed zkMenno/EV-Finder → **zkMenno/EV-Shortlist** (Nov 2026). Some docs still say "EV Finder".
- Building paused 19 Nov 2026 (token budget); now moving to Antigravity.
- His own car search ("New Car" Google Sheet, NL + FR used market, quick charging for road trips) feeds the shortlist rules.

## How Menno wants agents to work
- As autonomous as possible: reason, pick the recommended option, do it. Ask only for very impactful decisions.
- Prefer extra work now to be future-ready (growth, edge cases, stress tests); be efficient with tokens, time and decisions.
- Watch conversation length; hand off before the context fills up.
- Agents talk through MD files in the repo; Menno never relays messages.
- One named coordinator conversation; every other conversation is a throwaway batch (up to ~6–7 h, merges included).
- On long tasks, check progress about every 30 min to avoid loops.
- Keep project instructions in a living MD file he can copy into settings.
- Always link or attach files; when pointing to another conversation, give the exact paste text in a code block, every time, unasked.
- Public websites: pre-approved. Logins, forms, payments, posting in his name: ask him.
- Design: backgrounds (tiles, chips, buttons, icon squares) never touch or crowd text; generous padding. WCAG AA contrast.

## Communication style (all his work)
- Concise, scannable, warm, direct — a senior collaborator. No "great question", no hype.
- Honest: say what you know and don't; never fill gaps with plausible filler. 🟢 verified · 🟡 reasoned · 🔴 unsure.
- Metric and Celsius, always. European formats.
- Give an opinion with reasoning when asked, not a menu. Underspecified? State the assumption in one line and go.
- Anything published or sent in his name: plain, human writing, no AI-sounding filler; he approves before it goes out.
