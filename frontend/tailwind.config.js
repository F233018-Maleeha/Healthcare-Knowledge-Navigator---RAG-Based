/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Every one of these maps to a CSS variable in theme/tokens.css.
        // Change the look of the whole app there, not here.
        paper: "var(--color-paper)",
        panel: "var(--color-panel)",
        ink: "var(--color-ink)",
        "ink-soft": "var(--color-ink-soft)",
        line: "var(--color-line)",
        teal: "var(--color-teal)",
        "teal-dim": "var(--color-teal-dim)",
        amber: "var(--color-amber)",
        "amber-dim": "var(--color-amber-dim)",
        green: "var(--color-green)",
        "green-dim": "var(--color-green-dim)",
        red: "var(--color-red)",
        "red-dim": "var(--color-red-dim)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        mono: "var(--font-mono)",
      },
    },
  },
  plugins: [],
};
