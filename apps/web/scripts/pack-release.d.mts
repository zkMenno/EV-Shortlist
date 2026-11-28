// Types for scripts/pack-release.mjs (imported by its unit test).
export interface RuntimeFile {
  path: string;
  entry: { path: string; bytes: number; sha256: string } | null;
  required: boolean;
}
export function runtimeFiles(
  manifest: { files: { path: string; bytes: number; sha256: string; bundle?: { folder: string; files: { path: string; bytes: number; sha256: string }[] } }[] },
  wanted?: string[],
): { files: RuntimeFile[]; absent: string[] };
export function packRelease(opts: {
  src: string;
  out: string;
  log?: (...args: unknown[]) => void;
  warn?: (...args: unknown[]) => void;
}): { release: number; copied: number; photos: number };
