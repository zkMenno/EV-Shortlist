// "Popular used EVs" on the landing (T-131): the editorial list as generation cards, with the
// release photo (T-135), the used price band where the visitor lives and the real winter range.
// Server component: no extra JS on the landing beyond the shared <Num> / ⓘ it already loads.
import Link from "next/link";
import type { Currency } from "@ev/schema";
import type { T } from "@/i18n/t";
import { formatMoney, formatNumber, formatYears } from "@/lib/format";
import { isClaimField } from "@/lib/dc";
import { POPULAR_USED, type PopularCard, type PopularUsedMethod } from "@/lib/popular-used";
import { generationHref } from "@/app/[country]/[lang]/ev/_lib/routes";
import { CarFigure, photoText, type PhotoRef } from "./CarPhoto";
import { generationTitle } from "@/lib/generation-title";
import { Missing, Num } from "./Num";
import type { NumLabels } from "./num-labels";
import { TermInfo, type TermText } from "./Term";
import type { UiTerm } from "@/lib/taxonomy";

function moneyShort(v: number, currency: Currency, locale: string): string {
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency, notation: "compact", maximumFractionDigits: v >= 10_000 ? 0 : 1 }).format(v);
  } catch {
    return formatMoney(v, currency, locale);
  }
}

/** A generation name that already says its years ("(2021-2024)", "2024 update"). */
const YEAR_RE = /\b(19|20)\d{2}\b/;

export function PopularUsed({
  cards,
  base,
  currency,
  locale,
  t,
  photos,
  sources,
  labels,
  asOf,
  countryName,
  termText,
  winterTerm,
  method = POPULAR_USED.method,
}: {
  cards: PopularCard[];
  base: string;
  currency: Currency;
  locale: string;
  t: T;
  photos: Record<string, PhotoRef>;
  sources: Record<string, string>;
  labels: NumLabels;
  asOf: string;
  /** "in the Netherlands" (per-country key: prepositions differ). */
  countryName: string;
  termText: TermText;
  winterTerm: UiTerm | undefined;
  /** The points behind the list (data/editorial/popular_used.yaml `method`), for "How we pick these". */
  method?: PopularUsedMethod;
}) {
  if (!cards.length) return null;
  const text = photoText(t, termText);
  return (
    <section aria-labelledby="popular-used-title" className="evs-popular mt-12" data-testid="popular-used">
      <h2 id="popular-used-title" className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight">
        {t("landing.popular.title")}
      </h2>
      <p className="mt-2 max-w-3xl text-[var(--ink-2)]" data-testid="popular-used-intro">
        {t("landing.popular.intro")}
      </p>
      {/* T-169: this list's own points method (not the catalogue's "How we rank", a different blend). */}
      <details className="mt-2 max-w-3xl text-sm" id="how-we-pick" data-testid="popular-how">
        <summary className="min-h-11 cursor-pointer py-2 text-blue-800 underline underline-offset-2">{t("landing.popular.how")}</summary>
        <ul className="mt-1 grid list-disc gap-1 pl-5 text-[var(--ink-2)]">
          <li>{t("landing.popular.method.reg", { top: method.registration_top })}</li>
          <li>
            {t("landing.popular.method.owner", {
              shortlist: method.owner_points.shortlist,
              consider: method.owner_points.consider,
              ruledOut: formatNumber(method.owner_points.ruled_out, locale, 0),
              fav: method.favourite_bonus,
            })}
          </li>
          <li>{t("landing.popular.method.order")}</li>
        </ul>
      </details>
      <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(({ card: g, why }) => {
          const r = g.lead;
          const name = `${r.make_name} ${r.model_name}`;
          const used = g.used;
          const w = g.winter;
          return (
            <li key={g.generation_id} className="flex min-w-0 flex-col gap-2 rounded-xl border border-slate-300 bg-white p-4" data-testid="popular-card" data-generation={g.generation_id}>
              <CarFigure photo={photos[g.generation_id]} alt={generationTitle(r)} text={text} sizes="(min-width: 64rem) 22rem, (min-width: 40rem) 45vw, 100vw" card />
              <h3 className="text-lg font-bold leading-snug">
                <Link href={generationHref(base, r)} className="text-[var(--ink)] underline-offset-2 hover:underline">
                  {name}
                </Link>
              </h3>
              <p className="text-sm text-slate-700">
                {r.generation_name}
                {/* T-169: no years twice when the generation name already holds them ("e-tron GT (2021-2024)"). */}
                {YEAR_RE.test(r.generation_name) ? null : (
                  <>
                    {" · "}
                    <span className="tabular-nums">{formatYears(g.yearStart, g.yearEnd, t("years.now"))}</span>
                  </>
                )}
              </p>
              <p className="text-sm" data-testid="popular-why">
                {why}
              </p>
              <div className="mt-auto grid grid-cols-2 items-end gap-x-4 border-t border-dashed border-slate-300 pt-3">
                <div data-testid="popular-used-price">
                  {used ? (
                    <p className="text-lg font-bold tabular-nums">
                      {moneyShort(used.low, currency, locale)}–{moneyShort(used.high, currency, locale)}
                    </p>
                  ) : (
                    <p className="text-sm font-semibold text-slate-800">{t("card.used.none")}</p>
                  )}
                  <p className="text-xs text-slate-700">
                    {t("card.used.where", { country: countryName })}
                    {used?.estimate ? <span className="block">{t(used.lowConfidence ? "card.used.estimateLow" : "card.used.estimate")}</span> : null}
                  </p>
                </div>
                <div className="text-right" data-testid="popular-winter">
                  <p className="text-lg font-bold tabular-nums">
                    {w ? (
                      <Num
                        value={w.max}
                        text={w.min === w.max ? formatNumber(w.max, locale, 0) : `${formatNumber(w.min, locale, 0)}–${formatNumber(w.max, locale, 0)}`}
                        provenance={w.row.provenance.real_range_winter_km}
                        sources={sources}
                        locale={locale}
                        labels={labels}
                        digits={0}
                        claim={isClaimField(w.row, "real_range_winter_km")}
                        level="simple"
                        asOf={asOf}
                      />
                    ) : (
                      <Missing label={labels.noData} />
                    )}
                  </p>
                  <p className="inline-flex items-center gap-0.5 text-xs text-slate-700">
                    {t("card.fact.winter")}
                    <TermInfo term={winterTerm} base={base} text={termText} />
                  </p>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
