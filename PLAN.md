# Plan: Mumbai street food crawl recommender

## Starting state

- `./design-references/` did not exist when the build started, so the design tokens below come straight from section 5 of the brief.
- `./data/` did not exist either. `data/generate_data.py` creates a seeded synthetic dataset (fictional stalls in ten real Mumbai areas) that follows the section 2 contract exactly. Re-running it produces byte-identical files.

## Folder structure

```
/backend
  app/
    main.py            FastAPI app, CORS, routes
    config.py          env vars, weights, constants (single source of truth for every number)
    models.py          Pydantic v2 schemas (Stall, User, Rating, Preferences, API bodies)
    data_loader.py     loads + validates JSON, area centres, lookup tables, startup summary
    hours.py           opening-hours logic incl. midnight crossing
    geo.py             haversine, walking time
    intent.py          text -> Preferences (Claude tool use, regex fallback, UI overrides)
    llm.py             thin Anthropic client wrapper: timeout, in-memory cache by input hash
    recommender/
      filters.py       hard constraints, removal counts per rule
      features.py      stall + intent vectors
      content.py       cosine similarity
      quality.py       Bayesian average (IMDb weighted rating)
      collaborative.py item-based CF, mean-centred, k = 10
      hybrid.py        min-max normalise + weighted blend + penalties
      diversity.py     MMR re-ranking + intra-list similarity
      routing.py       greedy orienteering + 2-opt
      relax.py         "what single change would fix this" notice
      pipeline.py      runs every stage, assembles stops, totals and trace
    explain.py         why-lines (Claude JSON, template fallback)
  evaluation/evaluate.py   offline metrics -> evaluation/report.md
  tests/
/frontend
  src/
    main.tsx, App.tsx, api.ts, types.ts, theme.ts
    screens/AskScreen.tsx, screens/CrawlScreen.tsx
    components/ Menu, SegmentedControl, SpiceControl, Stepper, Button,
                CrawlMap, StopList, StopRow, HowPicked, StallSheet,
                BottomSheet, Notice, Skeleton, ThemeToggle
    hooks/ useDebounced, useMediaQuery, usePrefersReducedMotion, useCyclingPlaceholder
/data   stalls.json users.json ratings.json generate_data.py
Makefile, dev.ps1, dev.sh, README.md, PLAN.md, .env.example
```

## Recommender pipeline

```
text + UI controls
   │
   ▼  Stage 1  intent.py      Claude tool call (strict schema, 4 s timeout) ─┐
   │                          regex + synonym parser ◄─── fallback ──────────┘
   │                          UI controls override parsed values
   ▼  Stage 2  filters.py     diet → exclude categories → spice_max → open now
   │                          → closed day → radius from area centre → price cap
   ▼  Stage 3  scoring        content cosine | Bayesian quality | item CF
   │                          min-max each to 0..1, weighted blend, minus
   │                          wait + hygiene penalties
   ▼  Stage 4  diversity.py   MMR, λ = 0.7, ILS before/after
   ▼  Stage 5  routing.py     greedy  score − α·walk_km  under a total walk budget,
   │                          dessert forced last, 2-opt on the order
   ▼  Stage 6  explain.py     one ≤18-word line per stop (Claude JSON or template)
   ▼
 { preferences, stops[], totals, trace, notice? }
```

When fewer stops than asked come back, `relax.py` re-runs stages 2–5 with each constraint loosened on its own (budget, walk radius, spice cap, time, area) and suggests the single change that recovers the most stops.

## Design tokens

| Token | Light | Dark |
|---|---|---|
| bg | #FBFBFD | #000000 |
| surface | #FFFFFF | #1C1C1E |
| elevated (translucent, blur 20 saturate 180%) | rgba(255,255,255,0.72) | rgba(44,44,46,0.72) |
| text | #1D1D1F | #F5F5F7 |
| text-2 | #6E6E73 | #98989D |
| text-3 | #A1A1A6 | #6E6E73 |
| hairline | #E5E5EA | #38383A |
| accent (route, pin ring, spice dots only) | #F2B705 | #F2B705 |
| button | #1D1D1F on white text | #F5F5F7 with black text |
| open / closed | #30A46C / #D93F3F | same |

Type: SF Pro → Instrument Sans fallback. 13 caption, 15 body, 17 body-large, 22 title, 34 large title, 48 hero. Weights 400/500/600. Titles −0.02em, line-height 1.15; body 1.45. `tabular-nums` on all numbers.

Radii: 22 sheets + main input, 14 rows + menus, 10 controls, full for pills and the segmented track.
Shadow (floating only): `0 8px 30px rgba(0,0,0,0.08)`.
Spacing: 8 px grid; 64 px+ vertical rhythm on Ask.
Motion: `cubic-bezier(0.32, 0.72, 0, 1)`, 200–450 ms; springs stiffness 400 damping 40 for sheets and pins. Reduced motion → opacity fades only.

## Wireframes

Ask (desktop, mobile stacks the controls into two rows)
```
┌──────────────────────────────────────────────────────────────┐
│                                                   [◐]        │
│                                                              │
│               What are you craving?                          │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ 4 spicy veg stops near Dadar under ₹400              │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   Dadar ▾   (Any|Veg|Jain|Non-veg)   ●●●○○   − ₹400 +   − 4 + │
│                                                              │
│   Plan as: Just me ▾                     [ Plan my crawl ]   │
└──────────────────────────────────────────────────────────────┘
```

Crawl (desktop)
```
┌──────────────────────────┬───────────────────────────────────┐
│ ‹ 4 spicy veg stops ... Edit │                                │
│ 38 min walk  2.1 km  ₹360    │          map                   │
│ ─────────────────────────    │      ①──②                      │
│ 1  Shree Sai Vada Pav        │          ╲                     │
│    Vada pav  ₹30  ●●●●○      │           ③──④                 │
│    Known for vada pav...     │                                │
│    ┆ 6 min walk              │                                │
│ 2  ...                       │                                │
│ ─────────────────────────    │                                │
│ How this was picked      ▾   │                                │
└──────────────────────────────┴───────────────────────────────┘
          42%                              58%
```

Crawl (mobile)
```
┌──────────────────────┐
│ map                  │
│   ①──②──③            │
│                      │
├──────────────────────┤ ← sheet, detents peek / half / full
│ ───                  │
│ 38 min  2.1 km  ₹360 │
│ 1 Shree Sai ...      │
└──────────────────────┘
```

Stall details: side sheet 420 px on desktop, bottom sheet on mobile.

## Review against the brief

- Every stage writes into `trace` → yes (pipeline collects dicts per stage).
- Offline path → regex parser + template explanations; Claude is only touched when `ANTHROPIC_API_KEY` is set.
- Haiku 5.5 rejects non-default sampling parameters, so "low temperature" becomes `effort: low` with a strict tool schema; logged in README Decisions.
- `stops` > 6 in text is clamped to 6 and surfaced in the notice.
- No gradients, emoji, decorative icons, card grids; custom menu / segmented / stepper / spice controls with ARIA.
