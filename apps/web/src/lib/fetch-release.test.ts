import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fetchRelease, parseTar, unpackBundle, type BundleEntry } from "../../scripts/fetch-release.mjs";

const sha256 = (buf: Uint8Array) => createHash("sha256").update(buf).digest("hex");

/** Build a deterministic USTAR tar buffer in memory (fixture helper; zero network). */
function makeTar(entries: { name: string; data: Uint8Array; typeflag?: number }[]): Buffer {
  const chunks: Buffer[] = [];
  for (const e of entries) {
    const header = Buffer.alloc(512, 0);
    const nameBytes = Buffer.from(e.name, "utf8");
    if (nameBytes.length > 100) throw new Error("test tar name > 100");
    nameBytes.copy(header, 0);
    Buffer.from("0000644\0", "ascii").copy(header, 100);
    Buffer.from("0000000\0", "ascii").copy(header, 108);
    Buffer.from("0000000\0", "ascii").copy(header, 116);
    Buffer.from(`${e.data.length.toString(8).padStart(11, "0")}\0`, "ascii").copy(header, 124);
    Buffer.from("00000000000\0", "ascii").copy(header, 136);
    header.fill(0x20, 148, 156);
    header[156] = e.typeflag ?? 0x30; // '0' regular file
    Buffer.from("ustar\0", "ascii").copy(header, 257);
    Buffer.from("00", "ascii").copy(header, 263);
    let sum = 0;
    for (let i = 0; i < 512; i++) sum += header[i]!;
    Buffer.from(`${sum.toString(8).padStart(6, "0")}\0 `, "ascii").copy(header, 148);
    chunks.push(header);
    const dataBuf = Buffer.from(e.data);
    chunks.push(dataBuf);
    const pad = (512 - (dataBuf.length % 512)) % 512;
    if (pad) chunks.push(Buffer.alloc(pad, 0));
  }
  chunks.push(Buffer.alloc(1024, 0));
  return Buffer.concat(chunks);
}

function mockFetch(assets: Record<string, Buffer>, calls: string[]) {
  return async (url: string) => {
    calls.push(url);
    const name = decodeURIComponent(url.split("/").pop() ?? "");
    const buf = assets[name];
    if (!buf) return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer,
    };
  };
}

describe("scripts/fetch-release.mjs (Decision 086 photo bundle + releases 1–3)", () => {
  it("parses USTAR tar buffers and rejects bad checksums", () => {
    const content = Buffer.from("RIFFfakewebp", "utf8");
    const tar = makeTar([{ name: "images/car-400.webp", data: content }]);
    const parsed = parseTar(tar);
    expect(parsed).toHaveLength(1);
    expect(parsed[0]!.name).toBe("images/car-400.webp");
    expect(Buffer.from(parsed[0]!.data).equals(content)).toBe(true);

    const corrupt = Buffer.from(tar);
    corrupt[0] = 0x58; // break header checksum
    expect(() => parseTar(corrupt)).toThrow(/checksum/i);
  });

  it("downloads and unpacks images.tar on a bundled release, checks every file sha256, and re-unpacks locally on missing/corrupt files", async () => {
    const dir = mkdtempSync(path.join(tmpdir(), "ev-fetch-r4-"));
    const rdir = path.join(dir, "4");
    mkdirSync(rdir, { recursive: true });
    writeFileSync(path.join(dir, "latest"), "4\n");

    const catBuf = Buffer.from('{"release":4,"rows":[]}\n', "utf8");
    const img1 = Buffer.from("webp-photo-one-400", "utf8");
    const img2 = Buffer.from("webp-photo-two-800", "utf8");
    const tarBuf = makeTar([
      { name: "images/a-400.webp", data: img1 },
      { name: "images/b-800.webp", data: img2 },
    ]);

    const manifest = {
      schema: "ev-release-manifest/1",
      release: 4,
      storage: { download_url: "https://example.test/releases/download/data-v4/{asset}" },
      files: [
        { path: "catalogue.json", asset: "catalogue.json", bytes: catBuf.length, sha256: sha256(catBuf), in_git: false },
        {
          path: "images.tar",
          asset: "images.tar",
          bytes: tarBuf.length,
          sha256: sha256(tarBuf),
          in_git: false,
          bundle: {
            folder: "images/",
            files: [
              { path: "images/a-400.webp", bytes: img1.length, sha256: sha256(img1) },
              { path: "images/b-800.webp", bytes: img2.length, sha256: sha256(img2) },
            ],
          },
        },
      ],
    };
    writeFileSync(path.join(rdir, "manifest.json"), JSON.stringify(manifest));

    const calls: string[] = [];
    const fetchImpl = mockFetch({ "catalogue.json": catBuf, "images.tar": tarBuf }, calls);
    const logs: string[] = [];
    const warns: string[] = [];

    const first = await fetchRelease({
      dir,
      mode: "auto",
      fetchImpl,
      log: (m) => logs.push(String(m)),
      warn: (m) => warns.push(String(m)),
    });
    expect(first).toEqual({ status: "fetched", downloaded: 2, unpacked: 2 });
    expect(calls).toHaveLength(2);
    expect(readFileSync(path.join(rdir, "images/a-400.webp")).equals(img1)).toBe(true);
    expect(readFileSync(path.join(rdir, "images/b-800.webp")).equals(img2)).toBe(true);

    // Second run: everything present → no download, no unpack.
    calls.length = 0;
    const second = await fetchRelease({ dir, mode: "auto", fetchImpl, log: () => {}, warn: () => {} });
    expect(second).toEqual({ status: "ready", downloaded: 0, unpacked: 0 });
    expect(calls).toHaveLength(0);

    // Delete one photo: re-unpacks from kept images.tar without re-downloading.
    rmSync(path.join(rdir, "images/a-400.webp"));
    const repair = await fetchRelease({ dir, mode: "auto", fetchImpl, log: () => {}, warn: () => {} });
    expect(repair).toEqual({ status: "fetched", downloaded: 0, unpacked: 2 });
    expect(calls).toHaveLength(0);
    expect(readFileSync(path.join(rdir, "images/a-400.webp")).equals(img1)).toBe(true);

    // Corrupt one photo on disk: manifest mode catches it and re-unpacks cleanly.
    writeFileSync(path.join(rdir, "images/b-800.webp"), Buffer.from("webp-photo-BAD-800", "utf8"));
    const manifestRepair = await fetchRelease({ dir, mode: "manifest", fetchImpl, log: () => {}, warn: () => {} });
    expect(manifestRepair).toEqual({ status: "fetched", downloaded: 0, unpacked: 2 });
    expect(calls).toHaveLength(0);
    expect(readFileSync(path.join(rdir, "images/b-800.webp")).equals(img2)).toBe(true);
  });

  it("rejects mismatched member sha256, unexpected members, symlinks, and missing members inside images.tar", () => {
    const rdir = mkdtempSync(path.join(tmpdir(), "ev-bundle-bad-"));
    const good = Buffer.from("good-photo", "utf8");
    const tampered = Buffer.from("evil-photo", "utf8");

    // 1. Member sha256 mismatch
    const badMemberTar = makeTar([{ name: "images/a.webp", data: tampered }]);
    writeFileSync(path.join(rdir, "images.tar"), badMemberTar);
    const badHashEntry: BundleEntry = {
      path: "images.tar",
      bytes: badMemberTar.length,
      sha256: sha256(badMemberTar),
      bundle: {
        folder: "images/",
        files: [{ path: "images/a.webp", bytes: good.length, sha256: sha256(good) }],
      },
    };
    expect(() => unpackBundle(rdir, badHashEntry)).toThrow(/does not match the manifest/);
    expect(existsSync(path.join(rdir, "images/a.webp"))).toBe(false);

    // 2. Unexpected member / path traversal
    const extraTar = makeTar([
      { name: "images/a.webp", data: good },
      { name: "../escape.webp", data: good },
    ]);
    writeFileSync(path.join(rdir, "images.tar"), extraTar);
    expect(() =>
      unpackBundle(rdir, {
        path: "images.tar",
        bytes: extraTar.length,
        sha256: sha256(extraTar),
        bundle: { folder: "images/", files: [{ path: "images/a.webp", bytes: good.length, sha256: sha256(good) }] },
      }),
    ).toThrow(/unexpected member/);

    // 3. Symlink member rejected
    const symTar = makeTar([{ name: "images/a.webp", data: Buffer.alloc(0), typeflag: 0x32 }]);
    writeFileSync(path.join(rdir, "images.tar"), symTar);
    expect(() =>
      unpackBundle(rdir, {
        path: "images.tar",
        bytes: symTar.length,
        sha256: sha256(symTar),
        bundle: { folder: "images/", files: [{ path: "images/a.webp", bytes: 0, sha256: sha256(Buffer.alloc(0)) }] },
      }),
    ).toThrow(/unexpected member/);

    // 4. Missing listed member rejected
    const partialTar = makeTar([{ name: "images/a.webp", data: good }]);
    writeFileSync(path.join(rdir, "images.tar"), partialTar);
    expect(() =>
      unpackBundle(rdir, {
        path: "images.tar",
        bytes: partialTar.length,
        sha256: sha256(partialTar),
        bundle: {
          folder: "images/",
          files: [
            { path: "images/a.webp", bytes: good.length, sha256: sha256(good) },
            { path: "images/missing.webp", bytes: good.length, sha256: sha256(good) },
          ],
        },
      }),
    ).toThrow(/members missing: images\/missing\.webp/);
  });

  it("keeps releases 1–3 without a photo bundle working cleanly", async () => {
    const dir = mkdtempSync(path.join(tmpdir(), "ev-fetch-r3-"));
    const rdir = path.join(dir, "3");
    mkdirSync(rdir, { recursive: true });
    writeFileSync(path.join(dir, "latest"), "3\n");

    const catBuf = Buffer.from('{"release":3,"rows":[]}\n', "utf8");
    const imgBuf = Buffer.from("separate-photo-r3", "utf8");
    const manifest = {
      schema: "ev-release-manifest/1",
      release: 3,
      storage: { download_url: "https://example.test/releases/download/data-v3/{asset}" },
      files: [
        { path: "catalogue.json", asset: "catalogue.json", bytes: catBuf.length, sha256: sha256(catBuf), in_git: false },
        { path: "images/old.webp", asset: "images.old.webp", bytes: imgBuf.length, sha256: sha256(imgBuf), in_git: false },
      ],
    };
    writeFileSync(path.join(rdir, "manifest.json"), JSON.stringify(manifest));

    const calls: string[] = [];
    const fetchImpl = mockFetch({ "catalogue.json": catBuf, "images.old.webp": imgBuf }, calls);
    const res = await fetchRelease({ dir, mode: "auto", fetchImpl, log: () => {}, warn: () => {} });
    expect(res).toEqual({ status: "fetched", downloaded: 1, unpacked: 0 });
    expect(calls).toEqual(["https://example.test/releases/download/data-v3/catalogue.json"]);
    expect(existsSync(path.join(rdir, "catalogue.json"))).toBe(true);
    expect(existsSync(path.join(rdir, "images/old.webp"))).toBe(false);
  });
});
