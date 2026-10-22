import { AnimatePresence, motion } from "framer-motion";
import { useRef } from "react";
import { distance, minutes, rupees } from "../format";
import { quick, smooth, SPRING } from "../motion";
import type { Notice as NoticeT, Stop, Totals } from "../types";
import { Button, SpiceDots } from "./controls";

/* ------------------------------------------------------------------ summary */
export function Summary({ totals }: { totals: Totals }) {
  if (!totals.stops) return null;
  return (
    <p className="text-body text-ink-2 tnum">
      {totals.stops} stops, {minutes(totals.walk_min)} of walking over {distance(totals.walk_m)}, about{" "}
      {rupees(totals.cost_inr)} each.
    </p>
  );
}

/* ------------------------------------------------------------------ notice */
export function Notice({ notice, onApply, busy }: { notice: NoticeT; onApply: () => void; busy: boolean }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={smooth}
      role="status"
      className="rounded-row bg-fill/[0.07] px-4 py-3.5"
    >
      <p className="text-body text-ink">{notice.message}</p>
      {notice.action && (
        <Button variant="secondary" className="mt-3" onClick={onApply} disabled={busy}>
          {notice.action.label}
        </Button>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ number badge */
export function NumberBadge({ n, selected }: { n: number; selected?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`grid h-7 w-7 shrink-0 place-items-center rounded-full bg-button text-button-ink text-caption font-semibold tnum transition-shadow duration-300 ease-apple ${selected ? "shadow-[0_0_0_3px_rgb(var(--accent))]" : ""}`}
    >
      {n}
    </span>
  );
}

/* ------------------------------------------------------------------ row */
function StopRow({
  stop,
  selected,
  onSelect,
  onSwap,
  onDetails,
  swapping,
}: {
  stop: Stop;
  selected: boolean;
  onSelect: () => void;
  onSwap: () => void;
  onDetails: () => void;
  swapping: boolean;
}) {
  const s = stop.stall;
  const press = useRef<number | null>(null);
  const startPress = () => {
    press.current = window.setTimeout(onSelect, 450); // long-press on touch selects and reveals actions
  };
  const endPress = () => {
    if (press.current) window.clearTimeout(press.current);
  };

  return (
    <div
      className={`group relative flex gap-4 rounded-row px-3 py-3.5 transition-colors duration-200 ease-apple ${selected ? "bg-fill/[0.07]" : "hover:bg-fill/[0.04]"}`}
      onTouchStart={startPress}
      onTouchEnd={endPress}
      onTouchMove={endPress}
    >
      <div className="pt-0.5">
        <NumberBadge n={stop.order} selected={selected} />
      </div>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`Stop ${stop.order}: ${s.name}. Show on map`}
        className="absolute inset-0 rounded-row"
      />
      <div className="pointer-events-none relative min-w-0 flex-1">
        <h3 className="pr-28 text-body-lg font-semibold leading-snug text-ink">{s.name}</h3>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-ink-2">
          <span>{s.signature_dishes[0]}</span>
          <span className="tnum">{rupees(s.price_per_person_inr)}</span>
          <SpiceDots level={s.spice_level} />
        </div>
        <p className="mt-1.5 text-body text-ink">{stop.why}</p>
      </div>
      <div
        className={`absolute right-2 top-2.5 flex items-center gap-0.5 rounded-control transition-opacity duration-200 ease-apple ${selected ? "opacity-100" : "pointer-events-none opacity-0 group-hover:pointer-events-auto group-hover:opacity-100 focus-within:pointer-events-auto focus-within:opacity-100"}`}
      >
        <Button variant="plain" onClick={onSwap} disabled={swapping} aria-label={`Swap ${s.name} for the next best stall`}>
          Swap
        </Button>
        <Button variant="plain" onClick={onDetails} aria-label={`Details for ${s.name}`}>
          Details
        </Button>
      </div>
    </div>
  );
}

function Connector({ stop }: { stop: Stop }) {
  return (
    <div className="flex items-center gap-4 px-3" aria-hidden="true">
      <div className="flex w-7 justify-center">
        <span className="h-7 border-l-[1.5px] border-dotted border-ink-3" />
      </div>
      <span className="text-caption text-ink-2 tnum">
        {minutes(stop.leg.walk_min)} walk, {distance(stop.leg.walk_m)}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ list */
export function StopList({
  stops,
  visible,
  selectedId,
  onSelect,
  onSwap,
  onDetails,
  swappingId,
}: {
  stops: Stop[];
  visible: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onSwap: (id: string) => void;
  onDetails: (stop: Stop) => void;
  swappingId: string | null;
}) {
  return (
    <ol className="flex flex-col" aria-label="Your crawl, in walking order">
      <AnimatePresence initial={false} mode="popLayout">
        {stops.slice(0, visible).map((stop, i) => (
          <motion.li
            key={stop.stall.id}
            layout="position"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: swappingId === stop.stall.id ? 0.4 : 1, y: 0 }}
            exit={{ opacity: 0, x: -24, transition: quick }}
            transition={{ ...SPRING, opacity: smooth }}
          >
            {i > 0 && <Connector stop={stop} />}
            <StopRow
              stop={stop}
              selected={stop.stall.id === selectedId}
              onSelect={() => onSelect(stop.stall.id)}
              onSwap={() => onSwap(stop.stall.id)}
              onDetails={() => onDetails(stop)}
              swapping={swappingId !== null}
            />
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  );
}

/* ------------------------------------------------------------------ skeleton */
export function StopSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Planning your crawl">
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          className="flex gap-4 px-3 py-3.5"
          initial={{ opacity: 0.4 }}
          animate={{ opacity: [0.4, 0.9, 0.4] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut", delay: i * 0.12 }}
        >
          <span className="h-7 w-7 shrink-0 rounded-full bg-fill/15" />
          <div className="flex flex-1 flex-col gap-2 pt-0.5">
            <span className="h-4 w-1/2 rounded-full bg-fill/15" />
            <span className="h-3 w-1/3 rounded-full bg-fill/10" />
            <span className="h-3 w-5/6 rounded-full bg-fill/10" />
          </div>
        </motion.div>
      ))}
    </div>
  );
}
