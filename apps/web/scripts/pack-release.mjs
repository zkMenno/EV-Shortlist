#!/usr/bin/env node
// Copy the latest release's run-time files into the web image (T-168, Decisions 008, 035, 086).
// No dependencies, no network: it only checks and copies what fetch-release.mjs already put on disk.
//
// Before T-168 the Dockerfile copied only catalogue.json, so staging had no shortlist scores, used
// prices, charging stats, manifest (open-data page) or photos, and the hero said "ranking not
// available" (28 Nov 2026). The file list now comes from one place: DEFAULT_FILES in
// fetch-release.mjs, plus manifest.json, README.md and the unpacked photo bundle (`images/`).
//
// Every file the manifest lists must be on disk with the manifest's size and sha256, or the image
// build fails. Files the release doesn't have (older releases) only warn, as fetch-release does.
//
//   node pack-release.mjs <releases dir> <out dir>
//   → <out>/latest and <out>/<n>/{manifest.json, README.md, catalogue.json, …, images/…}

/* global process, console */
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { DEFAULT_FILES, safePath } from "./fetch-release.mjs";

const PHOTO_FOLDER = "images/";

function sha256(file) {
  return createHash("sha256").update(readFileSync(file)).digest("hex");
}

function checkFile(file, entry) {
  if (!existsSync(file)) return `${entry.path} is missing`;
  const bytes = statSync(file).size;
  if (bytes !== entry.bytes) return `${entry.path} is ${bytes} bytes, manifest says ${entry.bytes}`;
  if (sha256(file) !== entry.sha256) return `${entry.path} sha256 does not match the manifest`;
  return null;
}

/**
 * The release-relative files the web app reads at run time for one release, each with the
 * manifest entry to check it against (null = no checksum, e.g. manifest.json itself).
 * Pure: takes the parsed manifest.
 */
export function runtimeFiles(manifest, wanted = DEFAULT_FILES) {
  const byPath = new Map(manifest.files.map((e) => [e.path, e]));
  const out = [{ path: "manifest.json", entry: null, required: true }];
  const readme = byPath.get("README.md");
  if (readme) out.push({ path: "README.md", entry: readme, required: true });
  const absent = [];
  for (const f of wanted) {
    const e = byPath.get(f);
    if (e) out.push({ path: safePath(f), entry: e, required: true });
    else absent.push(f);
  }
  for (const e of manifest.files) {
    if (e.bundle?.folder !== PHOTO_FOLDER) continue;
    for (const m of e.bundle.files) out.push({ path: safePath(m.path), entry: m, required: true });
  }
  return { files: out, absent };
}

export function packRelease({ src, out, log = console.log, warn = console.warn }) {
  const n = readFileSync(path.join(src, "latest"), "utf8").trim();
  if (!/^\d+$/.test(n)) throw new Error(`data/releases/latest must hold a release number, got '${n}'`);
  const rdir = path.join(src, n);
  const odir = path.join(out, n);
  const mfile = path.join(rdir, "manifest.json");
  let list;
  if (existsSync(mfile)) {
    const manifest = JSON.parse(readFileSync(mfile, "utf8"));
    if (String(manifest.release) !== n) throw new Error(`manifest is for release ${manifest.release}, expected ${n}`);
    const { files, absent } = runtimeFiles(manifest);
    if (absent.length) warn(`pack-release: release ${n} has no ${absent.join(", ")} (not in its manifest)`);
    list = files;
  } else {
    // A release from before T-064 (fully in git, no manifest): ship what is there.
    list = ["catalogue.json", "README.md", ...DEFAULT_FILES]
      .filter((p, i, a) => a.indexOf(p) === i)
      .map((p) => ({ path: p, entry: null, required: p === "catalogue.json" }));
  }

  const problems = [];
  let copied = 0;
  let photos = 0;
  for (const f of list) {
    const from = path.join(rdir, f.path);
    if (!existsSync(from)) {
      if (f.required) problems.push(`${f.path} is missing`);
      continue;
    }
    if (f.entry) {
      const bad = checkFile(from, f.entry);
      if (bad) {
        problems.push(bad);
        continue;
      }
    }
    const to = path.join(odir, f.path);
    mkdirSync(path.dirname(to), { recursive: true });
    copyFileSync(from, to);
    copied++;
    if (f.path.startsWith(PHOTO_FOLDER)) photos++;
  }
  if (problems.length) {
    const more = problems.length > 8 ? ` (+${problems.length - 8} more)` : "";
    throw new Error(
      `release ${n} is incomplete for the web image: ${problems.slice(0, 8).join("; ")}${more}. ` +
        "Run apps/web/scripts/fetch-release.mjs without CATALOGUE_FILES first.",
    );
  }
  writeFileSync(path.join(out, "latest"), `${n}\n`);
  log(`pack-release: release ${n}: ${copied} file(s) checked and copied (${photos} photo file(s))`);
  return { release: Number(n), copied, photos };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [src, out] = process.argv.slice(2);
  if (!src || !out) {
    console.error("usage: node pack-release.mjs <releases dir> <out dir>");
    process.exit(2);
  }
  try {
    packRelease({ src, out });
  } catch (e) {
    console.error(`pack-release: ${e?.message ?? String(e)}`);
    process.exit(1);
  }
}
