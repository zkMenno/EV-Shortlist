export const RELEASES_DIR: string;
export const TOP40_FILE: string;
export const CONFIG_FILE: string;
export const OUT_FILE: string;
export interface PopularityConfig {
  registrations: number;
  owner_picks: number;
  pick_values: Record<"shortlist" | "consider" | "fallback", number>;
  favourite_bonus: number;
}
export interface PopularityWeights {
  registrations: number;
  owner_picks: number;
}
export interface LoadPopularityOpts {
  catalogueDir?: string;
  catalogueFile?: string;
  configFile?: string;
  top40File?: string;
  picksFile?: string;
  fallbackWeights?: PopularityWeights | null;
}
export function latestCatalogue(dir?: string): string | null;
export function parseConfig(doc: unknown): PopularityConfig;
export function registrationScores(doc: unknown): Record<string, number>;
export function pickScores(picksDoc: unknown, cfg: PopularityConfig): Record<string, number>;
export function fromRelease(catDoc: unknown, weights: PopularityWeights): Record<string, unknown> | null;
export function buildPopularity(top40Doc: unknown, picksDoc: unknown, configDoc: unknown): Record<string, unknown>;
export function loadPopularity(opts?: LoadPopularityOpts): Record<string, unknown> | null;
export function serialize(x: unknown): string;
