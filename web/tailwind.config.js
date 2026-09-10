/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx,js,jsx}", "./components/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0b0d10",
          surface: "#11141a",
          raised: "#161a22",
          hover: "#1c2129",
        },
        border: {
          subtle: "#1f2530",
          default: "#262d3a",
          strong: "#3a4252",
        },
        text: {
          primary: "#e8ecf2",
          secondary: "#9aa3b2",
          tertiary: "#646e7f",
          inverse: "#0b0d10",
        },
        accent: {
          green: "#76b900",
          "green-soft": "#8fcf3a",
          "green-dim": "rgba(118, 185, 0, 0.12)",
          amber: "#f5a623",
          "amber-dim": "rgba(245, 166, 35, 0.12)",
          red: "#ef4444",
          "red-dim": "rgba(239, 68, 68, 0.10)",
          blue: "#3b82f6",
          "blue-dim": "rgba(59, 130, 246, 0.12)",
          purple: "#a855f7",
          "purple-dim": "rgba(168, 85, 247, 0.12)",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
        xs: ["0.75rem", { lineHeight: "1.125rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.625rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }],
        "5xl": ["3rem", { lineHeight: "3.25rem" }],
      },
      letterSpacing: {
        tightest: "-0.04em",
        tighter: "-0.025em",
        tight: "-0.015em",
        wide: "0.025em",
        wider: "0.08em",
        widest: "0.16em",
      },
      spacing: {
        "0.5": "0.125rem",
        "1.5": "0.375rem",
        "2.5": "0.625rem",
        "3.5": "0.875rem",
        "18": "4.5rem",
        "22": "5.5rem",
        "30": "7.5rem",
      },
      boxShadow: {
        "raise-sm": "0 1px 2px rgba(0, 0, 0, 0.4)",
        raise: "0 2px 4px rgba(0, 0, 0, 0.5), 0 1px 2px rgba(0, 0, 0, 0.3)",
        "raise-lg":
          "0 8px 16px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.3)",
        "raise-xl":
          "0 16px 32px rgba(0, 0, 0, 0.6), 0 4px 8px rgba(0, 0, 0, 0.4)",
        "accent-glow": "0 0 0 1px rgba(118, 185, 0, 0.3), 0 4px 12px rgba(118, 185, 0, 0.15)",
        "focus-green": "0 0 0 3px rgba(118, 185, 0, 0.15)",
      },
      borderRadius: {
        xs: "4px",
        sm: "6px",
        DEFAULT: "8px",
        md: "10px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
      animation: {
        "fade-in": "fade-in 240ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "scale-in": "scale-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 2s linear infinite",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
