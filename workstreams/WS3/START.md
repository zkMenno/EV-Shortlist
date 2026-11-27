# WS3 lane brief: catalogue curation and content

For any batch chat whose prompt touches this lane. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3; rules: [rules.md](../../docs/process/rules.md). The lane keeps the hand-made parts of the catalogue right: makes, models, generations and variants in the seed, taxonomy tables, cited maker-document facts, photos, glossary, /learn texts, editorial lists and per-country config.

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`.
2. Read `AGENTS.md`, `REVIEW.md` (from `origin/main`), `docs/process/README.md`, your task files, this brief, `data/seed/README.md`, `data/taxonomy/README.md`.
3. Before each task and again before its first push: check open PRs and `git ls-remote --heads origin | grep <task-id>`; stop if another chat has it (G-41). Two WS3 chats built T-136 twice.
4. Spec only where the task points: `docs/spec/battery-and-voltage-guide.md`, `bidirectional-and-connectors.md`, `charging-buildout.md`, `trip-fit.md` §4 and §9, `marketplaces.md`, `source-matrix.md` ("Honest gaps"). Scope: `launch-scope.md` (Decision 051). Vehicle scope: BEV cars incl. van-based people carriers (M1); cargo vans later (Decision 084).

## What the lane owns
`data/seed/`, `data/manual/`, `data/taxonomy/`, `content/`, `config/` (countries, popularity, price-index; no secrets, Decision 004), plus the lists the lane maintains in `data/images/` (photos, press terms) and `data/editorial/` (popular used). The pipeline (WS1) validates and releases what you write; the web app (WS2) renders it. Changes in `pipeline/` (guard tests, matcher asks) or the schema: one line in `workstreams/WS0/INBOX.md`, and flag any one-line cross-lane change in the PR. Decision numbers: block 057–061.

## Lane rules
- Every hand-entered fact has a source URL, retrieval date and confidence. Maker documents: cite single facts by URL and date (single cited maker facts ship, Decision 068; any number of facts per car, never a whole table, range table or price list, Decision 087); never copy tables wholesale. Nothing from EV Database, marketplaces or Kilowatt rows that cite ev-database.org.
- Never fill from memory. Unknown = `not-disclosed` or empty. `iso15118_20_support` defaults to not disclosed, never inferred.
- Seed rows are our own structure; one generation per real platform or facelift split (Decision 057). A new model without enough facts for a card stays out of the hero.
- Taxonomies are rows, not code: a new chemistry, voltage class, caveat or profile is a new row with plain-language text.
- Writing for users: plain words first, technical term underneath, one or two sentences per tooltip, no jargon, no cheerleading. Every claim on a /learn page links to its rule or statistic. English first (Decision 082); other languages marked `review: needed`.
- Photos: Wikimedia Commons under CC BY / CC BY-SA, CC0 or worldwide PD (Decisions 081, 083), licence checked on the file page; credit line under every photo. Press photos only for makes marked `allowed` in `data/images/press-terms.yaml`.
- Owner verdicts are one person's opinion: label them so.

## Verify before every push
- `sh data/seed/data_qa.sh` (G-45, G-57, G-61): runs all six pre-push steps (`validate_seed`, `validate_variants`, `validate_taxonomy`, `backtest_rules`, `ev release approvals`, `pytest -m seed`).
- Seed, manual or taxonomy change: the `verify-pipeline` skill (`pipeline/.claude/skills/verify/SKILL.md`): `ev verify --base-release-from origin/main` (G-56) and plain `ev verify` against the latest published release. Approvals in `config/approved_changes.yaml` go in their own gate PR (G-54).
- After any seed change, print the new generations' built rows (battery, WLTP, power) and look at them before the PR: only that caught the e-tron GT facelift pack.
- Matching regression for seed or alias changes: load main's and the branch's `models.yaml` with `ev_pipeline.match.seed.load_seed`, run `find_model_noted` / `find_by_source_alias` over every staging record, diff the model ids (0 changes for previously matched records).
- Any generated image list: look at a contact sheet before the PR (rear views, interiors, wrong generation).
- Commits end with `Verified: <how>`.

## Gotchas
- EEA per-year registrations: `python3 -I research/R-41-catalogue-coverage/pull_eea.py /tmp/t136` (~8 min), then R-41's `coverage.py`.
- RDW BEV years per name: `data/staging/rdw.records.jsonl`, only `record_key` starting `m9d7-ebf2:` (the others repeat the count per spec). RDW's API rate-limits grouped queries (429): use the staged file.
- Commons, Wikipedia and Wikidata rate-limit this egress: batch searches (6 per query).
- OpenEV ignores `markets`: China-only files (NEDC/CLTC) would ship as EU variants (e.g. Leapmotor T03); OpenEV's 2024–2025 e-tron GT files repeat the old pack.
- `ev manual check` errors on facts targeting a retired id (#131; check `data/seed/retired_ids.yaml` before adding manual facts).
- US gov portals (`dis.epa.gov`, CARB): check the PDF's own copyright stamp before attributing US Gov PD (G-68).

## Done (per task)
Acceptance criteria ticked · data_qa.sh and verify pass · every new fact cited · English complete · PR with evidence · Status + Handoff notes in the task file · fresh review before merge · what WS1/WS2 can now use, in one INBOX line.

## Finish the batch
State lives in task files and PRs, not here. When the batch is done or blocked: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · …`, with the four retro answers or a link to them), then stop. No STATUS or HANDOFF files.

## Open lane threads (non-blocking / parked; current queue lives in BOARD.md and workstreams/WS0/HANDOFF.md)
- Post-release-4 G-62 cleanup: 10 report-only `missing_input_flag_changes` vs pre-Decision-088 release 3 (T-167 follow-up).
- Remaining `no-variant` groups after T-162 (`kia-ev5-gen1`, `bmw-ix3-gen2`, `mg-mg5-gen1`, `opel-ampera-e-gen1`, `kia-ev4-gen1`, `opel-frontera-gen1`, `xpeng-g9-gen1`).
- Generation-level platform links where a maker page names the platform (`stellantis-stla-medium`, `mercedes-eva2` unused): e-3008/e-5008, EQE/EQS (+SUV). Cited only.
- A-36 S4 NL loan rate only with an official sourced series; A-36 S3 /learn with Menno; price samples DE/FR/BE/UK; heat pump gaps; La Centrale slugs.
- T-041 `verified` waits for Menno's tap check (`workstreams/WS3/T-041-checklist.md`).
