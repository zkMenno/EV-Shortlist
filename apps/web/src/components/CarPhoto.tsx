// Car photos with their credit (Decision 081, 083; T-146 row thumbnails). Photos come from the
// release and are served from our own origin (/photos/…, src/lib/photos.ts); the credit is always
// one tap away: an ⓘ next to the photo names author, licence and the file page.
import { InfoTip, type TermText } from "./Term";

/** The minimum a client component needs for one photo (keeps the page payload small). */
export interface PhotoRef {
  src: string;
  /** Every width ("… 400w, … 800w"); cards and pages use it, row thumbnails don't need it. */
  srcSet?: string;
  credit: string;
  pageUrl: string;
}

export interface PhotoText {
  /** "Photo: {credit}" under a card or page photo (T-135). */
  caption?: string;
  /** "No photo yet" in the placeholder (T-135). */
  none?: string;
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

/**
 * A card or page photo (T-135): fixed box (3:2 on pages, 16:9 on cards) so nothing shifts while it loads, the credit line
 * right under it (author, licence, link to the file page). Without a photo: a neutral placeholder
 * of the same size that says so, so every card keeps the same shape.
 */
export function CarFigure({
  photo,
  alt,
  text,
  sizes,
  eager = false,
  card = false,
  testId = "car-photo",
}: {
  photo: PhotoRef | null | undefined;
  alt: string;
  text: PhotoText;
  /** `sizes` for the srcset, e.g. "(min-width: 64rem) 20rem, 100vw". */
  sizes: string;
  /** The page's main photo (above the fold) loads straight away; cards load lazily. */
  eager?: boolean;
  /** Catalogue cards use a flatter 16:9 box so a phone shows more of the list. */
  card?: boolean;
  testId?: string;
}) {
  const box = `evs-photo${card ? " evs-photo--card" : ""}`;
  if (!photo) {
    return (
      <div className={`${box} evs-photo--none`} data-testid={`${testId}-none`}>
        <svg viewBox="0 0 64 32" aria-hidden="true" className="evs-photo__icon">
          <path d="M6 22h52M10 22l5-9c1-2 3-3 5-3h20c2 0 4 1 5.5 2.5L52 18l5 1c1 0 2 1 2 2v1M16 22a4 4 0 0 0 8 0M40 22a4 4 0 0 0 8 0" />
        </svg>
        <span className="evs-photo__none">{text.none}</span>
      </div>
    );
  }
  return (
    <figure className="evs-photo-fig" data-testid={testId}>
      <div className={box}>
        {/* Plain <img>: the release ships sized WebP files; next/image would re-encode them on our server. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photo.src}
          srcSet={photo.srcSet}
          sizes={photo.srcSet ? sizes : undefined}
          alt={alt}
          width={400}
          height={card ? 225 : 267}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          className="evs-photo__img"
        />
      </div>
      <figcaption className="evs-photo__credit" data-testid="photo-caption">
        <a href={photo.pageUrl} target="_blank" rel="noopener nofollow" className="underline underline-offset-2">
          {(text.caption ?? "{credit}").replace("{credit}", photo.credit)}
        </a>
      </figcaption>
    </figure>
  );
}
