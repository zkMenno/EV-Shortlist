export const IN_FILE: string;
export const OUT_FILE: string;
export interface PopularUsedData {
  schema: "popular-used/v1";
  landing_count: number;
  licence: string | null;
  generations: { generation_id: string; why: string }[];
}
export function buildPopularUsed(doc: unknown): PopularUsedData;
