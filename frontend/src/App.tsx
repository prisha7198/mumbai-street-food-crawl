import { LayoutGroup, MotionConfig } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMeta, getStall, parseIntent, recommend } from "./api";
import { useIsDesktop, useTheme } from "./hooks";
import { AskScreen, type ControlValues } from "./screens/AskScreen";
import { CrawlScreen } from "./screens/CrawlScreen";
import type { Locked, Meta, Preferences, RecommendResponse, Stall } from "./types";

interface RunOptions {
  exclude?: string[];
  pinned?: string[];
  locked?: Locked;
  fresh?: boolean; // a new plan: replays the route drawing and shows the skeleton
  swapping?: string | null;
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const desktop = useIsDesktop();

  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [screen, setScreen] = useState<"ask" | "crawl">("ask");

  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Preferences | null>(null);
  const [locked, setLocked] = useState<Locked>({});
  const [profileId, setProfileId] = useState<string | null>(null);

  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawKey, setDrawKey] = useState(0);
  const [excludeIds, setExcludeIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Stall | null>(null);
  const [swappingId, setSwappingId] = useState<string | null>(null);

  const recAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    getMeta()
      .then(setMeta)
      .catch(() => setMetaError(true));
  }, []);

  // ---- live parsing: controls fill themselves in as the text is understood (500 ms debounce)
  useEffect(() => {
    if (!meta) return;
    const ctrl = new AbortController();
    const id = window.setTimeout(() => {
      parseIntent(text, locked, ctrl.signal)
        .then((r) => setParsed(r.preferences))
        .catch(() => {});
    }, text ? 500 : 0);
    return () => {
      window.clearTimeout(id);
      ctrl.abort();
    };
  }, [text, locked, meta]);

  const values: ControlValues | null = useMemo(() => {
    if (!meta) return null;
    const p = parsed;
    const pick = <K extends keyof Preferences>(k: K, fallback: Preferences[K]): Preferences[K] =>
      (locked[k as keyof Locked] as Preferences[K] | undefined) ?? (p ? p[k] : fallback);
    const spice = locked.spice_target !== undefined ? locked.spice_target || null : (p?.spice_target ?? null);
    const budget = locked.budget_total_inr !== undefined ? locked.budget_total_inr || null : (p?.budget_total_inr ?? null);
    return {
      area: pick("area", meta.defaults.area),
      diet: pick("diet", "any"),
      spice,
      budget,
      stops: pick("stops", meta.defaults.stops),
      time: locked.time !== undefined ? locked.time : (p?.time ?? null),
    };
  }, [meta, parsed, locked]);

  const onControl = useCallback(<K extends keyof Preferences>(key: K, value: Preferences[K] | 0) => {
    setLocked((l) => ({ ...l, [key]: value }));
  }, []);

  // ---- planning
  const run = useCallback(
    async (opts: RunOptions = {}) => {
      recAbort.current?.abort();
      const ctrl = new AbortController();
      recAbort.current = ctrl;
      setLoading(true);
      setError(null);
      if (opts.fresh) {
        setResult(null);
        setSelectedId(null);
        setDetails(null);
      }
      setSwappingId(opts.swapping ?? null);
      try {
        const r = await recommend(
          {
            text,
            preferences: opts.locked ?? locked,
            profile_id: profileId,
            exclude_ids: opts.exclude ?? [],
            pinned_ids: opts.pinned ?? [],
          },
          ctrl.signal,
        );
        if (opts.fresh) setDrawKey((k) => k + 1);
        setResult(r);
        setParsed(r.preferences);
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setError("Couldn't reach the planner. Check that the backend is running on port 8000, then try again.");
        }
      } finally {
        if (recAbort.current === ctrl) {
          setLoading(false);
          setSwappingId(null);
        }
      }
    },
    [text, locked, profileId],
  );

  const submit = () => {
    setExcludeIds([]);
    setScreen("crawl");
    run({ fresh: true });
  };

  const currentIds = result?.stops.map((s) => s.stall.id) ?? [];

  const actions = {
    onEdit: () => {
      setDetails(null);
      setScreen("ask");
    },
    onToggleTheme: toggleTheme,
    onSwap: (id: string) => {
      const exclude = [...excludeIds, id];
      setExcludeIds(exclude);
      run({ exclude, pinned: currentIds.filter((x) => x !== id), swapping: id });
    },
    onApplyNotice: () => {
      const patch = result?.notice?.action?.patch;
      if (!patch) return;
      const next = { ...locked, ...patch } as Locked;
      setLocked(next);
      setExcludeIds([]);
      run({ locked: next, fresh: true });
    },
    onAdd: (id: string) => {
      const stops = Math.min(meta?.defaults.max_stops ?? 6, currentIds.length + 1);
      const next = { ...locked, stops };
      const exclude = excludeIds.filter((x) => x !== id);
      setLocked(next);
      setExcludeIds(exclude);
      setDetails(null);
      run({ locked: next, exclude, pinned: [...currentIds, id] });
    },
    onRemove: (id: string) => {
      const stops = Math.max(meta?.defaults.min_stops ?? 2, currentIds.length - 1);
      const next = { ...locked, stops };
      const exclude = [...excludeIds, id];
      setLocked(next);
      setExcludeIds(exclude);
      setDetails(null);
      run({ locked: next, exclude, pinned: currentIds.filter((x) => x !== id) });
    },
    onOpenStall: (id: string) => {
      const inCrawl = result?.stops.find((s) => s.stall.id === id);
      if (inCrawl) {
        setDetails(inCrawl.stall);
        setSelectedId(id);
      } else {
        getStall(id).then(setDetails).catch(() => {});
      }
    },
  };

  if (metaError) {
    return (
      <div className="grid h-full place-items-center px-6 text-center">
        <div>
          <p className="text-title font-semibold">The planner isn't running</p>
          <p className="mt-2 text-body text-ink-2">
            Start the backend with <code className="tnum">uvicorn app.main:app --reload</code> in the backend folder, then reload.
          </p>
        </div>
      </div>
    );
  }

  if (!meta || !values) return <div className="h-full bg-bg" aria-busy="true" />;

  return (
    <MotionConfig reducedMotion="user">
      <LayoutGroup>
        {screen === "ask" ? (
          <AskScreen
            meta={meta}
            text={text}
            onText={setText}
            values={values}
            onControl={onControl}
            profileId={profileId}
            onProfile={setProfileId}
            onSubmit={submit}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
        ) : (
          <CrawlScreen
            meta={meta}
            text={text}
            result={result}
            loading={loading}
            error={error}
            drawKey={drawKey}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
            details={details}
            onCloseDetails={() => setDetails(null)}
            swappingId={swappingId}
            theme={theme}
            desktop={desktop}
            actions={actions}
            requestedStops={values.stops}
          />
        )}
      </LayoutGroup>
    </MotionConfig>
  );
}
