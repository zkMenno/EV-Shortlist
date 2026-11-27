// Generation photos from the current release: /photos/<generation id>-<sha8>-<width>.webp
// (Decision 081, 086; T-146). The file name carries the photo's hash, so a response is cacheable
// forever; a new photo gets a new name. Only names the release folder holds are served.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { PHOTO_FILE_RE, photosDir } from "@/lib/photos";

export const dynamic = "force-dynamic";

const notFound = () => new Response("Not found", { status: 404, headers: { "cache-control": "no-store" } });

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const dir = photosDir();
  if (!dir || !PHOTO_FILE_RE.test(file)) return notFound();
  let body: Buffer;
  try {
    body = await readFile(path.join(dir, file));
  } catch {
    return notFound();
  }
  return new Response(new Uint8Array(body), {
    headers: {
      "content-type": "image/webp",
      "content-length": String(body.length),
      "cache-control": "public, max-age=31536000, immutable",
      "x-content-type-options": "nosniff",
    },
  });
}
