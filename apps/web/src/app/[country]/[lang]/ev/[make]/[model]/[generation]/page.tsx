// Generation page (T-009): change markers, spec diff across variants, See listings, RDW count,
// used-price band, voltage class / chemistry / 400 V behaviour.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChargingLinks } from "@/components/ChargingLinks";
import { abrpLink, chargingLinks } from "@/lib/charging-links";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { CarFigure, photoText } from "@/components/CarPhoto";
import { generationPhoto } from "@/lib/photos";
import { Missing, Num } from "@/components/Num";
import { PriceBand } from "@/components/PriceBand";
import { PricePanel } from "@/components/PriceMode";
import { getClientDict } from "@/i18n";
import { financeTerms } from "@/lib/finance";
import { financeProfile } from "@/lib/finance-profiles";

import { SeeListings } from "@/components/SeeListings";
import { DiffOnly } from "@/components/DiffOnly";
import { SpecDiff } from "@/components/SpecDiff";
import { Term } from "@/components/Term";
import { isCountrySlug, isServed } from "@/config/countries";
import { parkedEnabled } from "@/config/features";
import { getCatalogue } from "@/lib/catalogue";
import { usedBandFor } from "@/lib/used-rankings";
import { hasDcData, isDcDependent } from "@/lib/dc";
import { registrationsFor } from "@/lib/registrations";
import { DASH, formatNumber, formatYears, localeFor } from "@/lib/format";
import { seeListings } from "@/lib/listings";
import { DIFF_KEYS, fieldsFor, specDiff, SPEC_FIELDS, variantDeltas, type SpecField } from "@/lib/spec-diff";
import { KnownIssues } from "../../../_components/KnownIssues";
import { OwnerNote } from "../../../_components/OwnerNote";
import { Registrations } from "../../../_components/Registrations";
import { YearsBadge } from "../../../_components/YearsBadge";
import { FieldLabel, SpecValue, textValue } from "../../../_components/SpecValue";
import { pageCtx, pageMeta, servedRoute, sourcesFor, type PageCtx } from "../../../_lib/context";
import { firstWith, generationTitle, generationView } from "../../../_lib/data";
import { generationParams, generationRows, modelHref, variantHref } from "../../../_lib/routes";

type Props = { params: Promise<{ country: string; lang: string; make: string; model: string; generation: string }> };

export function generateStaticParams() {
  return generationParams(getCatalogue().rows());
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await params;
  const route = servedRoute(p);
  const r = generationRows(getCatalogue().rows(), p.make, p.model, p.generation)[0];
  return r && route ? pageMeta(route, `ev/${p.make}/${p.model}/${p.generation}`, { title: generationTitle(r) }) : {};
}

/** One value for the whole generation, or "differs by variant". */
function Summary({ ctx, field, rows }: { ctx: PageCtx; field: Extract<SpecField, { kind: "text" }>; rows: Parameters<typeof textValue>[1][] }) {
  // textValue() applies the shared no-DC rule (src/lib/dc.ts), so DC behaviour never shows without DC data.
  const values = [...new Set(rows.map((r) => textValue(ctx, r, field.key)))];
  if (values.length === 1 && values[0] === DASH) {
    const noDc = isDcDependent(field.key) && rows.every((r) => !hasDcData(r));
    return <Missing label={noDc ? ctx.labels.noDc : ctx.labels.noData} />;
  }
  return <>{values.length === 1 ? values[0] : `${ctx.t("gen.mixed")}: ${values.join(", ")}`}</>;
}

export default async function GenerationPage({ params }: Props) {
  const { country, lang, make, model, generation } = await params;
  if (!isCountrySlug(country) || !isServed(country, lang)) notFound();
  const ctx = pageCtx(country, lang);
  const { base } = ctx;
  const rows = generationRows(ctx.cat.rows(), make, model, generation);
  if (!rows.length) notFound();
  const { t, cfg } = ctx;
  const g = generationView(ctx.cat, rows);
  const first = g.rows[0]!;
  const modelName = `${first.make_name} ${first.model_name}`;
  const fullName = generationTitle({ ...first, generation_name: g.name });
  const diff = specDiff(g.rows, fieldsFor(DIFF_KEYS), cfg.code);
  const deltas = variantDeltas(diff.columns);
  const locale = localeFor(lang);
  const rdw = firstWith(g.rows, "registered_count_nl");
  const rdwTerm = ctx.tax.terms["registrations-nl"];
  const textField = (key: string) => SPEC_FIELDS.find((f) => f.key === key) as Extract<SpecField, { kind: "text" }>;
  const keyFacts = ["voltage_class_id", "chemistry_id", "charger_400v_mode", "cooling_id"].map(textField);
  // T-135: the generation's photo from the release, with its credit line (Decision 081).
  const photo = generationPhoto(ctx.cat.generation(first.generation_id));

  return (
    <>
      <Breadcrumbs
        label={t("crumb.label")}
        items={[{ label: t("crumb.home"), href: base }, { label: modelName, href: modelHref(base, first) }, { label: g.name }]}
      />
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{fullName}</h1>
      <p className="mt-2 flex flex-wrap items-center gap-2 text-slate-800">
        <span className="sr-only">{t("years.label")}: </span>
        <span className="tabular-nums">{formatYears(g.yearStart, g.yearEnd, t("years.now"))}</span>
        <YearsBadge ctx={ctx} status={g.years} yearStart={g.yearStart} yearEnd={g.yearEnd} />
        {first.segment ? <span>· {t(`segment.${first.segment}`)}</span> : first.body ? <span>· {t(`body.${first.body}`)}</span> : null}
      </p>
      <div className="mt-4 max-w-xl">
        <CarFigure
          photo={photo}
          alt={fullName}
          text={photoText(t, ctx.termText)}
          sizes="(min-width: 40rem) 36rem, 100vw"
          eager
          testId="gen-photo"
        />
      </div>

      <section aria-labelledby="key-facts" className="mt-6">
        <h2 id="key-facts" className="text-xl font-semibold">
          {t("gen.keyFacts")}
        </h2>
        <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          {keyFacts.map((f) => (
            <div key={f.key}>
              <dt className="text-sm text-slate-700">
                <FieldLabel ctx={ctx} field={f} />
              </dt>
              <dd className="font-medium">
                <Summary ctx={ctx} field={f} rows={g.rows} />
              </dd>
            </div>
          ))}
          <div>
            <dt className="text-sm text-slate-700">
              <Term term={rdwTerm ? { ...rdwTerm, label: t("gen.rdw") } : undefined} fallback={t("gen.rdw")} base={base} text={ctx.termText} showTechnical={false} />
            </dt>
            <dd className="font-medium" data-testid="rdw-count">
              <Num
                value={rdw?.registered_count_nl}
                digits={0}
                provenance={rdw?.provenance.registered_count_nl}
                sources={sourcesFor(ctx, rdw?.provenance.registered_count_nl)}
                locale={ctx.locale}
                labels={ctx.labels}
                asOf={ctx.asOf}
              />
              <span className="sr-only">. {t("gen.rdw.help")}</span>
            </dd>
          </div>
          {parkedEnabled("registrations") ? (
            <div>
              <dt className="text-sm text-slate-700">{t("reg.title", { country: cfg.name })}</dt>
              <dd className="font-medium">
                {/* Generation- and model-level counts repeat on every variant: show the first variant that has any. */}
                <Registrations ctx={ctx} row={g.rows.find((r) => registrationsFor(r, cfg.code).length)} />
              </dd>
            </div>
          ) : null}
          <div>
            <dt className="text-sm text-slate-700">
              <Term term={ctx.tax.terms["used-price"] ? { ...ctx.tax.terms["used-price"], label: t("gen.usedPrice", { country: cfg.name }) } : undefined} fallback={t("gen.usedPrice", { country: cfg.name })} base={base} text={ctx.termText} showTechnical={false} />
            </dt>
            <dd>
              <PriceBand band={usedBandFor(ctx.cat.usedPrices(), g.id, cfg.code, cfg.currency)} currency={cfg.currency} locale={ctx.locale} notEnoughLabel={t("price.notEnough")} samplesLabel={t("price.samples")} />
            </dd>
          </div>
        </dl>
      </section>

      <PricePanel
        cars={g.rows.map((r) => ({ id: r.variant_id, label: r.variant_name, price: r.price_new?.[cfg.code]?.amount ?? null }))}
        profile={financeProfile(cfg.code)}
        currency={cfg.currency}
        code={cfg.code}
        lang={ctx.lang}
        dict={getClientDict(ctx.lang)}
        base={base}
        terms={financeTerms(ctx.tax.terms)}
      />
      <div className="mt-6">
        <SeeListings
          links={seeListings(country, first)}
          text={{
            title: t("listings.title"),
            intro: t("listings.intro", { name: modelName, country: cfg.name }),
            newTab: t("listings.newTab"),
            unverified: t("listings.unverified"),
            none: t("listings.none"),
          }}
        />
      </div>

      <OwnerNote ctx={ctx} generationIds={[g.id]} />
      <KnownIssues ctx={ctx} generationId={g.id} name={fullName} />

      <section aria-labelledby="timeline" className="mt-8">
        <h2 id="timeline" className="text-xl font-semibold">
          {t("gen.timeline")}
        </h2>
        {g.changeMarkers.length ? (
          <ol className="mt-3 border-l-2 border-slate-300 pl-4">
            {g.changeMarkers.map((m, i) => (
              <li key={`${m.year}-${i}`} className="relative mb-3">
                <span aria-hidden="true" className="absolute -left-[1.4rem] top-1.5 h-2.5 w-2.5 rounded-full bg-blue-800" />
                <span className="font-semibold tabular-nums">{m.year}</span>: {m.text}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-slate-800">{t("gen.timeline.empty")}</p>
        )}
      </section>

      <section aria-labelledby="spec-diff" className="mt-8">
        <h2 id="spec-diff" className="text-xl font-semibold">
          {t("gen.diff")}
        </h2>
        <p className="mb-2 mt-1 text-sm text-slate-700">{t("gen.diff.legend")}</p>
        <DiffOnly label={t("gen.diff.only")} enabled={diff.columns.length > 1 && diff.rows.some((r) => !r.changes)}>
        <SpecDiff
          caption={t("gen.diff.caption", { name: fullName })}
          fieldHeader={t("gen.diff.fieldHeader")}
          changedLabel={t("gen.diff.changed")}
          columns={diff.columns.map((r) => ({
            key: r.variant_id,
            header: (
              <span className="flex flex-col">
                <Link href={variantHref(base, r)} className="text-blue-800 underline underline-offset-2 hover:text-blue-950">
                  {r.variant_name}
                </Link>
                <span className="text-xs font-normal tabular-nums text-slate-700">{formatYears(r.year_start, r.year_end, t("years.now"))}</span>
              </span>
            ),
          }))}
          rows={diff.rows.map((dr) => ({
            key: dr.field.key,
            label: <FieldLabel ctx={ctx} field={dr.field} />,
            cells: dr.cells.map((c, i) => ({ changed: c.changed, content: <SpecValue ctx={ctx} row={diff.columns[i]!} field={dr.field} /> })),
            same: !dr.changes,
          }))}
        />
        </DiffOnly>
        {deltas.length ? (
          <div className="mt-4" data-testid="variant-deltas">
            <h3 className="text-base font-semibold">{t("gen.delta.title")}</h3>
            <ul className="mt-2 grid gap-1 text-sm">
              {deltas.map((d) => (
                <li key={d.to.variant_id}>
                  <span className="font-semibold">{t("gen.delta.pair", { to: d.to.variant_name, from: d.from.variant_name })}</span>{" "}
                  {d.items
                    .map((it) =>
                      t(`gen.delta.${it.field}` as Parameters<typeof t>[0], {
                        n: `${it.delta > 0 ? "+" : "−"}${formatNumber(Math.abs(it.delta), locale, 1)}`,
                      }),
                    )
                    .join(", ")}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-slate-700">{t("gen.delta.note")}</p>
          </div>
        ) : null}
      </section>
      <ChargingLinks links={chargingLinks(country, { withoutAbrp: true, lang })} abrp={abrpLink()} t={t} statsHref={`${base}/charging`} />
    </>
  );
}
