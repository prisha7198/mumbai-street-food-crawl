import { AnimatePresence, motion } from "framer-motion";
import { useId, useState, type ReactNode } from "react";
import { distance, rupees } from "../format";
import { smooth } from "../motion";
import type { Stop, Trace } from "../types";
import { Chevron } from "./controls";
import { NumberBadge } from "./StopList";

const SOURCE = { you: "set by you", request: "from your words", default: "default" } as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="py-5 first:pt-2">
      <h3 className="text-body font-semibold text-ink">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/* the three score parts; shades of ink keep the yellow reserved for the route */
const PARTS = [
  { key: "content", label: "Match", cls: "bg-ink" },
  { key: "quality", label: "Rating", cls: "bg-ink/45" },
  { key: "cf", label: "People like you", cls: "bg-ink/20" },
] as const;

function ScoreBars({ stops, trace }: { stops: Stop[]; trace: Trace }) {
  const max = Math.max(...stops.map((s) => s.components.parts.content + s.components.parts.quality + s.components.parts.cf), 0.01);
  const parts = PARTS.filter((p) => p.key !== "cf" || trace.scoring.cf_active);
  return (
    <div>
      <ul className="flex flex-col gap-3">
        {stops.map((s) => {
          const c = s.components;
          return (
            <li key={s.stall.id} className="flex items-center gap-3">
              <NumberBadge n={s.order} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-body text-ink">{s.stall.name}</span>
                  <span className="text-caption text-ink-2 tnum">{c.score.toFixed(2)}</span>
                </div>
                <div
                  className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-fill/10"
                  role="img"
                  aria-label={parts.map((p) => `${p.label} ${c.parts[p.key].toFixed(2)}`).join(", ")}
                >
                  {parts.map((p, i) => (
                    <motion.span
                      key={p.key}
                      className={`${p.cls} h-full`}
                      initial={{ width: 0 }}
                      animate={{ width: `${(c.parts[p.key] / max) * 100}%` }}
                      transition={{ ...smooth, delay: 0.05 * i }}
                    />
                  ))}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5">
        {parts.map((p) => (
          <span key={p.key} className="inline-flex items-center gap-2 text-caption text-ink-2">
            <span className={`h-2 w-2 rounded-full ${p.cls}`} aria-hidden="true" />
            {p.label} {Math.round(trace.scoring.weights[p.key] * 100)}%
          </span>
        ))}
      </div>
      <p className="mt-3 text-caption text-ink-2">
        Match is cosine similarity between your request and each stall. Rating is a Bayesian average that trusts
        stalls with more reviews.
        {trace.scoring.cf_active
          ? ` People like you is item-based collaborative filtering from ${trace.profile?.name}'s ratings.`
          : " Pick a profile under Plan as to add collaborative filtering."}
      </p>
    </div>
  );
}

function Funnel({ trace }: { trace: Trace }) {
  const f = trace.filters;
  const steps = f.steps.filter((s) => s.removed > 0);
  return (
    <ol className="flex flex-col">
      <li className="flex items-baseline justify-between py-1.5 text-body">
        <span className="text-ink">Every stall in the city</span>
        <span className="text-ink tnum">{f.start}</span>
      </li>
      {steps.map((s) => (
        <li key={s.rule} className="py-1.5">
          <div className="flex items-baseline justify-between gap-3 text-body">
            <span className="text-ink-2">{s.label}</span>
            <span className="text-ink-2 tnum whitespace-nowrap">−{s.removed}</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-fill/10">
            <motion.div
              className="h-full rounded-full bg-ink/60"
              initial={{ width: 0 }}
              animate={{ width: `${(s.remaining / f.start) * 100}%` }}
              transition={smooth}
            />
          </div>
        </li>
      ))}
      <li className="mt-1 flex items-baseline justify-between border-t border-hairline pt-2.5 text-body">
        <span className="font-medium text-ink">Left to choose from</span>
        <span className="font-medium text-ink tnum">{f.remaining}</span>
      </li>
    </ol>
  );
}

export function HowPicked({
  trace,
  stops,
  onOpenStall,
}: {
  trace: Trace;
  stops: Stop[];
  onOpenStall: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const d = trace.diversity;
  const r = trace.routing;

  return (
    <div className="border-t border-hairline">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-row px-3 py-4 text-left hover:bg-fill/[0.04] transition-colors duration-200 ease-apple"
      >
        <span className="text-body-lg font-semibold text-ink">How this was picked</span>
        <Chevron open={open} className="text-ink-2" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={smooth}
            className="overflow-hidden"
          >
            <div className="divide-y divide-hairline px-3 pb-6">
              <Section title="What we understood">
                <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
                  {trace.understood.map((u) => (
                    <div key={u.label} className="contents">
                      <dt className="text-body text-ink-2">{u.label}</dt>
                      <dd className="flex flex-wrap items-baseline justify-between gap-x-3 text-body text-ink">
                        <span>{u.value}</span>
                        <span className="text-caption text-ink-2">{SOURCE[u.source]}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </Section>

              <Section title="Narrowing down">
                <Funnel trace={trace} />
              </Section>

              {stops.length > 0 && (
                <Section title="Scoring each stop">
                  <ScoreBars stops={stops} trace={trace} />
                </Section>
              )}

              {stops.length > 1 && (
                <Section title="Keeping it varied">
                  <p className="text-body text-ink">
                    {d.moved > 0
                      ? `Diversity re-ranking brought in ${d.moved} stall${d.moved > 1 ? "s" : ""} that a pure score ranking would have missed, so the list is not all one kind of food.`
                      : d.changed
                        ? "Diversity re-ranking kept the same stalls but changed their order."
                        : "The top stalls were already varied, so diversity re-ranking did not change the list."}
                  </p>
                  <div className="mt-3 flex items-baseline gap-6 tnum">
                    <div>
                      <div className="text-caption text-ink-2">Similarity before</div>
                      <div className="text-title font-semibold text-ink-2">{d.ils_before.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-caption text-ink-2">After</div>
                      <div className="text-title font-semibold text-ink">{d.ils_after.toFixed(2)}</div>
                    </div>
                  </div>
                  <p className="mt-2 text-caption text-ink-2">
                    Average similarity between the stops (lower is more varied), using maximal marginal relevance with
                    λ = {d.lambda}.
                  </p>
                </Section>
              )}

              {stops.length > 1 && (
                <Section title="The walking route">
                  <p className="text-body text-ink">
                    Stops were added one at a time, each time taking the best score for the least extra walking, within a{" "}
                    {r.budget_km} km budget.{" "}
                    {r.two_opt_saved_m > 0
                      ? `Reordering with 2-opt then cut ${distance(r.two_opt_saved_m)} from the walk.`
                      : "Reordering with 2-opt found no shorter order."}
                    {r.dessert_forced ? " Something sweet was held back for the last stop." : ""}
                    {r.dessert_unavailable ? " No dessert stall fitted at the end, so the crawl ends without one." : ""}
                  </p>
                  <p className="mt-2 text-caption text-ink-2">
                    {r.streets?.used
                      ? `Planning uses straight-line distance × 1.3, which works offline. The line on the map and the walk times follow real streets from OpenStreetMap: ${distance(r.streets.street_m ?? 0)} on foot against the ${distance(r.streets.estimated_m ?? 0)} estimate.`
                      : "Street routing was not reachable, so the map shows straight lines between stops and walk times are estimates."}
                  </p>
                </Section>
              )}

              {trace.alternatives.length > 0 && (
                <Section title="Also considered">
                  <ul className="-mx-2 flex flex-col">
                    {trace.alternatives.map((a) => (
                      <li key={a.id}>
                        <button
                          type="button"
                          onClick={() => onOpenStall(a.id)}
                          className="flex w-full items-baseline justify-between gap-3 rounded-control px-2 py-2 text-left hover:bg-fill/[0.06] transition-colors duration-200 ease-apple"
                        >
                          <span className="min-w-0">
                            <span className="block truncate text-body text-ink">{a.name}</span>
                            <span className="block text-caption text-ink-2">{a.category_label}</span>
                          </span>
                          <span className="text-body text-ink-2 tnum">{rupees(a.price_per_person_inr)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              <p className="pt-5 text-caption text-ink-2 tnum">
                {trace.parser_used === "rules"
                  ? "Your request was read by the offline keyword parser"
                  : "Your request was read by Claude"}
                {trace.explain_source === "claude" ? ", and Claude wrote the notes." : ", and the notes come from templates."}{" "}
                Planned in {Math.round(trace.timings_ms.total)} ms.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
