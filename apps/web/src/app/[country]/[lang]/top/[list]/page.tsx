// One ranking list (T-011), with a method note on the metric, its sources and estimate status.
import type { Metadata } from "next";
import Link from "next/link";
import { parkedEnabled } from "@/config/features";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Num } from "@/components/Num";
import { RankingTable } from "@/components/RankingTable";
import { TermInfo } from "@/components/Term";
import { COUNTRIES, isCountrySlug, isServed, type CountrySlug } from "@/config/countries";
import { isClaimField } from "@/lib/dc";
import { formatMoney, formatYears, localeFor } from "@/lib/format";
import { isRankingId, PRICE_THRESHOLD, ranking, RANKING_IDS, type RankEntry, type RankingId } from "@/lib/rankings";
import { getCatalogue } from "@/lib/catalogue";
import { isUsedRankingId, USED_CAP, usedRanking, visibleUsedRankings, type UsedRankingId } from "@/lib/used-rankings";
import { pageCtx, pageMeta, servedRoute, sourcesFor, type PageCtx } from "../../ev/_lib/context";
import { generationTitle } from "../../ev/_lib/data";
import { generationHref, variantHref } from "../../ev/_lib/routes";
import { getT } from "@/i18n";

type Props = { params: Promise<{ country: string; lang: string; list: string }> };

// Used-price lists ("best used EV under €15k / 20k / 25k") exist only for countries where at least
// USED_MIN_ENTRIES generations have a sourced used price (src/lib/used-rankings.ts). Release 1 has
// no used prices, so tonight none are generated: those URLs are 404 and nothing links to them.
export function generateStaticParams({ params }: { params: { country: string; lang: string } }) {
  // Parked until after launch (Decision 051): no ranking pages are built unless RANKINGS=1 or PARKED=1.
  if (!parkedEnabled("rankings")) return [];
  const used = isCountrySlug(params.country)
    ? visibleUsedRankings(getCatalogue().rows(), getCatalogue().usedPrices(), COUNTRIES[params.country].code, COUNTRIES[params.country].currency)
    : [];
  return [...RANKING_IDS, ...used].map((list) => ({ list }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await params;
  const route = servedRoute(p);
  const { list } = p;
  if (route && isUsedRankingId(list)) {
    const cfg = COUNTRIES[route.country];
    // hreflang only for countries where this list exists (A-05 L4; same rule as sitemap.ts).
    return pageMeta(
      route,
      `top/${list}`,
      { title: getT(route.lang)("top.used.title", { price: formatMoney(USED_CAP[list][cfg.currency], cfg.currency, localeFor(route.lang)) }) },
      (c) => usedListExists(list, c),
    );
  }
  if (!route || !isRankingId(list)) return {};
  const { lang } = route;
  const cfg = COUNTRIES[route.country];
  return pageMeta(route, `top/${list}`, {
    title: getT(lang)(`top.${list}.title`, { price: formatMoney(PRICE_THRESHOLD[cfg.currency], cfg.currency, localeFor(lang)) }),
  });
}

/** The used-price list exists for this country (enough sourced prices). */
function usedListExists(list: UsedRankingId, country: CountrySlug): boolean {
  const cat = getCatalogue();
  const c = COUNTRIES[country];
  return visibleUsedRankings(cat.rows(), cat.usedPrices(), c.code, c.currency).includes(list);
}

const METRIC_TERM: Record<RankingId, string> = {
  "longest-real-range-under-30k": "real-range",
  "fastest-dc": "dc-km-20min",
  "most-available-nl": "registrations-nl",
};

const UNIT: Record<RankingId, string | undefined> = {
  "longest-real-range-under-30k": "km",
  "fastest-dc": "km",
  "most-available-nl": undefined,
};

function metricCell(ctx: PageCtx, e: RankEntry, unit: string | undefined) {
  const prov = e.row.provenance[e.field];
  const note =
    e.field === "real_range_km" && e.row.real_range_rung
      ? ctx.t(`rung.${e.row.real_range_rung}`)
      : undefined;
  return (
    <Num
      value={e.value}
      unit={unit}
      digits={0}
      provenance={prov}
      sources={sourcesFor(ctx, prov)}
      locale={ctx.locale}
      labels={ctx.labels}
      note={note}
      noteTerm={note ? "rung" : undefined}
      claim={isClaimField(e.row, e.field)}
      asOf={ctx.asOf}
    />
  );
}

export default async function RankingPage({ params }: Props) {
  const { country, lang, list } = await params;
  if (!parkedEnabled("rankings")) notFound();
  if (isCountrySlug(country) && isServed(country, lang) && isUsedRankingId(list)) return <UsedRankingPage ctx={pageCtx(country, lang)} list={list} />;
  if (!isCountrySlug(country) || !isServed(country, lang) || !isRankingId(list)) notFound();
  const ctx = pageCtx(country, lang);
  const { base } = ctx;
  const { t, cfg } = ctx;
  const price = formatMoney(PRICE_THRESHOLD[cfg.currency], cfg.currency, ctx.locale);
  const title = t(`top.${list}.title`, { price });
  const entries = ranking(list, ctx.cat.rows(), cfg.code, cfg.currency);
  const estimates = entries.filter((e) => e.estimate).length;
  const perGeneration = list === "most-available-nl";

  // Glossary ⓘ on the metric and price headers (glossary sweep item 9).
  const head = (label: string, termId: string) => (
    <span className="inline-flex items-center gap-1">
      {label}
      <TermInfo term={ctx.tax.terms[termId]} base={base} text={ctx.termText} />
    </span>
  );
  const headers = [
    perGeneration ? t("top.most-available-nl.generation") : t("top.car"),
    head(t(`top.${list}.metric`), METRIC_TERM[list]),
    ...(list === "longest-real-range-under-30k" ? [head(t("top.longest-real-range-under-30k.price"), "new-price")] : []),
  ];

  const rows = entries.map((e) => {
    const r = e.row;
    const years = formatYears(r.year_start, r.year_end, t("years.now"));
    const car = perGeneration ? (
      <span className="flex flex-col">
        <Link href={generationHref(base, r)} className="text-blue-800 underline underline-offset-2 hover:text-blue-950">
          {generationTitle(r)}
        </Link>
      </span>
    ) : (
      <span className="flex flex-col">
        <Link href={variantHref(base, r)} className="text-blue-800 underline underline-offset-2 hover:text-blue-950">
          {r.make_name} {r.model_name} {r.variant_name}
        </Link>
        <span className="text-xs font-normal text-slate-700">
          {r.generation_name} · <span className="tabular-nums">{years}</span>
        </span>
      </span>
    );
    const cells = [car, metricCell(ctx, e, UNIT[list])];
    if (list === "longest-real-range-under-30k") {
      const m = r.price_new?.[cfg.code];
      const prov = r.provenance[`price_new.${cfg.code}`];
      cells.push(
        <Num
          value={m?.amount}
          text={m ? formatMoney(m.amount, m.currency, ctx.locale) : undefined}
          provenance={prov}
          sources={sourcesFor(ctx, prov)}
          locale={ctx.locale}
          labels={ctx.labels}
          asOf={ctx.asOf}
        />,
      );
    }
    return { key: perGeneration ? r.generation_id : r.variant_id, rank: e.rank, cells };
  });

  const emptyText = list === "longest-real-range-under-30k" ? t("top.longest-real-range-under-30k.empty") : t("top.empty");

  return (
    <>
      <Breadcrumbs
        label={t("crumb.label")}
        items={[{ label: t("crumb.home"), href: base }, { label: t("crumb.top"), href: `${base}/top` }, { label: title }]}
      />
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-2 max-w-3xl text-slate-800">{t(`top.${list}.short`, { price, country: cfg.name })}</p>

      <section aria-labelledby="method" className="mt-4 max-w-3xl rounded-md border border-slate-300 bg-slate-50 p-4">
        <h2 id="method" className="font-semibold">
          {t("top.method")}
        </h2>
        <p className="mt-1 text-sm">{t(`top.${list}.method`, { price, country: cfg.name })}</p>
        {entries.length && estimates ? (
          <p className="mt-2 flex items-center gap-1 text-sm font-medium" data-testid="estimate-note">
            {estimates === entries.length ? t("top.allEstimates") : t("top.estimates", { n: estimates, total: entries.length })}
            <TermInfo term={ctx.tax.terms.estimate} base={base} text={ctx.termText} />
          </p>
        ) : null}
      </section>

      <div className="mt-6">
        {rows.length ? (
          <RankingTable caption={t("top.caption", { title })} rankHeader={t("top.rank")} headers={headers} rows={rows} />
        ) : (
          <p className="rounded-md border border-slate-300 p-4" data-testid="ranking-empty">
            {emptyText}
          </p>
        )}
      </div>
    </>
  );
}

/** "Best used EV under {price}": one row per generation, ranked by real range per 1,000 at the typical used price. */
function UsedRankingPage({ ctx, list }: { ctx: PageCtx; list: UsedRankingId }) {
  const { t, cfg, base } = ctx;
  // Hidden unless enough generations qualify (see generateStaticParams): never a thin or guessed list.
  if (!visibleUsedRankings(ctx.cat.rows(), ctx.cat.usedPrices(), cfg.code, cfg.currency).includes(list)) notFound();
  const entries = usedRanking(list, ctx.cat.rows(), ctx.cat.usedPrices(), cfg.code, cfg.currency);
  const price = formatMoney(USED_CAP[list][cfg.currency], cfg.currency, ctx.locale);
  const per = formatMoney(1000, cfg.currency, ctx.locale);
  const title = t("top.used.title", { price });
  const estimates = entries.filter((e) => e.estimate).length;
  const head = (label: string, termId: string) => (
    <span className="inline-flex items-center gap-1">
      {label}
      <TermInfo term={ctx.tax.terms[termId]} base={base} text={ctx.termText} />
    </span>
  );
  const headers = [t("top.most-available-nl.generation"), head(t("top.used.metric", { per }), "real-range"), head(t("top.used.range"), "real-range"), head(t("top.used.price"), "used-price")];
  const rows = entries.map((e) => {
    const r = e.row;
    const rangeProv = r.provenance.real_range_km;
    return {
      key: r.generation_id,
      rank: e.rank,
      cells: [
        <span key="car" className="flex flex-col">
          <Link href={generationHref(base, r)} className="text-blue-800 underline underline-offset-2 hover:text-blue-950">
            {generationTitle(r)}
          </Link>
          <span className="text-xs font-normal text-slate-700">
            {r.variant_name} · <span className="tabular-nums">{formatYears(r.year_start, r.year_end, t("years.now"))}</span>
          </span>
        </span>,
        // Derived ratio: through <Num> with its own provenance and the estimate badge (A-05 L3).
        <Num key="v" value={e.value} digits={1} provenance={e.valueProvenance} sources={sourcesFor(ctx, e.valueProvenance)} locale={ctx.locale} labels={ctx.labels} asOf={e.band.period} />,
        <Num key="r" value={e.rangeKm} unit="km" digits={0} provenance={rangeProv} sources={sourcesFor(ctx, rangeProv)} locale={ctx.locale} labels={ctx.labels} asOf={ctx.asOf} />,
        <Num
          key="p"
          value={e.band.median}
          text={formatMoney(e.band.median, e.band.currency, ctx.locale)}
          provenance={e.priceProvenance}
          sources={sourcesFor(ctx, e.priceProvenance)}
          locale={ctx.locale}
          labels={ctx.labels}
          asOf={e.band.period}
        />,
      ],
    };
  });
  return (
    <>
      <Breadcrumbs label={t("crumb.label")} items={[{ label: t("crumb.home"), href: base }, { label: t("crumb.top"), href: `${base}/top` }, { label: title }]} />
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-2 max-w-3xl text-slate-800">{t("top.used.short", { price, country: cfg.name, per })}</p>
      <section aria-labelledby="method" className="mt-4 max-w-3xl rounded-md border border-slate-300 bg-slate-50 p-4">
        <h2 id="method" className="font-semibold">
          {t("top.method")}
        </h2>
        <p className="mt-1 text-sm">{t("top.used.method", { price, country: cfg.name, per })}</p>
        {estimates ? (
          <p className="mt-2 flex items-center gap-1 text-sm font-medium" data-testid="estimate-note">
            {estimates === entries.length ? t("top.allEstimates") : t("top.estimates", { n: estimates, total: entries.length })}
            <TermInfo term={ctx.tax.terms.estimate} base={base} text={ctx.termText} />
          </p>
        ) : null}
      </section>
      <div className="mt-6">
        <RankingTable caption={t("top.caption", { title })} rankHeader={t("top.rank")} headers={headers} rows={rows} />
      </div>
    </>
  );
}
