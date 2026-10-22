import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export const useIsDesktop = () => useMediaQuery("(min-width: 900px)");
export const useReducedMotion = () => useMediaQuery("(prefers-reduced-motion: reduce)");

/** Cycles through examples slowly while `active`. */
export function useCycling<T>(items: T[], ms: number, active: boolean): T {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setI((n) => (n + 1) % items.length), ms);
    return () => window.clearInterval(id);
  }, [items.length, ms, active]);
  return items[i];
}

export type ThemeChoice = "light" | "dark";

function readStoredTheme(): ThemeChoice | null {
  try {
    const v = window.localStorage.getItem("crawl-theme");
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

/** Follows prefers-color-scheme until the user picks, then remembers the pick. */
export function useTheme(): [ThemeChoice, () => void] {
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const [choice, setChoice] = useState<ThemeChoice | null>(readStoredTheme);
  const theme: ThemeChoice = choice ?? (systemDark ? "dark" : "light");
  useEffect(() => {
    const root = document.documentElement;
    if (choice) root.setAttribute("data-theme", choice);
    else root.removeAttribute("data-theme");
  }, [choice]);
  const toggle = () => {
    const next: ThemeChoice = theme === "dark" ? "light" : "dark";
    setChoice(next);
    try {
      window.localStorage.setItem("crawl-theme", next);
    } catch {
      /* storage unavailable: the choice still applies for this visit */
    }
  };
  return [theme, toggle];
}
