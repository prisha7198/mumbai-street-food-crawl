export type Diet = "any" | "veg" | "jain" | "non_veg";

export interface Preferences {
  area: string;
  diet: Diet;
  spice_target: number | null;
  spice_max: number;
  budget_total_inr: number | null;
  stops: number;
  include_categories: string[];
  exclude_categories: string[];
  vibes: string[];
  end_with_dessert: boolean;
  time: string | null;
  day: string | null;
  max_walk_km: number;
}

/** What the user set by hand. 0 means "any" for spice and "no limit" for budget. */
export type Locked = Partial<Omit<Preferences, "spice_target" | "budget_total_inr">> & {
  spice_target?: number;
  budget_total_inr?: number;
};

export interface Status {
  open: boolean;
  label: string;
}

export interface Stall {
  id: string;
  name: string;
  type: string;
  area: string;
  landmark_hint: string;
  lat: number;
  lng: number;
  category: string;
  category_label: string;
  signature_dishes: string[];
  veg_type: "veg" | "non_veg" | "both";
  jain_options: boolean;
  spice_level: number;
  price_per_person_inr: number;
  price_band: string;
  rating: number;
  review_count: number;
  open_time: string;
  close_time: string;
  closed_day: string | null;
  peak_hours: string;
  avg_wait_minutes: number;
  seating: string;
  hygiene_score: number;
  payment: string[];
  vibe_tags: string[];
  description: string;
  sample_reviews: string[];
  status: Status;
  bayesian_rating?: number;
}

export interface Components {
  content: number;
  quality: number;
  cf: number | null;
  penalty: number;
  score: number;
  parts: { content: number; quality: number; cf: number };
  raw: { cosine: number; bayesian: number; cf_pred: number | null };
}

export interface Stop {
  order: number;
  stall: Stall;
  leg: { walk_km: number; walk_m: number; walk_min: number; geometry: [number, number][] | null; source: "streets" | "estimate" };
  components: Components;
  why: string;
}

export interface Totals {
  stops: number;
  walk_km: number;
  walk_m: number;
  walk_min: number;
  cost_inr: number;
  wait_min: number;
  total_min: number;
}

export interface FilterStep {
  rule: string;
  label: string;
  removed: number;
  remaining: number;
}

export interface Trace {
  parser_used: "claude" | "rules";
  llm_error: string | null;
  explain_source: "claude" | "template" | "mixed";
  understood: { label: string; value: string; source: "you" | "request" | "default" }[];
  requested_stops: number | null;
  profile: { id: string; name: string } | null;
  filters: { start: number; steps: FilterStep[]; remaining: number; time: string; day: string; per_stop_cap: number | null };
  scoring: { weights: { content: number; quality: number; cf: number }; cf_active: boolean; candidates: number; bayes: { C: number; m: number } };
  diversity: { lambda: number; pool: number; before_ids: string[]; after_ids: string[]; ils_before: number; ils_after: number; changed: boolean; moved: number };
  routing: { alpha: number; budget_km: number; greedy_km: number; two_opt_km: number; two_opt_saved_m: number; dessert_forced: boolean; dessert_unavailable?: boolean; stop_reason: string | null; streets?: { used: boolean; legs: number; of?: number; estimated_m?: number; street_m?: number } };
  alternatives: { id: string; name: string; category_label: string; price_per_person_inr: number; rating: number; score: number }[];
  timings_ms: Record<string, number>;
}

export interface Notice {
  kind: "short" | "empty" | "info";
  message: string;
  action: { label: string; patch: Partial<Preferences> } | null;
  bottleneck: string | null;
}

export interface RecommendResponse {
  preferences: Preferences;
  stops: Stop[];
  totals: Totals;
  trace: Trace;
  notice: Notice | null;
}

export interface Area {
  name: string;
  lat: number;
  lng: number;
  count: number;
}

export interface Profile {
  id: string;
  name: string;
  summary: string;
  home_area: string;
}

export interface Meta {
  areas: Area[];
  categories: { id: string; label: string }[];
  vibes: { id: string; label: string }[];
  profiles: Profile[];
  defaults: {
    area: string;
    stops: number;
    budget_total_inr: number | null;
    budget_step: number;
    budget_first_step: number;
    max_walk_km: number;
    min_stops: number;
    max_stops: number;
  };
  claude: boolean;
}
