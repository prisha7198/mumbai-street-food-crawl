import { AnimatePresence, motion } from "framer-motion";
import { useRef, type FormEvent } from "react";
import { Button, Field, Menu, Segmented, SpiceControl, Stepper, ThemeToggle } from "../components/controls";
import { DIET_OPTIONS, rupees, time12, WHEN_OPTIONS } from "../format";
import { useCycling } from "../hooks";
import { glide, smooth } from "../motion";
import type { Diet, Meta, Preferences } from "../types";

const EXAMPLES = [
  "4 spicy veg stops near Dadar under ₹400",
  "late night kebabs on Mohammed Ali Road",
  "something cheap and sweet near Juhu beach",
  "jain friendly chaat in Ghatkopar",
  "breakfast in Matunga, not too spicy",
];

export interface ControlValues {
  area: string;
  diet: Diet;
  spice: number | null;
  budget: number | null;
  stops: number;
  time: string | null;
}

export function AskScreen({
  meta,
  text,
  onText,
  values,
  onControl,
  profileId,
  onProfile,
  onSubmit,
  theme,
  onToggleTheme,
}: {
  meta: Meta;
  text: string;
  onText: (t: string) => void;
  values: ControlValues;
  onControl: <K extends keyof Preferences>(key: K, value: Preferences[K] | 0) => void;
  profileId: string | null;
  onProfile: (id: string | null) => void;
  onSubmit: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const example = useCycling(EXAMPLES, 3600, text.length === 0);
  const d = meta.defaults;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  const whenOptions = [...WHEN_OPTIONS];
  if (values.time && !whenOptions.some((o) => o.value === values.time)) {
    whenOptions.push({ value: values.time, label: time12(values.time) });
  }

  const budgetDown = () => {
    if (values.budget == null) return;
    onControl("budget_total_inr", values.budget - d.budget_step < 100 ? 0 : values.budget - d.budget_step);
  };
  const budgetUp = () =>
    onControl("budget_total_inr", values.budget == null ? d.budget_first_step : Math.min(5000, values.budget + d.budget_step));

  return (
    <main className="min-h-full flex flex-col">
      <header className="flex justify-end px-4 pt-4 sm:px-6">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </header>

      <div className="flex flex-1 flex-col items-center justify-center px-4 pb-16 pt-6 sm:px-6 sm:pb-24">
        <form onSubmit={submit} className="w-full max-w-[960px]">
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12, transition: { duration: 0.2 } }}
            transition={glide}
            className="font-display text-large-title sm:text-hero font-semibold text-center text-balance"
          >
            What are you craving?
          </motion.h1>

          <motion.div
            layoutId="request"
            transition={glide}
            className="relative mx-auto mt-10 max-w-[760px] sm:mt-12 rounded-sheet bg-surface border border-hairline transition-colors duration-300 ease-apple focus-within:border-ink-3 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring"
          >
            <label htmlFor="craving" className="sr-only">
              What are you craving?
            </label>
            <input
              id="craving"
              ref={inputRef}
              value={text}
              onChange={(e) => onText(e.target.value)}
              autoComplete="off"
              autoFocus
              spellCheck={false}
              className="peer w-full h-16 sm:h-[72px] bg-transparent px-6 text-body-lg sm:text-title text-ink outline-none rounded-sheet"
              style={{ outline: "none" }}
            />
            <AnimatePresence mode="wait">
              {text.length === 0 && (
                <motion.span
                  key={example}
                  aria-hidden="true"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={smooth}
                  className="pointer-events-none absolute inset-y-0 left-6 right-6 flex items-center truncate text-body-lg sm:text-title text-ink-2"
                >
                  {example}
                </motion.span>
              )}
            </AnimatePresence>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            transition={{ ...smooth, delay: 0.1 }}
            className="mx-auto mt-8 flex max-w-[760px] flex-col gap-3 sm:items-center sm:gap-5"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-center sm:gap-x-4 sm:gap-y-5">
            <Field label="Area" id="lbl-area">
              <Menu
                value={values.area}
                labelledBy="lbl-area"
                options={meta.areas.map((a) => ({ value: a.name, label: a.name }))}
                onChange={(v) => onControl("area", v)}
              />
            </Field>
            <Field label="Diet" id="lbl-diet">
              <Segmented
                value={values.diet}
                options={DIET_OPTIONS.map((o) => ({ value: o.value as Diet, label: o.label }))}
                onChange={(v) => onControl("diet", v)}
                labelledBy="lbl-diet"
                layoutId="diet-thumb"
              />
            </Field>
            <Field label="Spice" id="lbl-spice">
              <SpiceControl value={values.spice} onChange={(v) => onControl("spice_target", v ?? 0)} labelledBy="lbl-spice" />
            </Field>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-center sm:gap-x-4 sm:gap-y-5">
            <Field label="Budget per person" id="lbl-budget">
              <Stepper
                label="budget"
                labelledBy="lbl-budget"
                display={values.budget == null ? "No limit" : rupees(values.budget)}
                onDecrement={budgetDown}
                onIncrement={budgetUp}
                canDecrement={values.budget != null}
                canIncrement={values.budget == null || values.budget < 5000}
                minWidth={72}
              />
            </Field>
            <Field label="Stops" id="lbl-stops">
              <Stepper
                label="stops"
                labelledBy="lbl-stops"
                display={String(values.stops)}
                onDecrement={() => onControl("stops", Math.max(d.min_stops, values.stops - 1))}
                onIncrement={() => onControl("stops", Math.min(d.max_stops, values.stops + 1))}
                canDecrement={values.stops > d.min_stops}
                canIncrement={values.stops < d.max_stops}
                minWidth={28}
              />
            </Field>
            <Field label="When" id="lbl-when">
              <Menu
                value={values.time ?? ""}
                labelledBy="lbl-when"
                options={whenOptions}
                width={200}
                onChange={(v) => onControl("time", v === "" ? null : v)}
                align="right"
              />
            </Field>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            transition={{ ...smooth, delay: 0.15 }}
            className="mx-auto mt-12 flex max-w-[760px] flex-col-reverse items-center gap-5 sm:flex-row sm:justify-between"
          >
            <div className="flex items-center gap-2">
              <span id="lbl-plan-as" className="text-body text-ink-2">
                Plan as
              </span>
              <Menu
                value={profileId ?? ""}
                labelledBy="lbl-plan-as"
                width={280}
                buttonClassName="bg-transparent hover:bg-fill/[0.08] px-2.5"
                options={[
                  { value: "", label: "Just me", detail: "Ranks by your request and ratings" },
                  ...meta.profiles.map((p) => ({ value: p.id, label: p.name, detail: p.summary })),
                ]}
                onChange={(v) => onProfile(v || null)}
              />
            </div>
            <Button type="submit" className="w-full sm:w-auto">
              Plan my crawl
            </Button>
          </motion.div>
        </form>
      </div>
    </main>
  );
}
