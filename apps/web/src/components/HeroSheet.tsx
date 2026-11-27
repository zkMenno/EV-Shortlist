"use client";
// The hero results' answers sidebar (T-132 part 2) that becomes a bottom sheet on phones (T-146).
// One DOM for both, like the catalogue filters (T-130): at 640 px and up it is the plain sidebar
// (desktop sticky from lg); below 640 px it is hidden until "Answers & refine" opens it. Open, it
// keeps focus inside, and closes with the close button, Escape, Back (history entry pushed by the
// hero), a swipe down on its top bar, a tap outside, or when the screen gets wider.
import { useEffect, useRef, type ReactNode } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
/** Phone layout ends here (Tailwind `sm`). */
export const SHEET_MAX = "(max-width: 39.98rem)";
/** Swipe at least this far down (px) to close. */
const SWIPE_CLOSE = 80;

export function HeroSheet({
  id,
  open,
  onClose,
  label,
  title,
  closeLabel,
  doneLabel,
  children,
}: {
  id: string;
  open: boolean;
  onClose: () => void;
  /** aria-label of the sidebar landmark. */
  label: string;
  /** Sheet heading (phones only). */
  title: string;
  closeLabel: string;
  /** Bottom button: back to the results. */
  doneLabel: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Keep the latest callback without re-running the effect on every render (WS2 gotcha, review #126).
  const closeFn = useRef(onClose);
  useEffect(() => {
    closeFn.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      // An open ⓘ tip (use-popover.ts) takes its Escape first and marks it handled; the next Escape closes the sheet.
      if (e.key === "Escape" && !e.defaultPrevented) {
        closeFn.current();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const items = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      const inside = panelRef.current.contains(document.activeElement);
      if (e.shiftKey && (document.activeElement === first || !inside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const phone = window.matchMedia?.(SHEET_MAX);
    const onWide = () => {
      if (phone && !phone.matches) closeFn.current();
    };
    phone?.addEventListener?.("change", onWide);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      phone?.removeEventListener?.("change", onWide);
      document.body.style.overflow = overflow;
      if (panel) panel.style.transform = "";
      opener?.focus?.();
    };
  }, [open]);

  // Swipe down on the top bar: the sheet follows the finger; far enough = close, else it snaps back.
  const startY = useRef<number | null>(null);
  const dy = useRef(0);
  const onTouchStart = (e: React.TouchEvent) => {
    startY.current = e.touches[0]?.clientY ?? null;
    dy.current = 0;
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (startY.current === null || !panelRef.current) return;
    dy.current = Math.max(0, (e.touches[0]?.clientY ?? startY.current) - startY.current);
    panelRef.current.style.transform = dy.current ? `translateY(${dy.current}px)` : "";
  };
  const onTouchEnd = () => {
    if (startY.current === null) return;
    startY.current = null;
    if (dy.current > SWIPE_CLOSE) closeFn.current();
    else if (panelRef.current) panelRef.current.style.transform = "";
  };

  return (
    <aside
      id={id}
      aria-label={label}
      className={`${open ? "max-sm:fixed max-sm:inset-0 max-sm:z-50 max-sm:flex max-sm:flex-col max-sm:justify-end max-sm:bg-[color-mix(in_srgb,var(--ink)_45%,transparent)]" : "max-sm:hidden"} lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto`}
      onClick={(e) => {
        if (open && e.target === e.currentTarget) closeFn.current();
      }}
      data-testid="hero-side"
      data-sheet={open ? "open" : undefined}
    >
      <div
        ref={panelRef}
        role={open ? "dialog" : undefined}
        aria-modal={open || undefined}
        aria-labelledby={open ? `${id}-title` : undefined}
        className="max-sm:flex max-sm:max-h-[88vh] max-sm:flex-col max-sm:rounded-t-2xl max-sm:bg-[var(--paper)] max-sm:shadow-[var(--shadow-lift)]"
        data-testid="hero-sheet"
      >
        <div className="flex items-center justify-between gap-2 px-4 pb-1 pt-2 sm:hidden" onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd} onTouchCancel={onTouchEnd} data-testid="hero-sheet-bar">
          <div className="min-w-0 flex-1">
            <span aria-hidden="true" className="mx-auto mb-2 block h-1.5 w-10 rounded-full bg-[var(--line-strong)]" />
            <h2 id={`${id}-title`} className="text-lg font-bold">
              {title}
            </h2>
          </div>
          <button ref={closeRef} type="button" onClick={() => closeFn.current()} className="grid h-11 w-11 place-items-center rounded-full hover:bg-[var(--surface-sunk)]" aria-label={closeLabel} data-testid="hero-sheet-close">
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current" strokeWidth="2">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="max-sm:overflow-y-auto max-sm:px-4 max-sm:pb-4">{children}</div>
        <div className="border-t border-[var(--line)] px-4 py-3 sm:hidden">
          <button type="button" onClick={() => closeFn.current()} className="evs-cta w-full justify-center" data-testid="hero-sheet-done">
            {doneLabel}
          </button>
        </div>
      </div>
    </aside>
  );
}
