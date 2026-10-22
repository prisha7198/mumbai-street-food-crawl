import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { ThemeToggle } from "../components/controls";
import { CrawlMap } from "../components/CrawlMap";
import { HowPicked } from "../components/HowPicked";
import { BottomSheet, StallSheet, type Detent } from "../components/sheets";
import { Notice, StopList, StopSkeleton, Summary } from "../components/StopList";
import { glide, smooth } from "../motion";
import type { Meta, RecommendResponse, Stall, Stop } from "../types";

export interface CrawlActions {
  onEdit: () => void;
  onSwap: (id: string) => void;
  onApplyNotice: () => void;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
  onOpenStall: (id: string) => void;
  onToggleTheme: () => void;
}

function RequestHeader({ text, onEdit, floating }: { text: string; onEdit: () => void; floating: boolean }) {
  return (
    <motion.div
      layoutId="request"
      transition={glide}
      className={`flex min-w-0 flex-1 items-center gap-2 rounded-row ${floating ? "glass shadow-float border border-hairline/60" : "bg-fill/[0.07]"} h-11 pl-4 pr-1.5`}
    >
      <motion.span
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ ...smooth, delay: 0.15 }}
        className="min-w-0 flex-1 truncate text-body text-ink"
        title={text}
      >
        {text || "Your crawl"}
      </motion.span>
      <button
        type="button"
        onClick={onEdit}
        className="h-8 shrink-0 rounded-[8px] px-2.5 text-body font-medium text-ink-2 hover:text-ink hover:bg-fill/[0.1] transition-colors duration-200 ease-apple"
      >
        Edit request
      </button>
    </motion.div>
  );
}

export function CrawlScreen({
  meta,
  text,
  result,
  loading,
  error,
  drawKey,
  selectedId,
  onSelect,
  details,
  onCloseDetails,
  swappingId,
  theme,
  desktop,
  actions,
  requestedStops,
}: {
  meta: Meta;
  text: string;
  result: RecommendResponse | null;
  loading: boolean;
  error: string | null;
  drawKey: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  details: Stall | null;
  onCloseDetails: () => void;
  swappingId: string | null;
  theme: "light" | "dark";
  desktop: boolean;
  actions: CrawlActions;
  requestedStops: number;
}) {
  const [landed, setLanded] = useState(0);
  const [detent, setDetent] = useState<Detent>("half");
  const [sheetH, setSheetH] = useState(Math.round(window.innerHeight * 0.5));

  const stops = result?.stops ?? [];
  const areaName = result?.preferences.area ?? meta.defaults.area;
  const area = meta.areas.find((a) => a.name === areaName) ?? meta.areas[0];
  const ids = stops.map((s) => s.stall.id);
  const inCrawl = !!details && ids.includes(details.id);
  const vibeLabel = (v: string) => meta.vibes.find((x) => x.id === v)?.label ?? v;

  const showSkeleton = loading && !result;
  const visible = loading && !result ? 0 : Math.min(stops.length, landed);

  const list = (
    <div className="flex flex-col gap-4 pb-8">
      {desktop && result && !showSkeleton && (
        <div className="px-3">
          <Summary totals={result.totals} />
        </div>
      )}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mx-3 rounded-row bg-fill/[0.07] px-4 py-3.5 text-body text-ink" role="alert">
            {error}
          </motion.div>
        )}
        {result?.notice && !loading && (
          <div className="mx-3" key={result.notice.message}>
            <Notice notice={result.notice} onApply={actions.onApplyNotice} busy={loading} />
          </div>
        )}
      </AnimatePresence>
      {showSkeleton ? (
        <StopSkeleton count={requestedStops} />
      ) : (
        <StopList
          stops={stops}
          visible={visible}
          selectedId={selectedId}
          onSelect={onSelect}
          onSwap={actions.onSwap}
          onDetails={(s: Stop) => actions.onOpenStall(s.stall.id)}
          swappingId={swappingId}
        />
      )}
      {result && !showSkeleton && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ ...smooth, delay: 0.3 }}>
          <HowPicked trace={result.trace} stops={stops} onOpenStall={actions.onOpenStall} />
        </motion.div>
      )}
    </div>
  );

  const sheet = (
    <StallSheet
      stall={details}
      desktop={desktop}
      inCrawl={inCrawl}
      canAdd={ids.length < meta.defaults.max_stops}
      canRemove={ids.length > meta.defaults.min_stops}
      onAdd={() => details && actions.onAdd(details.id)}
      onRemove={() => details && actions.onRemove(details.id)}
      onClose={onCloseDetails}
      vibeLabel={vibeLabel}
    />
  );

  const map = (padding: { top: number; right: number; bottom: number; left: number }) => (
    <CrawlMap
      stops={stops}
      centre={[area.lat, area.lng]}
      selectedId={selectedId}
      onSelect={(id) => {
        onSelect(id);
        if (!desktop && detent === "peek") setDetent("half");
      }}
      theme={theme}
      drawKey={drawKey}
      padding={padding}
      onLanded={setLanded}
    />
  );

  if (desktop) {
    return (
      <div className="grid h-full grid-cols-[minmax(380px,42%)_1fr]">
        <aside className="flex h-full min-h-0 flex-col border-r border-hairline bg-bg">
          <header className="flex items-center gap-2 px-4 pb-3 pt-4">
            <RequestHeader text={text} onEdit={actions.onEdit} floating={false} />
            <ThemeToggle theme={theme} onToggle={actions.onToggleTheme} />
          </header>
          <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pt-2">{list}</div>
        </aside>
        <section className="relative h-full min-h-0" aria-label="Map of your crawl">
          {map({ top: 64, right: details ? 440 : 64, bottom: 64, left: 64 })}
          {sheet}
        </section>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 overflow-hidden">
      <div className="absolute inset-x-0 top-0" style={{ bottom: 0 }} aria-label="Map of your crawl" role="region">
        {map({ top: 84, right: 32, bottom: sheetH + 24, left: 32 })}
      </div>
      <div className="absolute inset-x-0 top-0 z-40 flex items-center gap-2 px-3 pt-[max(12px,env(safe-area-inset-top))]">
        <RequestHeader text={text} onEdit={actions.onEdit} floating />
        <div className="glass grid h-11 w-11 place-items-center rounded-full border border-hairline/60 shadow-float">
          <ThemeToggle theme={theme} onToggle={actions.onToggleTheme} />
        </div>
      </div>
      <BottomSheet
        detent={detent}
        onDetent={setDetent}
        onVisibleHeight={setSheetH}
        header={
          result && !showSkeleton ? (
            <Summary totals={result.totals} />
          ) : (
            <p className="text-body text-ink-2">{loading ? "Planning your crawl" : ""}</p>
          )
        }
      >
        {list}
      </BottomSheet>
      {sheet}
    </div>
  );
}
