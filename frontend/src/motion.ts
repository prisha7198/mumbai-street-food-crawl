import type { Transition } from "framer-motion";

export const EASE = [0.32, 0.72, 0, 1] as const;
export const SPRING: Transition = { type: "spring", stiffness: 400, damping: 40 };
export const quick: Transition = { duration: 0.2, ease: EASE };
export const smooth: Transition = { duration: 0.35, ease: EASE };
export const glide: Transition = { duration: 0.45, ease: EASE };

/** Time for the route line to travel one leg; each pin lands, and its row appears, as the line arrives. */
export const LEG_MS = 240;
