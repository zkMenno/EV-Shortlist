import { describe, expect, it } from "vitest";
import {
  CATALOGUE_BUDGET_KB,
  CATALOGUE_WARN_KB,
  EXPLORE_ENTRIES,
  evaluateCatalogueBudget,
  exploreChunks,
  parseClientReferenceManifest,
} from "../../scripts/budget.mjs";

describe("perf budget script", () => {
  it("parses a client-reference manifest", () => {
    const src = 'globalThis.__RSC_MANIFEST = globalThis.__RSC_MANIFEST || {};\nglobalThis.__RSC_MANIFEST["/[country]/page"] = {"entryJSFiles":{"a":["x.js"]}};\n';
    expect(parseClientReferenceManifest(src)).toEqual({ entryJSFiles: { a: ["x.js"] } });
  });

  it("counts root + Explore entry chunks once and leaves noModule polyfills out", () => {
    const build = { rootMainFiles: ["r1.js", "r2.js"], polyfillFiles: ["poly.js"] };
    const entryJSFiles = Object.fromEntries(EXPLORE_ENTRIES.map((e, i) => [e, ["shared.js", `e${i}.js`, "style.css"]]));
    const { modern, polyfills } = exploreChunks(build, { entryJSFiles });
    expect(modern.sort()).toEqual(["e0.js", "e1.js", "r1.js", "r2.js", "shared.js"]);
    expect(polyfills).toEqual(["poly.js"]);
  });

  it("fails loudly when the Explore route is missing from the manifest", () => {
    expect(() => exploreChunks({}, { entryJSFiles: {} })).toThrow(/no entry/);
  });

  it("warns above 85 % of the 300 KB client catalogue budget (255 KB) without changing the 300 KB fail limit (G-69)", () => {
    expect(CATALOGUE_BUDGET_KB).toBe(300);
    expect(CATALOGUE_WARN_KB).toBe(255);

    // Pass: well below and right on the 85 % boundary (255.0 KB)
    expect(evaluateCatalogueBudget(170_600)).toMatchObject({ status: "ok", kb: 170.6, message: null });
    expect(evaluateCatalogueBudget(255_000)).toMatchObject({ status: "ok", kb: 255, pct: 85, message: null });

    // Warn: strictly above 255 KB and still under 300 KB
    const justOver = evaluateCatalogueBudget(255_001);
    expect(justOver.status).toBe("warn");
    expect(justOver.message).toMatch(/255 KB/);
    expect(justOver.message).toMatch(/85 %/);

    const high = evaluateCatalogueBudget(293_800);
    expect(high).toMatchObject({ status: "warn", kb: 293.8, pct: 97.9 });
    expect(high.message).toContain("293.8 KB");
    expect(high.message).toContain("300 KB");

    expect(evaluateCatalogueBudget(299_999).status).toBe("warn");

    // Fail: 300 KB or more (threshold unchanged)
    expect(evaluateCatalogueBudget(300_000)).toMatchObject({
      status: "fail",
      kb: 300,
      message: "client catalogue 300 KB gzip is not under 300 KB",
    });
    expect(evaluateCatalogueBudget(337_400).status).toBe("fail");
  });
});
