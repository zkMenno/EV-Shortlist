# Questions for Menno

WS0 adds questions here (other chats send them via WS0's INBOX). Menno answers inline under **Answer:**. Once answered, WS0 moves the outcome into DECISIONS.md or the task file and moves the question to the closed archive.

Format: `Q-NNN` · task id (if any) · who asked · date.

---

**Only questions Menno must answer live here** (money, legal or licence risk, public or irreversible steps, his accounts and settings, scope). Engineering judgement calls are not questions: agents take the reversible default, log it in DECISIONS or the task file, and move on. Closed and triaged questions: `_archive/questions-closed.md` (archive: open only when Menno asks).

## Open — needs Menno (6)

### Q-003 · Pull requests on `main` · coordinator · 2026-11-15
Right now `main` only blocks force-pushes and deletion. Once code arrives, should `main` require a pull request with green CI (agents can't push straight to `main`)? Recommended: yes, from wave 1.

**Answer:**

### Q-028 · "See listings" URL patterns are guesses · T-008 / T-009 · builder · 2026-11-15
`apps/web/src/config/countries.ts` holds 2–3 marketplace search templates per country, all `verified: false` (best guesses, nothing fetched). **Default:** ship them marked unverified; someone opens each by hand before launch. Cazoo (UK) is skipped because it closed.

**Answer:**

### Q-037 · RDW notice: "do not state the data comes from RDW" · R-02 · coordinator · 2026-11-15
RDW's bijsluiter says reusers may not state that the data comes from RDW, or use its logo or house style. That clashes with showing "Source: RDW" on every number. **Default:** the UI keeps the source id but the label needs your call. Probably the clause targets edited data being passed off as official RDW data; an email to RDW would settle it. Options: label "Dutch vehicle register (open data, CC0)" with a method note, or ask RDW.

**Answer:**

### Q-047 · KilowattApp curves: provenance and likely ev-database.org origin · sources (kilowatt-openev) · builder · 2026-11-15
Upstream docs do not say how curves were obtained (no "measured" anywhere); its own tool generates template curves (`lib/vehicle_creator/charging_details.rb`). 22 records carry `url: https://ev-database.org/...` and `_manually_fixed_fields`, and the suggest form proposes ev-database.org as a source, so some values were probably taken from ev-database.org (no open licence). **Default:** import under the repo's MIT-with-attribution licence as a low-priority fallback; all curves `estimated`, confidence low; specs medium. Is that acceptable given rule 2 ("derived, not copied"), or should `kilowatt-openev` curves stay out of public releases until checked?

**Answer:**

### Q-072 · CCD2 warning in German and French, and Belgium's own wording · T-043 / Decision 017 · web builder · 2026-11-15
The loan calculator shows the CCD2 warning in the page language: EN "Borrowing money costs money." and NL "Let op! Geld lenen kost geld." (as given in the task). DE and FR have no reviewed wording yet, so they fall back to the English sentence (keys `loan.warning` missing in `de.json` / `fr.json` on purpose). Belgium may require its own national wording in Dutch and French (Code of Economic Law), which could differ from the Dutch "Let op! Geld lenen kost geld." used on `/be/nl`. **Default:** EN fallback for DE/FR, NL text on `/be/nl`, until R-03 (lawyer question) gives the exact wording per country and language; then add per-country keys. Needs a legal check before launch (CCD2 applies from 20 Nov 2026).

**Answer:**

### Q-079 · Weekly data refresh: let GitHub Actions open "Data release N" pull requests? · ADDENDUM-6 P4 · pipeline builder · 2026-11-15
One settings switch for you, no cost. `.github/workflows/data-refresh.yml` runs every Monday (and on demand), refreshes the open sources and opens a PR with only the new release folder and its QA report. **To make it work:** GitHub → repo Settings → Actions → General → tick "Allow GitHub Actions to create and approve pull requests". **Good to know:** PRs opened by the workflow's own token don't start CI by themselves; close and reopen the PR (one click) to run CI before you merge. Later option: a small GitHub App token so CI starts on its own (no cost, a bit of setup). **Default until you answer:** the workflow runs; if the setting is off, the PR step fails and the run's summary page still shows what changed. Also open: the S3 snapshot backend (Scaleway) is an interface only tonight; raw snapshots stay on the machine that runs the refresh (Decision 021).

**Answer:**

---

## Recently answered (logged in DECISIONS.md)

### Q-008 · Maker documents and unclear-licence registries · coordinator · 2026-11-15
**Answer:** Yes, single cited facts (Menno, 2026-11-17, popup) — **Decision 068**, widened to any number of single facts per car (never a whole table/price list) in **Decision 087**. KBA, SDES and EU Safety Gate stay blocked until reuse terms are checked.
