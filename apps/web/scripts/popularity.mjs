// Build-time inputs for the "Most popular" sort (T-130, T-149, T-157, Decision 038 blend).
// Reads `generations[].popularity` from the latest release (`data/releases/<latest>/catalogue.json`)
// instead of computing its own ranking. Older releases (1–3) without the field still build cleanly
// (REVIEW D5 N-1) by falling back to `data/seed/top40.yaml` + `data/editorial/menno-picks.yaml`.
// Weights come from `config/popularity.yaml` (never hard-coded; YAML stays build-time only).
//
//   node scripts/popularity.mjs           write the JSON (runs before `next build` and `next dev`)
//   node scripts/popularity.mjs --check   fail if the committed JSON is out of date
/* global process, console */
import { existsSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as yaml from "js-yaml";
import { PICKS_FILE, ownerNotes } from "./owner-picks.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
export const RELEASES_DIR = path.resolve(here, "../../../data/releases");
export const TOP40_FILE = path.resolve(here, "../../../data/seed/top40.yaml");
export const CONFIG_FILE = path.resolve(here, "../../../config/popularity.yaml");
export const OUT_FILE = path.resolve(here, "../src/config/popularity.generated.json");
const ID_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const VERDICTS = ["shortlist", "consider", "fallback"];

const load = (file) => yaml.load(readFileSync(file, "utf8"), { schema: yaml.CORE_SCHEMA });
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Same lookup as src/lib/catalogue.ts latestCataloguePath(). */
export function latestCatalogue(dir = RELEASES_DIR) {
  try {
    const latest = path.join(dir, "latest");
    const st = statSync(latest);
    const p = st.isDirectory() ? path.join(latest, "catalogue.json") : path.join(dir, readFileSync(latest, "utf8").trim(), "catalogue.json");
    return existsSync(p) ? p : null;
  } catch {
    return null;
  }
}

/** Validated blend config. Throws on anything the blend can't use. */
export function parseConfig(doc) {
  const w = doc?.weights ?? {};
  const reg = num(w.registrations);
  const picks = num(w.owner_picks);
  if (reg === null || picks === null || reg < 0 || picks < 0 || reg + picks <= 0) {
    throw new Error("popularity.yaml: weights.registrations and weights.owner_picks must be numbers ≥ 0, not both 0");
  }
  const pick_values = {};
  for (const v of VERDICTS) {
    const x = num(doc?.pick_values?.[v]);
    if (x === null || x < 0 || x > 1) throw new Error(`popularity.yaml: pick_values.${v} must be a number from 0 to 1`);
    pick_values[v] = x;
  }
  const bonus = num(doc?.favourite_bonus) ?? 0;
  if (bonus < 0 || bonus > 1) throw new Error("popularity.yaml: favourite_bonus must be from 0 to 1");
  return { registrations: reg, owner_picks: picks, pick_values, favourite_bonus: bonus };
}

/** model id → registration score (% share, top40 method), ranked and outside-top models together. */
export function registrationScores(doc) {
  const out = {};
  for (const m of [...(doc?.models ?? []), ...(doc?.seed_models_outside_top ?? [])]) {
    const id = m?.model_id;
    const s = num(m?.score_pct);
    if (typeof id !== "string" || !ID_RE.test(id) || s === null || s < 0) continue;
    out[id] = Math.max(out[id] ?? 0, s);
  }
  return Object.fromEntries(Object.keys(out).sort().map((k) => [k, out[k]]));
}

/** generation id → pick value 0..1: best verdict + favourite bonus, capped at 1. Unrated / ruled out → absent. */
export function pickScores(picksDoc, cfg) {
  const out = {};
  for (const [gen, notes] of Object.entries(ownerNotes(picksDoc).generations)) {
    let best = 0;
    for (const n of notes) {
      if (!n.verdict) continue;
      best = Math.max(best, Math.min(1, cfg.pick_values[n.verdict] + (n.favourite ? cfg.favourite_bonus : 0)));
    }
    if (best > 0) out[gen] = best;
  }
  return out;
}

/**
 * Read `generations[].popularity` from a published release (T-149, T-157).
 * Returns null when the release carries no popularity fields (older releases 1–3: N-1 fallback).
 */
export function fromRelease(catDoc, weights) {
  const gens = Array.isArray(catDoc?.generations) ? catDoc.generations : [];
  const entries = [];
  const sources = new Set();
  let asOf = null;
  for (const g of gens) {
    const id = g?.id;
    const p = g?.popularity;
    const score = num(p?.score);
    const rank = num(p?.rank);
    if (typeof id !== "string" || !ID_RE.test(id) || score === null || score < 0 || rank === null || !Number.isInteger(rank) || rank < 1) {
      continue;
    }
    entries.push([id, { score, rank }]);
    if (typeof p.as_of === "string" && DATE_RE.test(p.as_of) && (asOf === null || p.as_of > asOf)) {
      asOf = p.as_of;
    }
    if (Array.isArray(p.source_ids)) {
      for (const s of p.source_ids) if (typeof s === "string" && s) sources.add(s);
    }
  }
  if (!entries.length) return null;
  entries.sort((a, b) => a[0].localeCompare(b[0]));
  return {
    schema: "popularity-release/v1",
    release: typeof catDoc?.release === "number" ? catDoc.release : null,
    weights: { registrations: weights.registrations, owner_picks: weights.owner_picks },
    inputs: {
      as_of: asOf,
      registration_sources: sources.size ? [...sources].sort() : ["dft-veh", "rdw"],
    },
    rankings: Object.fromEntries(entries),
  };
}

/** Legacy fallback builder for older releases (1–3) without `generations[].popularity`. */
export function buildPopularity(top40Doc, picksDoc, configDoc) {
  const cfg = parseConfig(configDoc);
  return {
    schema: "popularity-inputs/v1",
    weights: { registrations: cfg.registrations, owner_picks: cfg.owner_picks },
    inputs: {
      top40_generated_on: typeof top40Doc?.generated_on === "string" ? top40Doc.generated_on : null,
      picks_imported: typeof picksDoc?.source?.imported === "string" ? picksDoc.source.imported : null,
      registration_sources: ["rdw", "dft-veh"],
    },
    models: registrationScores(top40Doc),
    generations: pickScores(picksDoc, cfg),
  };
}

function readWeights(configFile, fallbackWeights) {
  if (existsSync(configFile)) {
    const cfg = parseConfig(load(configFile));
    return { registrations: cfg.registrations, owner_picks: cfg.owner_picks };
  }
  const w = fallbackWeights;
  if (w && num(w.registrations) !== null && num(w.owner_picks) !== null && w.registrations + w.owner_picks > 0) {
    return { registrations: w.registrations, owner_picks: w.owner_picks };
  }
  return { registrations: 0.8, owner_picks: 0.2 };
}

export function loadPopularity(opts = {}) {
  const dir = opts.catalogueDir ?? (process.env.CATALOGUE_DIR ? path.resolve(here, "..", process.env.CATALOGUE_DIR) : RELEASES_DIR);
  const catFile = opts.catalogueFile ?? latestCatalogue(dir);
  const configFile = opts.configFile ?? CONFIG_FILE;
  if (catFile && existsSync(catFile)) {
    const catDoc = JSON.parse(readFileSync(catFile, "utf8"));
    const fromRel = fromRelease(catDoc, readWeights(configFile, opts.fallbackWeights));
    if (fromRel) return fromRel;
  }
  const top40File = opts.top40File ?? TOP40_FILE;
  const picksFile = opts.picksFile ?? PICKS_FILE;
  const missing = [top40File, picksFile, configFile].filter((f) => !existsSync(f));
  if (missing.length) return null;
  return buildPopularity(load(top40File), load(picksFile), load(configFile));
}

export function serialize(x) {
  return JSON.stringify(x, null, 2) + "\n";
}

function main() {
  const check = process.argv.includes("--check");
  const current = existsSync(OUT_FILE) ? readFileSync(OUT_FILE, "utf8") : "";
  let fallbackWeights = null;
  if (current) {
    try {
      fallbackWeights = JSON.parse(current)?.weights ?? null;
    } catch {
      fallbackWeights = null;
    }
  }
  const data = loadPopularity({ fallbackWeights });
  if (!data) {
    // e.g. a Docker build context on an N-1 release without data/ or config/: keep the committed JSON.
    if (check) throw new Error("popularity: release has no generations[].popularity and YAML fallback inputs are not found");
    console.warn(`popularity: release has no popularity and fallback YAML inputs not found, keeping ${path.basename(OUT_FILE)}`);
    return;
  }
  const json = serialize(data);
  if (check) {
    if (current !== json) {
      console.error("popularity: src/config/popularity.generated.json is out of date; run `node scripts/popularity.mjs`");
      process.exit(1);
    }
    return;
  }
  if (current !== json) writeFileSync(OUT_FILE, json);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
