import { motion } from "framer-motion";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { LEG_MS, SPRING } from "../motion";
import type { Stop } from "../types";

/* CARTO Positron / Dark Matter is the intended basemap, but CARTO's keyless endpoints now answer with an
   "API key required" placeholder. Stadia's Alidade Smooth is the same minimal style and needs no key on
   localhost, so it is the default. Set VITE_TILES=carto to switch back. */
const PROVIDERS = {
  carto: {
    light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  stadia: {
    light: "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png",
    dark: "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
    subdomains: "",
    attribution:
      '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
} as const;
const TILES = PROVIDERS[(import.meta.env.VITE_TILES as keyof typeof PROVIDERS) in PROVIDERS ? (import.meta.env.VITE_TILES as keyof typeof PROVIDERS) : "stadia"];

type LatLng = [number, number];

/* ------------------------------------------------------------------ pin */
function Pin({
  stop,
  selected,
  landed,
  onSelect,
}: {
  stop: Stop;
  selected: boolean;
  landed: boolean;
  onSelect: () => void;
}) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const icon = useMemo(() => L.divIcon({ className: "pin-host", html: "", iconSize: [0, 0] }), []);
  const label = `Stop ${stop.order}: ${stop.stall.name}`;

  // react-leaflet adds the marker before our handlers attach, so read the element from the ref instead
  useEffect(() => {
    let raf = 0;
    const grab = () => {
      const node = markerRef.current?.getElement();
      if (node) setEl(node);
      else raf = requestAnimationFrame(grab);
    };
    grab();
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    if (!el) return;
    el.setAttribute("role", "button");
    el.setAttribute("aria-label", label);
    el.setAttribute("aria-pressed", String(selected));
    el.setAttribute("title", stop.stall.name);
  }, [el, label, selected, stop.stall.name]);

  return (
    <Marker
      ref={markerRef}
      position={[stop.stall.lat, stop.stall.lng]}
      icon={icon}
      keyboard
      zIndexOffset={selected ? 1000 : stop.order}
      eventHandlers={{
        click: onSelect, // Leaflet also fires click on Enter when the marker has keyboard focus
      }}
    >
      {el &&
        createPortal(
          <motion.div
            className="pin absolute left-0 top-0 grid place-items-center rounded-full bg-button text-button-ink font-semibold tnum select-none"
            style={{ x: "-50%", y: "-50%", width: 30, height: 30, fontSize: 13 }}
            initial={{ scale: 0, opacity: 0 }}
            animate={
              landed
                ? {
                    scale: selected ? 1.3 : 1,
                    opacity: 1,
                    boxShadow: selected
                      ? "0 0 0 3px rgb(var(--accent)), 0 8px 30px rgba(0,0,0,0.18)"
                      : "0 0 0 2px rgb(var(--surface)), 0 4px 14px rgba(0,0,0,0.16)",
                  }
                : { scale: 0, opacity: 0 }
            }
            transition={SPRING}
          >
            {stop.order}
          </motion.div>,
          el,
        )}
    </Marker>
  );
}

/* ------------------------------------------------------------------ camera */
function Camera({
  points,
  centre,
  selected,
  padding,
  fitKey,
}: {
  points: LatLng[];
  centre: LatLng;
  selected: LatLng | null;
  padding: { top: number; right: number; bottom: number; left: number };
  fitKey: string;
}) {
  const map = useMap();
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    map.invalidateSize();
    if (points.length === 0) {
      map.flyTo(centre, 15, { duration: reduced ? 0 : 0.8, easeLinearity: 0.2 });
      return;
    }
    const bounds = L.latLngBounds(points);
    map.flyToBounds(bounds.pad(0.05), {
      paddingTopLeft: [padding.left, padding.top],
      paddingBottomRight: [padding.right, padding.bottom],
      maxZoom: 16,
      duration: reduced ? 0 : 0.8,
      easeLinearity: 0.2,
    });
    // fitKey changes when a new plan arrives or the visible area changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  useEffect(() => {
    if (!selected) return;
    const target = map.getZoom() < 16 ? 16 : map.getZoom();
    // keep the pin centred within the part of the map not covered by sheets
    const offset = L.point((padding.right - padding.left) / 2, (padding.bottom - padding.top) / 2);
    const px = map.project(L.latLng(selected), target).add(offset);
    map.flyTo(map.unproject(px, target), target, { duration: reduced ? 0 : 0.6, easeLinearity: 0.2 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.[0], selected?.[1]]);

  return null;
}

/* ------------------------------------------------------------------ route drawing */
/** The first `frac` (0..1) of a polyline, measured along its length. */
function partialPath(line: LatLng[], frac: number): LatLng[] {
  if (frac >= 1 || line.length < 2) return line;
  const seg = line.slice(1).map((p, i) => Math.hypot(p[0] - line[i][0], p[1] - line[i][1]));
  let remaining = seg.reduce((a, b) => a + b, 0) * frac;
  const out: LatLng[] = [line[0]];
  for (let i = 0; i < seg.length; i++) {
    const [a, b] = [line[i], line[i + 1]];
    if (remaining >= seg[i]) {
      out.push(b);
      remaining -= seg[i];
    } else {
      const k = seg[i] ? remaining / seg[i] : 0;
      out.push([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]);
      break;
    }
  }
  return out;
}

function useRouteDraw(legs: LatLng[][], drawKey: number, reduced: boolean) {
  // progress runs from 0 to legs.length (one unit per leg)
  const [progress, setProgress] = useState(legs.length);
  const lastKey = useRef<number | null>(null);
  const signature = legs.map((l) => `${l[0]?.join(",")}>${l[l.length - 1]?.join(",")}:${l.length}`).join("|");

  useEffect(() => {
    const n = legs.length;
    if (lastKey.current === drawKey || reduced || n === 0) {
      // same plan (swap, add, remove) or nothing to draw: no signature animation
      lastKey.current = drawKey;
      setProgress(n);
      return;
    }
    lastKey.current = drawKey;
    setProgress(0);
    let raf = 0;
    const startAt = performance.now() + 380; // let the camera settle first
    const tick = (now: number) => {
      const t = Math.max(0, now - startAt) / LEG_MS;
      setProgress(Math.min(n, t));
      if (t < n) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawKey, signature, reduced]);

  const drawn = useMemo(() => {
    const whole = Math.floor(progress);
    const frac = progress - whole;
    const out: LatLng[][] = legs.slice(0, whole);
    if (whole < legs.length && frac > 0) {
      // ease each leg with the same curve as the rest of the UI
      out.push(partialPath(legs[whole], 1 - Math.pow(1 - frac, 3)));
    }
    return out;
  }, [legs, progress]);

  // pin 1 is there from the start; pin k + 1 lands when leg k finishes
  const landed = Math.floor(progress + 1e-6) + 1;
  return { drawn, landed };
}

/* ------------------------------------------------------------------ map */
export function CrawlMap({
  stops,
  centre,
  selectedId,
  onSelect,
  theme,
  drawKey,
  padding,
  onLanded,
}: {
  stops: Stop[];
  centre: LatLng;
  selectedId: string | null;
  onSelect: (id: string) => void;
  theme: "light" | "dark";
  drawKey: number;
  padding: { top: number; right: number; bottom: number; left: number };
  onLanded?: (n: number) => void;
}) {
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const points = useMemo<LatLng[]>(() => stops.map((s) => [s.stall.lat, s.stall.lng]), [stops]);
  // each leg follows the streets when the backend found a walking route, else a straight line
  const legs = useMemo<LatLng[][]>(
    () =>
      stops.slice(1).map((s, i) => (s.leg.geometry && s.leg.geometry.length > 1 ? s.leg.geometry : [points[i], points[i + 1]])),
    [stops, points],
  );
  const { drawn, landed } = useRouteDraw(legs, drawKey, reduced);
  const selected = stops.find((s) => s.stall.id === selectedId);

  useEffect(() => {
    onLanded?.(landed);
  }, [landed, onLanded]);

  const fitKey = `${drawKey}|${stops.map((s) => s.stall.id).join(",")}|${centre.join(",")}|${padding.bottom}|${padding.right}`;

  return (
    <MapContainer
      center={centre}
      zoom={15}
      zoomControl={false}
      attributionControl
      className="isolate h-full w-full" // keep Leaflet's z-index 400 panes below the sheets
      preferCanvas={false}
    >
      <TileLayer key={theme} url={TILES[theme]} attribution={TILES.attribution} subdomains={TILES.subdomains || "abc"} maxZoom={20} />
      {drawn.length > 0 && (
        <>
          {/* soft casing under the line keeps it readable on both tile styles */}
          <Polyline
            positions={drawn}
            pathOptions={{ color: theme === "dark" ? "#000" : "#fff", weight: 9, opacity: 0.9, lineCap: "round", lineJoin: "round" }}
            interactive={false}
          />
          <Polyline
            positions={drawn}
            pathOptions={{ color: "#F2B705", weight: 5, opacity: 1, lineCap: "round", lineJoin: "round" }}
            interactive={false}
          />
        </>
      )}
      {stops.map((s, i) => (
        <Pin
          key={s.stall.id}
          stop={s}
          selected={s.stall.id === selectedId}
          landed={i < landed}
          onSelect={() => onSelect(s.stall.id)}
        />
      ))}
      <Camera
        points={[...points, ...legs.flat()]}
        centre={centre}
        selected={selected ? [selected.stall.lat, selected.stall.lng] : null}
        padding={padding}
        fitKey={fitKey}
      />
    </MapContainer>
  );
}
