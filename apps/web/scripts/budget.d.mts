// Types for scripts/budget.mjs (imported by its unit test).
export const WEB_DIR: string;
export const JS_BUDGET_KB: number;
export const CATALOGUE_BUDGET_KB: number;
export const CATALOGUE_WARN_RATIO: number;
export const CATALOGUE_WARN_KB: number;
export interface CatalogueBudgetResult {
  status: "ok" | "warn" | "fail";
  kb: number;
  pct: number;
  warnKb: number;
  budgetKb: number;
  message: string | null;
}
export function evaluateCatalogueBudget(gzBytes: number, budgetKb?: number, warnRatio?: number): CatalogueBudgetResult;
export const EXPLORE_ENTRIES: string[];
export const CATALOGUE_ENTRIES: string[];
export const PAGES: { label: string; dir: string; entries: string[] }[];
export function gzipBytes(buf: Uint8Array): number;
export function kb(bytes: number): number;
export function parseClientReferenceManifest(src: string): { entryJSFiles?: Record<string, string[]> };
export function exploreChunks(
  buildManifest: { rootMainFiles?: string[]; polyfillFiles?: string[] },
  clientManifest: { entryJSFiles?: Record<string, string[]> },
  entries?: string[],
): { modern: string[]; polyfills: string[] };
export function latestCatalogue(dir: string): string | null;
