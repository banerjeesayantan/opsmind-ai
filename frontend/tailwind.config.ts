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
//
// Spacing uses Tailwind's default scale, which is already 4px-based
// (1 = 4px, 2 = 8px, 3 = 12px, ...) - no override needed, just used
// consistently: 1/1.5 for tight icon gaps, 2.5/3 inside controls, 4/5
// between stacked elements, 6/8 between page sections.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0A0D12",
        surface: "#12161B",
        "surface-raised": "#171C24",
        "surface-hover": "#1D232C",
        "surface-active": "#232A35",
        border: {
          DEFAULT: "#232A35",
          subtle: "#1A2029",
          strong: "#2C3542",
        },
        ink: {
          DEFAULT: "#E8EBF1",
          secondary: "#93A0B4",
          tertiary: "#5B6472",
        },
        accent: {
          DEFAULT: "#4C8DFF",
          hover: "#6BA1FF",
          active: "#3D74D6",
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
        // network path to a font CDN at build time. The stack is ordered so
        // platforms that ship Inter-adjacent system fonts (Segoe UI Variable
        // on Windows, San Francisco on macOS, Roboto on Android/Chrome OS)
        // render close to the intended look. Swapping in Inter itself later
        // is a one-line change here plus a next/font import; nothing else in
        // the app depends on this choice.
        sans: [
          "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: [
          "ui-monospace", "SF Mono", "Cascadia Code", "Segoe UI Mono", "Roboto Mono", "Menlo", "Consolas", "monospace",
        ],
      },
      fontSize: {
        // A tighter scale than Tailwind's default, tuned for a dense,
        // information-heavy tool rather than marketing copy - smaller
        // steps between sizes, tighter line-heights throughout.
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.4rem" }],
        lg: ["1rem", { lineHeight: "1.5rem" }],
        xl: ["1.125rem", { lineHeight: "1.6rem", letterSpacing: "-0.01em" }],
        "2xl": ["1.375rem", { lineHeight: "1.8rem", letterSpacing: "-0.015em" }],
      },
      borderRadius: {
        sm: "5px",
        md: "7px",
        lg: "10px",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
        dropdown: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 12px 32px -8px rgba(0,0,0,0.6)",
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
