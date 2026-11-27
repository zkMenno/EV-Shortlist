import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import * as yaml from "js-yaml";
import { describe, expect, it } from "vitest";
import {
  buildPopularity,
  CONFIG_FILE,
  fromRelease,
  loadPopularity,
  OUT_FILE,
  parseConfig,
  pickScores,
  registrationScores,
  serialize,
} from "../../scripts/popularity.mjs";
import {
  rankGenerations,
  releasePopularity,
  releasePopularityAsOf,
  resolvePopularity,
  type PopularityInputs,
  type PopularityReleaseData,
} from "./popularity";
import { sortRows } from "./filters";
import { MENU_SORTS, sortBy, defaultState, fromSearchParams, toSearchParams } from "./state";
import type { ExploreRow } from "./explore-data";

const inputs: PopularityInputs = {
  weights: { registrations: 0.8, owner_picks: 0.2 },
  models: { a: 8, b: 4, c: 0 },
  generations: { "b-gen2": 1 },
};

const score = (rows: Parameters<typeof rankGenerations>[0], id: string, inp = inputs) => rankGenerations(rows, inp).get(id)?.score ?? null;
const one = (model: string, gen: string, n?: number) => ({ model_id: model, generation_id: gen, registered_count_nl: n ?? null });

describe("rankGenerations (T-130 blend)", () => {
  it("scales registrations to the top generation and adds the owner pick", () => {
    const rows = [one("a", "a-gen1"), one("b", "b-gen1")];
    expect(score(rows, "a-gen1")).toBe(80); // 0.8 × 8/8
    expect(score(rows, "b-gen1")).toBe(40); // 0.8 × 4/8
  });
  it("splits a model's share over its generations by the RDW count (review #117: no more ties)", () => {
    // Model a: 8 % share, RDW 300 vs 100 → 6 % and 2 %. Model b: 4 %, one generation.
    const rows = [one("a", "a-gen1", 300), one("a", "a-gen1", 300), one("a", "a-gen2", 100), one("b", "b-gen1", 50)];
    const r = rankGenerations(rows, inputs);
    expect(r.get("a-gen1")).toEqual({ score: 80, rank: 1 }); // 6/6
    expect(r.get("b-gen1")).toEqual({ score: 53.3, rank: 2 }); // 4/6
    expect(r.get("a-gen2")).toEqual({ score: 26.7, rank: 3 }); // 2/6
  });
  it("a generation with no RDW count while its siblings have one gets no registration share", () => {
    const rows = [one("a", "a-gen1", 100), one("a", "a-gen2")];
    expect(score(rows, "a-gen1")).toBe(80);
    expect(score(rows, "a-gen2")).toBe(0);
  });
  it("splits evenly when RDW has no count for any generation of the model", () => {
    const rows = [one("a", "a-gen1"), one("a", "a-gen2"), one("b", "b-gen1")];
    expect(score(rows, "a-gen1")).toBe(80); // 4 % each = the top
    expect(score(rows, "a-gen2")).toBe(80);
    expect(score(rows, "b-gen1")).toBe(80);
  });
  it("adds the pick per generation", () => {
    expect(score([one("b", "b-gen1"), one("b", "b-gen2"), one("a", "a-gen1")], "b-gen2")).toBe(40); // 0.8 × 2/8 + 0.2
  });
  it("no registrations and no pick: no score, no rank (never a guess); a pick alone counts", () => {
    const rows = [one("zz", "zz-gen1"), one("zz", "b-gen2"), one("a", "a-gen1")];
    const r = rankGenerations(rows, inputs);
    expect(r.has("zz-gen1")).toBe(false);
    expect(r.get("b-gen2")?.score).toBe(20);
  });
  it("weights are relative: doubling both changes nothing", () => {
    const rows = [one("a", "a-gen1"), one("b", "b-gen2")];
    expect(score(rows, "b-gen2", { ...inputs, weights: { registrations: 1.6, owner_picks: 0.4 } })).toBe(score(rows, "b-gen2"));
  });
  it("ranks each generation once and breaks ties by id, so ranks are stable", () => {
    const r = rankGenerations([one("x", "x-2"), one("x", "x-1"), one("x", "x-1")], { ...inputs, models: { x: 1 } });
    expect([...r.keys()]).toEqual(["x-1", "x-2"]);
    expect(r.get("x-1")?.rank).toBe(1);
  });
});

describe("releasePopularity and resolvePopularity (T-157)", () => {
  const relGens = [
    { id: "g-second", popularity: { score: 42.5, rank: 2, registrations: 12000, as_of: "2026-06-30", source_ids: ["dft-veh"] as [string, ...string[]] } },
    { id: "g-first", popularity: { score: 87.2, rank: 1, registrations: 50000, as_of: "2026-11-27", source_ids: ["dft-veh", "rdw"] as [string, ...string[]] } },
    { id: "g-none" },
  ];

  it("reads generations[].popularity ordered by rank and picks newest as_of", () => {
    const map = releasePopularity(relGens);
    expect([...map.entries()]).toEqual([
      ["g-first", { score: 87.2, rank: 1 }],
      ["g-second", { score: 42.5, rank: 2 }],
    ]);
    expect(releasePopularityAsOf(relGens)).toBe("2026-11-27");
  });

  it("prefers release generations[].popularity over fallback inputs", () => {
    const map = resolvePopularity([one("a", "g-first"), one("b", "g-second")], relGens, inputs);
    expect(map.get("g-first")).toEqual({ score: 87.2, rank: 1 });
    expect(map.get("g-second")).toEqual({ score: 42.5, rank: 2 });
  });

  it("falls back to rankGenerations on older releases without generations[].popularity (D5 N-1)", () => {
    const oldGens = [{ id: "a-gen1" }, { id: "b-gen1" }];
    expect(releasePopularity(oldGens).size).toBe(0);
    expect(releasePopularityAsOf(oldGens)).toBeNull();
    const map = resolvePopularity([one("a", "a-gen1"), one("b", "b-gen1")], oldGens, inputs);
    expect(map.get("a-gen1")).toEqual({ score: 80, rank: 1 });
    expect(map.get("b-gen1")).toEqual({ score: 40, rank: 2 });
  });

  it("uses build-time release rankings snapshot when a fixture has no generation popularity", () => {
    const snap: PopularityReleaseData = {
      schema: "popularity-release/v1",
      release: 4,
      weights: { registrations: 0.8, owner_picks: 0.2 },
      inputs: { as_of: "2026-11-27", registration_sources: ["dft-veh", "rdw"] },
      rankings: { "a-gen1": { score: 80, rank: 1 }, "other-gen": { score: 50, rank: 2 } },
    };
    const map = resolvePopularity([one("a", "a-gen1"), one("b", "b-gen1")], [{ id: "a-gen1" }], snap);
    expect([...map.entries()]).toEqual([["a-gen1", { score: 80, rank: 1 }]]);
  });
});

describe("popular sort", () => {
  const row = (id: string, pop?: number) => ({ variant_id: id, ...(pop === undefined ? {} : { pop }) }) as unknown as ExploreRow;
  it("sorts high to low with unknowns last", () => {
    const out = sortRows([row("u"), row("lo", 10), row("hi", 90)], "popular", "desc", "NL");
    expect(out.map((r) => r.variant_id)).toEqual(["hi", "lo", "u"]);
  });
  it("menu picks the natural direction and round-trips through the URL", () => {
    const s = sortBy(defaultState(), "popular");
    expect(s.dir).toBe("desc");
    expect(sortBy(defaultState(), "price").dir).toBe("asc");
    const back = fromSearchParams(Object.fromEntries(toSearchParams(s)));
    expect(back.sort).toBe("popular");
    expect(back.dir).toBe("desc");
    expect(MENU_SORTS[0]).toBe("popular");
  });
  it("the page's default view stays out of the URL; the other one is written (cards default on /cars)", () => {
    const table = { ...defaultState(), view: "table" as const };
    const cards = { ...defaultState(), view: "cards" as const };
    expect(toSearchParams(table).get("view")).toBeNull();
    expect(toSearchParams(cards).get("view")).toBe("cards");
    expect(toSearchParams(table, "cards").get("view")).toBe("table");
    expect(toSearchParams(cards, "cards").get("view")).toBeNull();
  });
});

describe("scripts/popularity.mjs", () => {
  it("committed JSON weights match config/popularity.yaml and rankings match the current release when aligned", () => {
    const committed = JSON.parse(readFileSync(OUT_FILE, "utf8")) as Record<string, unknown>;
    const cfg = parseConfig(yaml.load(readFileSync(CONFIG_FILE, "utf8"), { schema: yaml.CORE_SCHEMA }));
    expect(committed.weights).toEqual({ registrations: cfg.registrations, owner_picks: cfg.owner_picks });
    const fresh = loadPopularity();
    expect(fresh).not.toBeNull();
    // On the same release number, the committed JSON must stay in sync (`node scripts/popularity.mjs`).
    // A future data-refresh PR bumps `latest` before `pnpm build` regenerates OUT_FILE, so only fail when
    // the release number matches.
    if (committed.schema === fresh!.schema && committed.release === fresh!.release) {
      expect(readFileSync(OUT_FILE, "utf8")).toBe(serialize(fresh));
    }
  });
  it("fromRelease reads generations[].popularity directly and returns null when absent (N-1)", () => {
    const w = { registrations: 0.8, owner_picks: 0.2 };
    expect(fromRelease({ release: 3, generations: [{ id: "g1" }] }, w)).toBeNull();
    const out = fromRelease(
      {
        release: 4,
        generations: [
          { id: "b-gen", popularity: { score: 12.3, rank: 2, as_of: "2026-06-30", source_ids: ["dft-veh"] } },
          { id: "a-gen", popularity: { score: 87.2, rank: 1, as_of: "2026-11-27", source_ids: ["rdw", "dft-veh"] } },
          { id: "no-pop" },
        ],
      },
      w,
    );
    expect(out).toEqual({
      schema: "popularity-release/v1",
      release: 4,
      weights: w,
      inputs: { as_of: "2026-11-27", registration_sources: ["dft-veh", "rdw"] },
      rankings: {
        "a-gen": { score: 87.2, rank: 1 },
        "b-gen": { score: 12.3, rank: 2 },
      },
    });
  });
  it("loadPopularity reads release 4+ popularity and falls back to top40 + picks on an N-1 release", () => {
    const dir4 = mkdtempSync(path.join(tmpdir(), "ev-pop-r4-"));
    mkdirSync(path.join(dir4, "4"));
    writeFileSync(path.join(dir4, "latest"), "4\n");
    writeFileSync(
      path.join(dir4, "4", "catalogue.json"),
      JSON.stringify({
        release: 4,
        generations: [{ id: "tesla-model-y-gen1", popularity: { score: 87.2, rank: 1, as_of: "2026-11-27", source_ids: ["rdw"] } }],
      }),
    );
    const r4 = loadPopularity({ catalogueDir: dir4 });
    expect(r4).toMatchObject({ schema: "popularity-release/v1", release: 4, rankings: { "tesla-model-y-gen1": { score: 87.2, rank: 1 } } });

    const dir3 = mkdtempSync(path.join(tmpdir(), "ev-pop-r3-"));
    mkdirSync(path.join(dir3, "3"));
    writeFileSync(path.join(dir3, "latest"), "3\n");
    writeFileSync(path.join(dir3, "3", "catalogue.json"), JSON.stringify({ release: 3, generations: [{ id: "tesla-model-y-gen1" }] }));
    const r3 = loadPopularity({ catalogueDir: dir3 });
    expect(r3).toMatchObject({ schema: "popularity-inputs/v1" });
    expect(r3?.models).toBeDefined();
  });
  it("rejects bad weights", () => {
    expect(() => parseConfig({ weights: { registrations: 0, owner_picks: 0 }, pick_values: { shortlist: 1, consider: 0.5, fallback: 0.2 } })).toThrow();
    expect(() => parseConfig({ weights: { registrations: 1, owner_picks: -1 }, pick_values: { shortlist: 1, consider: 0.5, fallback: 0.2 } })).toThrow();
    expect(() => parseConfig({ weights: { registrations: 1, owner_picks: 0 }, pick_values: { shortlist: 2, consider: 0.5, fallback: 0.2 } })).toThrow();
  });
  it("reads ranked and outside-top models; drops bad ids", () => {
    expect(registrationScores({ models: [{ model_id: "a-b", score_pct: 2 }, { model_id: "Bad Id", score_pct: 1 }], seed_models_outside_top: [{ model_id: "c", score_pct: 0.5 }] })).toEqual({ "a-b": 2, c: 0.5 });
  });
  it("picks: best verdict + favourite bonus, capped at 1; unrated and ruled out give nothing", () => {
    const cfg = parseConfig({ weights: { registrations: 1, owner_picks: 1 }, pick_values: { shortlist: 1, consider: 0.6, fallback: 0.3 }, favourite_bonus: 0.2 });
    const doc = {
      primary_car_picks: [
        { seed_generation_id: "g1", verdict: "consider", favourite: true },
        { seed_generation_id: "g1", verdict: "fallback" },
        { seed_generation_id: "g2", verdict: "shortlist", favourite: true },
        { seed_generation_id: "g3", verdict: "unrated", notes: "note" },
        { seed_generation_id: "g4", verdict: "ruled_out" },
      ],
    };
    expect(pickScores(doc, cfg)).toEqual({ g1: 0.8, g2: 1 });
  });
  it("never carries sheet values into the output", () => {
    const out = JSON.stringify(buildPopularity({ models: [] }, { primary_car_picks: [{ seed_generation_id: "g", verdict: "shortlist", sheet_values: { secret: 1 } }] }, { weights: { registrations: 1, owner_picks: 1 }, pick_values: { shortlist: 1, consider: 0.6, fallback: 0.3 } }));
    expect(out).not.toContain("secret");
  });
});
