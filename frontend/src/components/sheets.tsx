import { animate, AnimatePresence, motion, useDragControls, useMotionValue, type PanInfo } from "framer-motion";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { rupees } from "../format";
import { SPRING } from "../motion";
import type { Stall } from "../types";
import { Button, SpiceDots } from "./controls";

/* ------------------------------------------------------------------ list bottom sheet (mobile) */
export type Detent = "peek" | "half" | "full";

function detentY(d: Detent, vh: number, topInset: number): number {
  if (d === "full") return topInset;
  if (d === "half") return Math.round(vh * 0.5);
  return vh - 176;
}

/** Apple Maps style sheet with three detents. Drag the grabber or summary area to resize. */
export function BottomSheet({
  children,
  header,
  detent,
  onDetent,
  topInset = 76,
  onVisibleHeight,
}: {
  children: ReactNode;
  header: ReactNode;
  detent: Detent;
  onDetent: (d: Detent) => void;
  topInset?: number;
  onVisibleHeight?: (h: number) => void;
}) {
  const [vh, setVh] = useState(() => window.innerHeight);
  const y = useMotionValue(detentY(detent, vh, topInset));
  const controls = useDragControls();
  const [scrollH, setScrollH] = useState(vh - detentY(detent, vh, topInset));

  useEffect(() => {
    const onResize = () => setVh(window.innerHeight);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const settle = useCallback(
    (d: Detent) => {
      const target = detentY(d, vh, topInset);
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced) y.set(target);
      else animate(y, target, { type: "spring", stiffness: 400, damping: 40 });
      setScrollH(vh - target);
      onVisibleHeight?.(Math.min(vh - target, vh * 0.5));
    },
    [vh, topInset, y, onVisibleHeight],
  );

  useEffect(() => settle(detent), [detent, settle]);

  const onDragEnd = (_: unknown, info: PanInfo) => {
    const projected = y.get() + info.velocity.y * 0.2;
    const options: Detent[] = ["full", "half", "peek"];
    const nearest = options.reduce((best, d) =>
      Math.abs(detentY(d, vh, topInset) - projected) < Math.abs(detentY(best, vh, topInset) - projected) ? d : best,
    );
    if (nearest === detent) settle(nearest);
    else onDetent(nearest);
  };

  const cycle = () => onDetent(detent === "peek" ? "half" : detent === "half" ? "full" : "peek");

  return (
    <motion.section
      aria-label="Your crawl"
      className="glass fixed inset-x-0 top-0 z-30 flex h-[100dvh] flex-col rounded-t-sheet shadow-float border-t border-hairline/60"
      style={{ y }}
      drag="y"
      dragListener={false}
      dragControls={controls}
      dragConstraints={{ top: topInset, bottom: vh - 120 }}
      dragElastic={0.12}
      dragMomentum={false}
      onDragEnd={onDragEnd}
    >
      <div className="touch-none cursor-grab active:cursor-grabbing" onPointerDown={(e) => controls.start(e)}>
        <button
          type="button"
          onClick={cycle}
          onKeyDown={(e) => {
            if (e.key === "ArrowUp") {
              e.preventDefault();
              onDetent(detent === "peek" ? "half" : "full");
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              onDetent(detent === "full" ? "half" : "peek");
            }
          }}
          aria-label={`Resize list, currently ${detent === "peek" ? "collapsed" : detent === "half" ? "half height" : "full height"}`}
          className="mx-auto flex h-6 w-full items-center justify-center"
        >
          <span className="h-[5px] w-9 rounded-full bg-fill/40" />
        </button>
        <div className="px-4 pb-2">{header}</div>
      </div>
      <div className="no-scrollbar overflow-y-auto overscroll-contain px-1" style={{ height: Math.max(0, scrollH - 72) }}>
        {children}
      </div>
    </motion.section>
  );
}

/* ------------------------------------------------------------------ stall details */
function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <dt className="text-body text-ink-2">{label}</dt>
      <dd className="text-right text-body text-ink">{children}</dd>
    </div>
  );
}

const DIET_WORD = { veg: "Pure veg", non_veg: "Non-veg", both: "Veg and non-veg" };

function StallDetails({
  stall,
  inCrawl,
  canAdd,
  canRemove,
  onAdd,
  onRemove,
  onClose,
  vibeLabel,
}: {
  stall: Stall;
  inCrawl: boolean;
  canAdd: boolean;
  canRemove: boolean;
  onAdd: () => void;
  onRemove: () => void;
  onClose: () => void;
  vibeLabel: (v: string) => string;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), [stall.id]);
  const st = stall.status;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 px-6 pt-6">
        <div className="min-w-0">
          <h2 id="stall-title" className="font-display text-title font-semibold text-ink">
            {stall.name}
          </h2>
          <p className="mt-1 text-body text-ink-2">
            {stall.area}, {stall.landmark_hint}
          </p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-fill/[0.12] text-ink-2 hover:text-ink transition-colors duration-200 ease-apple"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M1.5 1.5 8.5 8.5M8.5 1.5 1.5 8.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="no-scrollbar flex-1 overflow-y-auto px-6 pb-6">
        <p className="mt-4 flex items-center gap-2 text-body">
          <span className={`h-2 w-2 rounded-full ${st.open ? "bg-open" : "bg-closed"}`} aria-hidden="true" />
          <span className="font-medium text-ink">{st.open ? "Open now" : "Closed"}</span>
          <span className="text-ink-2 tnum">{st.label}</span>
        </p>

        <p className="mt-4 text-body text-ink">{stall.description}</p>

        <section className="mt-5">
          <h3 className="text-body font-semibold text-ink">Known for</h3>
          <ul className="mt-2 flex flex-col gap-1">
            {stall.signature_dishes.map((d) => (
              <li key={d} className="text-body text-ink">
                {d}
              </li>
            ))}
          </ul>
        </section>

        <dl className="mt-4 divide-y divide-hairline border-y border-hairline">
          <Detail label="Price">
            <span className="tnum">{rupees(stall.price_per_person_inr)} per person</span>
          </Detail>
          <Detail label="Spice">
            <span className="inline-flex items-center gap-2">
              <SpiceDots level={stall.spice_level} size={7} />
              <span className="tnum">{stall.spice_level}/5</span>
            </span>
          </Detail>
          <Detail label="Rating">
            <span className="tnum">
              {stall.rating.toFixed(1)} from {stall.review_count.toLocaleString("en-IN")} reviews
            </span>
          </Detail>
          <Detail label="Hours">
            <span className="tnum">
              {stall.open_time} to {stall.close_time}
              {stall.closed_day ? `, closed ${stall.closed_day}s` : ""}
            </span>
          </Detail>
          <Detail label="Usual wait">
            <span className="tnum">{stall.avg_wait_minutes} min</span>
          </Detail>
          <Detail label="Food">{DIET_WORD[stall.veg_type] + (stall.jain_options ? ", Jain on request" : "")}</Detail>
          <Detail label="Seating">{stall.seating.charAt(0).toUpperCase() + stall.seating.slice(1)}</Detail>
          <Detail label="Payment">{stall.payment.map((p) => (p === "upi" ? "UPI" : p.charAt(0).toUpperCase() + p.slice(1))).join(", ")}</Detail>
        </dl>

        {stall.vibe_tags.length > 0 && (
          <ul className="mt-5 flex flex-wrap gap-2" aria-label="Vibe">
            {stall.vibe_tags.map((v) => (
              <li key={v} className="rounded-full bg-fill/[0.1] px-3 py-1 text-caption text-ink">
                {vibeLabel(v)}
              </li>
            ))}
          </ul>
        )}

        {stall.sample_reviews.length > 0 && (
          <section className="mt-6">
            <h3 className="text-body font-semibold text-ink">What people say</h3>
            <ul className="mt-2 flex flex-col gap-3">
              {stall.sample_reviews.slice(0, 3).map((r, i) => (
                <li key={i} className="text-body text-ink-2">
                  “{r}”
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <div className="border-t border-hairline px-6 py-4">
        {inCrawl ? (
          <Button variant="secondary" className="w-full" onClick={onRemove} disabled={!canRemove}>
            Remove from crawl
          </Button>
        ) : (
          <Button className="w-full" onClick={onAdd} disabled={!canAdd}>
            Add to crawl
          </Button>
        )}
      </div>
    </div>
  );
}

export function StallSheet({
  stall,
  desktop,
  onClose,
  ...rest
}: {
  stall: Stall | null;
  desktop: boolean;
  inCrawl: boolean;
  canAdd: boolean;
  canRemove: boolean;
  onAdd: () => void;
  onRemove: () => void;
  onClose: () => void;
  vibeLabel: (v: string) => string;
}) {
  const dragControls = useDragControls();
  useEffect(() => {
    if (!stall) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stall, onClose]);

  return (
    <AnimatePresence>
      {stall &&
        (desktop ? (
          <motion.aside
            key="side"
            role="dialog"
            aria-labelledby="stall-title"
            initial={{ x: "calc(100% + 24px)" }}
            animate={{ x: 0 }}
            exit={{ x: "calc(100% + 24px)" }}
            transition={SPRING}
            className="glass absolute bottom-4 right-4 top-4 z-[1000] w-[400px] max-w-[calc(100%-32px)] overflow-hidden rounded-sheet border border-hairline/60 shadow-float"
          >
            <StallDetails stall={stall} onClose={onClose} {...rest} />
          </motion.aside>
        ) : (
          <motion.div key="bottom" className="fixed inset-0 z-[1100]" initial="hidden" animate="shown" exit="hidden">
            <motion.div
              className="absolute inset-0 bg-black/25"
              variants={{ hidden: { opacity: 0 }, shown: { opacity: 1 } }}
              onClick={onClose}
              aria-hidden="true"
            />
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="stall-title"
              variants={{ hidden: { y: "100%" }, shown: { y: 0 } }}
              transition={SPRING}
              drag="y"
              dragListener={false}
              dragControls={dragControls}
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={{ top: 0, bottom: 0.6 }}
              onDragEnd={(_, info) => {
                if (info.offset.y > 120 || info.velocity.y > 600) onClose();
              }}
              className="glass absolute inset-x-0 bottom-0 h-[88dvh] overflow-hidden rounded-t-sheet border-t border-hairline/60 shadow-float"
            >
              <div className="flex touch-none justify-center pb-1 pt-2" aria-hidden="true" onPointerDown={(e) => dragControls.start(e)}>
                <span className="h-[5px] w-9 rounded-full bg-fill/40" />
              </div>
              <div className="h-[calc(100%-13px)]">
                <StallDetails stall={stall} onClose={onClose} {...rest} />
              </div>
            </motion.div>
          </motion.div>
        ))}
    </AnimatePresence>
  );
}
