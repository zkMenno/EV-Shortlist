# Decisions — EV Finder

Engineering decisions for this repo, in a light ADR (Architectural Decision Record) format. Each entry has a number, status, date, context, decision and consequences. Never edit an accepted decision; supersede it with a new one.

**Product decisions** (scope, markets, business) live in the project decisions log and the Master spec v2: https://claude.ai/artifact/3HiNR86a22Fnm2kHxpfctx. This file records the ones that shape the code.

**Statuses:** Proposed · Accepted · Superseded by NNN

**Number blocks** (rule G-05; take the next free number in your own block, fetch `main` first):

| Block | Owner |
|---|---|
| 001–039, 050–051, 062–069, 080–089 | WS0 coordinator |
| 040–049 | WS1 pipeline |
| 052–056 | WS2 web (052–054 went to the Dependabot fix chat) |
| 057–061 | WS3 curation |
| 070–079 | WS4 infra, WS5 growth, UX (ask WS0 for a sub-range) |
| 090–099 | spare; ask WS0 |


---

## Decision 001: Adopted agentic scaffold and the agent workflow

**Status:** Accepted
**Date:** 2026-11-15

**Context:** The project is built by one person with many AI agents. Chats and sessions forget; files don't. Agents need shared rules, clear lanes and a place to hand off work.

**Decision:** Use the Agentic Scaffold pattern (AGENTS.md as canon, CLAUDE.md as wrapper, DECISIONS, CHANGELOG, ROADMAP) plus the workflow from the spec's Workflow tab: `BOARD.md`, `QUESTIONS.md`, `tasks/`, `research/`, `audits/`, five roles, one lane per builder.

**Consequences:**
- Agents have clear instructions from session one.
- Menno touches three things: `QUESTIONS.md`, the daily digest and phase gates.
- A few extra files, each with one job.

**Alternatives considered:** README only (not enough for agents); a project-management tool outside the repo (agents can't read it reliably).

---

## Decision 002: Public repo; AGPL-3.0 for code, CC BY 4.0 for published data

**Status:** Accepted
**Date:** 2026-11-15

**Context:** A public repo gets GitHub Actions minutes free on standard runners, plus free secret scanning. The project is mission-driven and open-source-first, but a closed clone of the hosted site would undercut it.

**Decision:**
- Repo is public.
- Code is licensed under **GNU AGPL-3.0** (`LICENSE`): anyone running a modified version as a network service must publish their changes.
- Data we publish openly is licensed under **CC BY 4.0** (`DATA_LICENSE.md`). Third-party inputs keep their own licences; ODbL inputs are never mixed into CC BY sets.
- Outside contributions require agreeing to the relicensing clause in `CONTRIBUTING.md`, so the maintainer can still change the licence later.

**Consequences:**
- Free CI and security tooling.
- Competitors can read the code, but can't run a closed fork as a service.
- Strategy-sensitive config must stay out of the repo (see 004).

**Alternatives considered:** MIT (allows closed SaaS clones); FSL/BSL source-available (not OSI open source, less community goodwill); no licence (blocks contributions).

---

## Decision 003: Lean monolith + separate data pipeline, one EU server

**Status:** Superseded by 006 (hosting and pipeline tooling); the monolith shape still holds
**Date:** 2026-11-15 (product decision 2026-11-14)

**Context:** A solo builder with AI agents must be able to understand, run and fix everything.

**Decision:** One monorepo with `apps/web` (Next.js + TypeScript), `pipeline/` (Python + Dagster, DuckDB + Parquet), `packages/schema` (JSON Schema → generated TS and Python types) and `infra/`. One Postgres database. pg-boss for jobs (no Redis). Better Auth for passkeys and magic links. Hosted on Hetzner via Coolify, Bunny CDN, S3-compatible object storage for raw fetches. Self-hosted Umami, GlitchTip and Uptime Kuma.

**Consequences:**
- The pipeline writes catalogue releases; the web app only reads them (and writes user data).
- Scale steps happen only on triggers (spec §13): Meilisearch above ~100k listings, a read replica above ~60% DB CPU, the pipeline on its own server if runs collide with traffic.

---

## Decision 004: Keep sampling targets and partner secrets out of the public repo

**Status:** Accepted
**Date:** 2026-11-15

**Context:** Automated used-price sampling (layer 3) carries ToS and EU database-right risk and needs a legal check before going live. Publishing exactly which sites we sample, and how often, adds risk and gives away strategy. Affiliate and partner credentials are secrets.

**Decision:** The code for sampling is generic and public. Target sites, URL templates for sampling, rates, kill-switch state and all partner/affiliate credentials live in runtime config (Coolify environment, or a private config repo), never in this repo. "See listings" deep-link templates (public, user-facing links) may live in the country config.

**Consequences:** `.env.example` documents variable names only. Reviewers reject PRs that hard-code targets or keys. GitHub secret scanning and push protection are on.

---

## Decision 005: Build images in GitHub Actions, not on the server

**Status:** Accepted (deploy details in 006)
**Date:** 2026-11-15

**Context:** The app will share an existing Hetzner Arm server. Building Next.js on the server peaks at 2–4 GB RAM and can starve other services. Public repos get free Actions minutes, including arm64 runners.

**Decision:** CI builds arm64 Docker images for `apps/web` and `pipeline`, pushes them to GitHub Container Registry, and the server pulls and runs them (SSH deploy, see 006).

**Consequences:** Likely no server upgrade at launch (to be confirmed once current free RAM is known). Adds a deploy workflow in Phase 0 (`infra` lane).


---

## Decision 006: Host on the shared AppInfra server; drop Coolify, Dagster and Brevo

**Status:** Accepted (limits to confirm with the capacity check, Q-001)
**Date:** 2026-11-15
**Source:** advice from AppInfra, agreed in the project chat; spec §13 updated to match.

**Context:** Menno already runs a Hetzner CAX31 (Arm, 8 cores, 16 GB) with Caddy, an image-based deploy, backups, a watchdog, Umami and staging for GardenLayer and Dungeon Tracker. Reusing that is cheaper and simpler than a new Coolify setup. Dagster's always-on services cost about 1–1.5 GB, too much on a shared server.

**Decision:**
- **Server:** the shared AppInfra server. Reuse Caddy, CI → Arm image → SSH deploy, backups, the `/health` watchdog, Umami, Scaleway email, the Sveltia editor and the staging setup. No Coolify.
- **Database:** EV Finder gets its own database, login and private network inside the shared Postgres 17 + PostGIS. No separate Postgres container. Connection pool: about 10 live, 3 staging, 3 jobs, out of the server's 100.
- **Pipeline:** Python jobs queued and scheduled through pg-boss. No Dagster. Raw snapshots go to Scaleway Object Storage.
- **Limits:** `ev-web` 768 MB / 1 CPU; `ev-web-staging` 256 MB / 0.5 CPU; `ev-jobs` 1 GB / 1 CPU at low priority, nightly only (🟡 00:30–02:30 UTC, to confirm).
- **Fit:** about 13.8 GB of 16 GB in limits by day, about 14.8 GB in the job window. Works while the paused Cahier app stays off.
- **When to grow:** upgrade, or move GardenLayer to its own server, once busy evenings show more than 70% RAM or CPU for weeks.
- "Coolify environment" in Decision 004 now means the server's env files.

**Consequences:**
- Provenance no longer comes from Dagster lineage. Every Fact stores source and date itself, and each job writes a run log (AGENTS.md, Python conventions).
- The shared Postgres has no CPU limit, so heavy imports run at night at low priority. Big one-off imports run on a temporary machine.
- 🔴 Off-site backups on the server may not be running. Fix that (AppInfra #482) before launch; it affects the other apps too.

---

## Decision 007: pnpm for the web app, uv for the pipeline

**Status:** Proposed (provisional, pending Q-002)
**Date:** 2026-11-15

**Context:** The overnight prototype needed a package manager before Q-002 was answered.

**Decision:** pnpm workspace at the root (`apps/*`, `packages/*`); uv for `pipeline/` (Python 3.12+). CI keeps a pip fallback so the existing auto-detect job still works.

**Consequences:** Easy to swap back to npm/pip if Q-002 says so: only lockfiles and CI install lines change.

---

## Decision 008: Prototype reads a published catalogue JSON, not Postgres

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** No database tonight. The web app still needs a stable read path that Postgres can replace later.

**Decision:** The pipeline writes `data/releases/<n>/catalogue.json` (one wide `PublishedVariant` row per variant) plus Parquet. The web app reads it through one `Catalogue` interface in `apps/web/src/lib/catalogue.ts`; a Postgres/Drizzle implementation can sit behind the same interface. Release numbers are integers counting up from 1 (`data/releases/1/`), with `data/releases/latest` naming the current one.

**Consequences:** Releases are plain files, so rollback means pointing `latest` back. Small releases live in git for now; move them to object storage once they grow.

---

## Decision 009: Source registry, per-field source rules, conflicts, coverage and charge curves

**Status:** Proposed (provisional, from the latest spec decisions, 2026-11-15 00:45)
**Date:** 2026-11-15

**Context:** Merging needs explicit rules per field, and we must be able to prove which sources may reach a public release.

**Decision:**
- `data/sources.yaml` lists every source: id, owner, licence, access (api | bulk | manual), cadence, terms note, status (active | waiting_permission | blocked). Only `active` sources with a named licence or written permission reach a public release.
- `data/field_sources.yaml` says, per field, which 1–2 primary sources to use, the fallbacks in order, the tolerance and the merge rule (priority | median | newest).
- Values that agree within tolerance raise confidence and count towards "N sources agree" (`FieldProvenance.agreeing_sources`). Conflicts outside tolerance go to `data/review/conflicts.csv` and are never averaged.
- Each release writes `coverage.md`: per field, the share of variants with ≥2 agreeing sources, 1 source, estimate only, or missing.
- DC charge curves are a Fact whose value is a `ChargeCurve`: (state of charge %, kW) points, conditions (battery temp, preconditioned, ambient temp, charger kW, software version) and a status of measured, estimated or default. From it we derive the average kW and minutes from 10 to 80%, km added in 10 and 20 minutes at motorway consumption, minutes above 90% of peak, and claim vs measured.
- The DC ranking uses km added in 20 minutes, not peak kW.
- Provisional estimates: motorway consumption = WLTP × 1.30; a generic default curve shape when no curve exists. Both are labelled "estimate".

**Consequences:** Most fields tonight have one source or an estimate, and coverage.md shows that honestly. Maker documents stay `blocked` until Q-008 is answered.

---

## Decision 010: Platforms, battery packs, taxonomy tables and display levels

**Status:** Proposed (provisional, addendum 3, 2026-11-15 00:48)
**Date:** 2026-11-15

**Context:** Voltage, chemistry and cooling matter to used buyers (fast charging on older chargers, daily charging to 100%) but are poorly explained elsewhere. Many variants share one pack, so pack facts should live in one place.

**Decision:**
- New entities `Platform` and `BatteryPack`. A Variant points to one of each. Pack facts (supplier, chemistry, cathode detail, cell format, cell-to-pack, gross/usable kWh, nominal and max V, cooling, warranty) are inherited by its variants unless the variant has its own measured fact.
- Taxonomies are data files in `data/taxonomy/`, not enums: `voltage_classes` (400 V ~300–550, 800 V ~550–850, 900 V+ ~850–1,100), `chemistries` (NMC, NCA, LFP, LMFP, LMO/NMC blend, sodium-ion, semi-solid, all-solid-state, LMR), `cooling_types` (liquid, refrigerant, air, passive) and `glossary_terms`, all with per-language strings. Filters, tooltips and learn pages read them, so adding a row needs no code change. The schema ids are free strings validated against these files at release time.
- Per variant: stated nominal/max voltage, marketing label, derived class, switchable flag and "400 V charger behaviour" (native | booster kW | limited kW). `not-disclosed` is a valid value everywhere.
- The UI has a Simple / Detailed / Nerd switch (localStorage + URL). Nerd shows raw values, sources with date and confidence, and the fallback rung. Every glossary term gets an ⓘ tooltip; labels are plain language with the technical name underneath; `/learn/[term]` pages are stubs tonight.

**Consequences:** The catalogue JSON ships the taxonomy tables, which adds a few KB. Most pack facts tonight come from hand-entered seed data (confidence low) or are `not-disclosed`.

---

## Decision 011: Bidirectional charging and plug standards as country-aware, conditional facts

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** Menno asked for filters on which cars support V2G/V2H, which work with the EU 2027 protocol, and with which caveats; plus CCS/NACS filters for the US. Research R-01: from 1 Jan 2027 AFIR (Delegated Regulation (EU) 2025/656) requires ISO 15118-20 on every new or renovated EU charging point, private ones included, but that is a protocol duty, not a bidirectional-hardware duty. Whether a car can actually do V2H/V2G depends on software version, battery size, build date, wallbox route (AC vs expensive DC box), energy contract and country. US ports switch from CCS1 to NACS by model year.

**Decision:**
- New taxonomies: `bidi_modes`, `bidi_routes`, `bidi_protocols`, `bidi_caveats`, `bidi_status`, `connector_types`, `bidi_equipment` (data rows, per-language strings).
- New entities `BidiCapability` (per variant or platform, with per-country status and conditions) and `ChargingPort` (per variant, market and model year). New variant Fact `iso15118_20_support` (default `not_disclosed`, never inferred).
- Filters default to "live in your selected country". Conditional eligibility is shown as conditions, never as a plain tick. Caveats come from the taxonomy, never free text.
- Copy rule: never say new 2027 chargers "are bidirectional"; say they "speak the standard that allows it".
- Bidi facts expire: older than 90 days shows "may be out of date".
- Phasing in docs/spec/bidirectional-and-connectors.md §4 (schema + EU ports + learn section Core 1; bidi filters Core 2; US ports/NACS Next).

**Consequences:** More rows per variant and a monthly re-check job for bidi facts. Most cars will show "not offered" or "not disclosed" for ISO 15118-20 at first, which is honest.

## Decision 012: Charging infrastructure as aggregate statistics with one definition per series

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** Spec tab "Charging buildout" (docs/spec/charging-buildout.md): buyers still picture the 2019 network. Countries count charging points, devices, locations and connectors differently (Belgium: ~22k fully public vs ~126k public + semi-public). Open Charge Map's per-location CC BY-SA licences clash with our CC BY 4.0 output.

**Decision:**
- Aggregates only (counts, power, per-capita), never point-level charger data, and no charger map of our own.
- New table `charging_stats` (country, region?, period_end, metric, power_band, value, unit, source_id, definition_id, confidence, entered_by) plus taxonomies `charging_metrics`, `charging_definitions`, `power_bands`, and config `country_charging_links`. Variant field `abrp_typecode` (nullable).
- A chart draws exactly one `definition_id`; a definition change starts a new series with a marked break. Cross-country comparison uses EAFO (Europe) or IEA (world) only.
- One official primary per country; PDF-only sources are entered by staff in `data/manual/charging/*.yaml` with a source URL. Monthly job inside the night window; release diff flags month-on-month changes above 15 % or any drop.
- Phasing: link-outs + /learn "Charging in 2026" = Core 1; country pages + ABRP car deep link = Core 2; EAFO comparison and "how this car fits the network" = Next.

**Consequences:** A small separate fact table and five taxonomies; definitions need curation (WS3). Some countries will show fewer metrics than others, which is honest.

## Decision 013: Trip fit routing on a separate Valhalla box; scoring in the browser

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** Spec tab "Trip fit" (docs/spec/trip-fit.md) needs routes split into road bands with climb per trip. The shared CAX31 is already ~1 GB over its worst-case budget in the job window (Decision 006). Free hosted routing plans (openrouteservice, GraphHopper) are non-commercial. Nominatim for Europe needs ~64 GB RAM.

**Decision:**
- Routing = self-hosted Valhalla (OpenStreetMap) on its own small Hetzner Arm box (~€5–15/month after a sizing test for NL+BE+LU+DE+FR+UK), not on the shared CAX31. Monthly tile rebuild.
- Hosted free routing APIs only for prototypes and staging.
- No Nominatim: town search from GeoNames cities (CC BY 4.0) plus a map pin.
- The server returns a route summary per trip (km per road band, climb, descent, starts); the browser multiplies it with a static per-variant consumption matrix (variants × 3 road bands × 5 temperature bands) published with each release. Re-ranking is instant and server load is one route call per trip edit.
- Privacy: addresses never reach the server; coordinates rounded to ~200 m before routing; no request logging on the route endpoint; accounts store trip names and summaries only; share links carry summaries, never places.
- Consumption model: per-road-band consumption × temperature curve per heater type + warm-up per cold start + climb; fallback ladder measured → platform → physics → WLTP ratio; P10–P90 band. Launch gate: back-test median error < 10 % on the top-40 used models.
- OSM-derived route data is ODbL: only per-trip summaries computed on the fly reach users; nothing OSM-derived enters the CC BY release.

**Consequences:** One more small server for WS4 to run and back up (tiles are rebuildable, so no backup of tiles). Quick check without routes (Core 1) can ship before the box exists.

## Decision 014: Workstreams coordinate through repo files; one owner per path

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** The first build chat lost time to two chats editing the same decisions file and to Menno relaying messages by hand.

**Decision:** Up to six long-running workstreams (WS0 coordinator, WS1 pipeline, WS2 web, WS3 curation, WS4 infra, WS5 partnerships). Each has `workstreams/<ws>/START.md`, `STATUS.md` and an append-only `INBOX.md`. Every path has one owning workstream (table in workstreams/README.md and BOARD.md); others write to the owner's INBOX. Read right before writing; small edits. The spec is mirrored into `docs/spec/` and the repo copy wins for builders. Research and audit numbers (R-NN, A-NN) are handed out by WS0 to avoid clashes.

**Consequences:** Slightly more files, far fewer overwrites and no human relay. AGENTS.md's role table still holds; workstreams are the long-running chats that fill those roles.

## Decision 015: Language and country both in the URL path

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** The SEO plan (docs/growth/seo-plan.md) needs one crawlable URL per country × language for hreflang across six languages and five launch countries. The prototype picks language from request headers, which also blocks static model pages (Q-033/Q-034).

**Decision:** URLs are `/{country}/{lang}/…` (e.g. `/nl/nl/`, `/be/fr/`, `/uk/en/`). Each country has a default language; `/{country}/` redirects to it. Headers only suggest a language on the first visit (a banner, not a redirect loop). Every page emits hreflang for all its country × language pairs plus `x-default`. The language choice is remembered but never overrides an explicit URL.

**Consequences:** Model pages can be static per country × language, which resolves Q-033/Q-034. Five countries × six languages = up to 30 variants per page; the sitemap lists only the pairs we serve (a country's own languages + English) until translations are reviewed.

## Decision 016: Open data release ships at launch

**Status:** Accepted (Menno, 2026-11-15)
**Date:** 2026-11-15

**Context:** The launch plan proposes the CC BY 4.0 dataset (catalogue + our real-range and charging figures) as the launch hook (Show HN, press, AI-search citations). It was tagged Next.

**Decision:** The open dataset is part of launch: each numbered release publishes a downloadable CC BY 4.0 bundle (CSV + JSON) with release number, date, licence and per-source attribution, only from sources that passed the licence gate (Decision 009). ODbL-derived values stay out.

**Consequences:** The licence gate and attribution file must be complete before launch; WS1 adds the bundle to the release job, WS2 a /data page.

## Decision 017: Prices in three modes (outright, loan, lease) from config tables

**Status:** Accepted (Menno's idea, WS0 defaults, 2026-11-15)
**Date:** 2026-11-15

**Context:** Many buyers lease or finance part of the price. Used leasing exists in NL, DE and FR. CCD2 (Directive (EU) 2023/2225) applies from 20 Nov 2026 to credit adverts with cost figures; in the UK, introducing consumers to finance or lease providers is FCA-regulated credit broking. Spec: master-spec-v2 §8 "Ways to pay".

**Decision:** A price mode (outright / loan per month / lease per month) on every price, remembered and in the URL. Loan = browser calculator from price, deposit, term and a typical rate from a new editable `finance_profiles` table (country, product, typical APR, default term and deposit, source, date). Calculator output is labelled an estimate, shows its assumptions, the total over the term and the CCD2 warning. Lease = partner-feed figures only, otherwise a plain labelled link. No finance commission at launch; no UK finance or lease links until the FCA question is answered.

**Consequences:** One small taxonomy (WS3), a price-mode control and calculator (WS2), a lawyer question in R-03. Lease figures stay Next until partner feeds exist.

## Decision 018: Working title "EV Shortlist"

**Status:** Accepted (Menno, 2026-11-15)
**Date:** 2026-11-15

**Context:** Name research in docs/brand/name-shortlist.md (rounds 1–2). evshortlist.com and evshortlist.nl were unregistered on 15 Nov 2026; .eu unchecked.

**Decision:** "EV Shortlist" is the working title in copy, drafts and the site's brand config. EV Field Guide stays the backup; other names and domains remain open. Repo name, package names and code ids stay `ev-finder` (no churn). The name lives only in config (`brand.name`), never hard-coded.

**Consequences:** Not final: no domain bought, no trademark filed, no logo finalised. Outreach still waits for the final name unless Menno says otherwise. Supersedes the "EV Finder" working name in AGENTS.md.
---

## Decision 019: Variant finder: grouped variants, differences only, clues in one data table

**Status:** Accepted (Menno, 2026-11-15)
**Date:** 2026-11-15

**Context:** One card per variant is right, but buyers can't see what differs between variants or match a used ad to the right one (EV Database pain). Silent mid-cycle changes (battery, charger, heat pump) are the costly traps.

**Decision:** Keep one card per variant. Add a "differences only" toggle and a variant change timeline (Core, no new data), a "spot it in an ad" clue box (Core for the 40 hand-checked models, Next for the rest), a "which one is it?" finder and NL plate lookup (Next), and listing-link paste (Later, marketplace terms). Clues are a new config-typed data table (Variant clue + Look-alike group) that also feeds listing matching (§8). Spec tab: docs/spec/variant-finder.md.

**Consequences:** Schema gains two entities (coordinator). WS3 writes clues for the top 40; WS1 owns clue data, look-alike detection and the RDW check; WS2 builds the toggle, timeline, box and later the finder; UX designs a colour-blind-safe diff highlight. No scraping of marketplaces.

## Decision 020: Schema conventions for bidi, charging stats and Trip fit (T-018, T-023, T-030)

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Addendum 4 added 37 schema defs. A few conventions differ from the spec text and need to be shared.

**Decision:**
- Taxonomy ids use hyphens (`ac-onboard`, `iso15118-20`, `dc-150-349`), not underscores, because every id must match the `Id` pattern (Decision 010). Seed tasks T-019, T-024 and T-031 write ids this way.
- New entities use `CountryCode` (any two-letter code, `UK` not `GB`), so US/AU rows need no schema change. The five-value `Country` enum stays for existing launch-market fields.
- No separate `usable_kwh` fact: `battery_kwh_net` is usable capacity. New fact names carry units (`frontal_area_m2`, `kerb_mass_kg`, `wheel_size_in`).
- Allowed values for `iso15118_20_support`, `heat_pump` and `drag_coefficient` facts are checked at release time (WS1), not in the schema, because a conditional schema rule broke the generated TypeScript `Fact` type.
- `CountryChargingLink`, `ChargingStat`, `ConsumptionModel` and `ClimateNormal` are defined but not yet part of `Catalogue`; WS1 decides how they ship.

**Consequences:** All additions are optional, so release 1 still validates. Details in Q-054.

## Decision 021: Data refresh runs from the CLI now; pg-boss schedules it once the database exists

**Status:** Proposed (provisional, overnight prototype 1, addendum 6 P1–P4)
**Date:** 2026-11-15

**Context:** The update loop is the heart of the product, but there is no database yet, so the pg-boss scheduling of Decisions 003/006 cannot run. Data still has to stay fresh, cheap and undoable.

**Decision:**
- One command, `ev refresh [--sources …] [--dry-run]`, runs every due source (cadence from `data/sources.yaml`): probe → fetch → snapshot → schema fingerprint → normalise → release → blocking QA. It is scheduled by GitHub Actions (`.github/workflows/data-refresh.yml`, weekly + manual) that opens a "Data release N" PR with only the release folder; on the server, the same command later becomes a pg-boss job (nightly window, 1 GB, Decision 006) without code changes.
- Raw fetches go to a content-addressed snapshot store (`$SNAPSHOT_DIR`, local now; S3-compatible behind the same interface, env vars only, not built yet). Unchanged sources (same hash, HTTP 304, same git commit) cost one probe and publish nothing.
- Per-source health (`data/releases/<n>/sources.json`): last success, last change, records vs previous, schema fingerprint. A breaking fingerprint change or a > 50 % record drop fails closed for that source (previous data kept, review item in `data/review/source-health.csv`) until `ev sources accept <id>`.
- `data/releases/latest` switches atomically (temp file + rename) and only after blocking QA passes; `ev release rollback --to <n>` and `ev release diff <a> <b>` undo and explain.

**Consequences:** No database or server needed for fresh data. The workflow's PRs don't start CI by themselves (GITHUB_TOKEN limit) and need the repo setting that lets Actions open PRs (Q-079). When pg-boss arrives, the job calls `ev refresh` and the snapshot backend switches to S3 by env var.

---

## Decision 022: Themes from design tokens, applied before paint without inline scripts

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Addendum 5 asked for a light "Day trip" and a dark "Night drive" theme. The strict CSP (no inline scripts) rules out the usual inline "apply theme before paint" snippet.

**Decision:** Colours come from `docs/design/tokens.json` (UX chat), generated into `apps/web/src/app/tokens.generated.css` by `scripts/theme.mjs` (a test fails when it is stale). `globals.css` maps the Tailwind colours the app uses onto the tokens. The default follows `prefers-color-scheme`; a header toggle stores the choice in localStorage; a same-origin `/theme-init.js` applies it before paint. Print is always light.

**Consequences:** The UX chat changes colours in one file. axe runs on both themes in CI (0 findings tonight).

---

## Decision 023: NEDC, worst-case WLTP and mass in running order are their own fields

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** R-08 found that the best open source for 2010–2020 EVs is RDW's type-approval data (TGK, CC0), which gives NEDC range, WLTP best and worst bounds and mass in running order (incl. 75 kg driver). Mixing these into WLTP or kerb weight would make numbers look comparable when they aren't.

**Decision:** New FactFields `nedc_range_km`, `nedc_consumption_kwh_100km`, `wltp_range_km_worst`, `wltp_consumption_kwh_100km_worst`, `mass_running_order_kg`, `power_30min_kw`, and optional PublishedVariant columns `nedc_range_km`, `wltp_range_km_worst`, `mass_running_order_kg`. NEDC never fills WLTP; running-order mass never fills kerb weight; 30-minute power never fills peak power. `wltp_range_km` keeps meaning the best case or the single stated value.

**Consequences:** Older cars can show an honest NEDC figure labelled as such. Real range stays derived from WLTP only.

---

## Decision 024: Type-approval values attach only on unique evidence; versions of one source are spread, not conflicts

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** RDW type approvals (rdw-tgk) carry many versions per car. Placing them on our variants needs evidence, and versions of one source that disagree are not a cross-source conflict.

**Decision:**
- A type-approval version attaches to a variant only when exactly one variant fits the evidence (range number in the name, years ±1, battery window from range × consumption, trade-name words, WLTP within 2%). Ties and misfits go to review with a reason; nothing is guessed.
- All versions of a source in `SPREAD_SOURCES` (today rdw-tgk) on one variant count as one vote, cast by the earliest model year's version. Other values are noted as "same-source versions differ" in provenance, not written to conflicts.csv, and can't outvote other sources.
- RDW plate values and RDW type approvals share one origin for agreement counts (Q-087).

**Consequences:** Pre-2020 rows gain NEDC, worst-case WLTP and running-order mass where the evidence is unique. Remaining ties (Zoe Z.E. 40, Honda e, Model 3 LR vs Performance) need more seed evidence (Q-089).

## Decision 025: Agreeing sources outvote one priority value; nameless records need evidence; lone-source DC peaks go to review

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Review A-05 found RDW model-year records (which blend all trims) landing on base trims and winning over other sources, RDW NEDC columns holding WLTP figures, and a DC peak on a Zoe that has no DC socket (Q-091).

**Decision:**
- A record without a variant name is not "base". It attaches only to a generation's only variant or on unique evidence; otherwise it goes to review.
- In priority fields, 2+ agreeing independent sources outvote a single priority value. Fields can opt out in `data/field_sources.yaml`. RDW stays first for WLTP and consumption.
- NEDC within 1 km of the same version's WLTP is dropped, and NEDC is dropped on 2018/858 approvals first registered after 2020 (inferred rule, logged in the run log).
- Only a source's own vote raises confidence.
- A DC peak that only KilowattApp gives goes to review until a second source or a charge-port field confirms it.

**Consequences:** EX30 base 475 → 341 km; 12 more rows reach "sourced"; 510 more records wait in review; 27 fewer rows show a DC peak until confirmed.

## Decision 026: Seed values can cite a source; git sources clone only from allow-listed GitHub URLs

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Hand-entered seed values had no per-value source (A-05 F5), and two adapters cloned from GitHub outside the safe fetcher (A-05 L6). Q-092.

**Decision:**
- `data/seed/variants.yaml` takes an optional `cited:` block per value (value, https source URL, retrieval date, locator, confidence). Each cited value becomes its own fact with that source. New seed values should be cited; uncited ones stay "unchecked" (Q-015).
- When a type-approval version still ties, a candidate named after a longer trade name (e.g. "i3s") drops out if the version's own trade name lacks that word.
- Git sources clone only from `https://github.com/<owner>/<repo>` with github.com in that source's `hosts:`; anything else fails closed before git runs.

**Consequences:** BMW i3s gains a cited battery figure and six more RDW versions place correctly. Honda e, Zoe Z.E. 40 and Model 3 gen1 trims still tie: no official figure separates them.

## Decision 027: Battery gate: records that contradict the seed battery go to review

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** A Zoe Z.E. 22 record (23.3 kWh) landed on the Z.E. 40 R90, an OpenEV Q4 40 (48 kWh) merged into the 77 kWh "40 e-tron", and Mach-E SR records landed on ER AWD. Nothing compared batteries before placing a record.

**Decision:**
- Each seed variant's battery (net, gross, cited, kWh in its name) is an anchor. A record whose battery differs by more than 15% on the same basis, or 20% across net/gross or name figures, never joins that variant; it goes to review with the reason.
- In the attach pass, ruled-out candidates go first; whatever remains still needs its own positive evidence, so the gate can't push a record onto the next-nearest trim.
- If either side has no battery figure, the gate rules nothing out.

**Consequences:** Zoe R90 23.3 → 41 kWh, Q4 40 e-tron 48 → 77 kWh (and 150 kW), Mach-E ER AWD 68 → 88 kWh. About 10 more records wait in review.

## Decision 028: A cited value beats a lone source

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** OpenEV gave the Mach-E GT 82 kWh net; Ford's own spec sheet says 88. One source with no backing beat a value with an official citation.

**Decision:**
- A cited fact (seed `cited:` or manual, medium or high confidence) wins when the merged winner disagrees with every citation and only one independent source backs it. The losing value goes to conflicts.csv.
- Two or more agreeing independent sources still beat a citation; disagreeing citations win nothing; `newest` fields are exempt; a citation never counts as independent confirmation. Opt out per field with `cited_wins: false`.
- Not decided tonight: withholding KilowattApp `ac_kw` for Zoe Phase 1 (it publishes 11 kW, even 23.3, where Renault's charger does 22 or 43 kW). Needs a cited Renault Phase 1 spec sheet first.

**Consequences:** Mach-E GT 82 → 88 kWh net, 98.7 gross; Mach-E SR 70 → 68 net. No cited value loses anywhere in the release.

## Decision 029: A value equal to another field of the same car is a mix-up and goes to review

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** KilowattApp put battery sizes in the AC charging field (Zoe R240 "23.3 kW", e-Golf 36 kWh "32 kW").

**Decision:**
- A field can list `mixup_with` fields in `data/field_sources.yaml` (today `ac_kw` → battery net and gross). A fact within 0.5 of one of them, on the same row or in the same source record, goes to conflicts.csv as a field mix-up and the field is merged again without it, unless the fact is cited or backed by another independent origin.
- Official manufacturer documents hosted on third-party sites may be cited at medium confidence when they name the exact version, low when they name only trims.

**Consequences:** Zoe Q90 43 kW, R110 22 kW, R240 22 kW, e-Golf 36 kWh 7.2 kW. Zoe Q210 and R90 still show 11 kW until a source names those motors (low-confidence citations can't win).

## Decision 030: Pack and platform links can be filled by rule within a generation

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** T-060: many release rows (from OpenEV and KilowattApp) had no battery pack or platform, because `variant_links.yaml` only knew seed ids.

**Decision:**
- `variant_links.yaml` accepts release variant ids; its links always win.
- A row gets a platform when every link in its generation names the same platform.
- A row gets a pack when its usable kWh fits exactly one pack already linked in its generation (within 6%, never above the pack's gross). The link's provenance records the rule and the gap. Ambiguous or misfitting rows stay unlinked with a reason in coverage.md.

**Consequences:** packs 123 → 181 rows, platforms 140 → 206 of 244. Links more than 5% off (Model 3/Y Highland/Juniper, Q4 50, Q8 55, Ioniq 6 Standard, Leaf e+) are flagged for a reviewer.

## Decision 031: Cited maker facts are gated like any source; a value a citation contradicts is withheld

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Review A-06 found cited seed values shipping as `seed-manual` (CC BY), skipping the licence gate for maker documents (Q-008), and guards that could resurrect overruled values or delete backed ones. Supersedes the consequence lines of Decisions 028 and 029 where they differ.

**Decision:**
- Seed `cited:` values are facts of source `maker-docs` (or another registered source) with their URL, date and confidence, and pass the licence gate. While Q-008 is open they don't ship; they still anchor the battery gate.
- If a blocked or low-confidence citation contradicts a value backed by at most one independent origin, that value goes to review and the field is merged again without it. Never ship a value we have evidence is wrong.
- All guards share one fact pool and repeat until stable; a removed fact never returns. `needs_backing` drops only the weak facts and re-merges.
- `manual` and `maker-docs` never count as independent. New policy keys: `seed_counts_as_backing` (only `dc_peak_kw`), `same_origin` (OpenEV EPA → fueleconomy).
- Cited platform links in `variant_links.yaml` still ship (memberships, not spec values) until Q-008 says otherwise.

**Consequences:** 0 of 15 cited facts ship; 16 rows regain a DC peak; Zoe Q210/Q90/R240 AC withheld; R90 still 11 kW (uncited); BMW i3s split into 94 Ah and 120 Ah rows (new id `bmw-i3-i01-i3s-94ah`).

## Decision 032: Citations for release-only rows live in data/manual; estimated curves never beat the peak

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Single-source values on rows that exist only in the release (no seed variant) couldn't be checked against a citation, and an estimated charge curve produced an average above the car's DC peak (e-Golf 24 kWh).

**Decision:**
- Citations for release-only rows go in `data/manual/specs/*.yaml` (source `manual`, attached by release id, blocked like maker documents until Q-008). They act as evidence for the withhold rule (Decision 031) but never ship.
- An estimated (not measured) curve is capped at the row's DC peak before integrating; a sourced average above the peak goes to validation.csv.
- A value withheld by a citation is not re-estimated from the same wrong record (e.g. net from gross).

**Consequences:** withheld: Mégane 40 kWh DC 130, R5 40 kWh DC 100, ID.3 Pro 2023 DC 135, EQA/EQB 60 kWh, Q4 40 Sportback 48 kWh, Q4 50 power/0–100, Zoe R90 AC 11. Zoe Q210/R240 usable 23.3 → 22. Five charging averages capped. Open: the OpenEV "Q4 50" rows are really Q4 40 data (drivetrain still RWD) and need restructuring.

## Decision 033: Source rows that copy a seed variant merge into it; known-wrong source naming is held for review

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** OpenEV/KilowattApp created rows that duplicated seed variants (e.g. Mégane "40 kWh" = EV40), and OpenEV's Audi Q4 names are one step off (its "50" is a Q4 40).

**Decision:**
- Duplicates join the seed variant through variant-level `source_names`, which may be year-scoped (`{name, years}`; overlaps are an error). Seed facts no longer start a year band on aliased variants.
- Seed power gate on alias joins: a joined record more than 5% off the seed's power goes to review.
- `source_holds` in `variants.yaml` sends a source's records to review by name, generation and years, with a reason (today: all 18 OpenEV Q4 records).
- Release 1 was never published (`previous_release: null`), so the 19 removed ids need no redirect. Before the first public release, the catalogue gets a `retired_ids` → successor map so later merges never 404 (schema + web task).
- Equipment trims with identical specs (Fiat 500e Icon/La Prima, Dacia Spring trims) stay unmerged until the product spec says whether trims get rows.

**Consequences:** 245 → 226 rows. Merged rows now follow merge policy, so some uncited seed values were replaced by source values; a few need a cited check (MG4 Standard DC 135, Mégane EV40 AC 22, Cupra Born 58 DC 135).

## Decision 034: AC charging means the standard on-board charger; optional chargers get their own field

**Status:** Proposed (provisional, overnight prototype 1)
**Date:** 2026-11-15

**Context:** Sources mix the standard and the optional on-board charger (e-208/e-2008 7.4 vs 11 kW, Mégane 7.4 vs 22, MG4 Standard 6.6 vs 11), so `ac_kw` flips between them by source.

**Decision:** `ac_kw` is the standard charger. An optional charger is a separate additive field `ac_kw_optional` (schema + pipeline + web task T-063). Until T-063 lands, rows keep today's merged value and the citation for the standard figure sits in review. Year-dependent values (Born 58 DC, e-208 51 vs 54 kWh, I-Pace AC) are split by model year in the seed when an official source gives both.

**Consequences:** some AC figures shown tonight are the optional charger; T-063 fixes the meaning.

## Decision 035: Releases move out of git; temporary 25 MB cap for release files

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** After PR #1, `data/releases/1/catalogue.json` is 7.1 MB (minified) for 226 rows, because every value carries its provenance. The CI guard (5 MB, meant for raw data) turned `main` red. At ~1,500 variants a release would be ~45 MB per release in git, which doesn't scale.

**Decision:** Raw data keeps the 5 MB cap. Files under `data/releases/` get a warning above 5 MB and fail above 25 MB, for now. Next step (T-064): published releases live outside git (GitHub Release assets now; Scaleway object storage once WS4 sets it up), the repo keeps only a small manifest per release (number, date, checksums, sizes, QA summary) plus a tiny fixture release for tests, and the web app fetches the release named in the manifest at build time. The catalogue also splits per generation so pages load only what they need.

**Consequences:** `main` is green again; WS1 + WS4 own T-064 before the catalogue grows past the top 40.

## Decision 036: Source choices from the overnight 2 research pack

**Status:** Accepted (WS0, 2026-11-15)
**Date:** 2026-11-15

**Context:** research/R-20, R-23, R-26, R-27, R-28 (merged with PR #2).

**Decision:**
- **Plate lookup (Next):** the visitor's browser calls opendata.rdw.nl directly with allow-listed fields; the plate never reaches our server, logs, URLs or analytics (R-23 §5).
- **Washington DOL EV population (ODbL):** internal cross-checks only; any public use waits for a separate ODbL output (Data rule 3).
- **EAFO:** `blocked` until EAFO confirms reuse terms in writing; Belgian charging counts wait too (R-26). BNetzA (CC BY 4.0), DfT (OGL v3), NDW (CC0) and AFDC go ahead.
- **Climate:** ERA5-Land daily 1991–2020 (CC BY 4.0) primary; Meteostat (CC BY 4.0) second; GeoNames for towns; GISCO and E-OBS skipped (non-commercial) (R-27).
- **Finance rates:** ECB MIR consumer-credit APRC series for euro countries ("Source: ECB statistics"), Bank of England for the UK; NL left blank until an official series exists; default term 48 months, deposit 10 %, labelled defaults (R-20).

**Consequences:** WS1 updates `data/sources.yaml`; schema follow-ups in T-065.

## Decision 037: Use EAFO and RDW data now, confirm licences afterwards

**Status:** Accepted (Menno, 2026-11-15); supersedes the EAFO "blocked" line in Decision 036
**Date:** 2026-11-15

**Context:** EAFO states no dataset licence (Commission notice: CC BY 4.0 unless otherwise indicated; data via Eco-Movement). RDW is CC0 but its notice says reusers may not state the data comes from RDW (Q-037). Menno: use the data now, ask afterwards.

**Decision:** EAFO aggregates go into releases now, credited "Source: European Alternative Fuels Observatory (European Commission), [date]", aggregates only, status `active_pending_confirmation` in data/sources.yaml. RDW stays in use; until RDW answers, attribution reads "Dutch open vehicle register (opendata.rdw.nl), CC0" with a link, no RDW logo or house style. Menno sends the questions in docs/outreach/drafts/licence-questions.md. If either answer is no, that source leaves the next release.

**Consequences:** Small, reversible licence risk 🟡 (aggregates, credited, removable). Belgium charging can use EAFO now.

## Decision 039: Dependabot patch and minor updates merge themselves; majors go to the coordinator

**Status:** Accepted (Menno, 2026-11-15)
**Date:** 2026-11-15

**Context:** Dependabot opens weekly grouped PRs. Menno doesn't want them reaching him. The first one (PR #3, the `actions` group: setup-uv 7.6.0→10.3.3, setup-buildx 3.12.0→4.4.1, metadata 5.10.0→6.2.0, build-push 6.19.2→7.4.0, login 3.7.0→4.8.0) was all majors. Their breaking changes: the docker actions moved to Node 24 (GitHub-hosted runners have it; Node 20 left the runners on 16 Sept 2026), build-push v7 adds a build summary, setup-uv v8 dropped moving major tags and changed the `manifest-file` format (not used here) and v9 stopped pruning the cache by default. None of our inputs changed. The PR's CI ran the new versions green apart from the 5 MB check, which predates Decision 035's release exemption; so the bumps were re-applied on top of current `main` in PR #8 (Dependabot's rebase command couldn't be posted from this session), which also regenerated the stale `tokens.generated.css` that had main's `web` job red.

**Decision:** `.github/workflows/dependabot-automerge.yml` runs after CI or Images. If the PR is from Dependabot, every check on its head commit is green (advisory `audit` aside) and every `update-type` in its commits is patch or minor, it squash-merges pinned to that commit. Otherwise it labels the PR `dependabot-major` and comments; the coordinator chat reviews the breaking changes, fixes inputs, merges and logs it here. Dependabot runs Mondays 09:00 Paris.

**Consequences:** No Dependabot PR needs Menno. Merging doesn't deploy (deploy is a manual SSH step), and merges made with GITHUB_TOKEN don't start CI on main; the next push does. The repo is public, so these runs cost no Actions minutes 🟡. Undo: delete the workflow file.
## Decision 038: Owner picks live in data/editorial; shortlist rules are rows with a back-test

**Status:** Accepted (WS0, 2026-11-15; Menno asked for it, thresholds await his review)
**Date:** 2026-11-15

**Context:** Menno's "New Car" sheet holds his own EV verdicts (tiers, colours, notes) for primary-car use in the NL and FR used market. He asked to put it in the product and to turn his way of choosing into rules for shortlist recommendations. The sheet's spec numbers were copied by hand from ev-database.org and Bjørn Nyland's 1000 km sheet.

**Decision:** New folder `data/editorial/` (owner WS3): `menno-picks.yaml` generated by `import_menno_sheet.py` (strips his postcode from links), `shortlist_rules.yaml` (profiles → gates, weighted factors, bonuses/penalties, bands per voltage class; price is a separate axis), `backtest_rules.py` in the CI data-qa job (fails under 60% exact band match). Verdicts and notes are publishable as a labelled "Owner's pick"; `sheet_values` are internal calibration only and never reach a release or the app. Production scoring reads our own published fields; factors without a field score neutral (0.5) until the field exists, never a guess. The rules file moves to `data/taxonomy/` once its schema exists (T-066).

**Consequences:** First recommendation profile ("only or main car, long trips") with 80% band agreement on his 30 rated cars and 85% pairwise agreement on the untuned July 2025 used tab (research/R-32). Risk: one person's taste, 30 rows 🟡; the UI must say so. Follow-ups T-066 (schema), T-067 (web), T-068 (seed), T-069 (scoring in the release).

## Decision 048: Catalogue target: every EU-sold EV model by generation and facelift at soft launch; variants towards ~1,500 as stretch

**Status:** Accepted (Menno, 2026-11-18, scope decision; logged by WS1)
**Date:** 2026-11-18

**Context:** R-41 (#108) measured 9.1 M EU BEVs 2010–2025; our 92 seed models cover 86.7 %, and ~40 missing models bring that to ~95 %. WS0 had put the long tail (R-41 task 5) post-launch (WS1 INBOX 2026-11-18 08:58).

**Decision:** Soft-launch bar: every EV model sold in the EU, split by generation and facelift (seed 92 + R-41's ~40 missing models, ~95 % of EU registrations). Stretch: as many variants as possible towards EV Database's ~1,500. R-41 task 5 (long tail) is back in scope as stretch, after the bar. This overrides WS0's 08:58 "long tail: post-launch". Every catalogue PR carries a coverage count (models / generations / variants / % EU registrations).

**Consequences:** WS1 does R-41 task 1 now (T-073), then task 5 as stretch. WS3's task 2 (missing models) is the bar. Kilowatt rows stay out (Q-047), no ev-database.org, no scraping.

## Decision 049: Variants come from RDW TGK versions; EEA corroborates with counts only (Q-039 default)

**Status:** Accepted (WS1 engineering default, 2026-11-18; reversible; Menno: Q-039 is an engineering call)
**Date:** 2026-11-18

**Context:** Q-039 asked whether EEA per-type-approval spec rows (TAN/Va/Ve averages of range, mass, power) may become facts. EEA's power field is reported inconsistently between countries and makers use variant codes very differently (R-41), so its averages are not stated values of one version.

**Decision:** EEA stays counts-only. Candidate variants come from RDW TGK versions (stated type-approval values, CC0). EEA registrations per TAN|variant|version only corroborate a candidate ("sold in the EU, n cars") and weight the % EU registrations coverage figure. No EEA spec average becomes a fact.

**Consequences:** T-073 builds on this. Reversing it means letting EEA rows add versions never registered in NL (R-08 plan B), a later task.

## Decision 050: Four usage profiles + where-you-live modifier preselect filters

**Status:** Accepted (WS0, 2026-11-15; Menno asked for it, non-road-trip thresholds await calibration)
**Date:** 2026-11-15

**Context:** Menno's picks (Decision 038) describe one use: a main car that also does road trips. He named two more (a main car with holidays by another mode, and a second car for short trips) and said urban vs rural living matters too.

**Decision:** `data/editorial/shortlist_rules.yaml` holds four base profiles: `road-tripper` (renamed from `only-car-long-trips`), `daily-driver`, `runabout`, and `kerbside-charger` (no home charger, which stacks on the other three). It also holds modifiers `urban` / `suburban` / `rural` (shift range gates and weights) and add-ons (high mileage, full car, tow, snow/mountain, keep 8+ years, used on a budget). Each profile carries `filter_presets` that Explore preselects as removable chips. A four-tap picker (car role, long trips, where you charge, where you live) chooses them; it reuses the trip-fit §4 answers and adds `home_area`. Weight steps are ×1.5 per step, then renormalised. `backtest_rules.py` now also checks that every rule field exists in PublishedVariant (or is marked a gap) and that steps and picker answers resolve.

**Consequences:** One template drives both Explore presets and the "Suggested" sort. Only road-tripper is back-tested; the other profiles use research thresholds (research/R-33) until the normie test (R-30) calibrates them 🟡. These profiles become `usage_profiles` rows once T-066 lands, so Trip fit and shortlist share one table.

## Decision 051: Strict launch scope: hero shortlist + catalogue, five countries

**Status:** Accepted (Menno, 2026-11-15)
**Date:** 2026-11-15

**Context:** Building with agents kept adding features. Menno: "EV Database, but better UX, some more features and more countries."

**Decision:** Launch = (1) a three-step hero (country → profile from the 4-tap picker, Decision 050 → budget with a rough "≈ €X/month" loan estimate; optional refine filters incl. body/seats, min winter range, towing, new/used and build years, brands in/out) that returns a top 10 of models with variant and build years, top 5 highlighted as the shortlist; (2) the full catalogue to browse (Explore, model/generation/variant pages, Compare with differences-only, tooltips); (3) five countries, six languages, used price bands per country by build year, the data pipeline, the open data download, and three /learn pages (winter range, charging in 2026, batteries and used battery health). Everything else is after launch or later (docs/spec/launch-scope.md). Builders take only BOARD tasks tagged Launch; anything else needs Menno's yes. Built work for parked features stays behind feature flags, off by default.

**Consequences:** Trip fit routes, charging pages, bidi filters, variant clue box/finder, lease figures, accounts, alerts and rankings pages wait. Supersedes the phase tags in earlier decisions where they conflict (e.g. Decision 017: only the loan estimate ships; Decision 019: only differences-only ships).

## Decision 040: Charging stats defaults (closes Q-075 / Q-076)
## Decision 043: Used price bands start as a labelled model, manual samples replace it

**Status:** Accepted (WS1 engineering default, 2026-11-15)
**Date:** 2026-11-15

**Context:** T-025 needed rules for source ids, unmatched values and dates in charging statistics; Menno did not need to decide these.

**Decision:** (1) Charging stats keep the taxonomy id as `source_id`; `data/sources.yaml` lists it in `aliases`; the release ships `source_aliases`. (2) Values with no taxonomy id (power band, metric) are skipped and counted, never forced into a nearby band. (3) EAFO year rows are dated 31 December; the newest row is the last day of the file's month. (4) Release diff: growth over 15 % a month (compound), any fall, revisions and vanished series go to `data/review/charging_changes.csv`. Review only, never blocks a release.

**Consequences:** Taxonomy gaps go to WS3 as rows. Q-075 and Q-076 can close.

## Decision 041: Climate per town and the consumption reference basis

**Status:** Accepted (WS1 engineering default, 2026-11-15)
**Date:** 2026-11-15

**Context:** T-034 and T-033 needed a cold-day definition, a town → weather-station rule and one basis for the consumption matrix.

**Decision:** (1) P10 = 10th percentile of January daily mean temperature, 1991–2020 (R-27 §6). (2) A town takes the nearest station within 60 km and 250 m elevation, preferring one with a P10; no interpolation. ERA5-Land replaces this as primary once the CDS key lands. (3) Consumption matrix: reference at 20 °C on battery basis (wall × 0.88); EPA 5-cycle adjusted values count as measured town/rural references; motorway from EPA highway × body drag factor; WLTP × body ratio otherwise; never from an estimate-only WLTP. Parameters live in `pipeline/ev_pipeline/derive/consumption_params.yaml`; every cell is an estimate.

**Consequences:** Trip fit and the shortlist read winter figures from the matrix, not from WLTP.

## Decision 042: Shortlist scores ship as an editorial release file with a basis bridge

**Status:** Accepted (WS1 engineering default, 2026-11-15)
**Date:** 2026-11-15

**Context:** T-069 scores every variant with `data/editorial/shortlist_rules.yaml` before the T-066 schema exists. The rule thresholds were set on ev-database's numbers in Menno's sheet; our own winter range, real efficiency and DC km-per-20-min run on a harsher basis (median sheet/ours on 13–15 matched picks: winter ×1.24, Wh/km ×1.155, DC ×1.42).

**Decision:** (1) Scores ship as `shortlist_scores.json` in each release (labelled editorial + estimate, CC BY 4.0), 18 combinations per variant: road-tripper / daily-driver / runabout × home or kerbside charging × town / city / countryside, with 0..1 factor values so the app can re-weight add-ons. (2) A per-field `basis_scale` in `pipeline/ev_pipeline/derive/shortlist_params.yaml` maps our values onto the rules' basis before thresholds apply; Menno's thresholds stay as written and the sheet values stay internal. (3) Winter factors and the road-tripper winter gate read the matrix's −10 °C mixed figure; unknown values score 0.5 and are listed; over half the weight unknown → `not-enough-data`. (4) The back-test against the owner's picks is reported in the release README, not a gate.

**Consequences:** Refit the scales when the consumption or DC curve model changes. When T-066 lands, the field and unit mapping in the params file moves into the rules rows and the file becomes typed.
**Context:** The hero's budget step needs a used price per variant, build year and country at launch (Decision 051). No marketplace feed exists, layer 3 stays off (Decision 004), the free price indices carry no licence and give only country trends (research/R-40), and no manual samples exist yet.

**Decision:** (1) Each release ships `used_prices.json`. A model band = list price at registration × share of value kept at that age (one EU curve from DAT, ING and Allianz anchors, research/R-40), P25/P75 = median × (1 ∓ 0.12), `samples: 0`, `estimate: true`. (2) List price: that year's `price_new` fact in that country; else the nearest year within 2; else (DE, FR, BE) the Dutch price moved to local VAT, low confidence. UK only from UK prices. No list price → no band. (3) Manual sample aggregates (count, P25, median, P75 per build year; URL and date; data/manual/prices, WS3) with ≥ 5 cars and ≤ 120 days old replace the model band for that variant; generation-level aggregates ship as generation bands. Every sample row is back-tested against the model in qa.json (not a gate). (4) Price indices stay internal sanity checks until a licence or permission exists.

**Consequences:** About 99 of 226 variants get a band from release 1's prices; coverage grows with cited list prices. Refit the curve when DAT's 3-year BEV figure moves by more than 3 points or samples disagree by more than 15 % median.
## Decision 052: Packages must be 3 days old before we lock them (matches Dependabot)

**Status:** Accepted (coordinator fix, 2026-11-15)
**Date:** 2026-11-15

**Context:** Every Dependabot npm job failed (and emailed Menno): Dependabot waits 3 days before trusting a new version and runs pnpm with that rule, but an agent had locked @playwright/test 1.65.1 (and a few transitive packages) when they were under 2 days old, so pnpm refused to install the project at all.

**Decision:** `minimumReleaseAge: 4320` (3 days) in pnpm-workspace.yaml, and an explicit `cooldown: default-days: 3` for npm in .github/dependabot.yml. The two values stay equal. Lockfile regenerated under the rule; @playwright/test pinned to 1.65.0.

**Consequences:** Agents can no longer lock a version fresher than Dependabot accepts, so this failure can't come back. Urgent security fixes that are under 3 days old go in `minimumReleaseAgeExclude` with a comment.

## Decision 053: Dependabot majors handled; red PRs always reach the coordinator

**Status:** Accepted (coordinator fix, 2026-11-15)
**Date:** 2026-11-15

**Context:** After Decision 052, Dependabot opened five majors (#16–#20). The auto-merge workflow only ran on green CI, so a red major (js-yaml 5, #19) never got the `dependabot-major` label and nobody was told. @types/node jumped to 26 while we run Node 22.

**Decision:** (1) Majors taken in one PR: eslint 10 + @eslint/js 10, typescript 6, json-schema-to-typescript 16 (regenerated types: comments only), js-yaml 5 (scripts use `import * as yaml`, since v5 has no default export). (2) dependabot-automerge.yml runs on green and red CI: majors get `dependabot-major` either way; red patch/minor PRs get `dependabot-failing`. Both are coordinator work. (3) Dependabot ignores @types/node majors; it moves by hand with the Node runtime in .nvmrc and the Dockerfile.

**Consequences:** Dependabot closes #17–#20 itself once main has those versions; #16 closes because of the ignore rule.
## Decision 054: Dependabot runs monthly, one npm group

**Decision:** Dependabot version updates move from weekly to monthly (the 1st, 09:00 Paris), and the two npm groups (dev, prod) merge into one. Security updates are unchanged and still open straight away.

**Consequences:** About 4 routine PRs a month instead of ~5 a week, so far fewer notifications for Menno. Updates arrive in bigger batches, so a failing batch may need a little more untangling.

## Decision 055: Hero on top of the landing page; profile filters never drop a car for missing data

**Status:** Accepted (WS2, 2026-11-15; T-080)
**Date:** 2026-11-15

**Context:** Decision 051 makes the three-step hero the landing page, while Explore (and every e2e test and internal link) already lives at `/{country}/{lang}/`. Release 1 has no used prices and no winter-range field, and many cars miss boot or mass values.

**Decision:** The hero sits at the top of `/{country}/{lang}/` and Explore follows under `#explore` (same URL, no redirects). The hero's refine filters are Explore's filters and URL params (new: `seats`, `ac`, `ymin`/`ymax`, `make`/`xmake`); the two components stay in step through a browser event. Ranking runs in the browser from `src/config/shortlist-rules.generated.json`, built from `data/editorial/shortlist_rules.yaml` (rows only, no evidence or sheet values). A profile's filter presets and gates exclude a car only on a known value; a missing value passes and is shown as "not known yet" (the visitor's own refine filters stay strict, as in Explore). A car without a price stays in the list, marked, unless a known price is over budget. Units in the rules: a factor whose `sheet_field` is `dc_km_per_h` reads `dc_km_per_20min × 3`; efficiency reads Wh/km; other DC factors (daily driver, runabout) read km per 20 min. Winter range shows "not known yet" until the release publishes it.

**Consequences:** No URL changes, nothing hidden for lack of data. WS3 should state units on each rule row (`unit:`) to remove the DC ambiguity; WS1/WS0 to publish a winter range field and used price bands, which the hero picks up without code changes.
## Decision 057: A facelift with new battery packs is its own generation

**Status:** Accepted (WS3, T-068)
**Date:** 2026-11-15

**Context:** Menno's picks rank the Kia EV6 and Hyundai Ioniq 5 2024 facelifts (84 kWh) and the XPENG G6 2025 update (5C LFP) as different cars from the earlier versions. In one generation, the shortlist, price bands by build year and pack links (T-057 pack guard) could not tell them apart.

**Decision:** When a mid-cycle update changes the battery packs together with a visible facelift, it becomes a new generation (`<model>-facelift`), with the earlier generation ending in the overlap year (one shared year, as the validator allows). Applied to kia-ev6, hyundai-ioniq-5 and xpeng-g6. Existing generation ids stay; their variants are capped at the split year. A battery change alone (e.g. ID.3 77 → 79 kWh) stays a change marker.

**Consequences:** RDW names both versions the same, so the shared year goes to model level (MODEL_LEVEL_FALLBACK) instead of a guessed generation. Facelift generations get rows from OpenEV by model year; WS1 checks placement on staging.

## Decision 058: Picks importer maps a sheet year one year off to the nearest generation

**Status:** Accepted (WS3, T-068)
**Date:** 2026-11-15

**Context:** Menno's sheet uses reveal or order years (Elroq 2024, Scenic 2023); the seed uses registration years (2025, 2024). Those rows had no generation, so the shortlist rules could not score them.

**Decision:** `import_menno_sheet.py` maps a year at most one year outside every generation of the model to the nearest one and lists those rows when it runs (the EditorialPick schema has no field for it; WS0 may add one). Further away stays unmapped. A `--remap` mode refreshes only the seed ids from the existing picks file, so the sheet is not needed after seed changes.

**Consequences:** Seed years stay evidence-based; the importer output and models.yaml notes (Elroq, Scenic) show which rows were matched by proximity.
## Decision 059: Heat pump fitment as cited manual facts; heater and temperature labels as taxonomy rows

**Status:** Accepted (WS3, T-031)
**Date:** 2026-11-15

**Context:** The consumption model (T-033) needs per-variant heat pump fitment and readable labels for its temperature columns and heater types. R-21 found fitment for about 40 generations, often only for some model years or one market.

**Decision:** Fitment goes in `data/manual/heat-pump/*.yaml` as one cited `heat_pump` fact per generation, only where the source covers the whole generation; `not-disclosed` is never entered (it is the default). Rows that change inside a generation wait for a year span on manual facts (asked WS1) or a seed variant split. `data/taxonomy/temperature_bands.yaml` and `heater_types.yaml` carry six-language labels and tooltips; their numbers mirror the model defaults in `consumption_params.yaml` and change there and here together.

**Consequences:** Fitment stays internal until Q-008 (source `manual` is blocked). The model's numbers are unchanged; only labels are added.

## Decision 060: Price samples from public search-result pages, aggregates only (owner's choice)

**Status:** Accepted (Menno, 2026-11-15; logged by WS3, T-081)
**Date:** 2026-11-15

**Context:** T-081 needs used price samples (layer 2) to calibrate and replace model estimates. R-03 assumed staff note them by hand; an agent doing it is automated access, which Decision 004 kept off. Menno chose to let an agent do it, accepting the terms-of-service and database-right risk (R-03), with one limit: read search-result pages for specific make/model (and variant/year) searches, the way a person tracks prices, and never open individual listings.

**Decision:** An agent may read a marketplace's public search-result pages, only where robots.txt allows the path for our user agent, with an honest user agent, a few pages per model, 8 s or more between requests, and it stops for good on any 403/429 or bot challenge from that site. It keeps only aggregates per generation and build year (count, P25, median, P75 of fixed asking prices, fuel = electric); no listing ids, titles, seller data or locations are stored. Files go in data/manual/prices/ with the search page as source. This narrows Decision 004 for layer 2 only; layer 3 (scheduled sampling) stays off.

**Consequences:** 2026-11-15 check: AutoScout24 disallows ClaudeBot in robots.txt; La Centrale and mobile.de answered 403. Those are not used. Marktplaats (NL) and Autotrader (UK) result pages were reachable and allowed. Reversible: delete the files and stop. 2026-11-17 check: 2dehands.be (BE, same platform as Marktplaats) allows `/l/auto-s/q/` and is used. leboncoin.fr disallows `/recherche` for Claude agents and its robots file says automated access needs permission: not used. kleinanzeigen.de blocks filtered result pages (fuel, year), so an unfiltered search would mostly read non-EV cars: not used for now. _(Restored 2026-11-17 by WS0: the de-dupe in e885fa0 dropped this line; QA A-35 S1.)_

## Decision 044: Release diff N vs N-1 blocks unapproved changes (T-123)

**Status:** Accepted (WS1 engineering default, 2026-11-17)
**Date:** 2026-11-17

**Context:** A-20 B1 shipped a release whose numbers nobody had meant to change, and review only saw the code. T-123 asks for a differential test: same records, old against new, noise taken out, and a list of changes someone approved.

**Decision:** (1) `release_diff` is a new **blocking** QA check, run inside every `ev release` build and by `check-release` (CI data-qa, rollback). It compares catalogue rows and generations, shortlist scores, used prices, consumption matrix, towns and stations per id and field (`pipeline/ev_pipeline/release/differ.py`). (2) Blocking: an unapproved record removal (unless retired_ids redirects it), a change beyond the field's threshold, a thresholded value that goes empty, a number that loses every source, or a file that disappears. Everything else is review: listed, never blocks. (3) Thresholds, record sets, ignored keys and approvals live in `config/approved_changes.yaml`; an approval needs a reason and `PR #n` or `Decision nnn`, and can be scoped to a release, file, id, field and kind; unused approvals are listed as stale. (4) Fail closed: a bad config or an N-1 whose files don't match their manifest fails the check. (5) Charging figures (Decision 040 item 4) go through the same report but stay review only. Outputs: `data/review/release_diff.csv`, qa.json `release_diff`, a qa.md section (which the data-refresh PR body already includes), and `ev release diff --from N-1 --to N [--check]`.

**Consequences:** The first refresh after this merges will block on every intended change since release 1 (T-068 seed models, new matching rules). That's on purpose: someone looks at the list once and adds a release-scoped bulk approval naming the PR. `config/` is WS3's folder; this one file is WS1's (T-123), and changing a threshold counts as a gate change (REVIEW.md R3).

## Decision 045: Sibling-variant real range scales by WLTP ratio, battery ratio only without it

**Status:** Accepted (WS1 engineering default, 2026-11-17)
**Date:** 2026-11-17

**Context:** The T-124 property tests (Hypothesis) found that the ladder's sibling-variant rung, which scaled a sibling's measured range by usable-battery ratio only, gave a same-pack variant with a lower WLTP (other wheels or trim) more real km than its own WLTP × 1.1. The spec's rung 3 scales "by usable kWh and wheel size"; we have no wheel size, but both variants' WLTP figures carry battery, wheels and trim together.

**Decision:** Scale the sibling's measured km by own WLTP / sibling WLTP when both are known; fall back to the battery ratio otherwise. The note on the result says which ratio was used.

**Consequences:** No change to today's release (all 203 rows with a real range use the body-ratio rung; no measured tests are licence-cleared yet). Once measured tests arrive, the synthetic back-test already improves (alpha-50: −2.0 % → +0.1 %). Reversible: one branch in `derive/metrics.real_range`.

## Decision 062: Verification layer: diff-triggered REVIEW.md, gates out of reach, evidence per PR, every miss becomes a check

**Status:** Accepted (Menno via the verification chat, 2026-11-17; logged by WS0)
**Date:** 2026-11-17

**Context:** Most launch tasks were merged without a fresh review (QA START, 17 Nov). Misses were caught late (stale release in MORNING.md, wrong EPA matches, duplicate decision numbers, conflict markers). Based on the Claude Code team's article on verification.

**Decision:**
- **REVIEW.md on main:** reviewers run only the items the diff triggers (R0–R3 always, D1–D13 by path), with evidence, and read the file from `origin/main`, never from the PR branch. One review = one commit (head SHA recorded in the task's `## Review`).
- **Gates out of reach:** gate files (CI, REVIEW.md, AGENTS.md, test config, QA thresholds; listed in `config/gate-files.yaml`) change in their own PR. The `gate-guard` CI job flags mixed PRs and deleted/skipped tests without a `Test-change:` line; observe for one week (until 2026-11-24), then enforce with a new decision. WS0's `gate-ok` label is the logged escape hatch.
- **Evidence pack per PR:** the PR template asks how it was verified and which REVIEW items fired; the `Verified:` commit stamp and the self-merge rule follow in T-128.
- **Every miss becomes a check:** `docs/process/rules.md` lists every rule, the incident behind it and where it is enforced; a miss after merge adds a row and a check; a 4th retro question asks what a check missed; prune each phase. First tool checks: conflict markers and duplicate decision numbers in CI.
- Decision number blocks per workstream at the top of this file.

**Consequences:** Tasks T-120–T-129. One reviewer, tuned, not a stack of reviewers. Slightly slower merges; fewer late surprises.

## Decision 063: One process doc, a lean QUESTIONS.md, and retire-don't-delete into `_archive/`

**Status:** Accepted (Menno via the verification chat, 2026-11-17; logged and reviewed as a gate change by WS0)
**Date:** 2026-11-17

**Context:** The workflow was described in five places, decisions in two, and QUESTIONS.md had 83 "open" items, most of them engineering defaults. Menno: move old docs, don't delete them.

**Decision:** `docs/process/README.md` is the one process doc. Project instructions live in `docs/process/project-instructions.md`. QUESTIONS.md holds only what Menno must answer; the rest moved to the archive with "default stands", and all ids were kept. AGENTS.md: when unsure, take the reversible default and note it; only Menno-only decisions block. Retired files go to `_archive/` (git mv plus a README row). Chats never read it unless Menno asks, and `.rgignore` keeps it out of searches (rule G-32). WS0 reviewed the AGENTS.md lines that went straight to main (266b373, e097843) and keeps them. The CI budget rule is G-33 (PR #45).

**Consequences:** Fewer places to keep in sync. Gate files still change through a PR from now on (G-06); straight-to-main is for STATUS/HANDOFF/INBOX only.

## Decision 064: Budget uses a price for every car: real used band, else a depreciation estimate from the new price

**Status:** Accepted (Menno, 2026-11-17, question popup; QA A-35 B2)
**Date:** 2026-11-17

**Context:** The hero let cars without a price through the budget filter, so €15k and €35k gave the same top 10 (A-35 B2).

**Decision:** The price the budget compares against, in order: (1) our used price band for that variant, build years and country (T-081/T-056); (2) a **used price estimate**: the new list price × a depreciation curve by age, fitted on our own used samples where we have them, otherwise a published curve with its source (T-113); (3) the new price, for new cars. Every variant gets a sourced new list price (T-112). Estimates are labelled "estimate" with the method and source in Nerd mode. A car with no price at all is never in the top 5; it is listed after every priced car with "price not known yet". The budget is a hard filter on the band's median (or the estimate).

**Consequences:** T-112, T-113, T-115. Every used figure keeps its provenance; estimated bands are replaced by real ones as samples arrive.

## Decision 065: One shortlist implementation: the web reads `shortlist_scores.json` from the release

**Status:** Accepted (Menno, 2026-11-17, question popup; QA A-35 B3)
**Date:** 2026-11-17

**Context:** The hero scored mild real range without `basis_scale` in the browser, while the back-tested T-069 pipeline scores winter range with `basis_scale`. Two implementations of one rule set (A-35 B3).

**Decision:** Scores per variant and profile come only from the release (`shortlist_scores.json`, T-069). The web applies the hard filters (country, budget per Decision 064, refine chips) and sorts by the release score; it no longer computes factor scores itself. The reason line uses the factor values in the release. The back-test therefore runs the ranking visitors see.

**Consequences:** T-114. Remove the web copy of the scoring rules, or keep it only as a test oracle. Release 2 must carry `shortlist_scores.json` (T-116).

## Decision 066: Spain and Italy join the launch countries (seven countries)

**Status:** Accepted (Menno, 2026-11-17, question popup: scope change; QA A-35 B5)
**Date:** 2026-11-17

**Context:** Launch scope listed Spanish and Italian as languages, but no page served them (A-35 B5).

**Decision:** Launch countries are NL, DE, FR, BE, UK, **ES and IT**. Spanish and Italian serve Spain (`/es/es`) and Italy (`/it/it`) only; no other Spanish- or Italian-speaking countries. Each new country gets what the others have: euro prices, a finance default with the CCD2 warning in the local language, used price bands (indices, samples or the Decision 064 estimate), and marketplace search links (link-outs only; Decision 004 and 060 rules apply to any sampling). Drafts are labelled; EN and NL stay the fully reviewed languages.

**Consequences:** T-117, T-118, T-119. Supersedes the country list in Decision 051's launch scope; docs/spec/launch-scope.md updated.

## Decision 046: Optional on-board charger: a citation routes a source's AC figure (T-063)

**Status:** Accepted (WS1 engineering default, 2026-11-17)
**Date:** 2026-11-17

**Context:** Decision 034 split AC into `ac_kw` (standard charger) and `ac_kw_optional`. OpenEV and KilowattApp give one max-AC number and never say whether it is the option: 0 of 746 OpenEV AC records mention one (checked 2026-11-17). A-06 found rows showing the option as AC (e-208 / e-2008 11 kW where 7.4 is standard, Megane EV40 22 kW, MG4 Standard 11 kW).

**Decision:** Before merging, a source `ac_kw` fact moves to `ac_kw_optional` only when a citation for that variant (seed `cited:` or data/manual) names that value as the optional charger and no citation names it as the standard one (`merge/ac_route.py`, ±2 % like `ac_kw`). Blocked citations (maker-docs, manual: Q-008) count as evidence for this, as in guard_contradicted (A-06 F3); they never ship. Without a citation nothing moves. A cited option not above the cited standard routes nothing and goes to review; a published option not above the standard is dropped (rows) and flagged (QA `ac_optional_not_above`).

**Consequences:** Release values change only when WS3 adds citations. Until Q-008 is answered a routed row shows the option and an empty standard AC rather than a wrong one. Every move is listed in the run log (`sections.ac_kw_optional`).

## Decision 067: Infra agents write runbooks; Menno applies them

**Status:** Accepted (WS0, 2026-11-17; WS4 inbox asked to settle a conflict)
**Date:** 2026-11-17

**Context:** WS4 START.md assumed the chat SSHes to the shared server; infra/AGENTS.md rule 1 says agents never ssh or apply.

**Decision:** infra/AGENTS.md wins: agents write files and copy-paste runbooks (with a read-only measure step), Menno runs them on the server. Fixed in WS4 START.md. Reason: the server is shared with GardenLayer and Dungeon Tracker, so the person who can see all three applies changes.

**Consequences:** Staging (T-040, PR #59) waits for Menno to run the runbook once.
## Decision 047: Derived WLTP consumption is wall basis: net kWh / WLTP x 1.16 (T-071)

**Status:** Accepted (WS1 engineering default, 2026-11-17)
**Date:** 2026-11-17

**Context:** Rows without an official WLTP consumption got net kWh / WLTP km x 100, a battery-basis figure. Official WLTP consumption is measured at the wall and includes charging losses, so these 58 rows ran about 14 % low (WS2 report 2026-11-17; A-32 found −11 % on 45 rows). The hero Nerd table and the road-tripper efficiency factor read this field.

**Decision:** The estimate is multiplied by 1.16, the median official / battery-basis ratio on release 1 (n 138, IQR 1.13–1.20). That is wall x 0.86 = battery, close to the matrix basis in Decision 041 (x 0.88), which stays as it is. qa.json reports our estimate against official figures every release (`estimate_vs_official_wltp`).

**Consequences:** 58 rows and their motorway, AC km/h and DC km values rise or fall with it in release 2 (release diff approval needed). Refit the factor when the back-test drifts above 5 % median abs error.

## Decision 068: Single cited facts from maker documents may ship (Q-008)

**Status:** Accepted (Menno, 2026-11-17, question popup)
**Date:** 2026-11-17

**Context:** Maker spec sheets and price lists have no licence, so Decision 009 kept them `blocked`. That kept T-110's corrected figures and T-112's new prices out of the release (A-35 B2/B4).

**Decision:** Single facts from maker documents (list price, WLTP range, battery size, consumption) may reach a release, one figure per car per document, each with its URL, retrieval date and confidence. Never copy a whole price list or spec table. KBA, SDES and EU Safety Gate stay blocked until their reuse terms are checked.

**Consequences:** WS1 sets the `manual` / maker-document source status in data/sources.yaml accordingly (with T-116). The licence column says "facts cited, no licence".

## Decision 069: A generation's sample band stands in for its variants (Decision 064 step 1)

**Status:** Accepted (WS0 engineering default, 2026-11-17; reversible)
**Date:** 2026-11-17

**Context:** All 106 real used-price sample bands are per generation, but the web reads variant rows only, so Decision 064's "real band first" step never ran on real data (fresh review of #64). Spreading one median over cheap and dear trims misprices both a little; an estimate from a curve misprices more.

**Decision:** When a variant has no own sample band for a build year and country, its row takes the generation's sample band for that year and country with `basis: band` and `scope: generation`, ahead of the depreciation estimate. Pages label it "typical for this generation". Variant-level samples, when they exist, win.

**Consequences:** Schema gains optional `scope: variant | generation` on UsedPriceYearBand (WS0). WS1 implements it in #64; the back-test reports how often the real median falls inside the shown band.

## Decision 080: Autotijd list prices are held; new prices come from makers (Menno)

**Status:** Accepted (Menno, 2026-11-17, question popup)
**Date:** 2026-11-17

**Context:** PR #65 (T-112) took 71 BE list prices one by one from autotijd.be ("all rights reserved", no reuse terms). Decision 068 clears single facts from maker documents only; repeated extraction from one third-party site is an EU database-right risk.

**Decision:** Merge the rows but register autotijd as its own source with status `blocked`, so they never reach a release. A builder re-sources those prices from the makers' own price lists or configurators (Decision 068). Meanwhile those cars use a used band or rank last (Decision 064).

**Consequences:** Release 2 prices only what makers publish. Autotijd could be unblocked later only with written permission (WS5).

## Decision 081: Car photos: maker press photos first, Wikimedia Commons as fallback, licence per maker logged

**Status:** Accepted (Menno, 2026-11-17, staging feedback item 4; licence risk is his call)
**Date:** 2026-11-17

**Context:** Cards on staging have no photos. Menno chose the source order and accepted the licence risk on the terms below.

**Decision:**
- Source order: (1) maker press/media photos, (2) Wikimedia Commons (CC BY / CC BY-SA only), credited under every photo.
- Per maker, `data/images/press-terms.yaml` records which press terms apply, the URL they come from, the date checked and whether our use (editorial identification of the car on a free, non-commercial-at-launch site) is allowed. A maker whose terms forbid it is skipped and falls back to Commons.
- Never hotlink: images are downloaded once, stored in our own object storage with the release, resized by us.
- Every image carries source URL, licence, credit line and retrieval date in the data; the card shows the credit line. CC BY-SA images keep their licence and are not mixed into the CC BY open data download (data rule 3: licences stay separate; images are excluded from the open data dump).
- One photo per generation at launch (variant photos later).

**Consequences:** T-133 (WS3 sourcing + licence log), T-134 (WS1 image fields + storage in the release), T-135 (WS2 cards + credit line). Supersedes nothing.

## Decision 082: English only at launch; the URL keeps the language segment

**Status:** Accepted (Menno, 2026-11-17, staging feedback item 6)
**Date:** 2026-11-17

**Context:** Translations (T-117 drafts, T-119 routes) cost review time before launch. Menno wants one good language first.

**Decision:** Every launch country serves `/{country}/en/` and English is the default (`/{country}/` redirects there). The URL structure of Decision 015 stays, so adding a language later changes no existing URL. The other languages' strings stay in the repo but are not served (country config `languages: []`, `default_language: en`); `/{country}/{nl|de|fr|es|it}/` is not linked, not in the sitemap or hreflang, and redirects to `/{country}/en/`. Translation work (T-117, T-119 follow-ups, REVIEW D6 for non-EN) is parked until after launch. Spain and Italy stay launch **countries** (Decision 066) with English pages.

**Consequences:** T-137 (WS2). Supersedes the language parts of Decision 066 and launch scope §3 for launch; REVIEW D6 needs EN only until languages return (gate PR).

## Decision 083: Commons CC0 and public-domain photos are allowed (widens Decision 081)

**Status:** Accepted (WS0 for Menno, 2026-11-18; Menno asked WS0 to answer WS3's question)
**Date:** 2026-11-18

**Context:** Decision 081 allows Wikimedia Commons photos under CC BY / CC BY-SA only. WS3 found good photos under CC0 and public domain (e.g. Citroën ë-C4). Those licences ask less of us than CC BY: no attribution duty, no share-alike, so they add photos without adding licence risk.

**Decision:** Commons files whose file page carries a **CC0** or a **worldwide public-domain** template (e.g. `PD-self`, `PD-author`, `PD-old`) are allowed, with the same rules as Decision 081 otherwise:
- Check the licence template on the file page itself (not a category or a mirror) and record the template name, the file page URL and the date in `data/images/press-terms.yaml` / the image facts.
- Still show a credit line: the author's name if Commons gives one, otherwise "Wikimedia Commons".
- Not allowed: public domain in one country only (`PD-US-*`, `PD-USGov-*` without a worldwide statement, `PD-textlogo`-style tags used for a photo), files with a personality-rights or no-FoP warning, and files Commons marks for deletion.
- Images stay out of the CC BY open-data download, as in Decision 081.

**Consequences:** T-133 (WS3) may add CC0 / PD photos. Reversible: if a file's status changes, the photo is swapped at the next release.

## Decision 084: People carriers in, cargo vans later (Menno, 2026-11-18)

**Status:** Accepted (Menno, relayed 2026-11-18 11:27 CET via WS3 2nd chat, WS0 INBOX 10:30 UTC)
**Date:** 2026-11-18

**Context:** The vehicle scope said "BEV cars only at launch; vans Later" (product decision 2026-11-14). The T-136 missing-model seed (#129, #138) found van-based people carriers among the EU's registered BEVs (~65k cars, 0.7 %), and WS3 asked whether EQV, ë-Berlingo and e-Rifter were in scope.

**Decision:** Van-based **people carriers**, the M1 passenger versions, are in the catalogue like any other car: Mercedes EQV / eVito Tourer / EQT, Citroën ë-Berlingo / ë-SpaceTourer, Peugeot e-Rifter / e-Traveller, Opel Combo-e Life / Zafira-e Life, Toyota Proace (City) Verso, Fiat e-Doblò / e-Ulysse, Nissan e-NV200 Evalia, Renault Kangoo E-Tech. "Vans Later" now means **cargo vans only** (N1 panel vans and their commercial versions stay out).

**Consequences:** WS3 seeds the M1 versions (T-136, #138) with the same data rules as other models; register rows for cargo versions stay unmatched or go to review, never onto the M1 generation. docs/spec/product-decisions.md updated. Reversible: a people carrier can be parked again with a flag.

## Decision 056: Ariakit is the UI library for complex widgets (supersedes "no UI libraries" in apps/web rule 4)

**Status:** Accepted (Menno, 2026-11-18: "development is still early stage, let's just make use of this library")
**Date:** 2026-11-18

**Context:** apps/web rule 4 banned UI libraries to protect the JS budget, so every widget was hand-built. Accessible comboboxes, dialogs and menus are hard to get right by hand. Ariakit (`@ariakit/react`, MIT) is unstyled (our tokens stay in charge), accessible, and supports React 17+ (we run 19).

**Decision:** Use Ariakit for interactive widgets with real keyboard and screen-reader logic: comboboxes, multi-selects, dialogs, menus, tabs. Plain HTML (`<details>`, `<select>`, `<dialog>`) still wins where it is enough. The JS budget stays: a widget that Explore doesn't need on first paint loads with `next/dynamic` / `import()`. First use: the hero's brand include / exclude picker (T-141). Measured on release 2: landing page first load 173.6 → 175.2 KB gzip when built (after main's /cars split, #117: landing 164.9 KB, /cars 163.3 KB); the picker chunk (Ariakit combobox) is ~44 KB gzip and loads only when "More filters" is opened.

**Consequences:** apps/web/AGENTS.md rule 4 changes in its own gate PR. The hand-built popovers (`use-popover.ts`: Num, Term ⓘ, Explore) stay for now: they are on Explore's first paint and an Ariakit popover there would eat most of the remaining ~25 KB budget headroom; revisit if the budget is raised or Ariakit's popover chunk proves small (measure first).

## Decision 085: Official WLTP range shown next to our real range; real range leads

**Status:** Accepted (Menno, 2026-11-18)
**Date:** 2026-11-18

**Context:** We lead with our own real-world range (and winter range). People also know and compare the official WLTP figure from ads and brochures; hiding it makes our numbers harder to trust and compare.

**Decision:** Wherever range appears (catalogue cards and rows, filters, car/variant pages, compare, hero cards), show the **real range first and most prominent**, with the **official WLTP range right next to it, in the same section** (smaller or secondary style, labelled "Official (WLTP)"). Winter range stays with the real range. Filters: a range filter defaults to real range, with WLTP available in the same filter group (e.g. a toggle or second slider). Sorting by range defaults to real range. If WLTP is missing, say so; never back-fill it from our estimate.

**Consequences:** T-143 (WS2, with UX for the layout). Data already in the release (`wltp_range_km`); no pipeline change. If decision 084 is not taken by the docs PR that logs people carriers, that PR uses 084 as planned.

## Decision 086: Photos ship as one bundle per release

**Status:** Accepted (WS0, 2026-11-19; engineering call, reversible)
**Date:** 2026-11-19

**Context:** Release 3 has 646 GitHub Release assets, 357 of them photo files (`images/`; the rest are 261 `catalogue/` files and 28 others). GitHub caps content creation at about 500 requests per hour, so a fresh release needs two runs (the second resumes, #162). Every new photo makes this worse. Asked by batch: data / release 3 (WS0 INBOX 2026-11-18 19:14 UTC).

**Decision:** Release photos go into **one asset per release**, `images.tar` (uncompressed: the files are already WebP), next to the other release files.
- The manifest lists the bundle with its size and sha256, plus every file inside it with its path and sha256 (as today), so a single photo can still be checked.
- `ev release fetch` downloads the bundle, checks it, unpacks it into `images/` and checks each file. A release without a bundle (1 to 3) still fetches the old way.
- Photo-only changes (#150) still make a new release; the bundle is rebuilt, never patched.
- The data-refresh `pr` job fails early when a release would upload more than 450 assets, so a run never stops halfway on the limit. With the bundle, a release like release 3 has about 290 assets; if `catalogue/` keeps growing towards the guard, it gets the same bundle treatment (a new decision).
- Licences are unchanged: photos stay out of the CC BY open-data download (Decision 081, 083); the bundle is a delivery format, not a dataset.

**Consequences:** T-150 (WS1). `apps/web/scripts/fetch-release.mjs` (the web build's own fetcher) does not download `images/` today; once the web needs photos (T-146 row thumbnails) it unpacks the bundle the same way, flagged as a cross-lane change. Everything after the fetch reads the unpacked `images/` folder as today. Reversible: go back to one asset per file by dropping the bundle line from the manifest.

## Decision 087: Any number of single facts per car from one maker document (widens Decision 068)

**Status:** Accepted (Menno, 2026-11-19, question popup)
**Date:** 2026-11-19

**Context:** Decision 068 allowed "one figure per car per document". Two batch chats (catalogue, variant queue; WS0 INBOX 2026-11-18 16:14 and 18:53 UTC) cited 2 to 4 headline figures per car from one maker page (power, consumption, DC charging, WLTP) and a reviewer flagged a 10-field sheet as too many, so figures were trimmed. Facts themselves aren't copyrighted; the risk is extracting a substantial part of a maker's table or price list (EU database right). 🟡 reasoned, not legal advice.

**Decision:** From a maker document, any number of single facts per car may reach a release, each with its URL, retrieval date and confidence. Never copy a whole spec table, range table or price list from one document. Everything else in Decision 068 stands, including citing one document for several cars' single facts (e.g. one maker price list feeding a few cars' list prices), and KBA, SDES and EU Safety Gate stay blocked until their reuse terms are checked.

**Consequences:** WS3 may restore figures trimmed under the old reading (T-154). Reviewers check "no whole table, range table or price list" instead of counting figures; the WS3 lane brief says so. Reversible: a stricter reading only drops facts from the next release.

## Decision 088: Newest / older version compares the same trim line, not the whole model (refines Decision 038)

**Status:** Accepted (WS0, 2026-11-19; engineering call, reversible)
**Date:** 2026-11-19

**Context:** The shortlist rules' `newest-version` bonus (+4) and `older-version` penalty compare every variant of one model by `year_start` (`pipeline/ev_pipeline/derive/shortlist.py`, `version_flags`). The 2025 Audi e-tron GT entry trim (T-154, #182) therefore made the 2024 S / RS / RS performance "older" (about −10 points, approved in #184). A new cheaper entry trim isn't a battery or charging update of the higher trims. Asked by batch: catalogue T-154 (WS0 INBOX 2026-11-19 09:15 UTC).

**Decision:** A variant is only compared with variants of the **same trim line**. Lines are formed per model and drivetrain (RWD / FWD / AWD): sort by power, start a new line whenever a variant's power is more than 15 % above the lowest power in the current line. `newest-version` goes to the newest year within that line; `older-version` needs a newer variant in the same line that charges faster (as today). A line with one year gets neither flag. A variant with unknown drivetrain or power is not compared and gets neither flag.

**Consequences:** T-161 (WS1). The rule's back-test (`backtest_rules.py`) must stay at or above today's band match; the R-32 evidence pairs (G6 2025 vs 2024, EV6 2024 vs 2021, IONIQ 5 2024 vs 2022) keep their flags; the e-tron GT 2024 S / RS / RS performance lose the `older-version` flag. The #184 approvals for those rows are replaced by new ones in T-161's gate PR. Reversible: group by model again.

## Decision 089: Migrate agent execution from Claude to Antigravity via an adapter layer

**Status:** Accepted (Menno, 2026-11-26)
**Date:** 2026-11-26

**Context:** Building paused on 2026-11-19 on Claude's token budget and is resuming on Antigravity. The repository's engineering rules (`AGENTS.md`), process (`docs/process/README.md`), review checks (`REVIEW.md`), and task state are already in git, while brand decisions (`claude/brand-design-decisions.md`) and owner working context lived in Claude Project knowledge outside the repo, and several docs reference Claude-era mechanics (`add_repo`, `claude.ai/code` links, session-push `workflow_dispatch` quirks, proxy limits).

**Decision:** Run EV Shortlist agents in Antigravity without rewriting the canonical engineering and process docs:
- Add `GEMINI.md` at the repo root as a thin adapter translating Claude-era mechanics to Antigravity; `AGENTS.md` and `docs/` remain canonical for engineering rules and product scope.
- Add Antigravity rules and workflows under `.agents/` (`rules/talking-to-menno.md`, `workflows/start-coordinator.md`, `start-batch.md`, `fresh-review.md`, `merge-pr.md`, `handoff.md`).
- Move former Claude Project docs into the repo: `docs/design/brand-design-decisions.md` and `docs/process/owner-context.md`, and update all active references outside `_archive/` to `docs/design/brand-design-decisions.md`.
- Keep all existing quality gates unchanged: `Verified: <how>` commits, independent `/fresh-review` before merge, and `sh scripts/merge_ready.sh <pr>` READY right before merging.

**Consequences:** Any Antigravity coordinator or batch conversation can pick up directly from the repo with no external project settings required. Old `claude.ai` links in `CHATS.md` remain as history; new rows use `Antigravity: <conversation title>`. Rule G-64 added in `docs/process/rules.md`. Reversible: `GEMINI.md` and `.agents/` are additive and do not alter `CLAUDE.md` or app/pipeline code.

<!-- Agentic Scaffold v0.5.0 | https://github.com/montymerlin/agentic-scaffold-plugin -->
