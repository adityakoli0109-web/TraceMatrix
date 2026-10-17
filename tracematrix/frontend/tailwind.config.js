/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1c2430",
        muted: "#5b6573",
        line: "#d8dde6",
        paper: "#f4f5f7",
        accent: "#1f4fd6",
        accentHover: "#1a43b5",
        danger: "#b42318",
        warn: "#b54708",
        ok: "#027a48",
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.06)",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "Segoe UI", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
