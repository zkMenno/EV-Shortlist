import { readFileSync } from "node:fs";
import * as yaml from "js-yaml";
import { describe, expect, it } from "vitest";
import { buildPopularUsed, IN_FILE, OUT_FILE } from "../../scripts/popular-used.mjs";
import type { ExploreRow } from "./explore-data";
import { popularUsedCards } from "./popular-used";

const row = (generation_id: string, variant_id: string, extra: Partial<ExploreRow> = {}) =>
  ({ generation_id, variant_id, make_id: "m", make_name: "M", model_name: "X", generation_name: generation_id, year_start: 2020, year_end: 2023, provenance: {}, ...extra }) as unknown as ExploreRow;

describe("popularUsedCards", () => {
  const list = {
    landing_count: 2,
    generations: [
      { generation_id: "a", why: "first" },
      { generation_id: "no-rows", why: "listed but not in the release" },
      { generation_id: "b", why: "second" },
      { generation_id: "c", why: "third" },
    ],
  };

  it("keeps the editorial order, skips generations without rows and still fills landing_count", () => {
    const cards = popularUsedCards([row("c", "c1"), row("b", "b1"), row("a", "a1"), row("a", "a2")], "NL", list);
    expect(cards.map((c) => c.card.generation_id)).toEqual(["a", "b"]);
    expect(cards.map((c) => c.why)).toEqual(["first", "second"]);
    expect(cards[0]!.card.rows).toHaveLength(2);
  });

  it("shows fewer cards rather than empty ones when the release has too few", () => {
    expect(popularUsedCards([row("c", "c1")], "NL", list).map((c) => c.card.generation_id)).toEqual(["c"]);
    expect(popularUsedCards([], "NL", list)).toEqual([]);
  });
});

describe("scripts/popular-used.mjs", () => {
  it("the committed JSON matches data/editorial/popular_used.yaml (run node scripts/popular-used.mjs)", () => {
    const doc = yaml.load(readFileSync(IN_FILE, "utf8"), { schema: yaml.CORE_SCHEMA });
    expect(readFileSync(OUT_FILE, "utf8")).toBe(`${JSON.stringify(buildPopularUsed(doc), null, 2)}\n`);
  });

  it("refuses rows without an id or a why line, duplicates and a missing landing_count", () => {
    const base = { schema: "editorial-popular-used/v1", method: { landing_count: 2 } };
    expect(() => buildPopularUsed({ ...base, generations: [{ order: 1, generation_id: "a" }] })).toThrow(/why/);
    expect(() => buildPopularUsed({ ...base, generations: [{ order: 1, why: "x" }] })).toThrow(/generation_id/);
    expect(() =>
      buildPopularUsed({ ...base, generations: [{ order: 1, generation_id: "a", why: "x" }, { order: 2, generation_id: "a", why: "y" }] }),
    ).toThrow(/twice/);
    expect(() => buildPopularUsed({ schema: base.schema, generations: [] })).toThrow(/landing_count/);
    expect(() => buildPopularUsed({ ...base, schema: "other" })).toThrow(/schema/);
  });

  it("orders by the file's order field, not by position", () => {
    const out = buildPopularUsed({
      schema: "editorial-popular-used/v1",
      method: { landing_count: 1 },
      generations: [{ order: 2, generation_id: "b", why: "two" }, { order: 1, generation_id: "a", why: "one" }],
    });
    expect(out.generations.map((g) => g.generation_id)).toEqual(["a", "b"]);
  });
});
