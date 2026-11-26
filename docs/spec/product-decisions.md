# Product decisions

One list of the product, data, market, architecture and business decisions, with pointers to the numbered engineering decisions in [DECISIONS.md](../../DECISIONS.md). Moved here from the claude.ai project doc `claude/decisions.md` on 2026-11-17, so every chat reads one copy. Owner: WS0. New product decisions: add a dated line here, and a numbered entry in DECISIONS.md when it changes engineering.

Main spec: https://claude.ai/artifact/3HiNR86a22Fnm2kHxpfctx (tabs: "Master spec v2" = source of truth; "Research & notes"; "Data sources"; "Source matrix"; "Marketplaces"; "Battery & voltage guide"; "Charging buildout"; "Bidirectional & plugs"; "Trip fit"; "Variant finder"). Builders read the mirror in [docs/spec/](.) (repo copy wins). Launch scope: [launch-scope.md](launch-scope.md) (Decision 051).

Brand and design: [docs/design/brand-design-decisions.md](../design/brand-design-decisions.md) (owned by the UX chat; design system https://claude.ai/artifact/EiqvMW5NcFgxFq6c5YHuPP; mirrored in [docs/design/](../design/)).

## Product
- 2026-11-14 — One-liner: EV Database, but built for finding used EVs, across more markets, with the features it's missing. Lean; strict scope guard (Core = phases 0–2, Next = 3–5, Later = parked).
- 2026-11-14 — Finder only (link out); no hosted listings, messaging, payments, leasing deals or own forum.
- 2026-11-14 — Landing page = Explore table: new and used prices side by side; table/cards toggle (remembered); compare tray that never resets; no signup needed. (Since Decision 055 the hero shortlist sits on top of Explore.)
- 2026-11-15 — Simple by default, nerdy on demand: plain-language labels with the technical term underneath; ⓘ tooltip on every term (one or two sentences, no jargon) reading from a glossary_terms table (6 languages, Sveltia-editable); detail switch Simple / Detailed / Nerd (remembered, in the URL); Nerd shows raw values, curves, every source with date and confidence, conflicts, fallback rung and downloads. Five-person normie test before launch (plan: research/R-30).
- 2026-11-14 — Vehicle scope: BEV cars only at launch; PHEVs with 80 km+ electric range = likely Next (own column, kept out of BEV rankings); vans Later (since 2026-11-18: cargo vans only, see the next line).
- 2026-11-18 — Van-based **people carriers (M1 passenger versions) are in** the catalogue (Menno, relayed 2026-11-18 11:27 CET; Decision 084): Mercedes EQV / eVito Tourer / EQT, Citroën ë-Berlingo / ë-SpaceTourer, Peugeot e-Rifter / e-Traveller, Opel Combo-e Life / Zafira-e Life, Toyota Proace (City) Verso, Fiat e-Doblò / e-Ulysse, Nissan e-NV200 Evalia, Renault Kangoo E-Tech (~65k EU cars, 0.7 %). "Vans Later" now means cargo (N1) vans only.
- 2026-11-14 — Catalogue: everything, like EV Database (~1,500 models/variants), with quality tiers (checked / sourced / single source). Top 40 used models hand-checked first.
- 2026-11-14 — Languages at launch: EN, NL, DE, FR, ES, IT.
- 2026-11-14 — Used prices: pre-filled "See listings" searches per country marketplace. Ranges from layer 0 (free published price indices), layer 1 (partner/affiliate feeds), layer 3 (low-rate automated sampling, aggregates only, kill switch per site, legal check first; off, Decision 004); layer 2 (manual sample) as backup.
- 2026-11-15 — Ways to pay (Decision 017): every price switches between buy outright, loan per month (our calculator, typical rates per country, CCD2 warning) and lease per month (partner feeds only; labelled link otherwise). No finance commission at launch; no UK finance/lease links until the FCA question is checked. Launch: loan estimate only.
- 2026-11-15 — Partnerships first: ~8 groups own most marketplaces (Autonex/AutoScout24, Adevinta, OLX Group, Vend, CAR Group, Carsome, Mercado Libre + independents). Pitch Autonex, Adevinta, Vend, OLX Group in Phase 1.
- 2026-11-14 — Accounts light: anonymous-first, passkey/magic link, favourites, shortlists, saved + shared comparisons, dashboard, GDPR export/delete. (Parked at launch.)
- 2026-11-14 — Community: owner data + reviews later; first just link into existing communities and offer "report a data issue".
- 2026-11-14 — Real-world range and charge speed computed ourselves; EV Database only as manual cross-check.
- 2026-11-14 — Real-range sources: Bjørn Nyland (ask permission, credit, sponsorship once revenue exists) plus NAF/Motor El Prix, ADAC, Edmunds, InsideEVs/Out of Spec, Consumer Reports, Spritmonitor. Tests stored with conditions.
- 2026-11-15 — DC charging shown as real numbers, never peak kW alone: average kW and minutes 10–80%, km added in 10/20 min, "peak held for N minutes", claim vs measured, winter time. DC ranking uses km in 20 min.
- 2026-11-15 — New filters EV Database lacks: voltage class (400 V / 800 V / 900 V+ from an editable table, plus a nominal-voltage slider), "fast on older 400 V chargers", chemistry (pros/cons/care popovers, "new" badge for emerging chemistries), battery cooling (air-cooled packs flagged on used cars), "charge to 100% daily". /learn page per chemistry and voltage class.
- 2026-11-15 — Charging buildout (spec tab "Charging buildout"; Decision 012): per-country charging pages from official statistics; /learn "Charging in 2026"; a link-out block to existing tools; ABRP deep link with the car pre-selected. No charger map of our own. Link-outs + learn page = Core 1; country pages + ABRP deep link = Core 2; EAFO Europe comparison = Next. (Launch: learn page only; rest parked, Decision 051.)
- 2026-11-15 — Bidirectional charging + plugs (spec tab; docs/spec/bidirectional-and-connectors.md, research/R-01 corrected by R-25, Decision 011, T-018–T-022): V2H / V2G / AC-route / ISO 15118-20 filters per country, caveat badges from a taxonomy, used-car checklist. From 1 Jan 2027 new/renovated EU wallboxes must speak ISO 15118-20 (protocol, not bidi hardware). US: CCS1 vs NACS per model year (Next, phase 4). (Parked after launch, Decision 051.)
- 2026-11-15 — Trip fit (spec tab "Trip fit"; Decision 013): usage profile picker + places with frequency + winter settings → "range you truly need", Explore column ✓/⚠/✗ + Fit score, hard filter for must-do trips, model-page widget. Model = per-road-band consumption × temperature curve per heater type + warm-up + climb, fallback ladder, P10–P90 band; launch gate = back-test median error <10 % on top-40 used. ABRP stays the trip planner. (Launch: profile picker + winter range in the hero; routed trips parked.)
- 2026-11-15 — Open data release ships at launch (CC BY 4.0 bundle per release, gate-passed sources only) and is the launch hook (Decision 016).
- 2026-11-15 — Variant finder (Decision 019, docs/spec/variant-finder.md): one card per variant, "differences only" toggle and variant change timeline (Core); "spot it in an ad" clue box (Core top 40, Next rest); "which one is it?" finder and NL plate lookup in the browser (Next, Decision 036); listing-link paste via partners (Later).
- 2026-11-15 — Outreach in Menno's name waits until the brand name is chosen. Drafts in docs/outreach/drafts/ (incl. NL/DE/FR versions).
- 2026-11-15 — Hero shortlist ("Used EVs got good.") on top of the landing page; profile filters never drop a car for missing data (Decision 055); launch scope frozen in docs/spec/launch-scope.md (Decision 051).

## Data
- 2026-11-14 — Open data first: no paid or licensed datasets. Sales/registrations from official sources; aggregators as fallback.
- 2026-11-15 — Every data point has 1–2 primary sources plus all available fallbacks (spec tab "Source matrix"; data/sources.yaml, data/field_sources.yaml); coverage report per release; target 80 % of top-40 used models with ≥2 agreeing sources on headline fields; conflicts go to review; licence gate before public release.
- 2026-11-15 — Data model adds Platform and BatteryPack entities and taxonomy tables (voltage_classes, chemistries, cooling_types, glossary_terms), so new architectures and chemistries are a new row, not new code. "Not disclosed" is a real value; inferred values are low confidence.
- 2026-11-15 — Charging sources: Fastned curves (ask permission), Open EV Data (MIT + attribution, drop default curves), NAF El Prix, ADAC, P3 Charging Index, Automobile Propre, Bjørn Nyland. EVKX = manual cross-check only (terms forbid competing databases).
- 2026-11-15 — Added: RDW inspections + defects (CC0) and DVSA MOT history (OGL) for "Known issues"; Aviloo and Car-Pass battery tests; emerging-market registration data (VAHAN, Thailand DLT, INEGI RAIAVL, ABVE, NZ MoT).
- 2026-11-15 — Charging infrastructure data: aggregates only, never point-level charger data. One official primary per country (RVO, Bundesnetzagentur, Avere-France, DfT, AFDC, EV Council), EAFO for cross-country comparison, IEA as global fallback. Licences checked (R-26): BNetzA CC BY 4.0, DfT OGL v3, NDW CC0, AFDC free; EAFO: use now, ask afterwards (Q-094).
- 2026-11-15 — Bidirectional data: taxonomies + BidiCapability and ChargingPort entities; iso15118_20_support defaults to not disclosed, never inferred; facts older than 90 days show "may be out of date".
- 2026-11-15 — Trip fit data: taxonomies road_classes, speed_profiles, temperature_bands, heater_types, usage_profiles; variant fields heat_pump, drag_coefficient, frontal_area, kerb_mass, wheel_size, usable_kwh; condition-tagged consumption_tests; climate ERA5-Land primary, Meteostat second; towns from GeoNames (Decision 036).
- 2026-11-15 — Finance rates: ECB MIR consumer-credit APRC for euro countries, Bank of England for the UK; NL blank until an official series exists (Decision 036, R-20).
- 2026-11-14 — Published open data licence: CC BY 4.0. ODbL and CC BY-SA inputs kept separate (Washington DOL internal only; RVO cross-check only).

## Markets
- 2026-11-14 — Launch NL, DE, FR, BE, UK; then US + Australia (NZ and Canada as cheap extras); then rest of Europe. China parked. Adding a country = config + data (marketplace block, charging block).
- 2026-11-15 — Proposed emerging order (not yet confirmed by Menno): Türkiye, South Korea, Thailand/Malaysia/Indonesia, Brazil/Chile, Mexico, Vietnam; India later. Readiness check (R-31): Türkiye first.

## Architecture
- 2026-11-14 — Lean monolith + data pipeline: Next.js + Postgres + Python jobs, open-source stack, staff area in-app.
- 2026-11-15 — Hosting on Menno's shared AppInfra server (Hetzner CAX31, Arm, 16 GB, next to GardenLayer and Dungeon Tracker): Caddy, CI → Arm image → SSH deploy, backups, watchdog, Umami, Scaleway email, Sveltia, staging. No Coolify, Brevo or Dagster (pg-boss + scheduled Python jobs). Raw snapshots in Scaleway Object Storage. Decision 006.
- 2026-11-15 — Own database + login inside the shared Postgres 17 + PostGIS server. Limits: ev-web 768 MB / 1 CPU, ev-web-staging 256 MB / 0.5 CPU, ev-jobs 1 GB at low priority, nightly 00:30–02:30 UTC. Upgrade to CAX41 or move GardenLayer when busy evenings show >10 GB or >70 % CPU for weeks.
- 2026-11-15 — Routing for Trip fit: self-hosted Valhalla on a separate small Hetzner box (~€5–15/month, sizing test first); hosted free routing APIs staging only; scoring in the browser; addresses never stored, coordinates rounded ~200 m, no route logging.
- 2026-11-15 — Public repo; code AGPL-3.0, data CC BY 4.0 (Decision 002). Sampling targets and partner secrets never in the repo (Decision 004). arm64 images built in GitHub Actions (Decision 005). Published releases move out of git (Decision 035). URLs /{country}/{lang}/ + hreflang (Decision 015).

## Workflow
- 2026-11-15 — Agents coordinate through markdown files in the repo; workstreams WS0–WS5 + UX (+ QA from 17 Nov), one owner per path (Decision 014). Public web access pre-approved; logins, forms, payments and posting need Menno.
- 2026-11-17 — One process doc ([docs/process/README.md](../process/README.md)) with the verify-and-learn loop; QUESTIONS.md holds only what Menno must answer; product decisions live here, not in the project.

## Business
- 2026-11-14 — Ambition: bootstrapped/profitable + mission-driven. Revenue: affiliate/leads first, battery-test referrals, supporter membership, paid API later. No ads, no paid rankings.
- 2026-11-15 — Working title "EV Shortlist" (Decision 018); EV Field Guide as backup; final name + domain still open (docs/brand/name-shortlist.md). Name lives in config only.

## Still open (Menno)
Live list: [QUESTIONS.md](../../QUESTIONS.md). Product-level items not yet there: final name + domain; legal check on price sampling and finance display (research/R-03; written opinion likely €1.5–4k, estimate; layer 3 off until then); affiliate links live from day 1?; confirm the emerging-market order.
