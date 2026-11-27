// Performance budget check (A-01, apps/web/AGENTS.md rule 4). Run after `next build`:
//
//   node apps/web/scripts/budget.mjs        (from the repo root or apps/web)
//
// 1. First-load JS of the landing page /[country]/[lang] and of Explore on /[country]/[lang]/cars (T-130), read from the build
//    manifests (build-manifest.json rootMainFiles + the client-reference manifest's entryJSFiles
//    for app/[country]/[lang]/layout and app/[country]/[lang]/page), each gzipped (level 9) and
//    summed. Fails above 200 KB. noModule polyfills are reported but not counted (modern browsers
//    skip them), matching how A-01 measured.
// 2. Client catalogue (/data/catalogue-<n>.json): built from the latest release (CATALOGUE_DIR or
//    data/releases, else the dev fixture) with the app's own toClientCatalogue(), gzipped. Fails
//    at 300 KB or more.
//
// Sizes are KB = 1000 bytes, as in A-01. No dependencies beyond Node (>= 22.18 for .ts import).
/* global process, console, Buffer */
import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";

const here = path.dirname(fileURLToPath(import.meta.url));
export const WEB_DIR = path.resolve(here, "..");
export const JS_BUDGET_KB = 200;
export const CATALOGUE_BUDGET_KB = 300;
/** G-69 (T-167 retro): warn above 85 % of the client catalogue budget (255 KB) before it fails at 300 KB. */
export const CATALOGUE_WARN_RATIO = 0.85;
export const CATALOGUE_WARN_KB = CATALOGUE_BUDGET_KB * CATALOGUE_WARN_RATIO;

/** The app entries whose client chunks load on /[country]/[lang] (Explore). */
// Since Decision 015 the root layout is app/[country]/[lang]/layout (no app/layout).
export const EXPLORE_ENTRIES = ["[project]/apps/web/src/app/[country]/[lang]/layout", "[project]/apps/web/src/app/[country]/[lang]/page"];
/** Explore itself lives on the catalogue page since T-130; both pages get the same JS budget. */
export const CATALOGUE_ENTRIES = ["[project]/apps/web/src/app/[country]/[lang]/layout", "[project]/apps/web/src/app/[country]/[lang]/cars/page"];
export const PAGES = [
  { label: "Landing /[country]/[lang]", dir: "[country]/[lang]", entries: EXPLORE_ENTRIES },
  { label: "Explore /[country]/[lang]/cars", dir: "[country]/[lang]/cars", entries: CATALOGUE_ENTRIES },
];

export const gzipBytes = (buf) => gzipSync(buf, { level: 9 }).length;
export const kb = (bytes) => Math.round(bytes / 100) / 10;

/**
 * Evaluate the gzipped client catalogue size against the budget (G-69):
 * - "fail" when >= budgetKb * 1000 (300 KB, unchanged)
 * - "warn" when >  budgetKb * warnRatio * 1000 (255 KB = 85 % of 300 KB)
 * - "ok"   otherwise
 */
export function evaluateCatalogueBudget(gzBytes, budgetKb = CATALOGUE_BUDGET_KB, warnRatio = CATALOGUE_WARN_RATIO) {
  const budgetBytes = budgetKb * 1000;
  const warnKb = Math.round(budgetKb * warnRatio * 10) / 10;
  const warnBytes = Math.round(budgetBytes * warnRatio);
  const sizeKb = kb(gzBytes);
  const pct = Math.round((gzBytes / budgetBytes) * 1000) / 10;
  if (gzBytes >= budgetBytes) {
    return {
      status: "fail",
      kb: sizeKb,
      pct,
      warnKb,
      budgetKb,
      message: `client catalogue ${sizeKb} KB gzip is not under ${budgetKb} KB`,
    };
  }
  if (gzBytes > warnBytes) {
    return {
      status: "warn",
      kb: sizeKb,
      pct,
      warnKb,
      budgetKb,
      message: `client catalogue ${sizeKb} KB gzip is ${pct} % of the ${budgetKb} KB budget (warning threshold ${warnKb} KB / ${Math.round(warnRatio * 100)} %)`,
    };
  }
  return { status: "ok", kb: sizeKb, pct, warnKb, budgetKb, message: null };
}

/** Reads `globalThis.__RSC_MANIFEST[...] = {...}` from a client-reference manifest file. */
export function parseClientReferenceManifest(src) {
  const i = src.indexOf("= {", src.indexOf("__RSC_MANIFEST["));
  if (i < 0) throw new Error("client-reference manifest: unexpected format");
  const json = src.slice(i + 2).trim().replace(/;\s*$/, "");
  return JSON.parse(json);
}

/** Chunk paths (relative to .next) loaded by Explore, plus the noModule polyfills. */
export function exploreChunks(buildManifest, clientManifest, entries = EXPLORE_ENTRIES) {
  const files = new Set(buildManifest.rootMainFiles ?? []);
  const entryJS = clientManifest.entryJSFiles ?? {};
  for (const e of entries) {
    const list = entryJS[e];
    if (!list) throw new Error(`client-reference manifest has no entry ${e} (did the route move?)`);
    for (const f of list) files.add(f);
  }
  const polyfills = new Set(buildManifest.polyfillFiles ?? []);
  return {
    modern: [...files].filter((f) => f.endsWith(".js") && !polyfills.has(f)),
    polyfills: [...polyfills].filter((f) => f.endsWith(".js")),
  };
}

/** Same lookup as src/lib/catalogue.ts latestCataloguePath(). */
export function latestCatalogue(dir) {
  try {
    const latest = path.join(dir, "latest");
    const st = statSync(latest);
    const p = st.isDirectory() ? path.join(latest, "catalogue.json") : path.join(dir, readFileSync(latest, "utf8").trim(), "catalogue.json");
    return existsSync(p) ? p : null;
  } catch {
    return null;
  }
}

function measureJs(nextDir, page) {
  const buildManifest = JSON.parse(readFileSync(path.join(nextDir, "build-manifest.json"), "utf8"));
  const crm = path.join(nextDir, `server/app/${page.dir}/page_client-reference-manifest.js`);
  if (!existsSync(crm)) throw new Error(`${crm} not found: run \`pnpm --filter @ev/web build\` first`);
  const { modern, polyfills } = exploreChunks(buildManifest, parseClientReferenceManifest(readFileSync(crm, "utf8")), page.entries);
  const size = (f) => {
    const buf = readFileSync(path.join(nextDir, f));
    return { file: f, raw: buf.length, gz: gzipBytes(buf) };
  };
  return { modern: modern.map(size).sort((a, b) => b.gz - a.gz), polyfills: polyfills.map(size) };
}

async function measureCatalogue() {
  const dir = process.env.CATALOGUE_DIR ? path.resolve(WEB_DIR, process.env.CATALOGUE_DIR) : path.resolve(WEB_DIR, "../../data/releases");
  const file = latestCatalogue(dir) ?? path.join(WEB_DIR, "src/fixtures/catalogue.sample.json");
  const cat = JSON.parse(readFileSync(file, "utf8"));
  // The app's own transform (type-only imports, so Node's type stripping can load it).
  const { toClientCatalogue } = await import(pathToFileURL(path.join(WEB_DIR, "src/lib/explore-data.ts")).href);
  // The optional files the data route adds (used prices per build year, release shortlist scores).
  const { parseVariantUsedPrices } = await import(pathToFileURL(path.join(WEB_DIR, "src/lib/variant-prices.ts")).href);
  const { parseShortlistScores } = await import(pathToFileURL(path.join(WEB_DIR, "src/lib/release-scores.ts")).href);
  const side = (name) => {
    const p = path.join(path.dirname(file), name);
    return existsSync(p) ? JSON.parse(readFileSync(p, "utf8")) : null;
  };
  // Popularity per generation (T-130, T-157), as catalogue.ts resolves it.
  const { resolvePopularity } = await import(pathToFileURL(path.join(WEB_DIR, "src/lib/popularity.ts")).href);
  const pop = resolvePopularity(cat.rows, cat.generations, JSON.parse(readFileSync(path.join(WEB_DIR, "src/config/popularity.generated.json"), "utf8")));
  const body = Buffer.from(JSON.stringify(toClientCatalogue(cat.release, cat.sources, cat.rows, parseVariantUsedPrices(side("used_prices.json")), parseShortlistScores(side("shortlist_scores.json")), pop)));
  return { file: path.relative(process.cwd(), file), rows: cat.rows.length, raw: body.length, gz: gzipBytes(body) };
}

async function main() {
  const nextDir = path.join(WEB_DIR, ".next");
  const fails = [];
  for (const page of PAGES) {
    const js = measureJs(nextDir, page);
    const jsGz = js.modern.reduce((s, f) => s + f.gz, 0);
    const jsRaw = js.modern.reduce((s, f) => s + f.raw, 0);
    const polyGz = js.polyfills.reduce((s, f) => s + f.gz, 0);
    console.log(`${page.label} first-load JS: ${js.modern.length} chunks, ${kb(jsGz)} KB gzip (${kb(jsRaw)} KB raw); budget < ${JS_BUDGET_KB} KB`);
    for (const f of js.modern) console.log(`  ${kb(f.gz).toFixed(1).padStart(6)} KB  ${f.file}`);
    console.log(`  + noModule polyfills (not counted): ${kb(polyGz)} KB gzip`);
    if (jsGz > JS_BUDGET_KB * 1000) fails.push(`${page.label} JS ${kb(jsGz)} KB gzip is over ${JS_BUDGET_KB} KB`);
  }
  const cat = await measureCatalogue();
  const catCheck = evaluateCatalogueBudget(cat.gz);

  console.log(`Client catalogue (${cat.file}, ${cat.rows} rows): ${kb(cat.gz)} KB gzip (${kb(cat.raw)} KB raw); budget < ${CATALOGUE_BUDGET_KB} KB (warn > ${CATALOGUE_WARN_KB} KB)`);

  if (catCheck.status === "warn") console.warn(`::warning::Perf budget: ${catCheck.message}`);
  if (catCheck.status === "fail") fails.push(catCheck.message);
  if (fails.length) {
    for (const f of fails) console.error(`::error::Perf budget: ${f}`);
    process.exit(1);
  }
  console.log("Perf budget: OK");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(`::error::Perf budget check failed to run: ${err.message}`);
    process.exit(1);
  });
}
