"use client";
// The landing-page hero (T-080, Decision 051): country → 4-tap profile picker → budget with a rough
// monthly estimate → optional refine → top 10, the first five marked "Your shortlist".
// T-132: one question per screen (progress road, answer tiles, answer trail); the step is in the URL
// (`q`, src/lib/hero-state.ts) and every step change is a history entry, so Back = previous question.
// The server renders the first result from the URL; the browser re-ranks on every change with the
// same pure functions (src/lib/shortlist.ts) once the compact catalogue has loaded. Scores come from
// the release's shortlist_scores.json (Decision 065); without it the hero says so and ranks nothing. All state is in
// the URL; the refine filters are Explore's filters, kept in step through src/lib/filter-bus.ts.
import dynamic from "next/dynamic";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { BrandChips } from "./BrandChips";
import type { Body, Country, Currency } from "@ev/schema";
import { COUNTRIES, COUNTRY_SLUGS, isServed, type CountrySlug, type Lang } from "@/config/countries";
import { makeT, type Dict, type MsgKey, type T } from "@/i18n/t";
import { loadClientCatalogue } from "@/lib/client-catalogue";
import { compareStore, COMPARE_MAX } from "@/lib/compare-store";
import type { ExploreRow } from "@/lib/explore-data";
import { onFilters, publishAnswers, publishFilters } from "@/lib/filter-bus";
import { effectiveLoan, monthlyFor, type FinanceProfileView } from "@/lib/finance";
import { formatMoney, formatNumber, formatYears, localeFor } from "@/lib/format";
import { nerdValue, numberParts } from "@/lib/nerd-value";
import { priceHowText } from "@/lib/price-how";
import {
  DRIVING_STEPS,
  drivingQuestion,
  heroFromSearchParams,
  heroStep,
  heroToSearchParams,
  mergeHeroIntoUrl,
  nextStep,
  prevStep,
  roadStop,
  type HeroState,
  type HeroStep,
} from "@/lib/hero-state";
import { AnswerTiles, AnswerTrail, BackChevron, Pencil, ProgressRoad, type TrailItem } from "./HeroSteps";
import { buildListingUrl, type ListingSite } from "@/lib/listing-url";
import {
  AREAS,
  asksTrips,
  CHARGES,
  presetsFor,
  rankHero,
  SHORTLIST_N,
  reasons,
  resolveProfile,
  ROLES,
  TRIPS,
  type ActivePreset,
  type Answers,
  type Condition,
  type HeroPick,
  type HeroResult,
  type PresetField,
  type ResolvedProfile,
  type UsedBands,
} from "@/lib/shortlist";
import { BODIES, defaultFilters, type ExploreFilters } from "@/lib/state";
import type { UiTerm } from "@/lib/taxonomy";
import { useLevel } from "@/lib/use-level";
import { useListStore } from "@/lib/use-list-store";
import { generationHref } from "@/app/[country]/[lang]/ev/_lib/routes";
import { LoanBox, LoanWarning, useLoanSettings, type FinanceUi } from "./PriceMode";
import { profileName } from "./SuggestedSort";
import { TermInfo, type TermText } from "./Term";
import { OfficialRange } from "./OfficialRange";
import { CarThumb, photoText, type PhotoRef } from "./CarPhoto";
import { generationTitle } from "@/lib/generation-title";
import { HeroSheet } from "./HeroSheet";
import { numLabels } from "./num-labels";
import { ParallaxScene } from "@/components/parallax/ParallaxScene";
import { city as cityScene, village as villageScene } from "@/components/parallax/scenes.generated";

export interface HeroProps {
  country: CountrySlug;
  code: Country;
  currency: Currency;
  lang: Lang;
  dict: Dict;
  base: string;
  initial: HeroState;
  /** Ranked on the server from the URL; null when the picker isn't answered yet. */
  initialResult: HeroResult | null;
  /** The release has shortlist_scores.json (Decision 065). */
  hasScores: boolean;
  /** Release number (Nerd mode names where the scores come from). */
  release: number;
  /** Source id → name (Nerd mode: where a price comes from). */
  sources: Record<string, string>;
  dataUrl: string;
  total: number;
  finance: FinanceProfileView | null;
  usedBands: UsedBands;
  nowYear: number;
  makes: { id: string; name: string }[];
  /** This country's "See listings" sites, best first. */
  listingSites: ListingSite[];
  terms: Record<string, UiTerm | undefined>;
  /** Launch /learn guides that exist (winter range, charging in 2026, batteries). */
  learnLinks?: { slug: string; title: string; href: string }[];
  /** Generation id → its photo from the release (T-146 row thumbnails); absent = no photo. */
  photos?: Record<string, PhotoRef>;
}

// Five amounts + "No limit" = the 3×2 grid of the budget step (T-132).
const QUICK_BUDGETS: Record<Currency, number[]> = {
  EUR: [15000, 20000, 25000, 30000, 40000],
  GBP: [12000, 17000, 20000, 25000, 35000],
};

/** Preset field → the factor label that names it ("not known yet" lists). */
const PRESET_FACTOR: Partial<Record<PresetField, string>> = {
  dc_km_per_20min: "dc-speed",
  real_range_km: "winter-range",
  boot_l: "space",
  length_mm: "size",
  ac_kw: "ac-speed",
};

/** Score factors for parked features (bidirectional charging is parked, launch-scope.md): they still
 *  count in the release score, but the card never names them in its "not known yet" line (A-36). */
const PARKED_FACTORS: ReadonlySet<string> = new Set(["v2l", "home-power"]);

const toggleCls =
  "inline-flex min-h-11 items-center rounded-md border border-slate-400 bg-white px-3 py-2 text-sm aria-pressed:border-blue-800 aria-pressed:bg-blue-100 aria-pressed:font-semibold";
const inputCls = "w-32 rounded-md border border-slate-400 bg-white px-3 py-2 text-base tabular-nums";

// Ariakit brand picker (T-141, Decision 056): loads only once the refine step is opened. Only the
// 48 px input is in the chunk (the placeholder has its exact height); label, hint and the picked
// brands (BrandChips) render straight away, so nothing jumps while it arrives.
const BrandPicker = dynamic(() => import("./BrandPicker").then((m) => m.BrandPicker), {
  ssr: false,
  loading: () => <div className="h-12" aria-hidden="true" />,
});

function cap(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s;
}

function presetLabel(p: ActivePreset, t: T, locale: string): string {
  if (p.field === "length_mm" && p.max !== undefined) {
    return t("hero.preset.length_mm.max", { n: formatNumber(p.max / 1000, locale, 1) });
  }
  const n = formatNumber(p.min ?? p.max ?? 0, locale, 0);
  return t(`hero.preset.${p.field}.${p.min !== undefined ? "min" : "max"}` as MsgKey, { n });
}

// ── Home-hero scene (UX design v6): village, or city for city answers; day and night, layered ──

function Scene({ city }: { city: boolean }) {
  // Depth + parallax (Menno 2026-11-17): flat SVG first, drifting layers on top when motion is allowed.
  return (
    <div className="mx-auto w-full max-w-[14rem] md:max-w-[22rem]">
      <ParallaxScene scene={city ? cityScene : villageScene} testId="hero-scene" />
    </div>
  );
}

// ── Small building blocks ───────────────────────────────────────────────────────────────────

function NumberSelect({
  label,
  value,
  options,
  onChange,
  t,
  testid,
}: {
  label: string;
  value: number | null;
  options: number[];
  onChange: (v: number | null) => void;
  t: T;
  testid: string;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      <select
        id={id}
        value={value === null ? "" : String(value)}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="mt-1 rounded-md border border-slate-400 bg-white px-3 py-2 text-base"
        data-testid={testid}
      >
        <option value="">{t("hero.refine.any")}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── The hero ────────────────────────────────────────────────────────────────────────────────

export function Hero(props: HeroProps) {
  const t = useMemo(() => makeT(props.dict), [props.dict]);
  const locale = localeFor(props.lang);
  const level = useLevel();
  const [hero, setHero] = useState<HeroState>(props.initial);
  const [rows, setRows] = useState<ExploreRow[] | null>(null);
  const [copied, setCopied] = useState(false);
  // The loan settings box renders only when opened (one LoanBox per page until then).
  const [loanOpen, setLoanOpen] = useState(false);
  const [refineOpen, setRefineOpen] = useState(false);
  // T-146: on phones (< 640 px) the answers sidebar opens as a bottom sheet from the results.
  const [sheet, setSheet] = useState(false);
  const sheetOpen = useRef(false);
  /** The sheet pushed a history entry (so the phone's Back button closes it). */
  const sheetPushed = useRef(false);
  /** history.back() is on its way (popstate is async): a second close in the meantime must not go back again. */
  const sheetClosing = useRef(false);
  const [dirty, setDirty] = useState(false);
  const lastUrl = useRef(heroToSearchParams(props.initial).toString());
  // Focus moves to the new question's heading after a step change (not on first paint).
  const focusStep = useRef(false);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [loanSettings, setLoanSettings] = useLoanSettings();
  const loan = useMemo(() => effectiveLoan(props.finance, loanSettings), [props.finance, loanSettings]);
  const money = (n: number) => formatMoney(n, props.currency, locale);
  const termText: TermText = { about: t("term.about"), learnMore: t("term.learnMore") };
  // ⓘ for a glossary id; renders nothing until the release has the term (T-100 ids).
  const tip = (id: string) => <TermInfo term={props.terms[id]} base={props.base} text={termText} />;
  const qid = useId();
  const step = heroStep(hero);
  // The latest state for the popstate handler (it is registered once).
  const heroRef = useRef(hero);
  useEffect(() => {
    heroRef.current = hero;
  }, [hero]);

  useEffect(() => {
    let live = true;
    void loadClientCatalogue(props.dataUrl).then((c) => {
      if (live && c) setRows(c.rows);
    });
    return () => {
      live = false;
    };
  }, [props.dataUrl]);

  // Explore below changed a filter: take it over (same params, one URL).
  useEffect(() => onFilters("hero", (filters) => setHero((h) => ({ ...h, filters: { ...filters, tripFit: false } }))), []);

  // State → URL (replaceState: no round trip; the link stays shareable). Step changes push their own
  // history entry in goTo(), so the back button goes to the previous question (T-132).
  useEffect(() => {
    const qs = heroToSearchParams(hero).toString();
    if (qs === lastUrl.current) return;
    lastUrl.current = qs;
    window.history.replaceState(null, "", mergeHeroIntoUrl(window.location.href, hero));
  }, [hero]);

  // Back / forward between questions: the URL is the state.
  useEffect(() => {
    const onPop = () => {
      if (sheetOpen.current) {
        // Back closed the sheet (T-146). The entry we land on still holds the address from before the
        // sheet opened: write today's answers into it, so nothing changed in the sheet is lost.
        sheetOpen.current = false;
        sheetPushed.current = false;
        sheetClosing.current = false;
        setSheet(false);
        lastUrl.current = heroToSearchParams(heroRef.current).toString();
        window.history.replaceState(null, "", mergeHeroIntoUrl(window.location.href, heroRef.current));
        return;
      }
      const s = heroFromSearchParams(new URLSearchParams(window.location.search));
      lastUrl.current = heroToSearchParams(s).toString();
      focusStep.current = true;
      setDirty(true);
      setHero(s);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => () => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
  }, []);

  useEffect(() => {
    if (!focusStep.current) return;
    focusStep.current = false;
    document.getElementById(`${qid}-${step}`)?.focus();
  }, [step, qid]);

  const writeUrl = (s: HeroState, mode: "push" | "replace") => {
    lastUrl.current = heroToSearchParams(s).toString();
    const href = mergeHeroIntoUrl(window.location.href, s);
    if (mode === "push") window.history.pushState(null, "", href);
    else window.history.replaceState(null, "", href);
  };

  const update = (patch: Partial<HeroState>) => {
    setDirty(true);
    setCopied(false);
    setHero((h) => ({ ...h, ...patch }));
  };
  /** Show another question (a new history entry). "results" is the default screen, so no q. */
  const goTo = (to: HeroStep, from: HeroState = hero) => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    // A change button inside the phone sheet opens a question: the sheet goes (its history entry
    // stays behind as the results, so Back from the question returns to them).
    if (sheetOpen.current) {
      sheetOpen.current = false;
      sheetPushed.current = false;
      sheetClosing.current = false;
      setSheet(false);
    }
    const s: HeroState = { ...from, step: to === "results" ? null : to };
    writeUrl(s, "push");
    focusStep.current = true;
    setDirty(true);
    setCopied(false);
    setHero(s);
  };
  const setAnswers = (patch: Partial<Answers>) => {
    const answers = { ...hero.answers, ...patch };
    update({ answers, presetsOff: [] });
    publishAnswers(answers);
    return answers;
  };
  /** Answer the current question, show the tick, then move on (≈250 ms; instant with reduced motion). */
  const answer = (patch: Partial<Answers>) => {
    const answers = setAnswers(patch);
    const here: HeroState = { ...hero, answers, presetsOff: [], step };
    writeUrl(here, "replace");
    const go = () => goTo(nextStep(step, answers), here);
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) go();
    else advanceTimer.current = setTimeout(go, 250);
  };
  const setFilters = (filters: ExploreFilters) => {
    update({ filters });
    publishFilters({ filters, from: "hero" });
  };

  const rp = useMemo(() => resolveProfile(hero.answers), [hero.answers]);
  const presets = useMemo(() => (rp ? presetsFor(rp) : []), [rp]);
  const result: HeroResult | null = useMemo(() => {
    if (!rp) return null;
    if (!rows) return dirty ? null : props.initialResult;
    return rankHero(rows, rp, {
      country: props.code,
      cond: hero.cond,
      budget: hero.budget,
      filters: hero.filters,
      presetsOff: hero.presetsOff,
      usedBands: props.usedBands,
      nowYear: props.nowYear,
    }, { hasScores: props.hasScores });
  }, [rp, rows, dirty, hero, props.code, props.usedBands, props.nowYear, props.initialResult, props.hasScores]);

  const monthly = hero.budget !== null ? monthlyFor(hero.budget, loan) : null;
  const ui: FinanceUi = {
    t,
    locale,
    currency: props.currency,
    code: props.code,
    level,
    base: props.base,
    terms: props.terms,
    termText,
  };

  /** Another country is another page: same answers, next question. */
  const countryHref = (slug: CountrySlug) => {
    const lang = isServed(slug, props.lang) ? props.lang : COUNTRIES[slug].defaultLang;
    const qs = heroToSearchParams({ ...hero, step: nextStep("country", hero.answers) }).toString();
    return `/${slug}/${lang}${qs ? `?${qs}` : ""}`;
  };
  const pickCountry = (slug: CountrySlug) => {
    if (slug === props.country) goTo(nextStep("country", hero.answers));
    else window.location.assign(countryHref(slug));
  };

  const share = () => {
    void navigator.clipboard?.writeText(window.location.href).then(
      () => setCopied(true),
      () => setCopied(false),
    );
  };

  const openSheet = () => {
    if (sheetOpen.current || sheetClosing.current) return;
    window.history.pushState(null, "", window.location.href);
    sheetPushed.current = true;
    sheetOpen.current = true;
    setSheet(true);
  };
  /** Close button, Escape, swipe down, tap outside, wider screen: all go through Back when the
   *  sheet added a history entry, so the entry never stays behind. */
  const closeSheet = () => {
    // Double tap, Escape + tap, swipe + tap: one Back only (review #235: a second Back left the results).
    if (!sheetOpen.current || sheetClosing.current) return;
    if (sheetPushed.current) {
      sheetClosing.current = true;
      window.history.back();
      return;
    }
    sheetOpen.current = false;
    setSheet(false);
  };

  // ── What the visitor said so far (trail pills, T-132) ──
  const a = hero.answers;
  const stop = roadStop(step);
  const trail: TrailItem[] = [];
  if (stop > 0) trail.push({ key: "country", text: t(`hero.country.${props.country}` as MsgKey), to: "country" });
  if (stop === 1) {
    for (const st of DRIVING_STEPS) {
      if (st === step || (st === "trips" && !asksTrips(a))) continue;
      const v = a[st];
      if (v !== null) trail.push({ key: st, text: t(`hero.a.${st}.${v}` as MsgKey), to: st });
    }
  } else if (stop >= 2 && rp) {
    // After step 2 the four answers collapse into the profile name.
    trail.push({ key: "profile", text: profileName(rp, t), to: "role" });
  }
  // Desktop sidebar on the results (T-132 part 2): every answer with its own change button.
  const sideAnswers: SideAnswer[] = [{ key: "country", label: t("hero.side.country"), value: t(`hero.country.${props.country}` as MsgKey), to: "country" }];
  for (const st of DRIVING_STEPS) {
    if (st === "trips" && !asksTrips(a)) continue;
    const v = a[st];
    if (v !== null) sideAnswers.push({ key: st, label: t(`hero.side.${st}` as MsgKey), value: t(`hero.a.${st}.${v}` as MsgKey), to: st });
  }
  sideAnswers.push({
    key: "budget",
    label: t("hero.side.budget"),
    value: `${hero.budget === null ? t("hero.summary.noLimit") : t("hero.summary.upTo", { amount: money(hero.budget) })} · ${t(`hero.summary.cond.${hero.cond}` as MsgKey)}`,
    to: "budget",
  });
  const allCarsQuery = (() => {
    const q = heroToSearchParams({ ...hero, step: "results" });
    q.delete("q");
    if (rp) q.set("sort", "-suggested");
    return q.toString();
  })();
  const dq = drivingQuestion(step, a);
  const stepLine = dq ? t("hero.stepQuestion", { n: 2, q: dq.n, of: dq.of }) : t("hero.stepOf", { n: stop + 1 });
  const titleId = `${qid}-${step}`;
  const tiles = <V extends string>(kind: "role" | "trips" | "charge" | "area", values: readonly V[], hints: readonly V[] = []) =>
    values.map((v) => ({
      value: v,
      label: t(`hero.a.${kind}.${v}` as MsgKey),
      hint: hints.includes(v) ? t(`hero.hint.${kind}.${v}` as MsgKey) : undefined,
    }));
  const refineCount = activeRefine(hero.filters) + (a.keep8 ? 1 : 0);

  const refine = (summary: string) => (
    <details className="mt-4" data-testid="hero-refine" open={refineOpen} onToggle={(e) => setRefineOpen(e.currentTarget.open)}>
      <summary className="evs-lnk cursor-pointer">{summary}</summary>
      {/* "Keep it 8 years" lives here (T-132): its scores don't exist yet, so it doesn't take a question slot. */}
      <div className="mt-3 flex items-center gap-1">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          {/* The ⓘ sits next to the label, not inside it (Term.tsx): inside, its text joins the checkbox's name. */}
          <input type="checkbox" checked={a.keep8} onChange={(e) => setAnswers({ keep8: e.target.checked })} className="h-5 w-5" data-testid="hero-keep8" />
          {t("hero.keep8")}
        </label>
        {tip("keep-8-years")}
      </div>
      {/* The release scores have no keep-8-years combination yet (T-069 combos), so the box is
          remembered but can't change the order: say so rather than pretend (Decision 065). */}
      {a.keep8 ? <p className="text-xs text-slate-700" data-testid="hero-keep8-note">{t("hero.keep8.pending")}</p> : null}
      <Refine filters={hero.filters} onChange={setFilters} makes={props.makes} nowYear={props.nowYear} t={t} open={refineOpen} />
    </details>
  );

  const back = (
    <button type="button" className="evs-lnk" onClick={() => goTo(prevStep(step, a))} data-testid="hero-back">
      <BackChevron />
      {t("hero.back")}
    </button>
  );

  const question = (() => {
    switch (step) {
      case "country":
        return (
          <>
            <AnswerTiles
              name="country"
              title={t("hero.ask.country.title")}
              titleId={titleId}
              help={t("hero.ask.country.help")}
              columns={2}
              tiles={COUNTRY_SLUGS.map((slug) => ({ value: slug, label: t(`hero.country.${slug}` as MsgKey) }))}
              value={props.country}
              onPick={() => undefined}
              onAnswer={pickCountry}
            />
            <p className="mt-4 text-[15px] text-[var(--ink-2)]">{t("hero.ask.country.foot")}</p>
          </>
        );
      case "role":
      case "trips":
      case "charge":
      case "area": {
        const kind = step;
        const values = { role: ROLES, trips: TRIPS, charge: CHARGES, area: AREAS }[kind] as readonly string[];
        const hints = { role: [], trips: ["never", "few_a_year", "often"], charge: CHARGES, area: [] }[kind] as readonly string[];
        return (
          <>
            <AnswerTiles
              name={kind}
              title={t(`hero.ask.${kind}.title` as MsgKey)}
              titleId={titleId}
              help={kind === "trips" ? undefined : t(`hero.ask.${kind}.help` as MsgKey)}
              info={kind === "area" ? tip("home-area") : undefined}
              tiles={tiles(kind, values, hints)}
              value={a[kind]}
              onPick={(v) => setAnswers({ [kind]: v } as Partial<Answers>)}
              onAnswer={(v) => answer({ [kind]: v } as Partial<Answers>)}
            />
            <div className="evs-qnav">
              {back}
              <span className="text-[15px] text-[var(--ink-2)]">{t("hero.tapToGo")}</span>
            </div>
          </>
        );
      }
      case "budget":
        return (
          <>
            <h2 id={titleId} tabIndex={-1} className="evs-q__title outline-none">
              {t("hero.ask.budget.title")}
            </h2>
            {/* The ⓘ sits outside the heading: the heading names the budget field. */}
            <p id={`${titleId}-help`} className="evs-q__help">
              {t("hero.ask.budget.help")} {tip("budget")}
            </p>
            <BudgetField value={hero.budget} currency={props.currency} t={t} money={money} labelId={titleId} locale={locale} onChange={(budget) => update({ budget })} />
            <div className="evs-month" data-testid="hero-monthly">
              {hero.budget === null ? (
                <p>{t("hero.budget.noLimitNote")}</p>
              ) : monthly ? (
                <>
                  <p className="text-lg font-bold">
                    {t("hero.monthly", { amount: money(monthly.monthly) })} <TermInfo term={props.terms.loan} base={props.base} text={termText} />
                  </p>
                  <p>
                    {t("hero.monthly.how", {
                      deposit: formatNumber(loan.depositPct, locale, 1),
                      term: loan.termMonths,
                      apr: formatNumber(loan.aprPct, locale, 2),
                    })}
                  </p>
                </>
              ) : (
                <p>{t("hero.monthly.noRate")}</p>
              )}
              {hero.budget !== null ? <LoanWarning t={t} /> : null}
              <details className="mt-1" onToggle={(e) => setLoanOpen(e.currentTarget.open)}>
                <summary className="min-h-11 cursor-pointer py-2 text-[var(--link)] underline underline-offset-2">{t("hero.monthly.edit")}</summary>
                {loanOpen ? <LoanBox profile={props.finance} settings={loanSettings} onChange={setLoanSettings} ui={ui} price={hero.budget} /> : null}
              </details>
            </div>
            <fieldset className="mt-5" data-testid="hero-q-cond">
              <legend className="text-base font-bold">{t("hero.cond.label")}</legend>
              <div className="evs-seg">
                {(["used", "new", "any"] as const).map((c) => (
                  <label key={c}>
                    <input type="radio" name="hero-cond" value={c} checked={hero.cond === c} onChange={() => update({ cond: c })} className="sr-only" data-testid={`hero-cond-${c}`} />
                    {t(`hero.cond.${c}` as MsgKey)}
                  </label>
                ))}
              </div>
            </fieldset>
            <button type="button" className="evs-cta" onClick={() => goTo("results")} data-testid="hero-show">
              {t("hero.cta")}
            </button>
            <div className="evs-qnav mt-2">
              {back}
              <button type="button" className="evs-lnk" onClick={() => setRefineOpen((o) => !o)} aria-expanded={refineOpen} data-testid="hero-more-filters">
                {t("hero.step4")}
              </button>
            </div>
            {refineOpen ? refine(t("hero.step4")) : null}
          </>
        );
      default:
        return null;
    }
  })();

  const roadLabels: [string, string, string, string] = [t("hero.road.country"), t("hero.road.driving"), t("hero.road.budget"), t("hero.road.shortlist")];
  const asking = step !== "results";

  return (
    <div className="evs-hero evs-tex evs-tex--map evs-tex--no-sun rounded-lg border border-slate-300 bg-[var(--paper-sea)] p-4 shadow-[var(--shadow-sticker)] sm:p-6" data-testid="hero" data-step={step}>
      {/* One scene, placed by the grid: phone = under the title on the first question only; desktop =
          beside the questions (T-132 frames t132-m1 and t132-d1). Results take the whole width. */}
      <div className={`grid items-start gap-x-6 ${asking ? "md:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]" : ""}`}>
        <div className={`min-w-0 md:col-start-1 md:row-start-1 ${step === "country" ? "" : "sr-only md:not-sr-only"}`}>
          <h1 className="font-[family-name:var(--font-display)] text-[2.375rem] font-extrabold leading-tight tracking-tight sm:text-[3.25rem]">{t("hero.title")}</h1>
          <p className="mt-3 max-w-2xl text-lg text-[var(--ink-2)]">{t("hero.intro")}</p>
        </div>
        {asking ? (
          <div className={`mt-4 md:col-start-2 md:row-span-2 md:row-start-1 md:mt-0 md:block ${step === "country" ? "" : "hidden"}`}>
            <Scene city={a.area === "city"} />
          </div>
        ) : null}
        <div className="min-w-0 md:col-start-1 md:row-start-2">
          {asking ? (
            <section aria-labelledby={titleId} className="-mx-1 mt-6 max-w-[40rem] rounded-xl border-[1.5px] border-[var(--line)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sticker)] sm:mx-0 sm:px-8 sm:py-7" data-testid="hero-panel">
              <ProgressRoad now={stop} labels={roadLabels} label={t("hero.road.label")} doneText={t("hero.road.done")} />
              {trail.length ? (
                <div className="mt-4">
                  <AnswerTrail items={trail} onGo={(to) => goTo(to as HeroStep)} label={t("hero.trail.label")} changeLabel={(answer) => t("hero.trail.change", { answer })} />
                </div>
              ) : null}
              <div key={step} className="evs-q__step mt-4">
                <p className="evs-q__count" data-testid="hero-stepline">
                  {stepLine}
                </p>
                {question}
              </div>
            </section>
          ) : (
            <div className="mt-6">
              <div className="max-w-[40rem]">
                <ProgressRoad now={3} labels={roadLabels} label={t("hero.road.label")} doneText={t("hero.road.done")} />
              </div>
              {/* T-132 part 2: phone = profile, refine, then the results; desktop = the answers in a sticky
                  sidebar (each editable) beside the top 10 (frames t132-m4 / t132-d2). */}
              <div className="lg:mt-6 lg:grid lg:grid-cols-[19rem_minmax(0,1fr)] lg:items-start lg:gap-8">
              {/* T-146: phones get a one-line summary and "Answers & refine"; the sidebar opens as a sheet. */}
              {rp ? (
                <div className="mt-4 flex items-center gap-3 rounded-xl border-[1.5px] border-[var(--line)] bg-[var(--surface)] p-3 sm:hidden" data-testid="hero-phone-bar">
                  <p className="min-w-0 flex-1 text-[15px] leading-snug">
                    <strong className="font-[family-name:var(--font-display)]">{profileName(rp, t)}</strong>
                    <br />
                    <span className="text-[var(--ink-2)]">{hero.budget === null ? t("hero.summary.noLimit") : t("hero.summary.upTo", { amount: money(hero.budget) })}</span>
                  </p>
                  <button
                    type="button"
                    className="evs-btn-out shrink-0"
                    aria-haspopup="dialog"
                    aria-expanded={sheet}
                    aria-controls={`${qid}-side`}
                    onClick={openSheet}
                    data-testid="hero-refine-open"
                  >
                    {refineCount ? t("hero.sheet.openN", { n: refineCount }) : t("hero.sheet.open")}
                  </button>
                </div>
              ) : null}
              <HeroSheet
                id={`${qid}-side`}
                open={sheet}
                onClose={closeSheet}
                label={t("hero.side.label")}
                title={t("hero.sheet.title")}
                closeLabel={t("hero.sheet.close")}
                doneLabel={t("hero.sheet.done")}
              >
              <ProfileBar
                rp={rp}
                t={t}
                tip={tip}
                country={t(`hero.country.${props.country}` as MsgKey)}
                cond={hero.cond}
                budget={hero.budget === null ? t("hero.summary.noLimit") : t("hero.summary.upTo", { amount: money(hero.budget) })}
                presets={presets}
                presetsOff={hero.presetsOff}
                locale={locale}
                onEdit={() => goTo("budget")}
                onRemovePreset={(f) => update({ presetsOff: [...hero.presetsOff, f] })}
                onRestorePresets={() => update({ presetsOff: [] })}
                answers={sideAnswers}
                onGo={(to) => goTo(to)}
              />
              {refine(t("hero.refine.button", { n: refineCount }))}
              </HeroSheet>
        <Results
          result={result}
          rp={rp}
          hero={hero}
          props={props}
          t={t}
          locale={locale}
          level={level}
          money={money}
          loan={loan}
          presets={presets}
          onRemovePreset={(f) => update({ presetsOff: [...hero.presetsOff, f] })}
          share={share}
          copied={copied}
          allCarsQuery={allCarsQuery}
          onEditBudget={() => goTo("budget")}
        />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Refine filters the visitor set (not the profile's presets): the "Refine · n" count. */
function activeRefine(f: ExploreFilters): number {
  const d = defaultFilters();
  let n = 0;
  if (f.bodies.length) n++;
  if (f.seatsMin !== d.seatsMin) n++;
  if (f.towingMin !== d.towingMin) n++;
  if (f.acMin !== d.acMin) n++;
  if (f.rangeMin !== d.rangeMin) n++;
  if (f.yearMin !== d.yearMin || f.yearMax !== d.yearMax) n++;
  if (f.makes.length) n++;
  if (f.excludeMakes.length) n++;
  return n;
}

/** One answer in the desktop results sidebar (T-132 part 2). */
interface SideAnswer {
  key: string;
  label: string;
  value: string;
  to: HeroStep;
}

/** Results screen: who you are, where, how much; Edit goes back to the questions (T-132). */
function ProfileBar({
  rp,
  t,
  tip,
  country,
  cond,
  budget,
  presets,
  presetsOff,
  locale,
  onEdit,
  onRemovePreset,
  onRestorePresets,
  answers = [],
  onGo,
}: {
  answers?: SideAnswer[];
  onGo?: (to: HeroStep) => void;
  rp: ResolvedProfile | null;
  t: T;
  tip: (id: string) => ReactNode;
  country: string;
  cond: Condition;
  budget: string;
  presets: ActivePreset[];
  presetsOff: PresetField[];
  locale: string;
  onEdit: () => void;
  onRemovePreset: (f: PresetField) => void;
  onRestorePresets: () => void;
}) {
  if (!rp) return null;
  return (
    <div className="mt-4 rounded-xl border-[1.5px] border-[var(--line)] bg-[var(--surface)] p-4" aria-live="polite" data-testid="hero-profile">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1">
          <span className="text-[15px] text-[var(--ink-2)]">{t("hero.profile.label")}</span>
          <br />
          <strong className="font-[family-name:var(--font-display)] text-xl">{profileName(rp, t)}</strong> {tip(rp.base.id)}
          {rp.layer ? tip(rp.layer.id) : null}
          <br />
          <span className="text-[15px] text-[var(--ink-2)]" data-testid="hero-summary">
            {country} · {t(`hero.summary.cond.${cond}` as MsgKey)} · {budget}
          </span>
        </p>
        <button type="button" className="evs-lnk" onClick={onEdit} aria-label={t("hero.summary.editLabel")} data-testid="hero-edit">
          <Pencil />
          {t("hero.summary.edit")}
        </button>
      </div>
      <p className="mt-2 text-sm text-[var(--ink)]">
        {t(`hero.profile.${rp.base.id}.short` as MsgKey)}
        {rp.layer ? ` ${t(`hero.profile.${rp.layer.id}.short` as MsgKey)}` : ""}
      </p>
      {answers.length ? (
        // Desktop sidebar and the phone sheet (T-146); between 640 px and lg the summary line and Edit say it in less room.
        <dl className="mt-3 hidden max-sm:block lg:block" data-testid="hero-answers">
          {answers.map((x) => (
            <div key={x.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 border-t border-[var(--line)] py-2">
              <dt className="col-start-1 text-[13px] text-[var(--ink-2)]">{x.label}</dt>
              <dd className="col-start-1 font-semibold">{x.value}</dd>
              <dd className="col-start-2 row-span-2 row-start-1">
                <button type="button" className="evs-lnk min-h-11 min-w-11 justify-center" onClick={() => onGo?.(x.to)} aria-label={t("hero.side.change", { what: x.label })} data-testid={`hero-answer-${x.key}`}>
                  <Pencil />
                </button>
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {presets.length ? (
        <div className="mt-2">
          <p className="text-xs font-semibold text-[var(--ink-2)]">{t("hero.presets.title")}</p>
          <ul className="mt-1 flex flex-wrap gap-2" data-testid="hero-presets">
            {presets
              .filter((p) => !presetsOff.includes(p.field))
              .map((p) => {
                const label = presetLabel(p, t, locale);
                return (
                  <li key={p.field}>
                    <button
                      type="button"
                      onClick={() => onRemovePreset(p.field)}
                      className="inline-flex min-h-11 items-center gap-2 rounded-md border border-slate-400 bg-white px-3 py-1 text-sm"
                      aria-label={t("hero.presets.remove", { label })}
                    >
                      {label}
                      <span aria-hidden="true">×</span>
                    </button>
                  </li>
                );
              })}
          </ul>
          {presetsOff.length ? (
            <button type="button" onClick={onRestorePresets} className="mt-2 text-sm text-blue-800 underline underline-offset-2">
              {t("hero.presets.restore")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function BudgetField({
  value,
  currency,
  t,
  money,
  labelId,
  locale,
  onChange,
}: {
  locale: string;
  value: number | null;
  currency: Currency;
  t: T;
  money: (n: number) => string;
  /** The question heading names the field. */
  labelId: string;
  onChange: (v: number | null) => void;
}) {
  // Thousands separators like the frames ("25,000", review N3); typing stays free, digits count.
  const grouped = (n: number) => formatNumber(n, locale, 0);
  const [text, setText] = useState(value === null ? "" : grouped(value));
  useEffect(() => {
    // Keep the field in step when a quick pick or the URL changes the budget.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setText((cur) => (Number(cur.replace(/[^\d]/g, "")) === value || (cur === "" && value === null) ? cur : value === null ? "" : formatNumber(value, locale, 0)));
  }, [value, locale]);
  const symbol = currency === "GBP" ? "£" : "€";
  return (
    <div>
      <div className="evs-money">
        <span aria-hidden="true">{symbol}</span>
        <input
          inputMode="numeric"
          autoComplete="off"
          aria-labelledby={labelId}
          aria-describedby={`${labelId}-help`}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            const n = Number(e.target.value.replace(/[^\d]/g, ""));
            onChange(e.target.value.trim() === "" || !Number.isFinite(n) || n <= 0 ? null : n);
          }}
          onBlur={() => {
            if (value !== null) setText(grouped(value));
          }}
          data-testid="hero-budget"
        />
      </div>
      <div className="evs-quick" role="group" aria-label={t("hero.budget.quick")}>
        {QUICK_BUDGETS[currency].map((b) => (
          <button key={b} type="button" aria-pressed={value === b} onClick={() => onChange(b)} className="evs-qb" data-testid={`hero-budget-${b}`}>
            {money(b)}
          </button>
        ))}
        <button type="button" aria-pressed={value === null} onClick={() => onChange(null)} className="evs-qb" data-testid="hero-budget-none">
          {t("hero.budget.clear")}
        </button>
      </div>
    </div>
  );
}

function Refine({
  filters,
  onChange,
  makes,
  nowYear,
  t,
  open,
}: {
  filters: ExploreFilters;
  onChange: (f: ExploreFilters) => void;
  makes: { id: string; name: string }[];
  nowYear: number;
  t: T;
  open: boolean;
}) {
  const set = (patch: Partial<ExploreFilters>) => onChange({ ...filters, ...patch });
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v].sort());
  const years: number[] = [];
  for (let y = nowYear; y >= 2011; y--) years.push(y);
  const rangeId = useId();
  const refineId = useId();
  return (
    <div className="mt-3 grid gap-4">
      <fieldset>
        <legend className="text-sm font-semibold">{t("hero.refine.body")}</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {BODIES.map((b) => (
            <button
              key={b}
              type="button"
              aria-pressed={filters.bodies.includes(b)}
              onClick={() => set({ bodies: toggle(filters.bodies, b) as Body[] })}
              className={toggleCls}
            >
              {t(`body.${b}` as MsgKey)}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap gap-4">
        <NumberSelect label={t("hero.refine.seats")} value={filters.seatsMin} options={[4, 5, 6, 7]} onChange={(seatsMin) => set({ seatsMin })} t={t} testid="hero-seats" />
        <NumberSelect label={t("hero.refine.towing")} value={filters.towingMin} options={[500, 750, 1000, 1500, 2000]} onChange={(towingMin) => set({ towingMin })} t={t} testid="hero-towing" />
        <NumberSelect label={t("hero.refine.ac")} value={filters.acMin} options={[7, 11, 22]} onChange={(acMin) => set({ acMin })} t={t} testid="hero-ac" />
        <div>
          <label htmlFor={rangeId} className="block text-sm font-semibold">
            {t("hero.refine.range")}
          </label>
          <input
            id={rangeId}
            inputMode="numeric"
            value={filters.rangeMin ?? ""}
            onChange={(e) => {
              const n = Number(e.target.value.replace(/[^\d]/g, ""));
              set({ rangeMin: e.target.value.trim() === "" || !n ? null : n });
            }}
            className={`${inputCls} mt-1`}
            data-testid="hero-range"
          />
        </div>
      </div>
      <fieldset>
        <legend className="text-sm font-semibold">{t("hero.refine.years")}</legend>
        <div className="mt-1 flex flex-wrap gap-4">
          <NumberSelect label={t("hero.refine.yearFrom")} value={filters.yearMin} options={years} onChange={(yearMin) => set({ yearMin })} t={t} testid="hero-ymin" />
          <NumberSelect label={t("hero.refine.yearTo")} value={filters.yearMax} options={years} onChange={(yearMax) => set({ yearMax })} t={t} testid="hero-ymax" />
        </div>
      </fieldset>
      {open
        ? (
            [
              ["makes", "hero.refine.brands", "hero-brands"],
              ["excludeMakes", "hero.refine.xbrands", "hero-xbrands"],
            ] as const
          ).map(([key, label, testid]) => (
            <div key={key} data-testid={testid}>
              <label htmlFor={`${refineId}-${key}`} className="block text-sm font-semibold">
                {t(label)}
              </label>
              <div className="mt-1 max-w-sm">
                <BrandPicker
                  makes={makes}
                  selected={filters[key]}
                  onChange={(ids) => set({ [key]: ids })}
                  testid={testid}
                  inputId={`${refineId}-${key}`}
                  hintId={`${refineId}-${key}-hint`}
                  text={{ placeholder: t("hero.refine.brandSearch"), none: t("hero.refine.brandNone") }}
                />
              </div>
              <p id={`${refineId}-${key}-hint`} className="mt-1 text-[15px] leading-[22px] text-slate-500">
                {t("hero.refine.brandHint")}
              </p>
              <BrandChips
                ids={filters[key]}
                name={(id) => makes.find((m) => m.id === id)?.name ?? id}
                onRemove={(ids) => set({ [key]: ids })}
                removeLabel={t("hero.refine.brandRemove")}
                inputTestId={`${testid}-input`}
              />
            </div>
          ))
        : null}
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <button type="button" onClick={() => onChange({ ...defaultFilters(), voltageClasses: filters.voltageClasses, chemistries: filters.chemistries, coolings: filters.coolings })} className="text-blue-800 underline underline-offset-2">
          {t("hero.refine.reset")}
        </button>
        <a href="#explore" className="text-blue-800 underline underline-offset-2">
          {t("hero.refine.more")}
        </a>
      </div>
    </div>
  );
}

// ── Results ─────────────────────────────────────────────────────────────────────────────────

interface ResultsProps {
  result: HeroResult | null;
  rp: ResolvedProfile | null;
  hero: HeroState;
  props: HeroProps;
  t: T;
  locale: string;
  level: ReturnType<typeof useLevel>;
  money: (n: number) => string;
  loan: ReturnType<typeof effectiveLoan>;
  presets: ActivePreset[];
  onRemovePreset: (f: PresetField) => void;
  share: () => void;
  copied: boolean;
  /** Hero answers as a query for the catalogue link (suggested sort). */
  allCarsQuery: string;
  /** Back to the budget question (T-152: "Raise your budget"). */
  onEditBudget: () => void;
}

function Results(r: ResultsProps) {
  const { t, result, rp } = r;
  const id = useId();
  if (!rp) {
    return (
      <section aria-labelledby={id} className="mt-6 rounded-md bg-slate-50 p-4" data-testid="hero-results">
        <h2 id={id} className="sr-only">
          {t("hero.results.title", { n: 10 })}
        </h2>
        <p className="text-slate-800">{t("hero.results.pick")}</p>
      </section>
    );
  }
  // "Your shortlist" = priced cars only (Decision 064); more priced cars follow under "Also worth a
  // look"; cars with no price get their own section without place numbers, after every priced car.
  const top = result?.picks.slice(0, result.shortlistN) ?? [];
  const more = result?.picks.slice(result?.shortlistN ?? 0, result?.priced ?? 0) ?? [];
  const noPrice = result?.picks.slice(result?.priced ?? 0) ?? [];
  const activePresets = r.presets.filter((p) => !r.hero.presetsOff.includes(p.field));
  return (
    <section aria-labelledby={id} className="mt-8 min-w-0 lg:mt-0" data-testid="hero-results">
      {result?.status === "no-scores" ? (
        // No release scores: no count, no "top 0", just the plain reason (Decision 065).
        <>
          <h2 id={id} className="sr-only">
            {t("hero.results.title", { n: 10 })}
          </h2>
          <div className="mt-4 rounded-md border border-slate-300 p-4" role="status" data-testid="hero-no-scores">
            <p className="font-semibold">{t("hero.noScores")}</p>
            <p className="mt-1 text-sm text-slate-800">{t("hero.noScores.why")}</p>
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id={id} className="font-[family-name:var(--font-display)] text-2xl font-bold">
              {result && result.priced === 0 && result.picks.length > 0
                ? t("hero.results.titleUnpriced")
                : t("hero.results.title", { n: result ? Math.min(10, result.priced) : 10 })}
            </h2>
            <button type="button" onClick={r.share} className="min-h-11 text-sm text-blue-800 underline underline-offset-2">
              {r.copied ? t("hero.results.copied") : t("hero.results.share")}
            </button>
          </div>
          <p className="mt-1 text-sm text-slate-800" aria-live="polite" data-testid="hero-count">
            {result ? t("hero.results.count", { n: result.qualifying }) : t("hero.results.updating")}
          </p>
          <ul className="mt-2 grid gap-1 text-xs text-slate-700">
            <li>{rp.base.calibrated ? t("hero.caveat.owner") : t("hero.caveat.research")}</li>
            {/* With release scores the winter figures are the release's own estimates (Decision 065). */}
            <li>{result?.picks.some((p) => p.result.derived.winter_range_km !== undefined) ? t("hero.caveat.winterEstimate") : t("hero.caveat.winter")}</li>
            {result && result.unpriced > 0 ? <li data-testid="hero-unpriced">{t("hero.unpriced")}</li> : null}
          </ul>
        </>
      )}

      {result && result.status === "ranked" && result.picks.length === 0 ? (
        <div className="mt-4 rounded-md border border-slate-300 p-4" data-testid="hero-empty">
          <p>{t("hero.results.empty")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {activePresets.map((p) => {
              const label = presetLabel(p, t, r.locale);
              return (
                <button key={p.field} type="button" onClick={() => r.onRemovePreset(p.field)} className={toggleCls}>
                  {t("hero.results.removePreset", { label })}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {result && result.status === "ranked" && result.picks.length > 0 && result.shortlistN === 0 ? (
        // Decision 064: unpriced cars never fill the shortlist, so say why it is empty.
        <p className="mt-4 rounded-md border border-slate-300 p-3 text-sm" data-testid="hero-no-priced">
          {t(r.hero.budget !== null ? "hero.results.noPriced" : "hero.results.noPricedAny")}
        </p>
      ) : null}
      {top.length ? (
        <div className="mt-4 rounded-xl bg-[var(--sunflower-tint)] p-3 sm:p-4" data-testid="hero-shortlist">
          <h3 className="font-[family-name:var(--font-display)] text-xl font-bold">
            {t("hero.results.shortlist")} <TermInfo term={r.props.terms.shortlist} base={r.props.base} text={{ about: t("term.about"), learnMore: t("term.learnMore") }} />
          </h3>
          <RowHead t={t} />
          <ol className="mt-2 grid gap-2 lg:mt-0">
            {top.map((p) => (
              <Card key={p.row.model_id} pick={p} r={r} />
            ))}
          </ol>
        </div>
      ) : null}
      {more.length ? (
        <div className="mt-6" data-testid="hero-more">
          <h3 className="font-[family-name:var(--font-display)] text-xl font-bold">{t("hero.results.more")}</h3>
          <ol className="mt-2 grid" start={top.length + 1}>
            {more.map((p) => (
              <LineCard key={p.row.model_id} pick={p} r={r} />
            ))}
          </ol>
        </div>
      ) : null}
      {noPrice.length ? (
        <div className="mt-6" data-testid="hero-no-price">
          {/* Fewer than five priced cars fit: say so plainly instead of ranking unpriced cars as picks. */}
          <h3 className="text-lg font-semibold">
            {t((result?.priced ?? 0) < SHORTLIST_N ? "hero.results.noPriceFits" : "hero.results.noPriceList")}
          </h3>
          <ul className="mt-2 grid">
            {noPrice.map((p) => (
              <LineCard key={p.row.model_id} pick={p} r={r} />
            ))}
          </ul>
        </div>
      ) : null}
      {result?.status === "ranked" && r.hero.budget !== null && (result.unpricedFar > 0 || result.unpricedCapped > 0) ? (
        // T-152: fewer fill-ins than before, so say which were left out and why, and offer a way on.
        <div className="mt-4 rounded-md border border-[var(--line)] p-3 text-sm" role="note" data-testid="hero-left-out">
          {result.unpricedFar > 0 ? <p data-testid="hero-left-out-far">{t("hero.results.leftOutFar", { n: result.unpricedFar })}</p> : null}
          {result.unpricedCapped > 0 ? (
            <p className={result.unpricedFar > 0 ? "mt-1" : undefined} data-testid="hero-left-out-capped">
              {t("hero.results.leftOutCapped", { n: result.unpricedCapped })}
            </p>
          ) : null}
          {/* Only a car left out for its price comes back with a higher budget; the cap does not lift. */}
          {result.unpricedFar > 0 ? (
            <button type="button" onClick={r.onEditBudget} className="evs-btn-out mt-2" data-testid="hero-raise-budget">
              {t("hero.results.raiseBudget")}
            </button>
          ) : null}
        </div>
      ) : null}
      {r.props.learnLinks?.length ? (
        <nav aria-label={t("hero.learn.title")} className="mt-6 rounded-md bg-slate-50 p-3" data-testid="hero-learn">
          <p className="text-sm font-semibold">{t("hero.learn.title")}</p>
          <ul className="mt-1 grid gap-1 text-sm">
            {r.props.learnLinks.map((l) => (
              <li key={l.slug}>
                <a href={l.href} className="text-blue-800 underline underline-offset-2">
                  {l.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      {/* "Show all cars" closes the results (T-132): the catalogue with these answers, so its
          "Suggested for you" sort matches this list. */}
      <div className="mt-6 flex flex-wrap items-center gap-4 rounded-xl border-[1.5px] border-[var(--line)] bg-[var(--surface)] p-4" data-testid="hero-all-cars">
        <div className="min-w-0 flex-1">
          <p className="font-bold">{t("hero.allCars.title")}</p>
          <p className="text-sm text-[var(--ink-2)]">{t("hero.allCars.body", { n: r.props.total })}</p>
        </div>
        <a href={`${r.props.base}/cars${r.allCarsQuery ? `?${r.allCarsQuery}` : ""}`} className="evs-btn-out" data-testid="hero-all-cars-link">
          {t("hero.allCars.button")} <span aria-hidden="true">›</span>
        </a>
      </div>
    </section>
  );
}

function reasonText(pick: HeroPick, r: ResultsProps): string {
  const { t, locale } = r;
  const row = pick.row;
  const d = pick.result.derived;
  // Plus reasons from the release, with the values the release scored them on (winter range and
  // real efficiency are its own derived estimates, Decision 065).
  const bits = reasons(pick.result).map((x) => {
    switch (x.id) {
      case "dc-speed":
        return t("hero.why.dc-speed", { km: formatNumber(row.dc_km_per_20min, locale, 0) });
      case "winter-range":
        return d.winter_range_km !== undefined ? t("hero.why.winter-range.winter", { km: formatNumber(d.winter_range_km, locale, 0) }) : t("hero.factor.winter-range");
      case "space":
        return t("hero.why.space", { l: formatNumber(row.boot_l, locale, 0) });
      case "efficiency":
        return d.real_wh_km !== undefined ? t("hero.why.efficiency", { kwh: formatNumber(d.real_wh_km / 10, locale, 1) }) : t("hero.factor.efficiency");
      case "ac-speed":
        return t("hero.why.ac-speed", { kw: formatNumber(row.ac_kw, locale, 1) });
      case "size":
        return t("hero.why.size", { m: formatNumber((row.length_mm ?? 0) / 1000, locale, 2) });
      default:
        return t(`hero.why.${x.id}` as MsgKey);
    }
  });
  if (pick.result.adjustments.some((a) => a.id === "newest-version")) bits.push(t("hero.why.newest-version"));
  if (!bits.length) bits.push(t("hero.why.none"));
  if (r.hero.budget !== null && pick.price) {
    const head = r.hero.budget - pick.price.amount;
    if (head >= 500) bits.push(t("hero.card.underBudget", { amount: r.money(Math.floor(head / 500) * 500) }));
  }
  return cap(bits.join(", "));
}

/** "€19.5k": compact money for the price column (the full sentence sits under the row). Hand-rolled
    rather than Intl's compact notation: Node and the browser format that differently ("€21.0K" vs
    "€21K"), which broke hydration. */
function moneyShort(n: number, currency: Currency, locale: string): string {
  const sym = currency === "GBP" ? "£" : "€";
  if (n < 1000) return `${sym}${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n)}`;
  const k = n / 1000;
  return `${sym}${new Intl.NumberFormat(locale, { minimumFractionDigits: 0, maximumFractionDigits: k >= 100 ? 0 : 1 }).format(k)}k`;
}

/** Everything a result row needs, shared by the shortlist rows and the one-line rows. */
function useCardData(pick: HeroPick, r: ResultsProps) {
  const { t, props } = r;
  const row = pick.row;
  const cmp = useListStore(compareStore);
  const inCmp = cmp.some((c) => c.id === row.variant_id);
  const full = !inCmp && cmp.length >= COMPARE_MAX;
  const name = `${row.make_name} ${row.model_name}`;
  const years = formatYears(pick.price?.yearFrom ?? row.year_start, pick.price ? pick.price.yearTo : row.year_end, t("years.now"));
  let price: string;
  let short: string;
  if (!pick.price) {
    price = t("hero.card.priceUnknown");
    short = "—";
  } else if (pick.price.kind === "new") {
    price = t("hero.card.priceNew", { amount: r.money(pick.price.amount) });
    short = moneyShort(pick.price.amount, props.currency, r.locale);
  } else if (pick.price.low !== null && pick.price.high !== null) {
    price = t("hero.card.priceUsed", { years, low: r.money(pick.price.low), high: r.money(pick.price.high), country: COUNTRIES[props.country].name });
    short = `${moneyShort(pick.price.low, props.currency, r.locale)}–${moneyShort(pick.price.high, props.currency, r.locale)}`;
  } else {
    price = t("hero.card.priceUsedOne", { years, amount: r.money(pick.price.amount), country: COUNTRIES[props.country].name });
    short = `≈ ${moneyShort(pick.price.amount, props.currency, r.locale)}`;
  }
  const winter = pick.result.derived.winter_range_km;
  const compare = (
    <button
      type="button"
      aria-pressed={inCmp}
      aria-disabled={full || undefined}
      onClick={() => {
        if (inCmp) compareStore.remove(row.variant_id);
        else if (!full) compareStore.add({ id: row.variant_id, label: `${name} ${row.variant_name}` });
      }}
      className="evs-cmp"
      title={inCmp ? t("hero.card.inCompare") : full ? t("hero.card.compareFull") : t("hero.card.compare")}
      data-testid="hero-compare"
    >
      <span aria-hidden="true">{inCmp ? "✓" : "+"}</span>
      <span className="sr-only">
        {inCmp ? t("hero.card.inCompare") : full ? t("hero.card.compareFull") : t("hero.card.compare")}: {`${name} ${row.variant_name}`}
      </span>
    </button>
  );
  const rank =
    pick.rank !== null ? (
      <span className="evs-rank" aria-label={t("hero.card.rank", { n: pick.rank })}>
        {pick.rank}
      </span>
    ) : (
      <span aria-hidden="true" />
    );
  const link = (
    <a href={generationHref(props.base, row)} className="text-blue-800 underline-offset-2 hover:underline">
      {name}
    </a>
  );
  return { row, name, price, short, winter, compare, rank, link };
}

/** "—" on screen, "not known yet" for screen readers (a missing value is never 0). */
function Unknown({ t }: { t: T }) {
  return (
    <>
      <span aria-hidden="true">—</span>
      <span className="sr-only">{t("hero.card.notKnown")}</span>
    </>
  );
}

const cardAttrs = (pick: HeroPick) => ({
  "data-testid": "hero-card",
  "data-rank": pick.rank ?? undefined,
  "data-variant": pick.row.variant_id,
  "data-price": pick.price?.amount,
  "data-price-basis": pick.price?.basis ?? "none",
});

/** Column labels above the shortlist rows on desktop (the rows carry their own labels for screen readers). */
function RowHead({ t }: { t: T }) {
  return (
    <div className="evs-srow evs-srow--head" aria-hidden="true">
      <span>#</span>
      <span style={{ gridArea: "car" }}>{t("hero.col.car")}</span>
      <span style={{ gridArea: "price" }}>{t("hero.col.price")}</span>
      <span style={{ gridArea: "winter" }}>{t("hero.col.winter")}</span>
      <span style={{ gridArea: "dc" }}>{t("hero.col.dc")}</span>
      <span style={{ gridArea: "why" }}>{t("hero.col.why")}</span>
      <span style={{ gridArea: "act" }}>{t("hero.col.compare")}</span>
    </div>
  );
}

/** A shortlist row (T-132 part 2): the same numbers in the same place on every row. */
function Card({ pick, r }: { pick: HeroPick; r: ResultsProps }) {
  const { t, locale, level, props } = r;
  const { row, price, short, winter, compare, rank, link } = useCardData(pick, r);
  const heroNumLabels = numLabels(t);
  const site = props.listingSites[0];
  const monthly = pick.price ? monthlyFor(pick.price.amount, r.loan) : null;
  const unknownLabels = [
    ...pick.result.unknown,
    ...pick.presetUnknown.map((f) => PRESET_FACTOR[f]).filter((x): x is string => !!x),
  ]
    .filter((x, i, a) => a.indexOf(x) === i && !PARKED_FACTORS.has(x))
    .map((id) => t(`hero.factor.${id}` as MsgKey));
  const priceNote =
    pick.price?.basis === "estimate"
      ? t(pick.price.lowConfidence ? "hero.card.estimateLow" : "hero.card.estimate")
      : pick.price?.basis === "band" && pick.price.scope === "generation"
        ? t("hero.card.generationBand")
        : null;
  const priceHow = level === "nerd" && pick.price ? priceHowText(pick.price, t, locale, r.money, props.sources) : null;
  const cond = pick.price ? t(pick.price.kind === "new" ? "hero.card.cond.new" : "hero.card.cond.used") : null;
  const tt = { about: t("term.about"), learnMore: t("term.learnMore") };
  const photo = props.photos?.[row.generation_id];

  return (
    <li className="evs-srow evs-srow--card" {...cardAttrs(pick)}>
      <span style={{ gridArea: "rank" }}>{rank}</span>
      <div style={{ gridArea: "car" }} className="flex min-w-0 flex-wrap items-start gap-x-3 gap-y-2">
        {/* T-146: the generation's photo when the release has one; rows without keep the old layout. */}
        {photo ? <CarThumb photo={photo} alt={generationTitle(row)} text={photoText(t, tt)} /> : null}
        {/* Narrow rows put the photo above the name (the name keeps at least 8rem). */}
        <div className="min-w-0 grow basis-[8rem]">
          <h4 className="text-[17px] font-bold leading-snug">{link}</h4>
          <p className="text-sm text-[var(--ink-2)]">
            {row.variant_name} · {formatYears(row.year_start, row.year_end, t("years.now"))}
            {cond ? ` · ${cond}` : ""}
          </p>
        </div>
      </div>
      <div className="evs-srow__facts">
        <p style={{ gridArea: "price" }} className="font-bold tabular-nums">
          <span className="sr-only">{t("hero.col.price")}: </span>
          {short}
        </p>
        <p style={{ gridArea: "winter" }} className="tabular-nums" data-testid="hero-winter">
          <span className="sr-only">{t("hero.col.winter")}: </span>
          <span aria-hidden="true">❄ </span>
          {winter !== undefined ? <strong>{`${formatNumber(winter, locale, 0)} km`}</strong> : <Unknown t={t} />}
          <span className="lg:hidden" aria-hidden="true"> {t("hero.card.winterShort")}</span>
        </p>
        <p style={{ gridArea: "dc" }} className="tabular-nums">
          <span className="sr-only">{t("hero.col.dc")}: </span>
          <span aria-hidden="true">⚡ </span>
          {row.dc_km_per_20min ? <strong>{t("hero.card.dc20", { km: formatNumber(row.dc_km_per_20min, locale, 0) })}</strong> : <Unknown t={t} />}
          <span className="lg:hidden" aria-hidden="true"> {t("hero.card.dc20Label")}</span>
        </p>
      </div>
      <p style={{ gridArea: "why" }} className="text-sm" data-testid="hero-why">
        <strong className="lg:sr-only">{t("hero.card.whyLabel")} </strong>
        {reasonText(pick, r)}
      </p>
      <span style={{ gridArea: "act" }} className="justify-self-end">
        {compare}
      </span>
      {/* The detail line: the full price sentence, real range with the official WLTP (T-143), listings. */}
      <div style={{ gridArea: "more" }} className="grid gap-1 text-[13px] text-[var(--ink-2)]">
        <p data-testid="hero-price">
          {price}
          {monthly ? <> · {t("hero.monthly", { amount: r.money(monthly.monthly) })}</> : null}
        </p>
        {priceNote ? <p data-testid="hero-price-note">{priceNote}</p> : null}
        {priceHow ? <p data-testid="hero-price-how">{priceHow}</p> : null}
        <p className="flex flex-wrap items-center gap-x-3">
          <span>
            {t("hero.card.realRange")} <TermInfo term={props.terms["real-range"]} base={props.base} text={tt} />{" "}
            <strong className="tabular-nums text-[var(--ink)]">{row.real_range_km ? `${formatNumber(row.real_range_km, locale, 0)} km` : t("hero.card.notKnown")}</strong>
          </span>
          <OfficialRange
            value={row.wltp_range_km}
            provenance={row.provenance.wltp_range_km}
            sources={props.sources}
            locale={locale}
            labels={heroNumLabels}
            text={{ label: t("range.wltp.label"), notKnown: t("range.wltp.notKnown"), tip: t("range.wltp.tip") }}
            info={{ href: `${props.base}/learn/wltp`, termText: tt }}
            testId="hero-wltp"
          />
          <span>
            {t("hero.card.winterNote")} <TermInfo term={props.terms["real-winter-range"]} base={props.base} text={tt} />
          </span>
        </p>
        {level !== "simple" && unknownLabels.length ? <p>{t("hero.card.unknown", { list: unknownLabels.join(", ") })}</p> : null}
        {level !== "simple" && pick.alternatives > 0 ? <p>{t("hero.card.alternatives", { n: pick.alternatives })}</p> : null}
        {site ? (
          <p>
            <a href={buildListingUrl(site, row.make_name, row.model_name)} rel="nofollow noopener" target="_blank" className="font-semibold text-blue-800 underline underline-offset-2" data-testid="hero-listings">
              {t("hero.card.listings", { site: site.label })}
              <span aria-hidden="true"> ↗</span>
              <span className="sr-only"> {t("hero.card.newTab")}</span>
            </a>
          </p>
        ) : null}
      </div>
      {level === "nerd" ? (
        <div style={{ gridArea: "nerd" }} className="min-w-0">
          <NerdScore pick={pick} r={r} />
        </div>
      ) : null}
    </li>
  );
}

/** "Also worth a look" and no-price rows: one line each (rank, name, price, winter range, compare). */
function LineCard({ pick, r }: { pick: HeroPick; r: ResultsProps }) {
  const { t, locale, level } = r;
  const { row, price, short, winter, compare, rank, link } = useCardData(pick, r);
  return (
    <li className="evs-lrow" {...cardAttrs(pick)}>
      <span className="evs-lrow__rank">{rank}</span>
      <span className="min-w-0">
        <span className="block font-semibold leading-snug">{link}</span>
        <span className="block text-[13px] text-[var(--ink-2)]">
          {row.variant_name} · {formatYears(row.year_start, row.year_end, t("years.now"))}
        </span>
      </span>
      <span className="text-right font-bold tabular-nums" title={price}>
        <span className="sr-only" data-testid="hero-price">
          {price}
        </span>
        <span aria-hidden="true">{short}</span>
      </span>
      <span className="whitespace-nowrap text-right tabular-nums" data-testid="hero-winter">
        <span aria-hidden="true">❄ </span>
        {winter !== undefined ? `${formatNumber(winter, locale, 0)} km` : <Unknown t={t} />}
        <span className="sr-only"> {t("hero.card.winterShort")}</span>
      </span>
      {compare}
      {level === "nerd" ? (
        <div className="col-span-full min-w-0">
          <NerdScore pick={pick} r={r} />
        </div>
      ) : null}
    </li>
  );
}

function NerdScore({ pick, r }: { pick: HeroPick; r: ResultsProps }) {
  const { t, locale } = r;
  const res = pick.result;
  return (
    <div className="mt-2 rounded border border-slate-300 bg-slate-50 p-2 text-xs" data-testid="hero-nerd">
      <p className="font-semibold">
        {t("hero.card.score", { score: formatNumber(res.score, locale, 1), band: t(`hero.band.${res.band}` as MsgKey) })}
      </p>
      {/* Numbers never break mid-value; only factor names wrap. If a language still needs more room,
          the table scrolls inside the card instead of widening the page (verify-web, 360 px). */}
      <div className="mt-1 overflow-x-auto">
      <table className="w-full text-left [&_td]:pr-2 [&_th]:pr-2">
        <caption className="sr-only">{t("hero.nerd.factors")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("hero.nerd.factor")}</th>
            <th scope="col">{t("hero.nerd.value")}</th>
            {/* One column for points × weight: two narrow numeric columns cost ~45 px a 360 px card
                doesn't have (T-097 review: headers broke mid-word, "Poi/ds"). */}
            <th scope="col">
              {t("hero.nerd.points")} × {t("hero.nerd.weight")}
            </th>
          </tr>
        </thead>
        <tbody>
          {res.factors.map((f) => (
            <tr key={f.id}>
              <th scope="row" className="font-normal hyphens-auto [overflow-wrap:anywhere]">
                {t(`hero.factor.${f.id}` as MsgKey)}
              </th>
              {/* The car's own figure with its unit (T-097), not the scaled scoring value. May wrap at
                  the spaces of the unit ("387 km in 20 min") on a phone; the number itself never splits
                  (no spaces inside formatted numbers; FR uses a no-break space). Units and words stay short and
                  breakable so the table fits a 360 px card in every language (axe: no scroll region). Headers
                  and words may break mid-word when a wider system font needs it (CI DE was 16 px over);
                  numbers sit in nowrap spans so they never split. */}
              <td className="tabular-nums hyphens-auto [overflow-wrap:anywhere]" data-testid={`hero-nerd-value-${f.id}`}>
                {numberParts(nerdValue(f, t, locale)).map((p, i) =>
                  p.num ? <span key={i} className="whitespace-nowrap">{p.text}</span> : p.text,
                )}
              </td>
              <td className="whitespace-nowrap tabular-nums" data-testid={`hero-nerd-points-${f.id}`}>
                {formatNumber(f.score ?? 0.5, locale, 2)} × {formatNumber(f.weight, locale, 1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {res.adjustments.length ? (
        <p className="mt-1">{t("hero.nerd.adjust", { list: res.adjustments.map((a) => `${t(`hero.adj.${a.id}` as MsgKey)} ${a.points > 0 ? "+" : ""}${a.points}`).join(", ") })}</p>
      ) : null}
      <p className="mt-1">{t("hero.nerd.rules")}</p>
      <p className="mt-1" data-testid="hero-nerd-source">{t("hero.nerd.source", { n: r.props.release })}</p>
    </div>
  );
}
