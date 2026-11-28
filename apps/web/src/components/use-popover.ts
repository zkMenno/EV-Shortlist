"use client";
// Shared hover / focus / tap popover behaviour (Num, Term ⓘ, chemistry ⓘ). No library.
// Fixed positioning so table scroll containers never clip it; closes on scroll, Escape,
// blur and outside tap.
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

export function usePopover() {
  const id = useId();
  const btn = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const pinned = useRef(false);

  const place = useCallback(() => {
    const b = btn.current;
    const p = pop.current;
    if (!b || !p) return;
    const r = b.getBoundingClientRect();
    const w = Math.min(304, window.innerWidth - 16);
    p.style.width = `${w}px`;
    p.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - w - 8))}px`;
    const below = r.bottom + 6;
    p.style.top = `${below + p.offsetHeight > window.innerHeight ? Math.max(8, r.top - p.offsetHeight - 6) : below}px`;
  }, []);

  useEffect(() => {
    if (!open) return;
    place();
    const close = () => {
      pinned.current = false;
      setOpen(false);
    };
    const onDown = (e: PointerEvent) => {
      if (!btn.current?.contains(e.target as Node) && !pop.current?.contains(e.target as Node)) close();
    };
    window.addEventListener("scroll", close, { capture: true, passive: true });
    window.addEventListener("resize", close);
    document.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("scroll", close, { capture: true });
      window.removeEventListener("resize", close);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open, place]);

  const buttonProps = {
    ref: btn,
    type: "button" as const,
    "aria-describedby": id,
    "aria-expanded": open,
    onMouseEnter: () => setOpen(true),
    onMouseLeave: () => {
      if (!pinned.current) setOpen(false);
    },
    onFocus: () => setOpen(true),
    onBlur: (e: React.FocusEvent) => {
      // Keep it open while focus moves into the popover (e.g. its "Learn more" link).
      if (pop.current?.contains(e.relatedTarget as Node)) return;
      pinned.current = false;
      setOpen(false);
    },
    onClick: () => {
      pinned.current = !pinned.current || !open;
      setOpen(pinned.current);
    },
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // An open tip takes this Escape: a dialog around it (the hero's phone sheet) stays open (review #235).
        if (open) e.preventDefault();
        pinned.current = false;
        setOpen(false);
      }
    },
  };
  const popoverProps = {
    ref: pop,
    id,
    role: "tooltip" as const,
    hidden: !open,
    onMouseLeave: () => {
      if (!pinned.current) setOpen(false);
    },
    className:
      "fixed z-50 rounded-md border border-slate-300 bg-white p-3 text-left text-sm font-normal normal-case text-slate-900 shadow-lg",
  };
  return { open, buttonProps, popoverProps };
}
