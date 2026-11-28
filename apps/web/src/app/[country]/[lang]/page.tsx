import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { catalogueRedirect } from "@/lib/catalogue-redirect";
import { siteBase } from "@/lib/site-paths";
import { ChargingLinks } from "@/components/ChargingLinks";
import Link from "next/link";
import { Hero } from "@/components/Hero";
import { ParallaxScene } from "@/components/parallax/ParallaxScene";
import { canal, highway } from "@/components/parallax/scenes.generated";
import { showable } from "@/components/PriceBand";
import { COUNTRIES, isCountrySlug, isServed } from "@/config/countries";
import { getClientDict, getT } from "@/i18n";
import { clientCatalogueKey, getCatalogue } from "@/lib/catalogue";
import { chargingLinks } from "@/lib/charging-links";
import { sourceNames, toExploreRow } from "@/lib/explore-data";
import { financeProfile } from "@/lib/finance-profiles";
import { heroFromSearchParams } from "@/lib/hero-state";
import { article, articleTitle } from "@/lib/learn";
import { LISTING_SITES } from "@/lib/listings";
import { rankHero, resolveProfile, type UsedBands } from "@/lib/shortlist";
import { generationPhotos } from "@/lib/photos";
import { popularUsedCards } from "@/lib/popular-used";
import { PopularUsed } from "@/components/PopularUsed";
import { numLabels } from "@/components/num-labels";
import { localeFor } from "@/lib/format";
import type { MsgKey } from "@/i18n/t";
import { localizeTaxonomy } from "@/lib/taxonomy";
import { pageMeta, servedRoute } from "./ev/_lib/context";

type Props = {
  params: Promise<{ country: string; lang: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const route = servedRoute(await params);
  if (!route) return {};
  return pageMeta(route, "", { title: getT(route.lang)("hero.title") });
}

export default async function ExplorePage({ params, searchParams }: Props) {
  const { country, lang } = await params;
  if (!isCountrySlug(country) || !isServed(country, lang)) notFound();
  const cfg = COUNTRIES[country];
  const sp = await searchParams;
  // T-130: Explore moved to /cars. Old shared Explore links (they carry view or sort, which the hero never writes)
  // follow it with the same query, so no state is lost. Filter-only links stay: the hero reads them as refine filters.
  const exploreLink = catalogueRedirect(sp);
  if (exploreLink !== null) redirect(`${siteBase(country, lang)}/cars${exploreLink}`);
  const dict = getClientDict(lang);
  const t = getT(lang);

  const cat = getCatalogue();
  const used = cat.variantUsedPrices();
  // Release shortlist scores (Decision 065): the only basis for the hero and "Suggested" order.
  const scores = cat.shortlistScores();
  const hasScores = scores !== null;
  const all = cat.rows().map((r) => toExploreRow(r, used, scores));
  // Hero (T-080): answers come from the URL.
  const hero = heroFromSearchParams(sp);
  const profile = resolveProfile(hero.answers);
  // Hero (T-080): ranked on the server from the URL, re-ranked in the browser on every change.
  const usedBands: UsedBands = {};
  for (const b of cat.usedPrices()) {
    if (b.country !== cfg.code || !showable(b, cfg.currency)) continue;
    (usedBands[b.generation_id] ??= []).push(b);
  }
  const nowYear = Number(cat.generatedAt().slice(0, 4)) || new Date().getFullYear();
  const heroResult = profile
    ? rankHero(all, profile, {
        country: cfg.code,
        cond: hero.cond,
        budget: hero.budget,
        filters: hero.filters,
        presetsOff: hero.presetsOff,
        usedBands,
        nowYear,
      }, { hasScores })
    : null;
  const makes = [...new Map(all.map((r) => [r.make_id, r.make_name])).entries()]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const tax = localizeTaxonomy(cat.taxonomy(), lang);
  const heroTerms = Object.fromEntries(
    [
      "real-range", "loan", "apr", "loan-term", "deposit", "total-cost-over-term", "used-price", "new-price",
      // T-100 (WS3): hero and profile picker terms; ⓘ shows once the release carries them.
      "shortlist", "road-tripper", "daily-driver", "runabout", "kerbside-charger", "home-area", "keep-8-years", "budget", "real-winter-range",
    ].map((id) => [id, tax.terms[id]]),
  );
  // Launch /learn pages linked from the hero (Decision 051), only those that exist.
  const learnLinks = ["winter-range", "charging-2026", "batteries-health", "batteries", "battery-health", "chemistries"]
    .map((slug) => article(slug))
    .filter((a): a is NonNullable<typeof a> => !!a)
    .slice(0, 3)
    .map((a) => ({ slug: a.slug, title: articleTitle(a, lang), href: `${siteBase(country, lang)}/learn/${a.slug}` }));
  const dataUrl = `/data/catalogue-${clientCatalogueKey(cat)}.json`;
  // T-146: row thumbnails. Only what a row needs (small src + credit), for generations whose photo
  // files are on disk; the rest keep today's layout.
  const photos = Object.fromEntries(
    Object.entries(generationPhotos(cat.generations())).map(([id, p]) => [id, { src: p.src, credit: p.credit, pageUrl: p.pageUrl, licence: p.licence }]),
  );

  return (
    <>
      <Hero
        country={country}
        code={cfg.code}
        currency={cfg.currency}
        lang={lang}
        dict={dict}
        base={siteBase(country, lang)}
        initial={hero}
        initialResult={heroResult}
        hasScores={hasScores}
        release={cat.release()}
        sources={sourceNames(cat.sources())}
        dataUrl={dataUrl}
        total={all.length}
        finance={financeProfile(cfg.code)}
        usedBands={usedBands}
        nowYear={nowYear}
        makes={makes}
        listingSites={[...LISTING_SITES[country]].sort((a, b) => a.priority - b.priority)}
        terms={heroTerms}
        learnLinks={learnLinks}
        photos={photos}
      />
      {/* T-131: popular used EVs (editorial list, data/editorial/popular_used.yaml), hidden on the results. */}
      <PopularUsed
        cards={popularUsedCards(all, cfg.code)}
        base={siteBase(country, lang)}
        currency={cfg.currency}
        locale={localeFor(lang)}
        t={t}
        photos={photos}
        sources={sourceNames(cat.sources())}
        labels={numLabels(t, { base: siteBase(country, lang), terms: tax.terms })}
        asOf={cat.generatedAt().slice(0, 10)}
        countryName={t(`country.in.${cfg.code}` as MsgKey)}
        termText={{ about: t("term.about"), learnMore: t("term.learnMore") }}
        winterTerm={tax.terms["real-winter-range"]}
      />
      {/* T-130: the full list moved to the catalogue page; the landing links there. */}
      <section aria-labelledby="all-cars-title" className="evs-allcars mt-12 rounded-lg border border-slate-300 bg-white p-6" data-testid="show-all-cars">
        <h2 id="all-cars-title" className="text-xl font-bold tracking-tight">
          {t("landing.allCars.title")}
        </h2>
        <p className="mt-2 text-slate-800">{t("landing.allCars.body", { n: all.length })}</p>
        <Link
          href={`${siteBase(country, lang)}/cars`}
          className="mt-4 inline-flex min-h-11 items-center rounded-md bg-blue-800 px-4 py-2 font-semibold text-white hover:bg-blue-950"
          data-testid="show-all-cars-link"
        >
          {t("landing.allCars.button")}
        </Link>
      </section>
      {/* Wide illustration bands with horizontal parallax (UX, Menno 2026-11-17): decorative, no text. */}
      <ParallaxScene scene={highway} className="mt-12" testId="band-highway" />
      <ChargingLinks links={chargingLinks(country, { lang })} t={t} statsHref={`${siteBase(country, lang)}/charging`} />
      <ParallaxScene scene={canal} className="mt-12" testId="band-canal" />
    </>
  );
}
