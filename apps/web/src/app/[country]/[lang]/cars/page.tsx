// Catalogue page (T-130): every car with Explore's filters, "Most popular" first.
// The landing page links here ("Show all cars") instead of rendering the full list.
import { generationPhotos } from "@/lib/photos";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Explore } from "@/components/Explore";
import { COUNTRIES, isCountrySlug, isServed } from "@/config/countries";
import { tripFitEnabled } from "@/config/features";
import popularityInputs from "@/config/popularity.generated.json";
import { getClientDict, getT } from "@/i18n";
import { clientCatalogueKey, getCatalogue } from "@/lib/catalogue";
import { sourceNames, toExploreRow } from "@/lib/explore-data";
import { applyFilters, sortRows } from "@/lib/filters";
import { brandCounts, generationCount } from "@/lib/generation-cards";
import { financeProfile } from "@/lib/finance-profiles";
import { heroFromSearchParams } from "@/lib/hero-state";
import { resolveProfile, suggestedScore } from "@/lib/shortlist";
import { fromSearchParams, hasLevelParam, hasPayParam, hasViewParam } from "@/lib/state";
import { localizeTaxonomy } from "@/lib/taxonomy";
import { hasTowns } from "@/lib/trip-model";
import { pageMeta, servedRoute } from "../ev/_lib/context";

/** Rows rendered on the server (table) and generations (cards); the client takes over with the full list. */
const SSR_ROWS = 25;
const SSR_CARDS = 12;
const HOW_ID = "how-we-rank";

type Props = {
  params: Promise<{ country: string; lang: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const route = servedRoute(await params);
  if (!route) return {};
  return pageMeta(route, "/cars", { title: getT(route.lang)("catalogue.title") });
}

/** Whole percentages of the blend, summing to 100 (config/popularity.yaml). */
function weightPercents(w: { registrations: number; owner_picks: number }) {
  const total = w.registrations + w.owner_picks;
  const regs = total > 0 ? Math.round((100 * w.registrations) / total) : 0;
  return { regs, picks: 100 - regs };
}

export default async function CataloguePage({ params, searchParams }: Props) {
  const { country, lang } = await params;
  if (!isCountrySlug(country) || !isServed(country, lang)) notFound();
  const cfg = COUNTRIES[country];
  const sp = await searchParams;
  const dict = getClientDict(lang);
  const t = getT(lang);

  const cat = getCatalogue();
  const used = cat.variantUsedPrices();
  const scores = cat.shortlistScores();
  const popularity = cat.popularity();
  const all = cat.rows().map((r) => toExploreRow(r, used, scores, popularity));
  const state = fromSearchParams(sp);
  // Defaults for this page (T-130 design): most popular first, as cards. A URL value always wins.
  if (!("sort" in sp)) {
    state.sort = "popular";
    state.dir = "desc";
  }
  if (!hasViewParam(sp)) state.view = "cards";
  const tripFit = tripFitEnabled() && hasTowns(country);
  if (!tripFit) state.filters.tripFit = false;
  const hero = heroFromSearchParams(sp);
  const profile = resolveProfile(hero.answers);
  const scorer = profile ? (r: (typeof all)[number]) => suggestedScore(r, profile) : undefined;
  const matches = sortRows(applyFilters(all, state.filters, cfg.code), state.sort, state.dir, cfg.code, scorer);
  const tax = localizeTaxonomy(cat.taxonomy(), lang);
  // The first rows for the table and every variant of the first generations for the cards, so a
  // server-rendered card already shows its whole span (one card per generation, T-130).
  const firstGens = new Set<string>();
  for (const r of matches) {
    if (firstGens.size >= SSR_CARDS) break;
    firstGens.add(r.generation_id);
  }
  const initialRows = matches.filter((r, i) => i < SSR_ROWS || firstGens.has(r.generation_id));
  const pct = weightPercents(popularityInputs.weights);
  const popAsOf = cat.popularityAsOf() ?? undefined;
  // T-135: card photos for generations whose files are on disk (src, srcset, credit, file page).
  const photos = Object.fromEntries(
    Object.entries(generationPhotos(cat.generations())).map(([id, p]) => [id, { src: p.src, srcSet: p.srcSet, credit: p.credit, pageUrl: p.pageUrl, licence: p.licence }]),
  );

  return (
    <>
      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("catalogue.title")}</h1>
        <p className="mt-2 max-w-3xl text-slate-800">{t("catalogue.intro")}</p>
      </header>
      <Explore
        country={country}
        code={cfg.code}
        currency={cfg.currency}
        lang={lang}
        dict={dict}
        initialState={state}
        initialAnswers={hero.answers}
        viewFromUrl={hasViewParam(sp)}
        levelFromUrl={hasLevelParam(sp)}
        taxonomy={tax}
        asOf={cat.generatedAt().slice(0, 10)}
        initialRows={initialRows}
        initialMatches={matches.length}
        total={all.length}
        totalModels={generationCount(all)}
        initialMatchModels={generationCount(matches)}
        brands={brandCounts(all)}
        photos={photos}
        dataUrl={`/data/catalogue-${clientCatalogueKey(cat)}.json`}
        sources={sourceNames(cat.sources())}
        tripFit={tripFit}
        hasScores={scores !== null}
        finance={financeProfile(cfg.code)}
        payFromUrl={hasPayParam(sp)}
        defaultView="cards"
        popularityAsOf={popAsOf}
        howWeRankHref={`#${HOW_ID}`}
      />
      <section id={HOW_ID} aria-labelledby={`${HOW_ID}-title`} className="mt-12 max-w-3xl scroll-mt-4" data-testid="how-we-rank">
        <h2 id={`${HOW_ID}-title`} className="text-xl font-bold tracking-tight">
          {t("catalogue.how.title")}
        </h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-slate-800">
          <li>{t("catalogue.how.regs", { regs: pct.regs, date: popAsOf ?? "—" })}</li>
          <li>{t("catalogue.how.split")}</li>
          <li>{t("catalogue.how.picks", { picks: pct.picks })}</li>
          <li>{t("catalogue.how.none")}</li>
          <li>{t("catalogue.how.config")}</li>
        </ul>
      </section>
    </>
  );
}
