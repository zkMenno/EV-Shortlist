// "Popular used EVs" on the landing (T-131): the editorial list (data/editorial/popular_used.yaml,
// WS3; via scripts/popular-used.mjs) turned into generation cards from the release. Order and
// contents are data. A listed generation without any variant row in the release is skipped (never
// an empty card), and the next one moves up, so the landing still shows `landing_count` cards.
import type { Country } from "@ev/schema";
import data from "@/config/popular-used.generated.json";
import type { ExploreRow } from "./explore-data";
import { generationCards, type GenCard } from "./generation-cards";

export interface PopularUsedList {
  landing_count: number;
  generations: { generation_id: string; why: string }[];
}

export const POPULAR_USED: PopularUsedList = data;

export interface PopularCard {
  card: GenCard;
  why: string;
}

export function popularUsedCards(rows: readonly ExploreRow[], country: Country, list: PopularUsedList = POPULAR_USED): PopularCard[] {
  const byGen = new Map<string, ExploreRow[]>();
  for (const r of rows) {
    const g = byGen.get(r.generation_id);
    if (g) g.push(r);
    else byGen.set(r.generation_id, [r]);
  }
  const out: PopularCard[] = [];
  for (const g of list.generations) {
    if (out.length >= list.landing_count) break;
    const gen = byGen.get(g.generation_id);
    if (!gen?.length) continue;
    const card = generationCards(gen, country)[0];
    if (card) out.push({ card, why: g.why });
  }
  return out;
}
