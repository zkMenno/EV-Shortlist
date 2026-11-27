#!/usr/bin/env node
// Fetch the current catalogue release by its manifest (T-064, Decision 035; T-157, Decision 086).
// No dependencies: Node 22 fetch + crypto.
//
// Release files live in GitHub Release assets (tag data-v<n>). Git keeps
// data/releases/<n>/manifest.json with each file's size and sha256. This script reads
// data/releases/latest, then downloads every file the manifest lists that is missing (or, with
// CATALOGUE_SOURCE=manifest, also re-checks files already on disk), verifies size + sha256,
// and moves it into place atomically. When the manifest includes a photo bundle (`images.tar`,
// Decision 086), it downloads and verifies the tar, unpacks only the listed members into `images/`,
// and verifies each unpacked file's bytes + sha256. Releases 1–3 without a bundle still work.
// A mismatch fails the build; nothing unverified is kept.
//
//   CATALOGUE_SOURCE=auto      (default) fetch only when a listed file is missing
//   CATALOGUE_SOURCE=manifest  verify every file, re-download any that don't match
//   CATALOGUE_SOURCE=local     do nothing (CATALOGUE_DIR / dev fixture, offline work)
//   CATALOGUE_DIR              releases folder (default ../../data/releases), same as the loader
//   CATALOGUE_RELEASE          fetch this release number instead of `latest` (rollback preview)
//   CATALOGUE_FILES            comma-separated paths the web needs (a trailing / = a folder);
//                              default "catalogue.json,charging_stats.json,used_prices.json,shortlist_scores.json"
//                              (+ any photo bundle `images.tar` when the release manifest has one).
//   FETCH_RELEASE_ALLOW_HTTP_LOCAL=1  allow an http://127.0.0.1 download_url (local manual tests only)

/* global process, console, Buffer, fetch, setTimeout */
import { createHash } from "node:crypto";
import { createReadStream, existsSync, mkdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const DEFAULT_FILES = ["catalogue.json", "charging_stats.json", "used_prices.json", "shortlist_scores.json"];
const PARALLEL = 6;
const RETRIES = 3;
const TAR_BLOCK = 512;
const SHA256_RE = /^[0-9a-f]{64}$/;

function sha256File(file) {
  return new Promise((resolve, reject) => {
    const h = createHash("sha256");
    createReadStream(file).on("data", (c) => h.update(c)).on("end", () => resolve(h.digest("hex"))).on("error", reject);
  });
}

function sha256Buf(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

async function matches(file, entry) {
  if (!existsSync(file)) return false;
  if (statSync(file).size !== entry.bytes) return false;
  return (await sha256File(file)) === entry.sha256;
}

export function safePath(rel) {
  if (typeof rel !== "string" || !rel || rel.startsWith("/") || rel.includes("\\") || rel.split("/").includes("..")) {
    throw new Error(`unsafe path in manifest: ${rel}`);
  }
  return rel;
}

function readTarString(buf, start, len) {
  const end = buf.indexOf(0, start);
  const stop = end >= 0 && end < start + len ? end : start + len;
  return buf.subarray(start, stop).toString("utf8");
}

function readTarOctal(buf, start, len) {
  // Support POSIX octal ASCII (and GNU base-256 for completeness).
  if ((buf[start] & 0x80) !== 0) {
    let val = 0;
    for (let i = 1; i < len; i++) val = val * 256 + buf[start + i];
    return val;
  }
  const s = readTarString(buf, start, len).trim();
  if (!s) return 0;
  if (!/^[0-7]+$/.test(s)) throw new Error(`invalid octal field in tar header: ${JSON.stringify(s)}`);
  return parseInt(s, 8);
}

function isZeroBlock(buf, offset) {
  for (let i = 0; i < TAR_BLOCK; i++) if (buf[offset + i] !== 0) return false;
  return true;
}

/**
 * Parse an uncompressed USTAR/POSIX tar buffer into `{ name, typeflag, data }` entries.
 * Verifies every 512-byte header checksum and rejects truncated archives.
 */
export function parseTar(buf) {
  const out = [];
  let offset = 0;
  while (offset < buf.length) {
    if (offset + TAR_BLOCK > buf.length) throw new Error("truncated tar header");
    if (isZeroBlock(buf, offset)) {
      // Standard tar terminator: trailing zero blocks.
      offset += TAR_BLOCK;
      continue;
    }
    const header = buf.subarray(offset, offset + TAR_BLOCK);
    const storedSum = readTarOctal(header, 148, 8);
    let calcSum = 0;
    for (let i = 0; i < TAR_BLOCK; i++) calcSum += i >= 148 && i < 156 ? 0x20 : header[i];
    if (calcSum !== storedSum) throw new Error(`tar header checksum mismatch at offset ${offset}`);

    const baseName = readTarString(header, 0, 100);
    const magic = header.subarray(257, 262).toString("ascii");
    const prefix = magic === "ustar" ? readTarString(header, 345, 155) : "";
    const name = prefix ? `${prefix}/${baseName}` : baseName;
    const size = readTarOctal(header, 124, 12);
    const typeflag = header[156];
    const dataStart = offset + TAR_BLOCK;
    const dataEnd = dataStart + size;
    if (dataEnd > buf.length) throw new Error(`truncated tar member: ${name}`);
    out.push({ name, typeflag, data: buf.subarray(dataStart, dataEnd) });
    offset = dataStart + Math.ceil(size / TAR_BLOCK) * TAR_BLOCK;
  }
  return out;
}

/**
 * Unpack a verified bundle (`images.tar`) into `rdir`. Only regular files listed in
 * `entry.bundle.files` under `entry.bundle.folder` are accepted; each file's bytes and sha256
 * are verified against the manifest before moving atomically into place.
 */
export function unpackBundle(rdir, entry) {
  const bundle = entry?.bundle;
  if (!bundle || typeof bundle.folder !== "string" || !bundle.folder.endsWith("/") || !Array.isArray(bundle.files)) {
    throw new Error(`${entry?.path ?? "bundle"}: malformed bundle metadata in manifest`);
  }
  const folder = safePath(bundle.folder);
  const want = new Map();
  for (const m of bundle.files) {
    const p = safePath(m?.path);
    if (!p.startsWith(folder)) throw new Error(`${entry.path}: member ${p} is outside ${folder}`);
    if (typeof m.bytes !== "number" || !Number.isInteger(m.bytes) || m.bytes < 0 || !SHA256_RE.test(m.sha256 ?? "")) {
      throw new Error(`${entry.path}: invalid checksum metadata for ${p}`);
    }
    if (want.has(p)) throw new Error(`${entry.path}: duplicate member ${p} in manifest`);
    want.set(p, m);
  }

  const tarPath = path.join(rdir, safePath(entry.path));
  const tarBuf = readFileSync(tarPath);
  if (tarBuf.length !== entry.bytes || sha256Buf(tarBuf) !== entry.sha256) {
    throw new Error(`${entry.path}: archive does not match manifest checksum`);
  }

  const members = parseTar(tarBuf);
  const seen = new Set();
  for (const { name, typeflag, data } of members) {
    const isRegular = typeflag === 0x30 || typeflag === 0x00;
    if (!isRegular || !want.has(name) || !name.startsWith(folder) || seen.has(name)) {
      throw new Error(`${entry.path}: unexpected member ${JSON.stringify(name)}`);
    }
    const m = want.get(name);
    if (data.length !== m.bytes || sha256Buf(data) !== m.sha256) {
      throw new Error(`${name}: bundled file does not match the manifest`);
    }
    const dest = path.join(rdir, name);
    mkdirSync(path.dirname(dest), { recursive: true });
    const tmp = path.join(path.dirname(dest), `.${path.basename(dest)}.part-${process.pid}`);
    try {
      writeFileSync(tmp, data);
      renameSync(tmp, dest);
    } catch (err) {
      rmSync(tmp, { force: true });
      throw err;
    }
    seen.add(name);
  }
  const missing = [...want.keys()].filter((k) => !seen.has(k)).sort();
  if (missing.length) {
    throw new Error(`${entry.path}: members missing: ${missing.slice(0, 5).join(", ")}`);
  }
  return seen.size;
}

async function bundleMembersReady(rdir, entry, verifyHash) {
  for (const m of entry.bundle.files) {
    const dest = path.join(rdir, safePath(m.path));
    if (verifyHash) {
      if (!(await matches(dest, m))) return false;
    } else {
      if (!existsSync(dest) || statSync(dest).size !== m.bytes) return false;
    }
  }
  return true;
}

function entryWanted(entry, files, includePhotoBundle) {
  if (files.some((f) => (f.endsWith("/") ? entry.path.startsWith(f) : entry.path === f))) return true;
  const folder = entry.bundle?.folder;
  if (typeof folder !== "string" || !folder.endsWith("/")) return false;
  if (includePhotoBundle && folder === "images/") return true;
  return files.some((f) => f === folder || f.startsWith(folder));
}

function manifestHasTarget(manifestFiles, target) {
  return manifestFiles.some((e) => {
    if (target.endsWith("/") ? e.path.startsWith(target) : e.path === target) return true;
    const folder = e.bundle?.folder;
    return typeof folder === "string" && (target === folder || target.startsWith(folder));
  });
}

async function download(url, dest, entry, fetchImpl) {
  let lastErr;
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    const tmp = path.join(path.dirname(dest), `.${path.basename(dest)}.part-${process.pid}`);
    try {
      const res = await fetchImpl(url, { redirect: "follow" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length !== entry.bytes) throw new Error(`${buf.length} bytes, manifest says ${entry.bytes}`);
      if (sha256Buf(buf) !== entry.sha256) throw new Error("sha256 mismatch");
      writeFileSync(tmp, buf);
      renameSync(tmp, dest);
      return;
    } catch (e) {
      lastErr = e;
      rmSync(tmp, { force: true });
      if (attempt < RETRIES) await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }
  throw new Error(`${entry.path}: ${lastErr?.message ?? lastErr} (${url})`);
}

export async function fetchRelease(opts = {}) {
  const env = opts.env ?? process.env;
  const mode = opts.mode ?? env.CATALOGUE_SOURCE ?? "auto";
  const dir = opts.dir ?? env.CATALOGUE_DIR ?? path.resolve(process.cwd(), "../../data/releases");
  const customFiles = opts.files ?? (env.CATALOGUE_FILES ? env.CATALOGUE_FILES.split(",").map((x) => x.trim()).filter(Boolean) : null);
  const files = customFiles ?? DEFAULT_FILES;
  const includePhotoBundle = opts.includePhotoBundle ?? customFiles === null;
  const fetchImpl = opts.fetchImpl ?? fetch;
  const log = opts.log ?? console.log;
  const warn = opts.warn ?? console.warn;

  if (mode === "local") return { status: "local", downloaded: 0, unpacked: 0 };
  if (mode !== "auto" && mode !== "manifest") throw new Error(`unknown CATALOGUE_SOURCE=${mode}`);
  const latestFile = path.join(dir, "latest");
  const n = (opts.release ?? env.CATALOGUE_RELEASE ?? (existsSync(latestFile) ? readFileSync(latestFile, "utf8") : "")).trim();
  if (!n) return { status: "no-release", downloaded: 0, unpacked: 0 }; // no release yet: the loader uses the dev fixture
  if (!/^\d+$/.test(n)) throw new Error(`release must be a number, got "${n}"`);
  const rdir = path.join(dir, n);
  const mfile = path.join(rdir, "manifest.json");
  if (!existsSync(mfile)) {
    if (mode === "manifest") throw new Error(`${mfile} missing`);
    return { status: "no-manifest", downloaded: 0, unpacked: 0 }; // a release from before T-064, fully in git
  }
  const m = JSON.parse(readFileSync(mfile, "utf8"));
  if (m.schema !== "ev-release-manifest/1") throw new Error(`unknown manifest schema ${m.schema}`);
  if (String(m.release) !== n) throw new Error(`manifest is for release ${m.release}, expected ${n}`);
  const base = m.storage?.download_url;
  const allowLocal = env.FETCH_RELEASE_ALLOW_HTTP_LOCAL === "1";
  if (typeof base !== "string" || !(base.startsWith("https://") || (allowLocal && base.startsWith("http://127.0.0.1:"))) || !base.includes("{asset}")) {
    throw new Error("manifest has no https download_url");
  }

  const todo = [];
  const unpackOnly = [];
  const bundleLabels = [];
  for (const e of m.files) {
    if (!entryWanted(e, files, includePhotoBundle)) continue;
    const dest = path.join(rdir, safePath(e.path));
    if (e.bundle) {
      bundleLabels.push(e.path);
      const membersOk = await bundleMembersReady(rdir, e, mode === "manifest");
      if (membersOk && (mode === "auto" || (await matches(dest, e)))) continue;
      if (await matches(dest, e)) {
        unpackOnly.push(e);
        continue;
      }
      if (e.in_git) throw new Error(`${e.path} is kept in git but doesn't match the manifest (edited by hand?)`);
      todo.push({ e, dest, url: base.replace("{asset}", encodeURIComponent(e.asset)) });
      continue;
    }
    if (mode === "auto" && existsSync(dest)) continue;
    if (await matches(dest, e)) continue;
    if (e.in_git) throw new Error(`${e.path} is kept in git but doesn't match the manifest (edited by hand?)`);
    todo.push({ e, dest, url: base.replace("{asset}", encodeURIComponent(e.asset)) });
  }

  // Name what the release has, and warn about wanted files it lacks (QA A-35: release 1 has no
  // used_prices.json, but the log said "ready (… used_prices.json)", which hid a stale release).
  const listed = files.filter((f) => manifestHasTarget(m.files, f));
  const absent = files.filter((f) => !listed.includes(f));
  if (absent.length) warn(`fetch-release: release ${n} has no ${absent.join(", ")} (not in its manifest); pages that need it show "not known yet"`);

  const readyList = [...new Set([...listed, ...bundleLabels])];
  if (!todo.length && !unpackOnly.length) {
    log(`fetch-release: release ${n} ready (${readyList.join(", ") || "nothing wanted"})`);
    return { status: "ready", downloaded: 0, unpacked: 0 };
  }

  let unpacked = 0;
  if (todo.length) {
    log(`fetch-release: release ${n}: downloading ${todo.length} file(s)`);
    let i = 0;
    async function worker() {
      while (i < todo.length) {
        const job = todo[i++];
        mkdirSync(path.dirname(job.dest), { recursive: true });
        await download(job.url, job.dest, job.e, fetchImpl);
        if (job.e.bundle) unpacked += unpackBundle(rdir, job.e);
      }
    }
    await Promise.all(Array.from({ length: Math.min(PARALLEL, todo.length) }, worker));
  }
  for (const e of unpackOnly) {
    unpacked += unpackBundle(rdir, e);
  }
  const extra = unpacked ? `, unpacked ${unpacked} bundled file(s)` : "";
  log(`fetch-release: release ${n} verified (sha256${extra})`);
  return { status: "fetched", downloaded: todo.length, unpacked };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  fetchRelease().catch((e) => {
    console.error(`fetch-release: ${e?.message ?? String(e)}`);
    process.exit(1);
  });
}
