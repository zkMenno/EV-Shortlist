// T-168: the web image ships every run-time file of the latest release (not only catalogue.json).
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_FILES } from "../../scripts/fetch-release.mjs";
import { packRelease, runtimeFiles } from "../../scripts/pack-release.mjs";

const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");
const dirs: string[] = [];
afterEach(() => {
  for (const d of dirs.splice(0)) rmSync(d, { recursive: true, force: true });
});

/** A release folder on disk with a manifest: files listed + optional photo bundle. */
function makeRelease(opts: { files?: Record<string, string>; photos?: Record<string, string>; skip?: string[]; corrupt?: string[] } = {}) {
  const root = mkdtempSync(path.join(tmpdir(), "pack-release-"));
  dirs.push(root);
  const src = path.join(root, "releases");
  const rdir = path.join(src, "7");
  mkdirSync(path.join(rdir, "images"), { recursive: true });
  writeFileSync(path.join(src, "latest"), "7\n");
  const files = opts.files ?? Object.fromEntries(["README.md", ...DEFAULT_FILES].map((f) => [f, `{"f":"${f}"}`]));
  const photos = opts.photos ?? { "images/a-0123abcd-400.webp": "p400", "images/a-0123abcd-800.webp": "p800" };
  const entries: unknown[] = Object.entries(files).map(([p, body]) => ({ path: p, asset: p, bytes: Buffer.byteLength(body), sha256: sha256(body), in_git: p === "README.md" }));
  if (Object.keys(photos).length) {
    entries.push({
      path: "images.tar",
      asset: "images.tar",
      bytes: 1,
      sha256: "0".repeat(64),
      in_git: false,
      bundle: { folder: "images/", files: Object.entries(photos).map(([p, b]) => ({ path: p, bytes: Buffer.byteLength(b), sha256: sha256(b) })) },
    });
  }
  // Files on disk: the run-time ones, plus noise the image must not carry.
  for (const [p, body] of Object.entries({ ...files, ...photos, "qa.json": "{}", "images.tar": "tar" })) {
    if (opts.skip?.includes(p)) continue;
    writeFileSync(path.join(rdir, p), opts.corrupt?.includes(p) ? `${body}!` : body);
  }
  writeFileSync(path.join(rdir, "manifest.json"), JSON.stringify({ schema: "ev-release-manifest/1", release: 7, files: entries }));
  return { src, out: path.join(root, "out") };
}

const quiet = { log: () => {}, warn: () => {} };

describe("runtimeFiles", () => {
  it("lists manifest.json, README, every DEFAULT_FILES entry and the photo bundle members", () => {
    const manifest = JSON.parse(readFileSync(path.join(makeRelease().src, "7", "manifest.json"), "utf8"));
    const { files, absent } = runtimeFiles(manifest);
    expect(files.map((f) => f.path)).toEqual(["manifest.json", "README.md", ...DEFAULT_FILES, "images/a-0123abcd-400.webp", "images/a-0123abcd-800.webp"]);
    expect(absent).toEqual([]);
  });
});

describe("packRelease", () => {
  it("copies the run-time files and photos, not the tar or QA files", () => {
    const { src, out } = makeRelease();
    const res = packRelease({ src, out, ...quiet });
    expect(res).toEqual({ release: 7, copied: 2 + DEFAULT_FILES.length + 2, photos: 2 });
    expect(readFileSync(path.join(out, "latest"), "utf8")).toBe("7\n");
    for (const f of ["manifest.json", "README.md", "shortlist_scores.json", "used_prices.json", "charging_stats.json", "catalogue.json", "images/a-0123abcd-800.webp"]) {
      expect(existsSync(path.join(out, "7", f)), f).toBe(true);
    }
    expect(existsSync(path.join(out, "7", "images.tar"))).toBe(false);
    expect(existsSync(path.join(out, "7", "qa.json"))).toBe(false);
  });

  it("fails when a listed file is missing (the 28 Nov staging bug: scores not in the image)", () => {
    const { src, out } = makeRelease({ skip: ["shortlist_scores.json"] });
    expect(() => packRelease({ src, out, ...quiet })).toThrow(/shortlist_scores\.json is missing/);
    expect(existsSync(path.join(out, "latest"))).toBe(false);
  });

  it("fails when a photo is missing or a file does not match its sha256", () => {
    const a = makeRelease({ skip: ["images/a-0123abcd-400.webp"] });
    expect(() => packRelease({ ...a, ...quiet })).toThrow(/images\/a-0123abcd-400\.webp is missing/);
    const b = makeRelease({ corrupt: ["used_prices.json"] });
    expect(() => packRelease({ ...b, ...quiet })).toThrow(/used_prices\.json is .*bytes/);
  });

  it("warns, but packs, when an older release has no scores or photos in its manifest", () => {
    const { src, out } = makeRelease({ files: { "catalogue.json": "{}" }, photos: {} });
    const warns: string[] = [];
    const res = packRelease({ src, out, log: () => {}, warn: (m) => warns.push(String(m)) });
    expect(res.photos).toBe(0);
    expect(warns.join()).toMatch(/has no charging_stats\.json, used_prices\.json, shortlist_scores\.json/);
  });
});
