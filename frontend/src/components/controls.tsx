import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { quick, SPRING } from "../motion";

/* ------------------------------------------------------------------ Button */
export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
  className = "",
  ...rest
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "plain";
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const styles = {
    primary: "h-12 px-6 bg-button text-button-ink text-body-lg font-medium rounded-control hover:opacity-90",
    secondary: "h-10 px-4 text-body font-medium rounded-control border border-hairline bg-surface hover:bg-fill/5",
    plain: "h-9 px-2 text-body font-medium text-ink-2 rounded-control hover:text-ink",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap transition-[opacity,background-color,color] duration-200 ease-apple active:scale-[0.98] disabled:opacity-40 ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ Field (caption + control) */
export function Field({ label, id, children }: { label: string; id: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-start sm:justify-start sm:gap-1.5">
      <span id={id} className="text-body text-ink-2 sm:pl-0.5 sm:text-caption">
        {label}
      </span>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ Chevron (functional disclosure mark) */
export function Chevron({ open = false, className = "" }: { open?: boolean; className?: string }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      aria-hidden="true"
      className={`transition-transform duration-300 ease-apple ${open ? "rotate-180" : ""} ${className}`}
    >
      <path d="M2 3.5 5 6.5 8 3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ Menu (custom listbox) */
export interface MenuOption {
  value: string;
  label: string;
  detail?: string;
}

export function Menu({
  value,
  options,
  onChange,
  labelledBy,
  ariaLabel,
  align = "left",
  width = 240,
  buttonClassName = "",
}: {
  value: string;
  options: MenuOption[];
  onChange: (v: string) => void;
  labelledBy?: string;
  ariaLabel?: string;
  align?: "left" | "right";
  width?: number;
  buttonClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: "", at: 0 });
  const current = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    setActive(Math.max(0, options.findIndex((o) => o.value === value)));
    const onDoc = (e: MouseEvent) => {
      if (!buttonRef.current?.contains(e.target as Node) && !listRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    requestAnimationFrame(() => listRef.current?.focus());
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, options, value]);

  useEffect(() => {
    if (open) listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const choose = (i: number) => {
    onChange(options[i].value);
    setOpen(false);
    buttonRef.current?.focus();
  };

  const onListKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") setActive((a) => Math.min(options.length - 1, a + 1));
    else if (e.key === "ArrowUp") setActive((a) => Math.max(0, a - 1));
    else if (e.key === "Home") setActive(0);
    else if (e.key === "End") setActive(options.length - 1);
    else if (e.key === "Enter" || e.key === " ") choose(active);
    else if (e.key === "Escape" || e.key === "Tab") {
      setOpen(false);
      if (e.key === "Escape") buttonRef.current?.focus();
      return;
    } else if (e.key.length === 1) {
      // typeahead
      const now = Date.now();
      typed.current.text = (now - typed.current.at > 700 ? "" : typed.current.text) + e.key.toLowerCase();
      typed.current.at = now;
      const i = options.findIndex((o) => o.label.toLowerCase().startsWith(typed.current.text));
      if (i >= 0) setActive(i);
      return;
    } else return;
    e.preventDefault();
  };

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-labelledby={labelledBy ? `${labelledBy} ${listId}-value` : undefined}
        aria-label={ariaLabel}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
          }
        }}
        className={`h-10 pl-3.5 pr-3 inline-flex items-center gap-2 rounded-control bg-fill/[0.08] hover:bg-fill/[0.12] text-body font-medium transition-colors duration-200 ease-apple ${buttonClassName}`}
      >
        <span id={`${listId}-value`} className="relative overflow-hidden">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={current?.value}
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -10, opacity: 0 }}
              transition={quick}
              className="block whitespace-nowrap"
            >
              {current?.label}
            </motion.span>
          </AnimatePresence>
        </span>
        <Chevron open={open} className="text-ink-2" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            ref={listRef}
            id={listId}
            role="listbox"
            tabIndex={-1}
            aria-activedescendant={`${listId}-${active}`}
            aria-labelledby={labelledBy}
            aria-label={ariaLabel}
            onKeyDown={onListKey}
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: -2, transition: { duration: 0.15 } }}
            transition={SPRING}
            style={{ width, transformOrigin: align === "left" ? "top left" : "top right" }}
            className={`glass shadow-float absolute z-50 mt-2 max-h-[320px] overflow-auto no-scrollbar rounded-row border border-hairline/70 p-1.5 ${align === "left" ? "right-0 sm:left-0 sm:right-auto" : "right-0"}`}
          >
            {options.map((o, i) => {
              const selected = o.value === value;
              return (
                <li
                  key={o.value}
                  id={`${listId}-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={selected}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(i)}
                  className={`flex items-start gap-2.5 rounded-control px-2.5 py-2 cursor-default select-none ${i === active ? "bg-fill/[0.12]" : ""}`}
                >
                  <span className="mt-[3px] w-3.5 shrink-0 text-ink" aria-hidden="true">
                    {selected && (
                      <svg width="13" height="13" viewBox="0 0 14 14">
                        <path d="M2.5 7.5 5.5 10.5 11.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </span>
                  <span className="flex flex-col">
                    <span className="text-body text-ink">{o.label}</span>
                    {o.detail && <span className="text-caption text-ink-2">{o.detail}</span>}
                  </span>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ Segmented control */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  labelledBy,
  layoutId,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  labelledBy: string;
  layoutId: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % options.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + options.length) % options.length;
    else return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  };
  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="relative inline-flex h-10 items-center rounded-full bg-fill/[0.1] p-[3px]">
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => (refs.current[i] = el)}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={`relative h-full px-3.5 rounded-full text-body whitespace-nowrap transition-colors duration-200 ease-apple ${checked ? "text-ink font-medium" : "text-ink-2 hover:text-ink"}`}
          >
            {checked && (
              <motion.span
                layoutId={layoutId}
                transition={SPRING}
                className="absolute inset-0 rounded-full bg-thumb border border-hairline/80"
                aria-hidden="true"
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ Spice dots */
export const SPICE_WORDS = ["Any", "No spice", "Mild", "Medium", "Spicy", "Fiery"];

/** Read-only spice indicator. */
export function SpiceDots({ level, size = 6, label = true }: { level: number; size?: number; label?: boolean }) {
  return (
    <span className="inline-flex items-center gap-[3px]" role={label ? "img" : undefined} aria-label={label ? `Spice ${level} of 5` : undefined} aria-hidden={label ? undefined : true}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          style={{ width: size, height: size }}
          className={`rounded-full ${n <= level ? "bg-accent" : "bg-fill/25"}`}
        />
      ))}
    </span>
  );
}

/** 5-step spice picker drawn as dots that fill. Click the current level again to clear it. */
export function SpiceControl({
  value,
  onChange,
  labelledBy,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  labelledBy: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const v = value ?? 0;
  const onKey = (e: KeyboardEvent) => {
    let next = v;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = Math.min(5, v + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = Math.max(0, v - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = 5;
    else return;
    e.preventDefault();
    onChange(next === 0 ? null : next);
    refs.current[Math.max(0, next - 1)]?.focus();
  };
  return (
    <div className="flex h-10 items-center gap-3 rounded-control bg-fill/[0.08] px-3">
      <div role="radiogroup" aria-labelledby={labelledBy} className="flex items-center gap-1" onKeyDown={onKey}>
        {[1, 2, 3, 4, 5].map((n) => {
          const filled = n <= v;
          return (
            <button
              key={n}
              ref={(el) => (refs.current[n - 1] = el)}
              type="button"
              role="radio"
              aria-checked={n === v}
              aria-label={`${SPICE_WORDS[n]}, ${n} of 5`}
              tabIndex={n === Math.max(1, v) ? 0 : -1}
              onClick={() => onChange(n === v ? null : n)}
              className="grid h-6 w-5 place-items-center rounded-full"
            >
              <motion.span
                initial={false}
                animate={{ scale: filled ? 1 : 0.82 }}
                transition={{ ...SPRING, delay: filled ? (n - 1) * 0.03 : 0 }}
                className={`block h-[11px] w-[11px] rounded-full transition-colors duration-300 ease-apple ${filled ? "bg-accent" : "bg-transparent border-[1.5px] border-fill/40"}`}
              />
            </button>
          );
        })}
      </div>
      <span className="w-[62px] text-body text-ink-2" aria-live="polite">
        {SPICE_WORDS[v]}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ Stepper */
export function Stepper({
  label,
  display,
  onDecrement,
  onIncrement,
  canDecrement,
  canIncrement,
  labelledBy,
  minWidth = 56,
}: {
  label: string;
  display: string;
  onDecrement: () => void;
  onIncrement: () => void;
  canDecrement: boolean;
  canIncrement: boolean;
  labelledBy: string;
  minWidth?: number;
}) {
  const btn =
    "grid h-8 w-8 place-items-center rounded-[8px] text-ink transition-colors duration-200 ease-apple hover:bg-fill/[0.12] disabled:text-ink-3 disabled:hover:bg-transparent";
  return (
    <div role="group" aria-labelledby={labelledBy} className="flex h-10 items-center gap-0.5 rounded-control bg-fill/[0.08] px-1">
      <button type="button" className={btn} onClick={onDecrement} disabled={!canDecrement} aria-label={`Decrease ${label}`}>
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 6h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
      <span className="relative overflow-hidden text-center text-body font-medium tnum" style={{ minWidth }} aria-live="polite">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={display}
            initial={{ y: 8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={quick}
            className="block whitespace-nowrap"
          >
            {display}
          </motion.span>
        </AnimatePresence>
      </span>
      <button type="button" className={btn} onClick={onIncrement} disabled={!canIncrement} aria-label={`Increase ${label}`}>
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 6h8M6 2v8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ Theme toggle */
export function ThemeToggle({ theme, onToggle }: { theme: "light" | "dark"; onToggle: () => void }) {
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={dark ? "Switch to light appearance" : "Switch to dark appearance"}
      className="grid h-9 w-9 place-items-center rounded-full text-ink-2 hover:text-ink hover:bg-fill/[0.1] transition-colors duration-200 ease-apple"
    >
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M9 2.75a6.25 6.25 0 0 1 0 12.5Z" fill="currentColor" />
      </svg>
    </button>
  );
}
