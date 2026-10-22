# Crawl: a Mumbai street food crawl recommender

Type what you are craving ("4 spicy veg stops near Dadar under ₹400, something sweet at the end") and get a short, walkable crawl: which stalls, in what order, how far apart, roughly what it costs, and a plain-English trace of how each stop was picked.

- **Backend:** Python, FastAPI. All ranking is deterministic Python in `backend/app/recommender/`.
- **Frontend:** React 18, Vite, TypeScript, Tailwind, Framer Motion, Leaflet.
- **Claude** is only used for language (reading the request, writing the one-line "why" notes). Without an API key everything still works, using a keyword parser and templates.

Screenshots from the verification run are in [`docs/screenshots/`](docs/screenshots/).

---

## Setup (Windows or macOS)

### Prerequisites

- Python 3.11 or newer (`python --version`). Tested on 3.13.
- Node.js 18 or newer (`node --version`). Tested on Node 23, npm 11.
- Optional: an Anthropic API key.

### Install

From the project folder:

```bash
python -m venv backend/.venv
```

Windows:

```bash
backend\.venv\Scripts\python -m pip install -r backend/requirements.txt
```

macOS / Linux:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

Then the frontend:

```bash
cd frontend && npm install
```

Optional, for Claude: copy `.env.example` to `.env` in the project root and fill in `ANTHROPIC_API_KEY`. The key is read only by the backend and never reaches the browser.

### Run

Two terminals:

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
```

(macOS: `.venv/bin/python`, or activate the venv and run `uvicorn app.main:app --reload`.)

```bash
cd frontend && npm run dev
```

Open http://localhost:5173. The frontend proxies `/api` to the backend on port 8000.

One command for both: `make dev` (needs `make`), or `.\dev.ps1` on Windows PowerShell, or `./dev.sh` on macOS.

On startup the backend prints a data summary: stalls per area and category, area centres, and any rows it rejected.

### Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

112 tests: midnight-crossing hours, Jain and veg filtering, the Bayesian average, MMR reordering duplicates, the route never exceeding its walk budget (150 random cases), the fallback parser on 10 sentences, and the API (happy path, swap, impossible request, profile CF). Tests always run offline.

### Offline evaluation

```bash
cd backend && .venv/Scripts/python -m evaluation.evaluate
```

This writes `backend/evaluation/report.md`. Results are deterministic (seed 42).

| Variant | Precision@5 | Recall@10 | NDCG@10 | Coverage | Intra-list sim. |
|---|---:|---:|---:|---:|---:|
| Popularity | 0.034 | 0.090 | 0.057 | 20.9% | 0.442 |
| Content only | 0.098 | 0.217 | 0.157 | 86.6% | 0.629 |
| CF only | 0.038 | 0.092 | 0.060 | 88.4% | 0.465 |
| Hybrid + MMR | 0.064 | 0.213 | 0.139 | 69.2% | 0.484 |

### Regenerating the data

```bash
python data/generate_data.py
```

---

## How the recommender works

Every request goes through six stages. Each stage writes what it did into a `trace` object, which the "How this was picked" panel shows.

### 1. Understand the request (`intent.py`)

The sentence becomes a `Preferences` object: area, diet, spice, budget, number of stops, categories to include or skip, vibes, whether to end on something sweet, time, and how far you will walk.

- **With an API key:** Claude reads the sentence and calls a `set_preferences` tool. The tool's JSON schema is strict and lists the only valid areas, categories and vibes, so Claude cannot invent a value. Calls time out after 4 seconds and are cached by a hash of the input.
- **Without a key, or if the call fails:** a rule-based parser uses regular expressions and synonym maps ("teekha" means spicy, "shudh veg" means veg, "₹400", "400 rs" and "under 400" all mean a ₹400 budget, "no chinese" skips a category).
- Anything you set with the controls overrides what was parsed.

### 2. Hard filters (`recommender/filters.py`)

Stalls are removed, in order, if they are: too far from the area centre, wrong for your diet (Jain users only see stalls with Jain options; veg users never see non-veg stalls), in a category you skipped, spicier than your cap, on their weekly day off, closed at your time, or more than 1.5 times your per-stop share of the budget. Hours that cross midnight are handled properly: 01:00 on Tuesday at a stall open 18:00–02:30 belongs to Monday's session (`hours.py`). The trace records how many stalls each rule removed.

### 3. Scoring (`content.py`, `quality.py`, `collaborative.py`, `hybrid.py`)

Three scores per stall, each min-max normalised to 0–1 over the surviving stalls, then blended.

- **Content match: cosine similarity.** Each stall is a vector: one-hot category, multi-hot vibe tags, spice, price and diet flags (`features.py`). Your request becomes a vector with the same layout. Spice and price use a soft one-hot (a small Gaussian bump over bins) so that spice 4 is close to 5 and far from 1, which a raw number inside a cosine cannot express.
- **Quality: Bayesian average,** the IMDb weighted rating: `WR = (v/(v+m))·R + (m/(v+m))·C`, where R is the stall's rating, v its review count, C the mean rating of all stalls and m the 60th percentile of review counts. A 4.9 from 6 reviews is pulled towards the average; a 4.6 from 2,000 reviews barely moves.
- **People like you: item-based collaborative filtering,** only when you pick a profile under "Plan as". Ratings are mean-centred per user; similarity between two stalls is the cosine of their rating columns; your rating for an unseen stall is predicted from the 10 most similar stalls you have rated.
- **Blend:** `0.45·content + 0.30·quality + 0.25·CF`, minus small penalties for long queues and low hygiene. Without a profile, CF's weight is shared out in proportion (0.6 / 0.4). Weights are in `config.py`.

### 4. Diversity (`recommender/diversity.py`)

**Maximal Marginal Relevance** (Carbonell & Goldstein, 1998) re-ranks the top 30. Each next pick maximises `λ·relevance − (1−λ)·(max similarity to what is already picked)` with λ = 0.7, so three vada pav stalls in a row pay a price. The trace reports **intra-list similarity** (Ziegler et al., 2005) of the top N before and after.

### 5. Route (`recommender/routing.py`)

A small **Orienteering Problem** (Gavalas et al., 2014): pick N stops and an order that collect the most score within a walking budget.

- Distance is haversine × 1.3 (streets are not straight), at 4.5 km/h.
- **Greedy construction:** start at the area centre and repeatedly add the stall with the best `value − α·walk_km` that still fits in the budget. The value keeps MMR's redundancy term, so routing does not undo the variety from stage 4.
- **2-opt:** try reversing every segment of the route and keep any reversal that shortens it. 2-opt only reorders, so it can never break the budget.
- If you asked for something sweet at the end, a kulfi/dessert or juice/falooda stall is held back for the last slot, and every earlier pick must leave one reachable.
- **Streets on the map** (`streets.py`): once the crawl is chosen, each leg is sent to an OSRM walking router (the FOSSGIS server at routing.openstreetmap.de, OpenStreetMap data, no key). The map line then follows real streets, and the walk times and distances shown are real. Legs are cached, so a swap only fetches the legs that changed. Planning itself never waits on this: if the router is unreachable, the map falls back to straight lines and estimated times, and the app stops asking for 60 seconds. Set `USE_STREET_ROUTING=0` to turn it off.

### 6. Explain (`explain.py`)

One line per stop, at most 18 words, built only from the stall record and the route (dish, spice, price, rating, minutes from the previous stop). With a key, Claude writes all lines in one JSON call; any line that is missing or too long falls back to a template such as "Known for vada pav. 4 min from your last stop, around ₹35."

### When not enough fits

If fewer stops fit than you asked for, `relax.py` re-runs stages 2–5 with one constraint loosened at a time (budget up, more walking, no spice cap, a different time, a nearby area, no skipped categories) and suggests the single change that recovers the most stops. If no single change helps, it tries pairs. The suggestion comes with a button that applies it. Example for "10 stops in Colaba at 3 AM under ₹50": *"Crawls top out at 6 stops. No stalls are open near Colaba at 3 AM. Raise the budget to ₹600 and go at 9:30 PM to get 6 stops."*

**Swap** re-runs with that stall excluded and the other stops pinned.

---

## API

| Method | Path | Body / result |
|---|---|---|
| POST | `/api/intent` | `{text, preferences?}` → `{preferences, parser_used}` |
| POST | `/api/recommend` | `{text?, preferences?, profile_id?, exclude_ids?, pinned_ids?}` → `{preferences, stops[], totals, trace, notice?}` |
| GET | `/api/stalls`, `/api/stalls/{id}` | stall list / one stall with open status |
| GET | `/api/meta` | areas with centres, categories, vibes, demo profiles |
| GET | `/api/health` | status and whether Claude is configured |

Without Claude or street routing, `/api/recommend` answers in roughly 10–60 ms (the test suite asserts under 300 ms). The first street-routing call for a new crawl adds 1–3 seconds of network time; repeats come from the cache.

---

## Before the viva

- **Live demo script:** the four example requests from the brief plus the impossible one all work offline. Open "How this was picked" for each: the funnel, the score bars and "Keeping it varied" are the three things worth talking through.
- **Turn on CF:** pick a profile under "Plan as" and the score bars gain a third segment ("People like you").
- **The evaluation is honest, not flattering:** content-only has the best NDCG; the hybrid trades about 12% of that for a clearly more varied list, and CF alone is close to popularity because the rating matrix is only 19% full. That is a defensible accuracy-versus-diversity story, and the report says so.
- **Times depend on the clock:** with "When: Now", a daytime demo will see evening-only stalls as closed. Phrases like "late night" or "breakfast", or the When control, set the time explicitly.
- **Everything numeric lives in `backend/app/config.py`.**

---

## Decisions

Things the brief left open, or where reality differed from it:

1. **No design references.** `./design-references/` did not exist, so section 5 of the brief is the design spec as written.
2. **No data files.** `./data/` did not exist. `data/generate_data.py` creates a seeded, reproducible synthetic dataset that follows the section 2 contract exactly: 172 fictional stalls across 10 real Mumbai areas (real landmarks and coordinates, invented names), 48 users and 1,578 ratings. Ratings come from a latent quality score plus each user's tastes, so CF has real signal to find. `closed_day` is `null` when a stall has no day off. Stall `type` is one of cart, stall, counter, eatery. The loader also accepts a single combined JSON file.
3. **Map tiles.** CARTO's keyless Positron and Dark Matter endpoints now return an "API key required" placeholder for every request (checked from the browser and from Python). The default is therefore Stadia Maps' Alidade Smooth and Alidade Smooth Dark: the same minimal look, free without a key on localhost. Set `VITE_TILES=carto` to switch back to CARTO. A deployment beyond localhost needs a Stadia key or domain registration.
4. **"Low temperature".** Claude Haiku 5.5 rejects non-default sampling parameters, so determinism comes from `effort: low`, a strict tool schema and server-side validation instead. Forced `tool_choice` is rejected by the newest models, so the prompt asks for the tool call (`tool_choice: auto`), and a response without one counts as a failure and falls back to the rule parser.
5. **Spice and budget can be "any".** If the request does not mention spice or budget, they are `null` rather than a made-up default, so they neither filter stalls nor bias the content match. The UI shows "Any" and "No limit", and sends `0` to lock those choices explicitly.
6. **Walking budget.** `max_walk_km` (default 2.5) caps the walk *between* stops. The walk from the area centre to the first stop still counts against the greedy value (so crawls start near the centre) but not against the budget, because people usually arrive by train or cab. The same number is the radius filter (straight-line distance from the centre).
7. **Spice and price in the vector** use a soft one-hot (Gaussian over bins) instead of a single normalised number, because a single number inside a cosine makes "more" look "more similar".
8. **Routing keeps MMR's redundancy term** so the greedy route builder does not undo the diversity re-ranking.
9. **Categories.** "Include" categories are soft (they shape the content vector). "Skip" categories are a hard filter, added as an extra rule in stage 2.
10. **Pinned stops** (from Swap and "Add to crawl") bypass the filters, since you chose them.
11. **More than 6 stops** in the text is clamped to 6 and the notice says so.
12. **Total time** includes walking, each stall's average wait and 10 minutes of eating per stop.
13. **A "When" control** sits next to the five controls from the brief. Without it, a daytime demo has no way to plan an evening crawl except by typing a time.
14. **Signature animation timing.** The route draws leg by leg (240 ms a leg) and each row appears exactly when its pin lands. A literal 90 ms per leg drew the line too fast to follow, so the rows follow the pins instead of a fixed 90 ms stagger. With reduced motion everything appears at once with fades.
15. **Score bars use shades of the text colour,** keeping the yellow accent for the route, the selected pin ring and spice dots only.
16. **Focus ring** is a darker yellow (`#B08400`) in light mode so it passes 3:1 contrast on white; dark mode uses the brand yellow.
17. **Evaluation choices.** Popularity means "most reviews". Content-only uses the user's stated profile plus the average vector of stalls they rated 4 or more in training (a standard content-based profile). Every variant gets the same diet filter, so a veg user is never scored on non-veg stalls.
18. **Street routing is display only.** The recommender plans with straight-line distance × 1.3 so it is deterministic and works offline; the walking router only redraws the chosen legs along streets and replaces the shown times. Real street distance can be a little longer than the estimate, so the "How this was picked" panel shows both. The public OSRM demo server only offers car routes, which is why the FOSSGIS foot router is used.
19. **Demo profiles** in "Plan as" are six of the 48 users, chosen for variety of diet and number of ratings.

---

## References

- Trattner, C. & Elsweiler, D. (2017). Food Recommender Systems: Important Contributions, Challenges and Future Research Directions. arXiv:1711.02760.
- Zhao, S., King, I. & Lyu, M. R. A Survey of Point-of-interest Recommendation in Location-based Social Networks. arXiv:1607.00647.
- Gavalas, D., Konstantopoulos, C., Mastakas, K. & Pantziou, G. (2014). A survey on algorithmic approaches for solving tourist trip design problems. *Journal of Heuristics*, 20(3), 291–328.
- Ziegler, C.-N., McNee, S. M., Konstan, J. A. & Lausen, G. (2005). Improving Recommendation Lists Through Topic Diversification. *Proceedings of WWW 2005*.
- Carbonell, J. & Goldstein, J. (1998). The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries. *Proceedings of SIGIR 1998*.

---

## Project layout

```
backend/app/            FastAPI app, config, schemas, data loader, intent, explain
backend/app/recommender filters, features, content, quality, collaborative, hybrid,
                        diversity, routing, relax, pipeline
backend/evaluation/     evaluate.py and report.md
backend/tests/          pytest suite
frontend/src/           screens (Ask, Crawl), components, hooks, api client
data/                   stalls.json, users.json, ratings.json, generate_data.py
docs/screenshots/       verification screenshots
PLAN.md                 plan, design tokens and wireframes
```
