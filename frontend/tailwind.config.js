/** Design tokens live in src/index.css as CSS variables; Tailwind only maps names to them. */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        elevated: token("elevated"),
        ink: token("text"),
        "ink-2": token("text-2"),
        "ink-3": token("text-3"),
        hairline: token("hairline"),
        fill: token("fill"),
        thumb: token("thumb"),
        accent: token("accent"),
        ring: token("ring"),
        button: token("button"),
        "button-ink": token("button-text"),
        open: token("open"),
        closed: token("closed"),
      },
      fontFamily: {
        sans: ['"SF Pro Text"', '"SF Pro Display"', "-apple-system", "BlinkMacSystemFont", '"Instrument Sans"', "system-ui", "sans-serif"],
        display: ['"SF Pro Display"', '"SF Pro Text"', "-apple-system", "BlinkMacSystemFont", '"Instrument Sans"', "system-ui", "sans-serif"],
      },
      fontSize: {
        caption: ["13px", { lineHeight: "1.45" }],
        body: ["15px", { lineHeight: "1.45" }],
        "body-lg": ["17px", { lineHeight: "1.45" }],
        title: ["22px", { lineHeight: "1.15", letterSpacing: "-0.01em" }],
        "large-title": ["34px", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
        hero: ["48px", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
      },
      fontWeight: { normal: "400", medium: "500", semibold: "600" },
      borderRadius: { sheet: "22px", row: "14px", control: "10px" },
      boxShadow: { float: "0 8px 30px rgba(0,0,0,0.08)" },
      transitionTimingFunction: { apple: "cubic-bezier(0.32, 0.72, 0, 1)" },
    },
  },
  plugins: [],
};
