import { describe, expect, it } from "vitest";
import type { GenerationImage } from "@ev/schema";
import { generationPhoto, generationPhotos, PHOTO_FILE_RE } from "./photos";

const image = {
  files: [
    { width: 800, path: "images/kia-niro-ev-de-9ad70528-800.webp", bytes: 2, sha256: "0".repeat(64) },
    { width: 400, path: "images/kia-niro-ev-de-9ad70528-400.webp", bytes: 1, sha256: "0".repeat(64) },
  ],
  source: "commons" as const,
  page_url: "https://commons.wikimedia.org/wiki/File:Kia_Niro.jpg",
  file_url: "https://upload.wikimedia.org/x.jpg",
  licence: "CC-BY-SA-4.0",
  author: "A. Person",
  credit: "A. Person, CC BY-SA 4.0, via Wikimedia Commons",
  retrieved_at: "2026-11-17",
} as GenerationImage;
const all = () => true;

describe("generationPhoto", () => {
  it("gives the smallest width as src and every width in srcset, with the credit", () => {
    const p = generationPhoto({ image }, "/rel/4/images", all);
    expect(p).toEqual({
      src: "/photos/kia-niro-ev-de-9ad70528-400.webp",
      srcSet: "/photos/kia-niro-ev-de-9ad70528-400.webp 400w, /photos/kia-niro-ev-de-9ad70528-800.webp 800w",
      credit: image.credit,
      author: "A. Person",
      licence: "CC-BY-SA-4.0",
      pageUrl: image.page_url,
    });
  });

  it("shows nothing when one width is missing on disk (a release fetched without its bundle)", () => {
    const seen: string[] = [];
    const p = generationPhoto({ image }, "/rel/4/images", (f) => {
      seen.push(f);
      return !f.endsWith("-800.webp");
    });
    expect(p).toBeNull();
    expect(seen).toContain("/rel/4/images/kia-niro-ev-de-9ad70528-800.webp");
  });

  it("shows nothing without an image, without a release, or for a path outside images/", () => {
    expect(generationPhoto({}, "/rel/4/images", all)).toBeNull();
    expect(generationPhoto({ image }, null, all)).toBeNull();
    const odd = { ...image, files: [{ ...image.files[0]!, path: "../secrets/kia-niro-ev-de-9ad70528-800.webp" }] } as GenerationImage;
    expect(generationPhoto({ image: odd }, "/rel/4/images", all)).toBeNull();
  });

  it("maps generations with photos by id", () => {
    const gens = [{ id: "kia-niro-ev-de", image }, { id: "no-photo" }] as unknown as Parameters<typeof generationPhotos>[0];
    expect(Object.keys(generationPhotos(gens, null))).toEqual([]);
  });
});

describe("PHOTO_FILE_RE", () => {
  it("accepts release photo names only", () => {
    expect(PHOTO_FILE_RE.test("audi-a2-e-tron-gen1-9ad70528-1600.webp")).toBe(true);
    for (const bad of ["../x-9ad70528-400.webp", "x-9ad70528-400.png", "X-9ad70528-400.webp", "x-zzzzzzzz-400.webp", ".hidden-9ad70528-400.webp"]) {
      expect(PHOTO_FILE_RE.test(bad), bad).toBe(false);
    }
  });
});
