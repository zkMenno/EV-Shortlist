// Renders one spec field of one variant: numbers through <Num> (source + confidence + badges),
// taxonomy ids as localised labels. Server component; shared by variant, generation and compare pages.
import type { PublishedVariant } from "@ev/schema";
import { Missing, Num } from "@/components/Num";
import { OfficialRange } from "@/components/OfficialRange";
import { Term, TermInfo } from "@/components/Term";
import { hasMsgKey, type MsgKey } from "@/i18n";
import { acOptionalKw } from "@/lib/ac-optional";
import { hiddenForNoDc, isClaimField } from "@/lib/dc";
import { DASH, formatMoney } from "@/lib/format";
import type { SpecField } from "@/lib/spec-diff";
import { sourcesFor, type PageCtx } from "../_lib/context";

const ND = "not-disclosed";

export function fieldLabel(ctx: PageCtx, field: SpecField): string {
  const k = `field.${field.key}`;
  return hasMsgKey(k) ? ctx.t(k, { country: ctx.cfg.name }) : field.key;
}

/** Plain-language label with the glossary ⓘ (safe inside <th>, not inside <label>/<button>). */
export function FieldLabel({ ctx, field }: { ctx: PageCtx; field: SpecField }) {
  const label = fieldLabel(ctx, field);
  const term = field.term ? ctx.tax.terms[field.term] : undefined;
  // T-143 (Decision 085): the ⓘ next to "Official (WLTP)" says in one sentence how it differs from our real range.
  const short = field.key === "wltp_range_km" ? ctx.t("range.wltp.tip") : undefined;
  return (
    <Term
      term={term ? { ...term, label, ...(short ? { short } : {}) } : undefined}
      fallback={label}
      base={ctx.base}
      text={ctx.termText}
      showTechnical={false}
    />
  );
}

function msg(ctx: PageCtx, key: string, fallback: string): string {
  const out = ctx.t(key as MsgKey);
  return out === key ? fallback : out;
}

/** Display text for a text/boolean field. */
export function textValue(ctx: PageCtx, row: PublishedVariant, key: Extract<SpecField, { kind: "text" }>["key"]): string {
  // No DC data → no 400 V charger behaviour (shared rule, src/lib/dc.ts).
  if (hiddenForNoDc(row, key)) return DASH;
  const v = row[key];
  if (v === null || v === undefined || v === "") return DASH;
  if (v === ND) return ctx.t("notDisclosed");
  if (typeof v === "boolean") return ctx.t(v ? "yes" : "no");
  switch (key) {
    case "chemistry_id":
      return ctx.tax.chemistries.find((c) => c.id === v)?.label ?? String(v);
    case "cooling_id":
      return ctx.tax.coolings.find((c) => c.id === v)?.label ?? String(v);
    case "voltage_class_id":
      return ctx.tax.voltageClasses.find((c) => c.id === v)?.label ?? String(v);
    case "charger_400v_mode":
      return msg(ctx, `c400.${v}`, String(v));
    case "body":
      return msg(ctx, `body.${v}`, String(v));
    case "segment":
      return msg(ctx, `segment.${v}`, String(v));
    case "drivetrain": {
      const k = `drivetrain.${v}`;
      return hasMsgKey(k) ? ctx.t(k) : String(v);
    }
    default:
      return String(v);
  }
}

export function SpecValue({ ctx, row, field }: { ctx: PageCtx; row: PublishedVariant; field: SpecField }) {
  if (hiddenForNoDc(row, field.key)) return <Missing label={ctx.labels.noDc} />;
  if (field.kind === "text") {
    const text = textValue(ctx, row, field.key);
    if (text === DASH) return <Missing label={ctx.labels.noData} />;
    // "not disclosed" is a term too (glossary sweep item 7): the maker doesn't publish it.
    if (row[field.key] === ND)
      return (
        <span className="inline-flex items-center gap-1">
          {text}
          <TermInfo term={ctx.tax.terms["not-disclosed"]} base={ctx.base} text={ctx.termText} />
        </span>
      );
    return <span>{text}</span>;
  }
  if (field.kind === "price") {
    const m = row.price_new?.[ctx.cfg.code];
    const prov = row.provenance[`price_new.${ctx.cfg.code}`];
    return (
      <Num
        value={m?.amount}
        text={m ? formatMoney(m.amount, m.currency, ctx.locale) : undefined}
        provenance={prov}
        sources={sourcesFor(ctx, prov)}
        locale={ctx.locale}
        labels={ctx.labels}
        asOf={ctx.asOf}
      />
    );
  }
  const v = row[field.key];
  const prov = row.provenance[field.key];
  // T-143 (Decision 085): the official WLTP range in a secondary style under our real range; missing = "not known".
  if (field.key === "wltp_range_km")
    return (
      <OfficialRange
        value={typeof v === "number" ? v : null}
        provenance={prov}
        sources={sourcesFor(ctx, prov)}
        locale={ctx.locale}
        labels={ctx.labels}
        level="detailed"
        asOf={ctx.asOf}
        text={{ label: ctx.t("range.wltp.label"), notKnown: ctx.t("range.wltp.notKnown"), tip: ctx.t("range.wltp.tip") }}
        showLabel={false}
        className="text-sm"
      />
    );
  // The optional bigger on-board charger sits next to the standard one: "7.4 kW (11 kW optional)".
  const opt = field.key === "ac_kw" ? acOptionalKw(row) : null;
  if (opt !== null) {
    const optProv = row.provenance.ac_kw_optional;
    return (
      <span className="inline-flex flex-wrap items-start gap-x-1" data-testid="ac-optional">
        <Num
          value={typeof v === "number" ? v : null}
          unit={field.unit}
          digits={field.digits}
          provenance={prov}
          sources={sourcesFor(ctx, prov)}
          locale={ctx.locale}
          labels={ctx.labels}
          asOf={ctx.asOf}
        />
        <span className="inline-flex items-start">
          <span aria-hidden="true">(</span>
          <Num
            value={opt}
            unit={field.unit}
            digits={field.digits}
            provenance={optProv}
            sources={sourcesFor(ctx, optProv)}
            locale={ctx.locale}
            labels={ctx.labels}
            asOf={ctx.asOf}
          />
          <span>&nbsp;{ctx.t("field.ac_kw.optional")}</span>
          <span aria-hidden="true">)</span>
        </span>
      </span>
    );
  }
  const note =
    field.key === "real_range_km" && row.real_range_rung ? msg(ctx, `rung.${row.real_range_rung}`, row.real_range_rung) : undefined;
  return (
    <Num
      value={typeof v === "number" ? v : null}
      unit={field.unit}
      digits={field.digits}
      provenance={prov}
      sources={sourcesFor(ctx, prov)}
      locale={ctx.locale}
      labels={ctx.labels}
      note={note}
      noteTerm={note ? "rung" : undefined}
      claim={isClaimField(row, field.key)}
      asOf={ctx.asOf}
    />
  );
}
