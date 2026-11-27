// Car photos with their credit (Decision 081, 083; T-146 row thumbnails). Photos come from the
// release and are served from our own origin (/photos/…, src/lib/photos.ts); the credit is always
// one tap away: an ⓘ next to the photo names author, licence and the file page.
import { InfoTip, type TermText } from "./Term";

/** The minimum a client component needs for one photo (keeps the page payload small). */
export interface PhotoRef {
  src: string;
  credit: string;
  pageUrl: string;
}

export interface PhotoText {
  /** "Photo credit" (the ⓘ's label). */
  credit: string;
  /** "Photo page" (link to the file page / press page). */
  page: string;
  term: TermText;
}

/** The credit ⓘ: author + licence as the release gives them, and a link to where the photo lives. */
export function PhotoCredit({ photo, text }: { photo: PhotoRef; text: PhotoText }) {
  return (
    <InfoTip label={text.credit} text={text.term}>
      <span className="block" data-testid="photo-credit">
        {photo.credit}
      </span>
      <a href={photo.pageUrl} target="_blank" rel="noopener nofollow" className="mt-1 block text-blue-800 underline underline-offset-2">
        {text.page}
      </a>
    </InfoTip>
  );
}

/**
 * A small photo for a list row: fixed 3:2 box (rows never jump while it loads), lazy, cropped to fill.
 * `alt` names the car ("Kia Niro EV (2018–2022)"); the credit ⓘ sits beside it.
 */
export function CarThumb({ photo, alt, text }: { photo: PhotoRef; alt: string; text: PhotoText }) {
  return (
    <span className="evs-thumb" data-testid="car-thumb">
      {/* A plain <img>: the release already ships sized WebP files (400/800/1600 px), served as-is from
          our origin; next/image would re-encode them on our small shared server. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={photo.src} alt={alt} width={72} height={48} loading="lazy" decoding="async" className="evs-thumb__img" />
      <span className="evs-thumb__credit">
        <PhotoCredit photo={photo} text={text} />
      </span>
    </span>
  );
}
