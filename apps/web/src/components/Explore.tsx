"use client";
// Explore: one table of new and used EVs. The server renders the first rows; this component
// hydrates them, then fetches the compact catalogue JSON from our own origin and filters
// and sorts the full list in the browser. All state lives in the URL (see lib/state.ts).
// Taxonomy-driven filters (voltage, chemistry, cooling) read their options from data.
import { loadClientCatalogue } from "@/lib/client-catalogue";
import { onAnswers, onFilters, publishFilters } from "@/lib/filter-bus";
import { resolveProfile, suggestedScore, type Answers } from "@/lib/shortlist";
import { CarFigure, photoText, type PhotoRef } from "./CarPhoto";
import { generationTitle } from "@/lib/generation-title";
import { profileName, SuggestedSort } from "./SuggestedSort";
import type { Country, Currency, FieldProvenance } from "@ev/schema";
import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { generationHref, variantHref } from "@/app/[country]/[lang]/ev/_lib/routes";
import type { CountrySlug, Lang } from "@/config/countries";
import { makeT, type Dict, type MsgKey, type T } from "@/i18n/t";
import { compareStore, COMPARE_MAX } from "@/lib/compare-store";
import { hasDcData, isClaimField } from "@/lib/dc";
import type { ExploreRow } from "@/lib/explore-data";
import { favouriteStore } from "@/lib/favourites";
import { activeGroups, applyFilters, displayName, mostRestrictive, priceFor, sortRows, withoutGroup, type FilterGroup } from "@/lib/filters";
import { generationCards, generationCount, type GenCard, type Span } from "@/lib/generation-cards";
import { formatMoney, formatNumber, formatYears, localeFor } from "@/lib/format";
import { effectiveLoan, monthlyFor, readPayMode, writePayMode, type EffectiveLoan, type FinanceProfileView, type PayMode } from "@/lib/finance";
import { LeaseNotice, LoanBox, PayModeToggle, useLoanSettings, type FinanceUi } from "@/components/PriceMode";
import { siteBase } from "@/lib/site-paths";
import {
  BODIES,
  defaultFilters,
  ERAS,
  EXPLORE_PARAM_KEYS,
  LEVEL_KEY,
  LEVELS,
  MENU_SORTS,
  nextSort,
  sortBy,
  SEGMENTS,
  toSearchParams,
  VIEW_KEY,
  type ExploreFilters,
  type ExploreState,
  type Level,
  type NumericFilter,
  type SortKey,
  TRIP_KEY,
  type View,
} from "@/lib/state";
import { readStorage, writeStorage } from "@/lib/storage";
import { voltageBounds, type UiTaxonomy } from "@/lib/taxonomy";
import { useListStore } from "@/lib/use-list-store";
import { Missing, Num } from "./Num";
import { OfficialRange, type OfficialRangeText } from "./OfficialRange";
import { numLabels, type NumLabels } from "./num-labels";
import { QualityBadge } from "./QualityBadge";
import { InfoTip, TermInfo, TermLabel, type TermText } from "./Term";
import { usePopover } from "./use-popover";
// Type only: the trip module itself is loaded with import() on demand (T-036, JS budget).
import type * as TripModuleNs from "./trip/TripModule";

type TripModule = typeof TripModuleNs;
type CarFit = TripModuleNs.CarFit;
type TripSettings = TripModuleNs.TripSettings;

const loadTripModule = (): Promise<TripModule> => import("./trip/TripModule");

const PAGE = 50;

export interface ExploreProps {
  country: CountrySlug;
  code: Country;
  currency: Currency;
  lang: Lang;
  dict: Dict;
  initialState: ExploreState;
  /** The hero's picker answers from the URL (T-067 Suggested sort). */
  initialAnswers?: Answers;
  viewFromUrl: boolean;
  levelFromUrl: boolean;
  initialRows: ExploreRow[];
  initialMatches: number;
  total: number;
  dataUrl: string;
  sources: Record<string, string>;
  taxonomy: UiTaxonomy;
  /** Release date (YYYY-MM-DD), shown with sources at nerd level. */
  asOf: string;
  /** TRIP_FIT=1 (server env): shows the trip fit quick check. Off → no trip UI at all. */
  tripFit?: boolean;
  /** This country's finance profile (data/taxonomy/finance_profiles.yaml), Decision 017. */
  finance: FinanceProfileView | null;
  /** The URL sets ?pay= (else the remembered price mode wins). */
  payFromUrl: boolean;
  /** The release has shortlist_scores.json (Decision 065); without it "Suggested" can't order. */
  hasScores?: boolean;
  /** The page's default view, left out of the URL (T-130: cards on /cars). */
  defaultView?: View;
  /** Date of the registration counts behind "Most popular" (Nerd line under the tag). */
  popularityAsOf?: string;
  /** Link to the "How we rank" explanation of the Most popular order (T-130). */
  howWeRankHref?: string;
  /** Generations ("models") in the catalogue and in the server-side matches (T-130 count line). */
  totalModels: number;
  initialMatchModels: number;
  /** Every brand with its number of generations, for the brand filter and the pills (T-130). */
  brands: { id: string; name: string; count: number }[];
  /** Generation id → its release photo (T-135 cards); absent = the neutral placeholder. */
  photos?: Record<string, PhotoRef>;
}

interface Ctx {
  t: T;
  /** Date of the "Most popular" registration counts (T-130 Nerd line). */
  popAsOf?: string;
  locale: string;
  labels: NumLabels;
  sources: Record<string, string>;
  code: Country;
  currency: Currency;
  country: CountrySlug;
  /** "/{country}/{lang}": prefix for every link (Decision 015). */
  base: string;
  tax: UiTaxonomy;
  names: { voltage: Map<string, string>; chem: Map<string, string>; cool: Map<string, string> };
  termText: TermText;
  level: Level;
  asOf: string;
  /** Price mode and the effective loan inputs (Decision 017). */
  pay: PayMode;
  loan: EffectiveLoan;
  /**
   * Inside the table, numbers and secondary links are not Tab stops (one stop per row for the
   * name link, heart and compare; provenance via the variant page or the Nerd "sources" button).
   */
  inTable?: boolean;
  /** Generation photos (T-135). */
  photos?: Record<string, PhotoRef>;
  /** Trip fit verdicts (T-036) once the user entered a trip; drives the "Your trips" column. */
  trip?: { mod: TripModule; fits: Map<string, CarFit>; ui: TripModuleNs.TripUi };
}

export function Explore(props: ExploreProps) {
  const t = useMemo(() => makeT(props.dict), [props.dict]);
  const locale = localeFor(props.lang);

  const [state, setState] = useState<ExploreState>(props.initialState);
  const [answers, setAnswers] = useState<Answers | null>(props.initialAnswers ?? null);
  useEffect(() => onAnswers(setAnswers), []);
  const rp = useMemo(() => (answers ? resolveProfile(answers) : null), [answers]);
  const [all, setAll] = useState<ExploreRow[] | null>(null);
  const [sources, setSources] = useState(props.sources);
  const [limit, setLimit] = useState(PAGE);
  // True once the user changed anything: from then on counts come from the (partial or full) client list.
  const [dirty, setDirty] = useState(false);
  const lastUrl = useRef(toSearchParams(props.initialState, props.defaultView).toString());
  // Trip fit (T-036): module loaded on demand, answers from localStorage only.
  const [tripMod, setTripMod] = useState<TripModule | null>(null);
  const [tripSettings, setTripSettings] = useState<TripSettings | null>(null);
  const [tripOpen, setTripOpen] = useState(false);
  const tripFit = props.tripFit === true;
  const [loanSettings, setLoanSettings] = useLoanSettings();
  const loan = useMemo(() => effectiveLoan(props.finance, loanSettings), [props.finance, loanSettings]);

  const tripRows = all ?? props.initialRows;
  const fits = useMemo(
    () => (tripMod && tripFit ? tripMod.computeFits(tripRows, tripSettings, props.country) : null),
    [tripMod, tripFit, tripRows, tripSettings, props.country],
  );

  const ctx: Ctx = useMemo(
    () => ({
      t,
      locale,
      labels: numLabels(t, { base: siteBase(props.country, props.lang), terms: props.taxonomy.terms }),
      sources,
      code: props.code,
      currency: props.currency,
      country: props.country,
      base: siteBase(props.country, props.lang),
      tax: props.taxonomy,
      names: {
        voltage: new Map(props.taxonomy.voltageClasses.map((v) => [v.id, v.label])),
        chem: new Map(props.taxonomy.chemistries.map((v) => [v.id, v.label])),
        cool: new Map(props.taxonomy.coolings.map((v) => [v.id, v.label])),
      },
      termText: { about: t("term.about"), learnMore: t("term.learnMore") },
      level: state.level,
      asOf: props.asOf,
      popAsOf: props.popularityAsOf,
      photos: props.photos,
      pay: state.pay,
      loan,
      trip: tripMod && fits ? { mod: tripMod, fits, ui: {
              t,
              level: state.level,
              locale,
              labels: numLabels(t, { base: siteBase(props.country, props.lang), terms: props.taxonomy.terms }),
              country: props.country,
              gloss: { base: siteBase(props.country, props.lang), terms: props.taxonomy.terms, text: { about: t("term.about"), learnMore: t("term.learnMore") } },
            } } : undefined,
    }),
    [t, locale, sources, props.code, props.currency, props.country, props.lang, props.taxonomy, state.level, props.asOf, props.popularityAsOf, props.photos, state.pay, loan, tripMod, fits],
  );

  const openTrip = () => {
    setTripOpen(true);
    if (tripMod) return;
    loadTripModule()
      .then((m) => {
        setTripMod(m);
        setTripSettings(m.loadTripSettings() ?? m.normalizeTripSettings(null));
      })
      .catch(() => setTripOpen(false));
  };

  // A trip saved earlier: load the module after first paint so the column comes back.
  useEffect(() => {
    if (!tripFit || !readStorage(TRIP_KEY)) return;
    let live = true;
    loadTripModule()
      .then((m) => {
        if (!live) return;
        setTripMod(m);
        setTripSettings(m.loadTripSettings());
      })
      .catch(() => {
        /* no trip column; Explore works as before */
      });
    return () => {
      live = false;
    };
  }, [tripFit]);

  const changeTrip = (next: TripSettings) => {
    setTripSettings(next);
    tripMod?.saveTripSettings(next);
  };
  const clearTrip = () => {
    tripMod?.clearTripSettings();
    setTripSettings(tripMod ? tripMod.normalizeTripSettings(null) : null);
    if (state.filters.tripFit) update({ ...state, filters: { ...state.filters, tripFit: false } });
  };

  // Full list, fetched from our own origin after first paint (shared with the hero, T-080).
  useEffect(() => {
    let live = true;
    void loadClientCatalogue(props.dataUrl).then((c) => {
      if (live && c) {
        setAll(c.rows);
        setSources(c.sources);
      }
    });
    return () => {
      live = false;
    };
  }, [props.dataUrl]);

  // The hero's refine filters are Explore's filters (same URL params, T-080).
  useEffect(
    () =>
      onFilters("explore", (filters) => {
        setDirty(true);
        setLimit(PAGE);
        setState((s) => ({ ...s, filters: { ...filters, tripFit: s.filters.tripFit } }));
      }),
    [],
  );

  // Remembered table/cards and level preferences, unless the URL says otherwise.
  useEffect(() => {
    const patch: Partial<ExploreState> = {};
    if (!props.viewFromUrl) {
      const stored = readStorage(VIEW_KEY);
      let view: View | null = stored === "cards" || stored === "table" ? stored : null;
      if (!view && window.matchMedia?.("(max-width: 639px)").matches) view = "cards";
      if (view && view !== props.initialState.view) patch.view = view;
    }
    if (!props.levelFromUrl) {
      const stored = readStorage(LEVEL_KEY);
      if ((LEVELS as readonly string[]).includes(stored ?? "") && stored !== props.initialState.level) patch.level = stored as Level;
    }
    if (!props.payFromUrl) {
      const stored = readPayMode();
      if (stored && stored !== props.initialState.pay) patch.pay = stored;
    }
    // One-off read of browser-only preferences after hydration (reading them during render would
    // mismatch the server HTML), so a setState here is intended.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (Object.keys(patch).length) setState((s) => ({ ...s, ...patch }));
  }, [props.viewFromUrl, props.levelFromUrl, props.payFromUrl, props.initialState.view, props.initialState.level, props.initialState.pay]);

  // State → URL (replaceState: no server round trip, links stay shareable).
  useEffect(() => {
    const qs = toSearchParams(state, props.defaultView).toString();
    if (qs === lastUrl.current) return;
    lastUrl.current = qs;
    const url = new URL(window.location.href);
    for (const k of EXPLORE_PARAM_KEYS) url.searchParams.delete(k);
    new URLSearchParams(qs).forEach((v, k) => url.searchParams.set(k, v));
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  }, [state, props.defaultView]);

  const update = (next: ExploreState) => {
    setDirty(true);
    setLimit(PAGE);
    setState(next);
    if (next.filters !== state.filters) publishFilters({ filters: next.filters, from: "explore" });
  };
  const setFilter = (patch: Partial<ExploreFilters>) => update({ ...state, filters: { ...state.filters, ...patch } });
  const setView = (view: View) => {
    writeStorage(VIEW_KEY, view);
    setState({ ...state, view });
  };
  const setLevel = (level: Level) => {
    writeStorage(LEVEL_KEY, level);
    setState({ ...state, level });
  };
  const setPay = (pay: PayMode) => {
    writePayMode(pay);
    setState({ ...state, pay });
  };
  const financeUi: FinanceUi = {
    t,
    locale,
    currency: props.currency,
    code: props.code,
    level: state.level,
    base: ctx.base,
    terms: props.taxonomy.terms,
    termText: ctx.termText,
  };

  // The filter pipeline Explore shows: filters + (with a trip entered) the winter trip fit.
  const runFilters = useCallback(
    (f: ExploreFilters) => {
      let out = applyFilters(all ?? props.initialRows, f, props.code);
      // "Does my trips in winter": keeps ✓ and ⚠; only with a trip entered (the URL flag alone does nothing).
      if (f.tripFit && fits) out = out.filter((r) => {
        const v = fits.get(r.variant_id)?.verdict;
        return v === "ok" || v === "tight";
      });
      return out;
    },
    [all, props.initialRows, props.code, fits],
  );
  // "Suggested" sort (T-067): the release's score for the hero's profile (Decision 065); a car the
  // release rules out, or doesn't score, goes last.
  const scorer = useMemo(() => (rp ? (r: ExploreRow) => suggestedScore(r, rp) : undefined), [rp]);
  const matches = useMemo(() => {
    if (!all && !dirty && !(state.sort === "suggested" && answers !== props.initialAnswers)) return props.initialRows;
    return sortRows(runFilters(state.filters), state.sort, state.dir, props.code, scorer);
  }, [all, dirty, runFilters, state.filters, state.sort, state.dir, props.code, props.initialRows, scorer, answers, props.initialAnswers]);
  // Empty state with a reason: the one filter whose removal brings back the most cars.
  const relax = useMemo(
    () => (matches.length === 0 && (all || dirty) ? mostRestrictive(state.filters, (f) => runFilters(f).length) : null),
    [matches.length, all, dirty, state.filters, runFilters],
  );

  const rows = matches.slice(0, limit);
  // One card per generation, in the order of their best-placed variant (T-130 design).
  const cards = useMemo(() => generationCards(matches, props.code, state.filters), [matches, props.code, state.filters]);
  const shownCards = cards.slice(0, limit);
  const modelCount = all || dirty ? cards.length : props.initialMatchModels;
  const totalModels = all ? generationCount(all) : props.totalModels;
  const groups = activeGroups(state.filters).length;
  // Phone: the filters open as a bottom sheet (T-130 design); on lg+ they are a sidebar.
  const [sheet, setSheet] = useState(false);
  const moreLeft = state.view === "table" ? matches.length - rows.length : cards.length - shownCards.length;

  const countryName = t(`country.in.${props.code}` as MsgKey);
  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
      <FiltersPanel
        filters={state.filters}
        onChange={setFilter}
        onReset={() => update({ ...state, filters: defaultFilters() })}
        ctx={ctx}
        brands={props.brands}
        open={sheet}
        onClose={() => setSheet(false)}
        matches={modelCount}
      />
      <section aria-labelledby="results-heading" className="min-w-0">
        <h2 id="results-heading" className="sr-only">
          {t("explore.results")}
        </h2>
        <p aria-live="polite" className="mb-3 text-sm text-slate-800" data-testid="result-count">
          {groups ? t("explore.models.match", { shown: modelCount, total: totalModels }) : t("explore.models.all", { total: totalModels })}
          {props.code !== "UK" ? ` · ${t("explore.models.prices", { country: countryName })}` : ""}
          {!all ? <span className="ml-2 text-slate-600">{t("explore.loading")}</span> : null}
        </p>
        <div className="mb-3 flex flex-wrap gap-2">
          <span className="inline-flex items-center">
            <Toggle
              label={t("level")}
              options={LEVELS.map((l) => ({ value: l, label: t(`level.${l}`) }))}
              value={state.level}
              onChange={setLevel}
              testId="level-switch"
            />
            <TermInfo term={props.taxonomy.terms["detail-level"]} base={ctx.base} text={ctx.termText} />
          </span>
          <Toggle
            label={t("explore.view")}
            options={(["cards", "table"] as const).map((v) => ({ value: v, label: t(`explore.view.${v}`) }))}
            value={state.view}
            onChange={setView}
          />
        </div>

        {/* Phone: sticky bar with "Filters · n" and the sort menu; pills scroll sideways under it.
            lg+: pills + Clear on the left, sort on the right, in one bar (T-130 design). */}
        <div
          className="sticky top-0 z-30 -mx-1 mb-2 flex flex-wrap items-center gap-2 border-y border-slate-300 bg-[var(--paper)] px-1 py-2 lg:static lg:mx-0 lg:px-0"
          data-testid="explore-bar"
        >
          <button
            type="button"
            aria-expanded={sheet}
            aria-controls="filters-panel"
            onClick={() => setSheet(true)}
            className="order-1 inline-flex min-h-11 items-center gap-2 rounded-md border border-slate-500 bg-white px-3 text-sm font-semibold lg:hidden"
            data-testid="filters-open"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-none stroke-current" strokeWidth="2">
              <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
              <circle cx="16" cy="7" r="2" />
              <circle cx="10" cy="17" r="2" />
            </svg>
            {groups ? t("filters.button.n", { n: groups }) : t("filters.title")}
          </button>
          <SortMenu state={state} onChange={(k) => update(sortBy(state, k))} t={t} />
          <ActivePills
            filters={state.filters}
            ctx={ctx}
            brands={props.brands}
            onChange={(f) => update({ ...state, filters: f })}
          />
        </div>
        {state.sort === "popular" ? (
          <p className="mb-3 text-sm text-slate-700" data-testid="popular-why">
            {t("sort.popular.why")}{" "}
            {props.howWeRankHref ? (
              <a href={props.howWeRankHref} className="font-medium text-blue-800 underline underline-offset-2">
                {t("sort.popular.how")}
              </a>
            ) : null}
          </p>
        ) : null}

        <SuggestedSort
          rp={rp}
          active={state.sort === "suggested"}
          onToggle={() => update({ ...state, sort: state.sort === "suggested" ? null : "suggested", dir: "desc" })}
          t={t}
          termText={ctx.termText}
          profileName={rp ? profileName(rp, t) : ""}
          hasScores={props.hasScores !== false}
        />
        <div className="mb-3 flex flex-col gap-2">
          <PayModeToggle value={state.pay} onChange={setPay} ui={financeUi} />
          {state.pay === "loan" ? <LoanBox profile={props.finance} settings={loanSettings} onChange={setLoanSettings} ui={financeUi} /> : null}
          {state.pay === "lease" ? <LeaseNotice ui={financeUi} /> : null}
        </div>

        {tripFit ? (
          <TripBar
            ctx={ctx}
            open={tripOpen}
            settings={tripSettings}
            mod={tripMod}
            filterOn={state.filters.tripFit}
            onOpen={openTrip}
            onFilter={(on) => setFilter({ tripFit: on })}
          />
        ) : null}
        {tripFit && tripOpen ? (
          tripMod && tripSettings ? (
            <tripMod.TripPanel
              settings={tripSettings}
              onChange={changeTrip}
              onClose={() => setTripOpen(false)}
              onClear={clearTrip}
              fits={fits}
              ui={{ t, level: state.level, locale, labels: ctx.labels, country: props.country, gloss: { base: ctx.base, terms: ctx.tax.terms, text: ctx.termText } }}
            />
          ) : (
            <p className="mb-4 text-sm text-slate-700">{t("trip.loading")}</p>
          )
        ) : null}

        {rows.length === 0 ? (
          <EmptyState
            ctx={ctx}
            filters={state.filters}
            relax={relax}
            onRemove={(g) => update({ ...state, filters: withoutGroup(state.filters, g) })}
            onReset={() => update({ ...state, filters: defaultFilters() })}
          />
        ) : state.view === "table" ? (
          <ExploreTable rows={rows} state={state} onSort={(k) => update(nextSort(state, k))} ctx={ctx} />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="explore-cards">
            {shownCards.map((g) => (
              <GenerationCard key={g.generation_id} card={g} ctx={ctx} countryName={countryName} />
            ))}
          </ul>
        )}

        {moreLeft > 0 ? (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => setLimit((l) => l + PAGE * 2)}
              className="min-h-11 rounded-md border border-slate-500 px-4 py-2 text-sm font-medium hover:bg-slate-100"
              data-testid="show-more"
            >
              {t(state.view === "table" ? "explore.showMore" : "explore.showMoreModels", { n: Math.min(PAGE * 2, moreLeft) })}
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}

/* ---------- trip fit entry point (T-036) ---------- */

/** Label of one filter group as the filters panel shows it, with chosen values where it has them. */
function groupLabel(g: FilterGroup, f: ExploreFilters, c: Ctx): string {
  const { t } = c;
  const list = (label: string, values: string[]) => (values.length ? `${label}: ${values.join(", ")}` : label);
  switch (g) {
    case "usedMin": return t("filters.used");
    case "winterMin": return t("filters.winter");
    case "wltpMin": return t("filters.wltp");
    case "priceMax": return t("filters.price");
    case "eras": return list(t("filters.era"), f.eras);
    case "segments": return list(t("filters.segment"), f.segments.map((v) => t(`segment.${v}` as MsgKey)));
    case "bodies": return list(t("filters.body"), f.bodies.map((v) => t(`body.${v}` as MsgKey)));
    case "rangeMin": return t("filters.range");
    case "batteryMin": return t("filters.battery");
    case "dcMin": return t("filters.dc");
    case "bootMin": return t("filters.boot");
    case "lengthMax": return t("filters.length");
    case "towingMin": return t("filters.towing");
    case "seatsMin": return t("filters.seats");
    case "acMin": return t("filters.ac");
    case "yearMin": return t("filters.years");
    case "makes": return list(t("filters.makes"), f.makes);
    case "excludeMakes": return list(t("filters.excludeMakes"), f.excludeMakes);
    case "voltageClasses": return list(t("filters.voltage"), f.voltageClasses.map((v) => named(c.names.voltage, v, c)));
    case "voltageMin": return t("filters.vrange");
    case "fast400": return t("filters.fast400");
    case "chemistries": return list(t("filters.chemistry"), f.chemistries.map((v) => named(c.names.chem, v, c)));
    case "coolings": return list(t("filters.cooling"), f.coolings.map((v) => named(c.names.cool, v, c)));
    case "charge100": return t("filters.charge100");
    case "tripFit": return t("trip.filter");
  }
}

/** "No cars match": names the most restrictive filter and offers to remove it (or reset all). */
function EmptyState({
  ctx,
  filters,
  relax,
  onRemove,
  onReset,
}: {
  ctx: Ctx;
  filters: ExploreFilters;
  relax: { group: FilterGroup; count: number } | null;
  onRemove: (g: FilterGroup) => void;
  onReset: () => void;
}) {
  const { t } = ctx;
  const name = relax ? groupLabel(relax.group, filters, ctx) : "";
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-slate-400 p-6 text-center text-slate-800" data-testid="explore-empty" role="status">
      <p>{relax ? t("explore.noResults.reason", { filter: name, n: relax.count }) : t("explore.noResults")}</p>
      <div className="flex flex-wrap justify-center gap-3">
        {relax ? (
          <button
            type="button"
            onClick={() => onRemove(relax.group)}
            className="min-h-9 rounded-md border border-blue-800 bg-blue-800 px-3 text-sm font-semibold text-white hover:bg-blue-900"
            data-testid="explore-empty-remove"
            data-group={relax.group}
          >
            {t("explore.noResults.remove", { filter: name })}
          </button>
        ) : null}
        <button type="button" onClick={onReset} className="min-h-9 rounded-md border border-slate-400 px-3 text-sm text-blue-800 underline underline-offset-2">
          {t("filters.reset")}
        </button>
      </div>
    </div>
  );
}

function TripBar({
  ctx,
  open,
  settings,
  mod,
  filterOn,
  onOpen,
  onFilter,
}: {
  ctx: Ctx;
  open: boolean;
  settings: TripSettings | null;
  mod: TripModule | null;
  filterOn: boolean;
  onOpen: () => void;
  onFilter: (on: boolean) => void;
}) {
  const { t } = ctx;
  const has = !!mod && mod.hasTrip(settings);
  return (
    <div className="mb-3 flex flex-wrap items-center gap-3" data-testid="trip-bar">
      {has ? (
        <>
          <button
            type="button"
            onClick={onOpen}
            aria-expanded={open}
            className="inline-flex min-h-9 items-center gap-1 rounded-full border border-blue-800 bg-blue-50 px-3 text-sm font-medium text-blue-900 hover:bg-blue-100"
            data-testid="trip-chip"
          >
            {t("trip.chip", { km: settings!.roundTripKm! })} <span className="underline underline-offset-2">{t("trip.edit")}</span>
          </button>
          <span className="flex items-center gap-1">
            <label htmlFor="f-trip" className="flex items-center gap-2 text-sm font-medium">
              <input id="f-trip" type="checkbox" checked={filterOn} onChange={(e) => onFilter(e.target.checked)} className="h-4 w-4 accent-blue-800" />
              {t("trip.filter")}
            </label>
            <TermInfo term={ctx.tax.terms["trip-fit"]} base={ctx.base} text={ctx.termText} />
          </span>
        </>
      ) : (
        <button
          type="button"
          onClick={onOpen}
          aria-expanded={open}
          className="min-h-9 rounded-md border border-blue-800 px-3 text-sm font-semibold text-blue-900 hover:bg-blue-50"
          data-testid="trip-open"
        >
          {t("trip.open")}
        </button>
      )}
      {has ? null : <TermInfo term={ctx.tax.terms["trip-fit"]} base={ctx.base} text={ctx.termText} />}
    </div>
  );
}

function Toggle<V extends string>({
  label,
  options,
  value,
  onChange,
  testId,
}: {
  label: string;
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
  testId?: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-md border border-slate-400 p-0.5" data-testid={testId}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded px-3 py-1 text-sm ${value === o.value ? "bg-slate-900 text-white" : "text-slate-900 hover:bg-slate-100"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- filters ---------- */

function FilterLabel({ htmlFor, termId, fallback, ctx, plain = false }: { htmlFor?: string; termId: string; fallback: string; ctx: Ctx; plain?: boolean }) {
  const term = ctx.tax.terms[termId];
  const Tag = htmlFor ? "label" : "span";
  return (
    <span className="flex items-start justify-between gap-1">
      <Tag {...(htmlFor ? { htmlFor } : {})} className="text-sm font-medium">
        <TermLabel term={term ? { ...term, label: fallback } : undefined} fallback={fallback} showTechnical={!plain && ctx.level !== "simple"} />
      </Tag>
      <TermInfo term={term} base={ctx.base} text={ctx.termText} />
    </span>
  );
}

function NumberFilter({
  id,
  termId,
  label,
  value,
  onChange,
  step = 1,
  ctx,
  plain = false,
}: {
  /** Short label without the technical line (T-130 sidebar pairs: min/max, from/to). */
  plain?: boolean;
  id: NumericFilter;
  termId: string;
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
  ctx: Ctx;
}) {
  return (
    <div className="flex flex-col gap-1">
      <FilterLabel htmlFor={`f-${id}`} termId={termId} fallback={label} ctx={ctx} plain={plain} />
      <input
        id={`f-${id}`}
        name={id}
        type="number"
        inputMode="numeric"
        min={0}
        step={step}
        value={value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          const n = raw === "" ? null : Number(raw);
          onChange(n !== null && Number.isFinite(n) && n >= 0 ? n : null);
        }}
        className="w-full rounded-md border border-slate-400 bg-white px-2 py-1.5 text-sm tabular-nums"
      />
    </div>
  );
}

function Chips<V extends string>({
  legend,
  termId,
  options,
  selected,
  onChange,
  ctx,
  info,
  legendHidden = false,
}: {
  legend: string;
  /** The group already shows the title (T-130 sidebar): keep the legend for screen readers only. */
  legendHidden?: boolean;
  termId: string;
  options: readonly { value: V; label: string }[];
  selected: V[];
  onChange: (next: V[]) => void;
  ctx: Ctx;
  info?: (v: V) => ReactNode;
}) {
  const term = ctx.tax.terms[termId];
  return (
    <fieldset>
      {legendHidden ? (
        <legend className="sr-only">{legend}</legend>
      ) : (
        <legend className="mb-1 flex w-full items-start justify-between gap-1 text-sm font-medium">
          <span>{legend}</span>
          <TermInfo term={term} base={ctx.base} text={ctx.termText} />
        </legend>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <span key={o.value} className="inline-flex items-center">
            <label className="cursor-pointer">
              <input
                type="checkbox"
                className="peer sr-only"
                checked={selected.includes(o.value)}
                onChange={(e) => onChange(e.target.checked ? [...selected, o.value] : selected.filter((x) => x !== o.value))}
              />
              <span className="inline-flex min-h-10 items-center gap-1 rounded-md border border-slate-500 bg-white px-3 text-sm text-slate-900 hover:bg-slate-100 peer-checked:border-2 peer-checked:border-[var(--ink)] peer-checked:font-semibold peer-focus-visible:outline peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-blue-700">
                {selected.includes(o.value) ? <span aria-hidden="true">✓</span> : null}
                {o.label}
              </span>
            </label>
            {info?.(o.value)}
          </span>
        ))}
        {legendHidden ? (
          <span className="inline-flex items-center">
            <TermInfo term={term} base={ctx.base} text={ctx.termText} />
          </span>
        ) : null}
      </div>
    </fieldset>
  );
}

function Flag({ id, termId, label, checked, onChange, ctx }: { id: string; termId: string; label: string; checked: boolean; onChange: (v: boolean) => void; ctx: Ctx }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <label htmlFor={id} className="flex items-start gap-2 text-sm font-medium">
        <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-4 w-4 accent-blue-800" />
        {label}
      </label>
      <TermInfo term={ctx.tax.terms[termId]} base={ctx.base} text={ctx.termText} />
    </div>
  );
}

function VoltageSlider({ f, onChange, ctx }: { f: ExploreFilters; onChange: (p: Partial<ExploreFilters>) => void; ctx: Ctx }) {
  const { t } = ctx;
  const [lo, hi] = voltageBounds(ctx.tax);
  const vmin = f.voltageMin ?? lo;
  const vmax = f.voltageMax ?? hi;
  return (
    <details className="rounded-md border border-slate-300 bg-white p-2" open={ctx.level === "nerd" || f.voltageMin !== null || f.voltageMax !== null}>
      <summary className="cursor-pointer text-sm font-medium">{t("filters.advanced")}</summary>
      <div className="mt-2 flex flex-col gap-2">
        <FilterLabel termId="nominal-voltage" fallback={ctx.tax.terms["nominal-voltage"]?.label ?? t("filters.vmin")} ctx={ctx} />
        <label htmlFor="f-vmin" className="text-xs">
          {t("filters.vmin")}: <span className="tabular-nums">{vmin}</span>
        </label>
        <input id="f-vmin" type="range" min={lo} max={hi} step={10} value={vmin} onChange={(e) => {
          const v = Number(e.target.value);
          onChange({ voltageMin: v <= lo ? null : Math.min(v, vmax) });
        }} className="accent-blue-800" />
        <label htmlFor="f-vmax" className="text-xs">
          {t("filters.vmax")}: <span className="tabular-nums">{vmax}</span>
        </label>
        <input id="f-vmax" type="range" min={lo} max={hi} step={10} value={vmax} onChange={(e) => {
          const v = Number(e.target.value);
          onChange({ voltageMax: v >= hi ? null : Math.max(v, vmin) });
        }} className="accent-blue-800" />
      </div>
    </details>
  );
}

function ChemistryInfo({ id, ctx }: { id: string; ctx: Ctx }) {
  const c = ctx.tax.chemistries.find((x) => x.id === id);
  if (!c) return null;
  const { t } = ctx;
  const list = (title: string, items: string[]) =>
    items.length ? (
      <span className="mt-1 block">
        <span className="font-semibold">{title}</span>
        {items.map((i) => (
          <span key={i} className="block">
            · {i}
          </span>
        ))}
      </span>
    ) : null;
  return (
    <InfoTip label={c.label} href={`${ctx.base}/learn/chemistry`} text={ctx.termText}>
      {c.explainer ? <span className="block">{c.explainer}</span> : null}
      {list(t("chem.pros"), c.pros)}
      {list(t("chem.cons"), c.cons)}
      {list(t("chem.care"), c.care)}
      {c.charge100 !== null ? (
        <span className="mt-1 block">
          {t("chem.charge100")}: {c.charge100 ? t("yes") : t("no")}
        </span>
      ) : null}
    </InfoTip>
  );
}

/** One collapsible filter group (T-130 sidebar): open by default, or when one of its filters is on. */
function Group({ title, open, children, testId }: { title: string; open: boolean; children: ReactNode; testId: string }) {
  // `open` only ever opens the group (first render, or when one of its filters turns on): a group
  // never snaps shut under the cursor when its last value is cleared (review #126).
  const [initial] = useState(open);
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (open && ref.current) ref.current.open = true;
  }, [open]);
  return (
    <details ref={ref} open={initial} className="group border-t border-slate-300 pt-3 first:border-t-0 first:pt-0" data-testid={testId}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 font-semibold [&::-webkit-details-marker]:hidden">
        {title}
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 shrink-0 fill-none stroke-current transition-transform group-open:rotate-180" strokeWidth="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </summary>
      <div className="flex flex-col gap-3 pb-1 pt-1">{children}</div>
    </details>
  );
}

/** "+100 km" tiles for km added in 20 min (sets dcMin; pressing the chosen tile again clears it). */
const DC_STEPS = [100, 150, 200] as const;

/** Winter range slider bounds (km); 0 = any. */
const WINTER_MAX = 500;
const WINTER_STEP = 10;
/** T-143: the official WLTP slider's top (release 2's longest WLTP figure is 850 km). */
const WLTP_MAX = 900;

function BrandFilter({ f, onChange, brands, ctx }: { f: ExploreFilters; onChange: (p: Partial<ExploreFilters>) => void; brands: ExploreProps["brands"]; ctx: Ctx }) {
  const { t } = ctx;
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const needle = q.trim().toLowerCase();
  const found = needle ? brands.filter((b) => b.name.toLowerCase().includes(needle)) : brands;
  // Chosen brands always stay in the list, so they can be unticked.
  const list = needle || all ? found : found.filter((b, i) => i < BRANDS_SHOWN || f.makes.includes(b.id));
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor="f-brand-search" className="sr-only">
        {t("filters.brands.search")}
      </label>
      <input
        id="f-brand-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("filters.brands.search")}
        className="min-h-11 w-full rounded-md border border-slate-500 bg-white px-3 text-sm"
      />
      <ul className="flex flex-col" data-testid="brand-list">
        {list.map((b) => (
          <li key={b.id}>
            <label className="flex min-h-10 cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={f.makes.includes(b.id)}
                onChange={(e) => onChange({ makes: e.target.checked ? [...f.makes, b.id] : f.makes.filter((x) => x !== b.id) })}
                className="h-5 w-5 accent-blue-800"
              />
              <span className="flex-1">{b.name}</span>
              <span className="tabular-nums text-slate-700">
                <span aria-hidden="true">{b.count}</span>
                <span className="sr-only">{t("filters.brands.count", { n: b.count })}</span>
              </span>
            </label>
          </li>
        ))}
        {!list.length ? <li className="text-sm text-slate-700">{t("filters.brands.none")}</li> : null}
      </ul>
      {!needle && brands.length > BRANDS_SHOWN ? (
        <button type="button" aria-expanded={all} onClick={() => setAll((v) => !v)} className="min-h-10 w-fit text-sm font-medium text-blue-800 underline underline-offset-2">
          {all ? t("filters.brands.fewer") : t("filters.brands.all", { n: brands.length })}
        </button>
      ) : null}
    </div>
  );
}

const BRANDS_SHOWN = 6;
/** Tailwind's lg breakpoint: the sidebar layout. */
const LG_UP = "(min-width: 64rem)";
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

function FiltersPanel({
  filters: f,
  onChange,
  onReset,
  ctx,
  brands,
  open,
  onClose,
  matches,
}: {
  filters: ExploreFilters;
  onChange: (p: Partial<ExploreFilters>) => void;
  onReset: () => void;
  ctx: Ctx;
  brands: ExploreProps["brands"];
  /** Phone bottom sheet open (lg+: always shown as a sidebar). */
  open: boolean;
  onClose: () => void;
  /** Models matching now, for "Show 87 cars". */
  matches: number;
}) {
  const { t, level, tax } = ctx;
  const n = activeGroups(f).length;
  const more = level !== "simple";
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // The parent passes a new function every render; keep the latest in a ref so the effect below
  // runs only when the sheet opens or closes (review #126: it re-ran on every filter change and
  // pulled focus out of the field being typed in).
  const closeFn = useRef(onClose);
  useEffect(() => {
    closeFn.current = onClose;
  }, [onClose]);
  // Sheet: focus the close button on open, Escape closes, Tab stays inside, the page behind doesn't
  // scroll; widening to the sidebar layout closes it; focus goes back to the "Filters" button.
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeFn.current();
      if (e.key !== "Tab" || !sheetRef.current) return;
      const items = [...sheetRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      const inside = sheetRef.current.contains(document.activeElement);
      if (e.shiftKey && (document.activeElement === first || !inside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const wide = window.matchMedia?.(LG_UP);
    const onWide = () => {
      if (wide?.matches) closeFn.current();
    };
    wide?.addEventListener?.("change", onWide);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      wide?.removeEventListener?.("change", onWide);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [open]);
  const winter = f.winterMin ?? 0;
  const wltp = f.wltpMin ?? 0;
  const anyOf = (...keys: (keyof ExploreFilters)[]) => keys.some((k) => { const v = f[k]; return Array.isArray(v) ? v.length > 0 : typeof v === "boolean" ? v : v !== null; });
  const moreOpen = anyOf("priceMax", "rangeMin", "eras", "fast400", "charge100", "segments", "voltageClasses", "chemistries", "coolings", "bootMin", "lengthMax", "acMin", "voltageMin", "voltageMax", "excludeMakes") || (f.dcMin !== null && !(DC_STEPS as readonly number[]).includes(f.dcMin));
  return (
    <aside
      id="filters-panel"
      aria-labelledby="filters-heading"
      className={`${open ? "fixed inset-0 z-50 flex flex-col justify-end bg-[color-mix(in_srgb,var(--ink)_45%,transparent)]" : "hidden"} lg:z-auto lg:block lg:bg-transparent lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:self-start lg:overflow-y-auto`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      data-testid="filters-panel"
    >
      <div
        ref={sheetRef}
        role={open ? "dialog" : undefined}
        aria-modal={open || undefined}
        aria-labelledby={open ? "filters-heading" : undefined}
        className="flex max-h-[88vh] flex-col rounded-t-2xl bg-white lg:max-h-none lg:rounded-none lg:bg-transparent"
      >
        <div className="flex items-center justify-between gap-2 px-4 pb-2 pt-4 lg:px-0 lg:pt-0">
          <h2 id="filters-heading" ref={headingRef} tabIndex={-1} className="text-lg font-bold">
            {t("filters.title")}
          </h2>
          <span className="flex items-center gap-3">
            {n ? (
              <button
                type="button"
                // The button disappears once nothing is on: put focus on the heading, not on <body>.
                onClick={() => {
                  onReset();
                  headingRef.current?.focus();
                }}
                className="min-h-10 text-sm font-medium text-blue-800 underline underline-offset-2"
                data-testid="filters-clear-all"
              >
                {t("filters.clearAll")}
              </button>
            ) : null}
            <button ref={closeRef} type="button" onClick={onClose} className="grid h-11 w-11 place-items-center rounded-full hover:bg-slate-100 lg:hidden" aria-label={t("filters.close")}>
              <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current" strokeWidth="2">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </span>
        </div>
        <form
          id="filters-form"
          role="search"
          aria-labelledby="filters-heading"
          onSubmit={(e) => e.preventDefault()}
          className="flex flex-col gap-3 overflow-y-auto border-slate-300 px-4 pb-4 lg:overflow-visible lg:rounded-lg lg:border lg:bg-white lg:p-4"
        >
          <Group title={t("filters.used")} open testId="fg-used">
            <div className="grid grid-cols-2 gap-2">
              <NumberFilter id="usedMin" termId="used-price" plain label={t("filters.used.min", { currency: ctx.currency })} value={f.usedMin} step={1000} onChange={(v) => onChange({ usedMin: v })} ctx={ctx} />
              <NumberFilter id="usedMax" termId="" label={t("filters.used.max", { currency: ctx.currency })} value={f.usedMax} step={1000} onChange={(v) => onChange({ usedMax: v })} ctx={ctx} />
            </div>
          </Group>
          <Group title={t("filters.rangeGroup")} open testId="fg-winter">
            <span className="flex items-start justify-between gap-1">
              <label htmlFor="f-winterMin" className="text-sm">
                {winter > 0 ? t("filters.winter.atLeast", { n: winter }) : t("filters.winter.any")}
              </label>
              <TermInfo term={tax.terms["real-winter-range"]} base={ctx.base} text={ctx.termText} />
            </span>
            <input
              id="f-winterMin"
              type="range"
              min={0}
              max={WINTER_MAX}
              step={WINTER_STEP}
              value={winter}
              aria-valuetext={winter > 0 ? t("filters.winter.atLeast", { n: winter }) : t("filters.winter.any")}
              onChange={(e) => {
                const v = Number(e.target.value);
                onChange({ winterMin: v > 0 ? v : null });
              }}
              className="w-full accent-blue-800"
            />
            {/* T-143 (Decision 085): real range leads; the official WLTP figure is the second control in the same group. */}
            <span className="mt-2 flex items-start justify-between gap-1">
              <label htmlFor="f-wltpMin" className="text-xs text-slate-700">
                {wltp > 0 ? t("filters.wltp.atLeast", { n: wltp }) : t("filters.wltp.any")}
              </label>
              <InfoTip label={t("range.wltp.label")} href={`${ctx.base}/learn/wltp`} text={ctx.termText}>
                <span className="block">{t("range.wltp.tip")}</span>
              </InfoTip>
            </span>
            <input
              id="f-wltpMin"
              type="range"
              min={0}
              max={WLTP_MAX}
              step={WINTER_STEP}
              value={wltp}
              aria-valuetext={wltp > 0 ? t("filters.wltp.atLeast", { n: wltp }) : t("filters.wltp.any")}
              onChange={(e) => {
                const v = Number(e.target.value);
                onChange({ wltpMin: v > 0 ? v : null });
              }}
              className="w-full accent-blue-800"
              data-testid="filter-wltp"
            />
          </Group>
          <Group title={t("filters.body")} open testId="fg-body">
            <Chips legend={t("filters.body")} legendHidden termId="body-type" options={BODIES.map((b) => ({ value: b, label: t(`body.${b}` as MsgKey) }))} selected={f.bodies} onChange={(bodies) => onChange({ bodies })} ctx={ctx} />
          </Group>
          <Group title={t("filters.fast")} open testId="fg-fast">
            <div role="group" aria-label={t("filters.fast.label")} className="flex flex-wrap gap-2">
              {DC_STEPS.map((km) => (
                <button
                  key={km}
                  type="button"
                  aria-pressed={f.dcMin === km}
                  onClick={() => onChange({ dcMin: f.dcMin === km ? null : km })}
                  className={TILE}
                >
                  {f.dcMin === km ? <span aria-hidden="true">✓</span> : null}
                  {t("filters.fast.km", { n: km })}
                </button>
              ))}
            </div>
            <span className="flex items-start justify-between gap-1 text-sm text-slate-700">
              {t("filters.fast.hint")}
              <TermInfo term={tax.terms["dc-km-20min"]} base={ctx.base} text={ctx.termText} />
            </span>
          </Group>
          <Group title={t("filters.years")} open testId="fg-years">
            <div className="grid grid-cols-2 gap-2">
              <NumberFilter id="yearMin" termId="model-years" plain label={t("hero.refine.yearFrom")} value={f.yearMin} onChange={(v) => onChange({ yearMin: v })} ctx={ctx} />
              <NumberFilter id="yearMax" termId="" label={t("hero.refine.yearTo")} value={f.yearMax} onChange={(v) => onChange({ yearMax: v })} ctx={ctx} />
            </div>
          </Group>
          <Group title={t("filters.sbt")} open={anyOf("seatsMin", "batteryMin", "towingMin")} testId="fg-sbt">
            <NumberFilter id="seatsMin" termId="seats" label={t("filters.seats")} value={f.seatsMin} onChange={(v) => onChange({ seatsMin: v })} ctx={ctx} />
            <NumberFilter id="batteryMin" termId="usable-vs-gross" label={t("filters.battery")} value={f.batteryMin} onChange={(v) => onChange({ batteryMin: v })} ctx={ctx} />
            <NumberFilter id="towingMin" termId="towing-capacity" label={t("filters.towing")} value={f.towingMin} step={100} onChange={(v) => onChange({ towingMin: v })} ctx={ctx} />
          </Group>
          <Group title={t("filters.makes")} open testId="fg-brands">
            <BrandFilter f={f} onChange={onChange} brands={brands} ctx={ctx} />
          </Group>
          <Group title={t("filters.more")} open={moreOpen} testId="fg-more">
            <NumberFilter id="priceMax" termId="new-price" label={`${t("filters.price")} (${ctx.currency})`} value={f.priceMax} step={1000} onChange={(v) => onChange({ priceMax: v })} ctx={ctx} />
            <NumberFilter id="rangeMin" termId="real-range" label={t("filters.range")} value={f.rangeMin} step={10} onChange={(v) => onChange({ rangeMin: v })} ctx={ctx} />
            <Chips legend={t("filters.era")} termId="era" options={ERAS.map((e) => ({ value: e, label: e }))} selected={f.eras} onChange={(eras) => onChange({ eras })} ctx={ctx} />
            <Flag id="f-fast400" termId="400v-charger-behaviour" label={t("filters.fast400")} checked={f.fast400} onChange={(fast400) => onChange({ fast400 })} ctx={ctx} />
            <Flag id="f-c100" termId="charge-to-100" label={t("filters.charge100")} checked={f.charge100} onChange={(charge100) => onChange({ charge100 })} ctx={ctx} />
            {more ? (
              <>
                <Chips legend={t("filters.segment")} termId="segment" options={SEGMENTS.map((s) => ({ value: s, label: t(`segment.${s}` as MsgKey) }))} selected={f.segments} onChange={(segments) => onChange({ segments })} ctx={ctx} />
                <Chips legend={t("filters.voltage")} termId="voltage-class" options={tax.voltageClasses.map((v) => ({ value: v.id, label: v.label }))} selected={f.voltageClasses} onChange={(voltageClasses) => onChange({ voltageClasses })} ctx={ctx} />
                <Chips
                  legend={t("filters.chemistry")}
                  termId="chemistry"
                  options={tax.chemistries.map((c) => ({ value: c.id, label: c.label }))}
                  selected={f.chemistries}
                  onChange={(chemistries) => onChange({ chemistries })}
                  ctx={ctx}
                  info={(id) => <ChemistryInfo id={id} ctx={ctx} />}
                />
                <Chips legend={t("filters.cooling")} termId="cooling" options={tax.coolings.map((c) => ({ value: c.id, label: c.label }))} selected={f.coolings} onChange={(coolings) => onChange({ coolings })} ctx={ctx} />
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
                  <NumberFilter id="dcMin" termId="dc-km-20min" label={t("filters.dc")} value={f.dcMin} step={5} onChange={(v) => onChange({ dcMin: v })} ctx={ctx} />
                  <NumberFilter id="bootMin" termId="boot-volume" label={t("filters.boot")} value={f.bootMin} step={10} onChange={(v) => onChange({ bootMin: v })} ctx={ctx} />
                  <NumberFilter id="lengthMax" termId="vehicle-length" label={t("filters.length")} value={f.lengthMax} step={50} onChange={(v) => onChange({ lengthMax: v })} ctx={ctx} />
                  <NumberFilter id="acMin" termId="ac-charging" label={t("filters.ac")} value={f.acMin} onChange={(v) => onChange({ acMin: v })} ctx={ctx} />
                </div>
                <VoltageSlider f={f} onChange={onChange} ctx={ctx} />
              </>
            ) : null}
          </Group>
          <p className="text-xs text-slate-700">{t("filters.hint")}</p>
        </form>
        <div className="border-t border-slate-300 p-4 lg:hidden">
          <button type="button" onClick={onClose} className="min-h-12 w-full rounded-md bg-blue-800 px-4 text-base font-semibold text-white hover:bg-blue-900" data-testid="filters-show">
            {t("filters.show", { n: matches })}
          </button>
        </div>
      </div>
    </aside>
  );
}

/** Active filters as removable pills + Clear (T-130 design). List filters get one pill per value. */
function ActivePills({ filters: f, ctx, brands, onChange }: { filters: ExploreFilters; ctx: Ctx; brands: ExploreProps["brands"]; onChange: (f: ExploreFilters) => void }) {
  const { t, locale } = ctx;
  const money = (v: number) => formatMoney(v, ctx.currency, locale);
  const n = (v: number) => formatNumber(v, locale, 0);
  const brand = (id: string) => brands.find((b) => b.id === id)?.name ?? id;
  const pills: { key: string; label: string; next: ExploreFilters }[] = [];
  const drop = (g: FilterGroup, label: string) => pills.push({ key: g, label, next: withoutGroup(f, g) });
  const dropValue = <K extends "eras" | "segments" | "bodies" | "makes" | "excludeMakes" | "voltageClasses" | "chemistries" | "coolings">(k: K, v: string, label: string) =>
    pills.push({ key: `${k}:${v}`, label, next: { ...f, [k]: (f[k] as string[]).filter((x) => x !== v) } });
  for (const g of activeGroups(f)) {
    switch (g) {
      case "usedMin":
        drop(g, f.usedMin !== null && f.usedMax !== null ? t("pill.used.range", { min: money(f.usedMin), max: money(f.usedMax) }) : f.usedMax !== null ? t("pill.used.max", { max: money(f.usedMax) }) : t("pill.used.min", { min: money(f.usedMin ?? 0) }));
        break;
      case "winterMin": drop(g, t("pill.winter", { n: n(f.winterMin ?? 0) })); break;
      case "wltpMin": drop(g, t("pill.wltp", { n: n(f.wltpMin ?? 0) })); break;
      case "priceMax": drop(g, t("pill.price", { max: money(f.priceMax ?? 0) })); break;
      case "rangeMin": drop(g, t("pill.range", { n: n(f.rangeMin ?? 0) })); break;
      case "batteryMin": drop(g, t("pill.battery", { n: n(f.batteryMin ?? 0) })); break;
      case "dcMin": drop(g, t("pill.dc", { n: n(f.dcMin ?? 0) })); break;
      case "bootMin": drop(g, t("pill.boot", { n: n(f.bootMin ?? 0) })); break;
      case "lengthMax": drop(g, t("pill.length", { n: n(f.lengthMax ?? 0) })); break;
      case "towingMin": drop(g, t("pill.towing", { n: n(f.towingMin ?? 0) })); break;
      case "seatsMin": drop(g, t("pill.seats", { n: n(f.seatsMin ?? 0) })); break;
      case "acMin": drop(g, t("pill.ac", { n: n(f.acMin ?? 0) })); break;
      case "yearMin":
        drop(g, f.yearMin !== null && f.yearMax !== null ? t("pill.years.range", { from: f.yearMin, to: f.yearMax }) : f.yearMin !== null ? t("pill.years.from", { from: f.yearMin }) : t("pill.years.to", { to: f.yearMax ?? 0 }));
        break;
      case "eras": for (const v of f.eras) dropValue("eras", v, v); break;
      case "segments": for (const v of f.segments) dropValue("segments", v, t(`segment.${v}` as MsgKey)); break;
      case "bodies": for (const v of f.bodies) dropValue("bodies", v, t(`body.${v}` as MsgKey)); break;
      case "makes": for (const v of f.makes) dropValue("makes", v, brand(v)); break;
      case "excludeMakes": for (const v of f.excludeMakes) dropValue("excludeMakes", v, t("pill.exclude", { name: brand(v) })); break;
      case "voltageClasses": for (const v of f.voltageClasses) dropValue("voltageClasses", v, named(ctx.names.voltage, v, ctx)); break;
      case "chemistries": for (const v of f.chemistries) dropValue("chemistries", v, named(ctx.names.chem, v, ctx)); break;
      case "coolings": for (const v of f.coolings) dropValue("coolings", v, named(ctx.names.cool, v, ctx)); break;
      default: drop(g, groupLabel(g, f, ctx));
    }
  }
  if (!pills.length) return null;
  return (
    <ul
      className="order-3 flex w-full items-center gap-2 overflow-x-auto pb-1 lg:order-1 lg:w-auto lg:flex-1 lg:flex-wrap lg:overflow-visible lg:pb-0"
      aria-label={t("pill.list")}
      data-testid="filter-pills"
    >
      {pills.map((p) => (
        <li key={p.key} className="shrink-0">
          <button
            type="button"
            onClick={() => onChange(p.next)}
            className="inline-flex min-h-10 items-center gap-2 whitespace-nowrap rounded-full border border-slate-500 bg-white px-3 text-sm hover:bg-slate-100"
            data-testid="filter-pill"
          >
            {p.label}
            <span aria-hidden="true">×</span>
            <span className="sr-only">{t("pill.remove")}</span>
          </button>
        </li>
      ))}
      <li className="shrink-0">
        <button type="button" onClick={() => onChange(defaultFilters())} className="min-h-10 px-1 text-sm font-semibold text-blue-800 underline underline-offset-2" data-testid="filter-pills-clear">
          {t("pill.clear")}
        </button>
      </li>
    </ul>
  );
}

const TILE =
  "inline-flex min-h-10 items-center gap-1 rounded-md border border-slate-500 bg-white px-3 text-sm text-slate-900 hover:bg-slate-100 aria-pressed:border-2 aria-pressed:border-[var(--ink)] aria-pressed:font-semibold";


/* ---------- columns ---------- */

interface Col {
  id: string;
  key: SortKey | null;
  label: MsgKey;
  term?: string;
  num?: boolean;
  levels: readonly Level[];
  cell: (r: ExploreRow, c: Ctx) => ReactNode;
}

const ALL: readonly Level[] = LEVELS;
const DN: readonly Level[] = ["detailed", "nerd"];
const N: readonly Level[] = ["nerd"];

function num(r: ExploreRow, c: Ctx, v: number | null | undefined, field: string, unit?: string, digits = 1, note?: string, claim = isClaimField(r, field)) {
  return (
    <Num
      value={v}
      unit={unit}
      provenance={r.provenance[field]}
      sources={c.sources}
      locale={c.locale}
      labels={c.labels}
      digits={digits}
      note={note}
      noteTerm={field === "real_range_km" && note ? "rung" : undefined}
      claim={claim}
      level={c.level}
      asOf={c.asOf}
      focusable={!c.inTable}
    />
  );
}

function rangeNote(r: ExploreRow, c: Ctx): string | undefined {
  if (!r.real_range_rung) return undefined;
  const label = c.t(`rung.${r.real_range_rung}` as MsgKey);
  return c.level === "nerd" ? `${label} [${r.real_range_rung}]` : label;
}

/** T-143 (Decision 085): the strings and ⓘ link of the "Official (WLTP)" line. */
function wltpText(c: Ctx): OfficialRangeText {
  return { label: c.t("range.wltp.label"), notKnown: c.t("range.wltp.notKnown"), tip: c.t("range.wltp.tip") };
}

/** Real range leads; the official WLTP range sits under it in the same cell (no ⓘ in the table: Tab stops, rule 12). */
function rangeCell(r: ExploreRow, c: Ctx) {
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      {num(r, c, r.real_range_km, "real_range_km", "km", 0, rangeNote(r, c))}
      <OfficialRange
        value={r.wltp_range_km}
        provenance={r.provenance.wltp_range_km}
        sources={c.sources}
        locale={c.locale}
        labels={c.labels}
        level={c.level === "nerd" ? "nerd" : "simple"}
        asOf={c.asOf}
        focusable={!c.inTable}
        text={wltpText(c)}
        info={false}
      />
    </span>
  );
}

const NO_NAMES = new Map<string, string>();

function named(map: Map<string, string>, id: string | null | undefined, c: Ctx): string {
  if (!id) return "—";
  if (id === "not-disclosed") return c.t("notDisclosed");
  return map.get(id) ?? id;
}

function priceCell(r: ExploreRow, c: Ctx) {
  const amount = priceFor(r, c.code);
  const currency = r.price_new?.[c.code]?.currency ?? c.currency;
  if (c.pay === "lease") return <Missing label={c.t("pay.lease.none")} />;
  // Loan: the monthly estimate from this price + the shown loan inputs; hover = the price's source.
  const monthly = c.pay === "loan" ? monthlyFor(amount, c.loan) : null;
  if (c.pay === "loan" && !monthly) return <Missing label={amount === null ? c.t("num.noData") : c.t("pay.needRate")} />;
  return (
    <Num
      value={amount}
      text={
        monthly
          ? `≈ ${c.t("pay.perMonth", { amount: formatMoney(monthly.monthly, currency, c.locale) })}`
          : amount !== null
            ? formatMoney(amount, currency, c.locale)
            : undefined
      }
      note={monthly ? c.t("pay.estimate") : undefined}
      provenance={r.provenance[`price_new.${c.code}`] ?? r.provenance.price_new}
      sources={c.sources}
      locale={c.locale}
      labels={c.labels}
      level={c.level}
      asOf={c.asOf}
      focusable={!c.inTable}
    />
  );
}

function charger400(r: ExploreRow, c: Ctx) {
  // No DC figure means "no DC data": never imply the car fast-charges (shared rule, src/lib/dc.ts).
  if (!hasDcData(r)) return <Missing label={c.t("num.noDc")} />;
  if (!r.charger_400v_mode) return <Missing label={c.t("num.noData")} />;
  return (
    <span className="flex flex-col">
      <span>
        {c.t(`c400.${r.charger_400v_mode}` as MsgKey)}
        {r.fast_on_400v != null ? ` · ${r.fast_on_400v ? c.t("yes") : c.t("no")}` : ""}
      </span>
      {r.charger_400v_kw != null ? num(r, c, r.charger_400v_kw, "charger_400v_kw", "kW", 0) : null}
    </span>
  );
}

const COLS: Col[] = [
  { id: "car", key: "name", label: "col.car", levels: ALL, cell: () => null },
  { id: "gen", key: null, label: "col.generation", term: "generation", levels: DN, cell: (r, c) => (
      <Link href={generationHref(c.base, r)} tabIndex={c.inTable ? -1 : undefined} className="underline decoration-slate-400 underline-offset-2 hover:text-blue-900">
        {r.generation_name}
      </Link>
    ) },
  { id: "variant", key: null, label: "col.variant", term: "variant", levels: DN, cell: (r) => r.variant_name },
  { id: "years", key: "years", label: "col.years", term: "model-years", levels: ALL, cell: (r, c) => formatYears(r.year_start, r.year_end, c.t("years.now")) },
  { id: "era", key: "era", label: "col.era", term: "era", levels: DN, cell: (r) => r.era },
  { id: "range", key: "range", label: "col.range", term: "real-range", num: true, levels: ALL, cell: rangeCell },
  { id: "battery", key: "battery", label: "col.battery", term: "usable-vs-gross", num: true, levels: DN, cell: (r, c) => num(r, c, r.battery_kwh_net, "battery_kwh_net", "kWh") },
  { id: "dc", key: "dc", label: "col.dc", term: "dc-km-20min", num: true, levels: ALL, cell: (r, c) => num(r, c, r.dc_km_per_20min, "dc_km_per_20min", "km", 0) },
  { id: "ac", key: "ac", label: "col.ac", term: "ac-charging", num: true, levels: DN, cell: (r, c) => num(r, c, r.ac_km_per_h, "ac_km_per_h", "km/h", 0) },
  { id: "price", key: "price", label: "col.price", term: "new-price", num: true, levels: ALL, cell: priceCell },
  { id: "rdw", key: "rdw", label: "col.rdw", term: "registrations-nl", num: true, levels: DN, cell: (r, c) => num(r, c, r.registered_count_nl, "registered_count_nl", undefined, 0) },
  { id: "voltage", key: null, label: "col.voltage", term: "voltage-class", levels: DN, cell: (r, c) => named(c.names.voltage, r.voltage_class_id, c) },
  { id: "nominal", key: null, label: "col.voltage", term: "nominal-voltage", num: true, levels: N, cell: (r, c) => num(r, c, r.voltage_nominal_v, "voltage_nominal_v", "V", 0) },
  { id: "charger400", key: null, label: "col.charger400", term: "400v-charger-behaviour", levels: N, cell: charger400 },
  { id: "chem", key: null, label: "col.chemistry", term: "chemistry", levels: DN, cell: (r, c) => named(c.names.chem, r.chemistry_id, c) + (c.level === "nerd" && r.cell_format ? ` · ${named(NO_NAMES, r.cell_format, c)}` : "") },
  { id: "cool", key: null, label: "col.cooling", term: "cooling", levels: N, cell: (r, c) => named(c.names.cool, r.cooling_id, c) },
  { id: "platform", key: null, label: "col.platform", term: "platform", levels: N, cell: (r) => r.platform_name ?? "—" },
  { id: "pack", key: null, label: "col.pack", term: "battery-pack", levels: N, cell: (r, c) => named(NO_NAMES, r.battery_pack_id, c) },
  { id: "quality", key: "quality", label: "col.quality", term: "quality-tier", levels: ALL, cell: (r, c) => <QualityBadge tier={r.quality_tier} label={c.t(`tier.${r.quality_tier}`)} help={c.t(`tier.${r.quality_tier}.help`)} /> },
];

/** Columns shown at a level. Exported for tests. */
export function columnsFor(level: Level): string[] {
  return COLS.filter((c) => c.levels.includes(level)).map((c) => c.id);
}

/* ---------- table ---------- */

function ExploreTable({ rows, state, onSort, ctx: outer }: { rows: ExploreRow[]; state: ExploreState; onSort: (k: SortKey) => void; ctx: Ctx }) {
  const ctx = useMemo(() => ({ ...outer, inTable: true }), [outer]);
  const { t, level } = ctx;
  const cols = COLS.filter((c) => c.levels.includes(level));
  const trip = ctx.trip;
  // "Sort by {col}" split around the column name, so the words work in any language's order.
  const [sortBefore = "", sortAfter = ""] = t("sort.by", { col: "\u0000" }).split("\u0000");
  return (
    <div className="relative max-h-[75vh] overflow-auto rounded-lg border border-slate-300" tabIndex={0} aria-labelledby="results-heading" data-testid="explore-scroll">
      <table className="w-max min-w-full border-collapse text-sm" data-testid="explore-table">
        <thead>
          <tr>
            {cols.map((col, i) => {
              const sorted = col.key && state.sort === col.key;
              const ariaSort = sorted ? (state.dir === "asc" ? "ascending" : "descending") : col.key ? "none" : undefined;
              // Price column follows the price mode (Decision 017).
              const payCol = col.id === "price" && ctx.pay !== "buy" ? ctx.pay : null;
              const term = payCol ? ctx.tax.terms[payCol] : col.term ? ctx.tax.terms[col.term] : undefined;
              const label = <TermLabel term={term} fallback={payCol ? t(`pay.col.${payCol}`) : t(col.label)} showTechnical={level !== "simple"} />;
              return (
                <th
                  key={col.id}
                  scope="col"
                  aria-sort={ariaSort}
                  className={`sticky top-0 min-w-24 max-w-44 border-b border-slate-300 bg-slate-100 px-3 py-2 text-left align-bottom font-semibold ${i === 0 ? "left-0 z-30" : "z-20"}`}
                >
                  <span className={`flex items-end gap-1 ${col.num ? "justify-end" : ""}`}>
                    {col.key ? (
                      <button
                        type="button"
                        onClick={() => onSort(col.key!)}
                        // No aria-label: the accessible name must contain the visible label (WCAG 2.5.3,
                        // axe label-content-name-mismatch), so "Sort by" is sr-only text around it.
                        className="inline-flex min-h-6 items-end gap-1 rounded-sm text-left hover:underline"
                      >
                        {sortBefore.trim() ? <span className="sr-only">{sortBefore}</span> : null}
                        {label}
                        {sortAfter.trim() ? <span className="sr-only">{sortAfter}</span> : null}
                        <span aria-hidden="true" className="text-xs text-slate-600">
                          {sorted ? (state.dir === "asc" ? "▲" : "▼") : "↕"}
                        </span>
                      </button>
                    ) : (
                      label
                    )}
                    <TermInfo term={term} base={ctx.base} text={ctx.termText} />
                  </span>
                </th>
              );
            })}
            {trip ? (
              <th scope="col" className="sticky top-0 z-20 min-w-36 border-b border-slate-300 bg-slate-100 px-3 py-2 text-left align-bottom font-semibold" data-testid="trip-col">
                <span className="inline-flex items-end gap-1">
                  {t("trip.col")}
                  <TermInfo term={ctx.tax.terms["trip-fit"]} base={ctx.base} text={ctx.termText} />
                </span>
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const fit = trip?.fits.get(r.variant_id);
            const grey = fit?.verdict === "fail";
            return (
            <tr
              key={r.variant_id}
              className={`border-b border-slate-200 last:border-0 hover:bg-slate-50 ${grey ? "text-slate-600 [&>td]:opacity-70" : ""}`}
              data-testid="explore-row"
              data-trip={fit?.verdict}
            >
              {/* The sticky cell is a stacking context: while its Nerd "Sources" popover is open, lift it
                  above the sticky column headers (z-20/30), or an upward popover sits under them. */}
              <th scope="row" className="sticky left-0 z-10 bg-white px-3 py-2 text-left font-medium has-[[role=tooltip]:not([hidden])]:z-40">
                <div className="flex items-center gap-2">
                  <RowActions row={r} t={t} />
                  <span className="flex flex-col">
                    <Link href={variantHref(ctx.base, r)} className="inline-block min-h-6 whitespace-nowrap py-0.5 text-blue-800 underline underline-offset-2 hover:text-blue-950">
                      {r.make_name} {r.model_name}
                      {level !== "simple" ? <span className="sr-only"> {r.generation_name} {r.variant_name}</span> : null}
                    </Link>
                    {level === "nerd" ? <RowSources row={r} ctx={ctx} /> : null}
                    {level === "simple" ? (
                      <span className="whitespace-nowrap text-xs font-normal text-slate-700">
                        {r.generation_name} · {r.variant_name}
                      </span>
                    ) : null}
                  </span>
                </div>
              </th>
              {cols.slice(1).map((col) => (
                <td key={col.id} className={`px-3 py-2 ${col.num ? "text-right" : "whitespace-nowrap"}`}>
                  {col.cell(r, ctx)}
                </td>
              ))}
              {trip ? (
                <td className="px-3 py-2">
                  <trip.mod.TripCell fit={fit} ui={trip.ui} />
                </td>
              ) : null}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- per-row sources (Nerd level, keyboard access to provenance) ---------- */

/** Provenance key → column label, in display order. Price uses `price_new.<CC>`. */
const PROV_LABELS: readonly [string, MsgKey][] = [
  ["real_range_km", "col.range"],
  // T-143 review: the WLTP line in the range cell is not a Tab stop, so its sources must be reachable here.
  ["wltp_range_km", "range.wltp.label"],
  ["battery_kwh_net", "col.battery"],
  ["dc_km_per_20min", "col.dc"],
  ["dc_km_per_10min", "col.dc"],
  ["dc_peak_kw", "col.dcPeak"],
  ["ac_km_per_h", "col.ac"],
  ["price_new", "col.price"],
  ["registered_count_nl", "col.rdw"],
  ["voltage_nominal_v", "col.voltage"],
  ["charger_400v_kw", "col.charger400"],
  ["boot_l", "filters.boot"],
  ["length_mm", "filters.length"],
  ["towing_kg", "filters.towing"],
];

/** Rows of the per-row sources list: label, source names, confidence. Exported for tests. */
export function rowSources(r: ExploreRow, code: Country, sources: Record<string, string>) {
  const out: { key: string; label: MsgKey; names: string; confidence: FieldProvenance["confidence"]; estimate: boolean }[] = [];
  const dc = hasDcData(r);
  for (const [key, label] of PROV_LABELS) {
    if (key === "charger_400v_kw" && !dc) continue;
    const p = key === "price_new" ? (r.provenance[`price_new.${code}`] ?? r.provenance.price_new) : r.provenance[key];
    const value = key === "price_new" ? priceFor(r, code) : (r as unknown as Record<string, unknown>)[key];
    if (!p || value === null || value === undefined) continue;
    out.push({ key, label, names: p.source_ids.map((s) => sources[s] ?? s).join(", "), confidence: p.confidence, estimate: !!p.estimate });
  }
  return out;
}

function RowSources({ row, ctx }: { row: ExploreRow; ctx: Ctx }) {
  const { buttonProps, popoverProps } = usePopover();
  const list = rowSources(row, ctx.code, ctx.sources);
  if (!list.length) return null;
  const { t } = ctx;
  return (
    <span className="inline-flex">
      <button
        {...buttonProps}
        aria-label={t("explore.rowSources", { name: displayName(row) })}
        className="min-h-6 w-fit whitespace-nowrap rounded-sm text-left text-xs font-normal text-blue-800 underline decoration-dotted underline-offset-2"
        data-testid="row-sources"
      >
        {t("explore.sources")}
      </button>
      <span {...popoverProps}>
        <span className="mb-1 block font-semibold">{displayName(row)}</span>
        {list.map((x) => (
          <span key={x.key} className="block">
            <span className="font-semibold">{t(x.label)}:</span> {x.names} · {ctx.labels.conf[x.confidence]}
            {x.estimate ? ` · ${ctx.labels.estimate}` : ""}
          </span>
        ))}
        <span className="mt-1 block text-slate-700">{ctx.asOf}</span>
      </span>
    </span>
  );
}

/* ---------- cards ---------- */

/** Sort menu (T-130): a native select, so it works with keyboard and screen readers on every phone. */
function SortMenu({ state, onChange, t }: { state: ExploreState; onChange: (k: SortKey) => void; t: T }) {
  const inMenu = (MENU_SORTS as readonly string[]).includes(state.sort ?? "");
  return (
    <div className="order-2 flex min-w-0 flex-1 items-center gap-2 lg:order-3 lg:ml-auto lg:flex-none">
      <label htmlFor="sort-menu" className="sr-only text-sm text-slate-800 sm:not-sr-only">
        {t("sort.label")}
      </label>
      <select
        id="sort-menu"
        value={inMenu ? (state.sort as string) : ""}
        onChange={(e) => {
          const k = e.target.value;
          if ((MENU_SORTS as readonly string[]).includes(k)) onChange(k as SortKey);
        }}
        // min-w-0 + max-w-full: a native select is as wide as its longest option (FR/ES overflowed 360 px).
        className="min-h-11 min-w-0 max-w-full flex-1 rounded-md border border-slate-500 bg-white px-3 py-2 text-sm font-semibold sm:flex-none"
        data-testid="sort-menu"
      >
        {!inMenu ? <option value="">{t("sort.other")}</option> : null}
        {MENU_SORTS.map((k) => (
          <option key={k} value={k}>
            {t(`sort.${k}` as MsgKey)}
          </option>
        ))}
      </select>
    </div>
  );
}

/** "€17K–€32K": compact money for the card's used price band. */
function moneyShort(v: number, c: Ctx): string {
  try {
    return new Intl.NumberFormat(c.locale, { style: "currency", currency: c.currency, notation: "compact", maximumFractionDigits: v >= 10_000 ? 0 : 1 }).format(v);
  } catch {
    return formatMoney(v, c.currency, c.locale);
  }
}

/** "260–410" (or one number when all variants agree); the unit sits in the label. */
function spanText(s: Span, c: Ctx, digits = 0): string {
  const a = formatNumber(s.min, c.locale, digits);
  const b = formatNumber(s.max, c.locale, digits);
  return a === b ? b : `${a}–${b}`;
}

/** A card fact through <Num>: the range text, the provenance of the variant with the highest value. */
function spanNum(s: Span | null, field: string, c: Ctx, digits = 0, unit?: string) {
  if (!s) return <Missing label={c.t("num.noData")} />;
  return (
    <Num
      value={s.max}
      text={spanText(s, c, digits) + (unit ? `\u00a0${unit}` : "")}
      provenance={s.row.provenance[field]}
      sources={c.sources}
      locale={c.locale}
      labels={c.labels}
      digits={digits}
      claim={isClaimField(s.row, field)}
      // Cards stay calm (T-130 design): badges and sources live in the popover until Nerd level.
      level={c.level === "nerd" ? "nerd" : "simple"}
      asOf={c.asOf}
    />
  );
}

/** New price span through <Num> with the `price_new.<CC>` provenance of the dearest variant (rule 2). */
function newPriceNum(s: Span | null, c: Ctx) {
  if (!s) return <Missing label={c.t("num.noData")} />;
  const text = s.min === s.max ? formatMoney(s.max, c.currency, c.locale) : `${moneyShort(s.min, c)}–${moneyShort(s.max, c)}`;
  return (
    <Num
      value={s.max}
      text={text}
      provenance={s.row.provenance[`price_new.${c.code}`] ?? s.row.provenance.price_new}
      sources={c.sources}
      locale={c.locale}
      labels={c.labels}
      level={c.level === "nerd" ? "nerd" : "simple"}
      asOf={c.asOf}
    />
  );
}

/** One card per generation (T-130 design): "#n popular", name + years, used price band, three facts. */
function GenerationCard({ card: g, ctx: c, countryName }: { card: GenCard; ctx: Ctx; countryName: string }) {
  const { t, level } = c;
  const r = g.lead;
  const fit = c.trip?.fits.get(r.variant_id);
  const fact = (icon: ReactNode, value: ReactNode, label: ReactNode, testId: string) => (
    <div className="flex min-w-0 flex-col [overflow-wrap:anywhere]" data-testid={testId}>
      {/* The icon sits beside the number. At Nerd the value carries unbreakable source badges, so the
          row may wrap there (re-review 3: without it a 360 px card grew 3–9 px with CI's fonts). */}
      <dd className={`order-2 flex min-w-0 items-center gap-1 text-base font-bold tabular-nums ${level === "nerd" ? "flex-wrap" : ""}`}>
        {icon}
        <span className="min-w-0 [overflow-wrap:anywhere]">{value}</span>
      </dd>
      <dt className="order-3 text-xs text-slate-700">{label}</dt>
    </div>
  );
  const used = g.used;
  const note = used ? (used.estimate ? t(used.lowConfidence ? "card.used.estimateLow" : "card.used.estimate") : null) : null;
  const how = level === "nerd" && used?.how ? [used.how.src, used.how.date].filter(Boolean).join(", ") : "";
  return (
    <li
      className={`flex min-w-0 flex-col gap-2 rounded-xl border border-slate-300 bg-white p-4 ${fit?.verdict === "fail" ? "opacity-70" : ""}`}
      data-testid="explore-card"
      data-generation={g.generation_id}
      data-trip={fit?.verdict}
    >
      {/* T-135: the generation's photo with its credit line; a same-size placeholder when there is none. */}
      <CarFigure
        photo={c.photos?.[g.generation_id]}
        alt={generationTitle(r)}
        text={photoText(t, c.termText)}
        sizes="(min-width: 80rem) 22rem, (min-width: 40rem) 45vw, 100vw"
        card
      />
      {r.pop_rank ? (
        <p className="w-fit rounded-full border border-slate-500 bg-[var(--surface)] px-2 py-0.5 text-xs font-semibold" data-testid="popular-tag">
          {t("card.popular", { n: r.pop_rank })}
        </p>
      ) : null}
      {r.pop_rank && level === "nerd" ? (
        <p className="text-xs text-slate-700" data-testid="popular-nerd">
          {t("card.popular.nerd", { score: r.pop ?? "—", date: c.popAsOf ?? "—" })}
        </p>
      ) : null}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-lg font-bold leading-snug">
            <Link href={generationHref(c.base, r)} className="text-[var(--ink)] underline-offset-2 hover:underline">
              {r.make_name} {r.model_name}
            </Link>
          </h3>
          <p className="text-sm text-slate-700">
            {r.generation_name} · <span className="tabular-nums">{formatYears(g.yearStart, g.yearEnd, t("years.now"))}</span>
          </p>
        </div>
        <RowActions row={r} t={t} />
      </div>
      <div data-testid="card-used">
        {used ? (
          <p className="text-xl font-bold tabular-nums">
            {moneyShort(used.low, c)}–{moneyShort(used.high, c)}
          </p>
        ) : (
          <p className="text-sm font-semibold text-slate-800">{t("card.used.none")}</p>
        )}
        <p className="text-sm text-slate-700">
          {t("card.used.where", { country: countryName })}
          {note ? <span className="block text-xs">{note}</span> : null}
          {how ? <span className="block text-xs" data-testid="card-used-how">{t("card.used.how", { how })}</span> : null}
        </p>
      </div>
      {c.trip ? (
        <div className="text-sm">
          <span className="inline-flex items-center gap-0.5 text-xs text-slate-700">
            {t("trip.col")}
            <TermInfo term={c.tax.terms["trip-fit"]} base={c.base} text={c.termText} />
          </span>
          <c.trip.mod.TripCell fit={fit} ui={c.trip.ui} inTable={false} />
        </div>
      ) : null}
      <dl className="mt-auto grid grid-cols-3 gap-2 border-t border-dashed border-slate-300 pt-3">
        {fact(<IconSnow />, spanNum(g.winter, "real_range_winter_km", c), (
          <span className="inline-flex items-center gap-0.5">
            {t("card.fact.winter")}
            <TermInfo term={c.tax.terms["real-winter-range"]} base={c.base} text={c.termText} />
          </span>
        ), "fact-winter")}
        {fact(<IconSun />, spanNum(g.summer, "real_range_km", c), (
          <span className="inline-flex items-center gap-0.5">
            {t("card.fact.summer")}
            <TermInfo term={c.tax.terms["real-range"]} base={c.base} text={c.termText} />
          </span>
        ), "fact-summer")}
        {fact(<IconPlug />, spanNum(g.dc20, "dc_km_per_20min", c), (
          <span className="inline-flex items-center gap-0.5">
            {t("card.fact.dc20")}
            <TermInfo term={c.tax.terms["dc-km-20min"]} base={c.base} text={c.termText} />
          </span>
        ), "fact-dc20")}
        {/* T-143: the official WLTP range right under the real winter + summer range, secondary style. */}
        <div className="col-span-3 min-w-0">
          <dt className="sr-only">{t("range.wltp.label")}</dt>
          <dd className="min-w-0">
            <OfficialRange
              value={g.wltp?.max}
              valueText={g.wltp ? spanText(g.wltp, c) : undefined}
              provenance={g.wltp?.row.provenance.wltp_range_km}
              sources={c.sources}
              locale={c.locale}
              labels={c.labels}
              level={c.level === "nerd" ? "nerd" : "simple"}
              asOf={c.asOf}
              text={wltpText(c)}
              info={{ href: `${c.base}/learn/wltp`, termText: c.termText }}
              testId="fact-wltp"
            />
          </dd>
        </div>
      </dl>
      {level !== "simple" ? (
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex min-w-0 flex-col">
            <dt className="text-xs text-slate-700">{t("col.battery")}</dt>
            <dd>{spanNum(g.battery, "battery_kwh_net", c, 1, "kWh")}</dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-xs text-slate-700">{t("col.price")}</dt>
            <dd className="tabular-nums">{newPriceNum(g.newPrice, c)}</dd>
          </div>
        </dl>
      ) : null}
      <p className="text-sm">
        <Link href={generationHref(c.base, r)} className="text-blue-800 underline underline-offset-2" data-testid="card-versions">
          {t(g.rows.length === 1 ? "card.versions.one" : "card.versions", { n: g.rows.length })}
        </Link>
      </p>
    </li>
  );
}

const ICON = "h-4 w-4 shrink-0 fill-none stroke-current";
function IconSnow() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={ICON} strokeWidth="2">
      <path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5" />
    </svg>
  );
}
function IconSun() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={ICON} strokeWidth="2">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}
function IconPlug() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={ICON} strokeWidth="2">
      <path d="M6 3h8v18H6zM14 8h3a2 2 0 0 1 2 2v5a1.5 1.5 0 0 0 3 0V7M9 9l-1.5 3h3L9 15" />
    </svg>
  );
}


/* ---------- favourite + compare ---------- */

function RowActions({ row, t, withText = false }: { row: ExploreRow; t: T; withText?: boolean }) {
  const favs = useListStore(favouriteStore);
  const cmp = useListStore(compareStore);
  const fullId = useId();
  const name = displayName(row);
  const fav = favs.includes(row.variant_id);
  const inCmp = cmp.some((c) => c.id === row.variant_id);
  const full = !inCmp && cmp.length >= COMPARE_MAX;
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-pressed={fav}
        aria-label={t(fav ? "fav.remove" : "fav.add", { name })}
        onClick={() => favouriteStore.toggle(row.variant_id)}
        className="grid h-8 w-8 place-items-center rounded-full hover:bg-slate-100"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" className={`h-5 w-5 ${fav ? "fill-red-700 stroke-red-700" : "fill-none stroke-slate-700"}`} strokeWidth="2">
          <path d="M12 21s-7.5-4.6-9.5-9.2C1 8.2 3.4 4.5 7 4.5c2 0 3.6 1.1 5 3 1.4-1.9 3-3 5-3 3.6 0 6 3.7 4.5 7.3C19.5 16.4 12 21 12 21z" />
        </svg>
      </button>
      {/* Full tray: aria-disabled (not disabled) so keyboard and screen-reader users still reach it and hear why. */}
      <button
        type="button"
        aria-pressed={inCmp}
        aria-disabled={full || undefined}
        aria-describedby={full ? fullId : undefined}
        title={full ? t("compare.full", { max: COMPARE_MAX }) : undefined}
        data-testid="compare-toggle"
        onClick={() => {
          if (inCmp) compareStore.remove(row.variant_id);
          else if (!full) compareStore.add({ id: row.variant_id, label: name });
        }}
        className={`flex h-8 items-center gap-1 rounded-full border px-2 text-xs font-medium aria-disabled:cursor-not-allowed aria-disabled:opacity-50 ${inCmp ? "border-blue-800 bg-blue-800 text-white" : "border-slate-500 text-slate-900 hover:bg-slate-100"}`}
      >
        <span aria-hidden="true">{inCmp ? "✓" : "+"}</span>
        <span className={withText ? "" : "sr-only"}>{t("compare.add")}</span>
        {/* Name = the visible word + the car (WCAG 2.5.3 Label in Name; T-096). */}
        <span className="sr-only">: {name}</span>
      </button>
      {full ? (
        <span id={fullId} className="sr-only">
          {t("compare.full", { max: COMPARE_MAX })}
        </span>
      ) : null}
    </div>
  );
}
