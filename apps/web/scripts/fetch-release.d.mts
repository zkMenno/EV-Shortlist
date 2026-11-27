// Types for scripts/fetch-release.mjs (imported by its unit test).
export const DEFAULT_FILES: string[];
export function safePath(rel: string): string;
export function parseTar(buf: Uint8Array): { name: string; typeflag: number; data: Uint8Array }[];
export interface BundleMember {
  path: string;
  bytes: number;
  sha256: string;
}
export interface BundleEntry {
  path: string;
  bytes: number;
  sha256: string;
  bundle: {
    folder: string;
    files: BundleMember[];
  };
}
export function unpackBundle(rdir: string, entry: BundleEntry): number;
export interface FetchReleaseOptions {
  env?: Record<string, string | undefined>;
  mode?: string;
  dir?: string;
  release?: string;
  files?: string[];
  includePhotoBundle?: boolean;
  fetchImpl?: (url: string, init?: { redirect?: string }) => Promise<{ ok: boolean; status: number; arrayBuffer(): Promise<ArrayBuffer> }>;
  log?: (...args: unknown[]) => void;
  warn?: (...args: unknown[]) => void;
}
export function fetchRelease(opts?: FetchReleaseOptions): Promise<{ status: string; downloaded: number; unpacked: number }>;
