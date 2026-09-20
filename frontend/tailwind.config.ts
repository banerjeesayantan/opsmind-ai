import type { Config } from "tailwindcss";

// OpsMind design tokens.
//
// This is an incident-response tool for on-call SREs, not a marketing
// site - dark-first (the environment it's actually used in), a single
// restrained signal-blue accent for actions/focus, and a distinct
// semantic scale for severity/risk that never collides with the accent.
// Monospace is reserved for genuinely tabular/technical content
// (incident ids, timestamps, service names, JSON parameters) rather than
// used decoratively on labels.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0A0D12",
        surface: "#12161B",
        "surface-raised": "#171C24",
        "surface-hover": "#1D232C",
        border: {
          DEFAULT: "#232A35",
          subtle: "#1A2029",
        },
        ink: {
          DEFAULT: "#E8EBF1",
          secondary: "#93A0B4",
          tertiary: "#5B6472",
        },
        accent: {
          DEFAULT: "#4C8DFF",
          hover: "#6BA1FF",
          muted: "#1C2A45",
        },
        severity: {
          critical: "#E5484D",
          high: "#F5A623",
          medium: "#5B8DEF",
          low: "#38B27B",
        },
        risk: {
          high: "#E5484D",
          medium: "#F5A623",
          low: "#38B27B",
        },
        status: {
          new: "#93A0B4",
          progress: "#4C8DFF",
          waiting: "#F5A623",
          resolved: "#38B27B",
          unresolved: "#E5484D",
        },
      },
      fontFamily: {
        // Native system stacks, not a fetched webfont - this sandbox has no
        // network path to a font CDN at build time. Swapping in a real
        // brand typeface (e.g. IBM Plex Sans/Mono, which the visual design
        // was planned around) later is a one-line change here plus a
        // next/font import; nothing else in the app depends on this choice.
        sans: [
          "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: [
          "ui-monospace", "SF Mono", "Cascadia Code", "Segoe UI Mono", "Roboto Mono", "Menlo", "Consolas", "monospace",
        ],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in 150ms ease-out",
        "slide-up": "slide-up 200ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
