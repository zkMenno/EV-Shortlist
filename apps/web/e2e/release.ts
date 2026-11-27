// Which optional files the release under test carries (same folder and `latest` lookup as
// playwright.config.ts and src/lib/catalogue.ts). Hero ranking tests need shortlist_scores.json
// (Decision 065); budget tests also need used_prices.json (Decision 064). Release 1 has neither,
// so those tests skip with the reason and the "ranking not available" test runs instead.
import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const dir = path.resolve(process.cwd(), process.env.E2E_CATALOGUE_DIR ?? "../../data/releases");

function releaseFolder(): string | null {
  const latest = path.join(dir, "latest");
  try {
    if (statSync(latest).isDirectory()) return latest;
    const n = readFileSync(latest, "utf8").trim();
    return /^\d+$/.test(n) ? path.join(dir, n) : null;
  } catch {
    return null; // no release: the app runs on the dev fixture, which carries fixture scores
  }
}

const folder = releaseFolder();

/** True when the release under test has this file (the dev fixture counts as having scores only). */
export function releaseHas(file: "shortlist_scores.json" | "used_prices.json"): boolean {
  if (!folder) return file === "shortlist_scores.json";
  return existsSync(path.join(folder, file));
}

export const HAS_SCORES = releaseHas("shortlist_scores.json");
export const HAS_USED_PRICES = releaseHas("used_prices.json");
export const NO_SCORES_REASON = "the release under test has no shortlist_scores.json (Decision 065; release 2 / T-116 adds it)";

/** True when the release under test has its photos unpacked (`images/`, Decision 086; release 4+). */
export const HAS_PHOTOS = !!folder && existsSync(path.join(folder, "images"));
export const NO_PHOTOS_REASON = "the release under test has no unpacked images/ folder (photos arrive with release 4, Decision 086)";
