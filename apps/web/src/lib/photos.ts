// Generation photos (Decision 081, 083, 086; T-146 rows, T-135 cards and pages). Server only.
// The release ships one photo per generation in three widths, unpacked from `images.tar` into
// `<release>/images/` (scripts/fetch-release.mjs). We serve them ourselves from /photos/<file>
// (src/app/photos/[file]/route.ts): no hotlinking, no third-party request (rule 3).
// A photo is shown only when every width is on disk, so a release fetched without its bundle
// (or an image without the files) shows the page as it was, never a broken image.
import { existsSync } from "node:fs";
import path from "node:path";
import type { Generation } from "@ev/schema";
import { latestCataloguePath } from "./catalogue";

/** What a page needs to show one photo and its credit (plain data: crosses the client boundary). */
export interface PhotoView {
  /** Smallest width (thumbnails, the `src` fallback). */
  src: string;
  /** `srcset` with every width, e.g. "/photos/a-400.webp 400w, /photos/a-800.webp 800w". */
  srcSet: string;
  /** Credit line as the release gives it, e.g. "Alexander Migl, CC BY-SA 4.0, via Wikimedia Commons". */
  credit: string;
  author: string | null;
  licence: string;
  /** The file page (Commons) or the maker's press page: the credit links here. */
  pageUrl: string;
}

/** File names we serve: `<generation id>-<sha8>-<width>.webp` (pipeline/ev_pipeline/images). */
export const PHOTO_FILE_RE = /^[a-z0-9][a-z0-9-]*-[0-9a-f]{8}-\d{2,4}\.webp$/;

/** `<release>/images` of the current release, or null without a release (dev fixture). */
export function photosDir(cataloguePath: string | null = latestCataloguePath()): string | null {
  return cataloguePath ? path.join(path.dirname(cataloguePath), "images") : null;
}

const seen = new Map<string, boolean>();
function onDisk(file: string): boolean {
  let ok = seen.get(file);
  if (ok === undefined) {
    ok = existsSync(file);
    // Remember only hits: a missing file may still arrive (fetch-release running), a present one stays.
    if (ok) seen.set(file, ok);
  }
  return ok;
}

/** The photo of one generation, or null when the release has none or its files aren't on disk. */
export function generationPhoto(gen: Pick<Generation, "image"> | undefined, dir: string | null = photosDir(), exists: (f: string) => boolean = onDisk): PhotoView | null {
  const img = gen?.image;
  if (!img || !dir || !img.files?.length) return null;
  const files = [...img.files].sort((a, b) => a.width - b.width);
  const names: { name: string; width: number }[] = [];
  for (const f of files) {
    // Release-relative "images/<name>"; anything else (a folder, ../) is not ours to serve.
    const name = /^images\/([^/]+)$/.exec(f.path)?.[1];
    if (!name || !PHOTO_FILE_RE.test(name) || !exists(path.join(dir, name))) return null;
    names.push({ name, width: f.width });
  }
  const smallest = names[0];
  if (!smallest) return null;
  return {
    src: `/photos/${smallest.name}`,
    srcSet: names.map((n) => `/photos/${n.name} ${n.width}w`).join(", "),
    credit: img.credit,
    author: img.author ?? null,
    licence: img.licence,
    pageUrl: img.page_url,
  };
}

/** Generation id → photo, for every generation whose files are on disk. */
export function generationPhotos(gens: readonly Generation[], dir: string | null = photosDir()): Record<string, PhotoView> {
  const out: Record<string, PhotoView> = {};
  for (const g of gens) {
    const p = generationPhoto(g, dir);
    if (p) out[g.id] = p;
  }
  return out;
}
