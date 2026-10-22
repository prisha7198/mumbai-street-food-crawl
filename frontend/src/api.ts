import type { Locked, Meta, Preferences, RecommendResponse, Stall } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getMeta = () => request<Meta>("/api/meta");

export const getStall = (id: string) => request<Stall>(`/api/stalls/${id}`);

export const parseIntent = (text: string, preferences: Locked, signal?: AbortSignal) =>
  request<{ preferences: Preferences; parser_used: "claude" | "rules"; requested_stops: number | null }>("/api/intent", {
    method: "POST",
    body: JSON.stringify({ text, preferences }),
    signal,
  });

export interface RecommendBody {
  text: string;
  preferences: Locked;
  profile_id: string | null;
  exclude_ids?: string[];
  pinned_ids?: string[];
}

export const recommend = (body: RecommendBody, signal?: AbortSignal) =>
  request<RecommendResponse>("/api/recommend", { method: "POST", body: JSON.stringify(body), signal });
