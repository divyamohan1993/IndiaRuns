import type { Config } from "tailwindcss";

// ATLAS design system — DESIGN §7.2 ("mission control for talent").
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Core palette (locked by §7.2)
        navy: {
          DEFAULT: "#0A0E1A", // space-navy — base canvas
          900: "#0A0E1A",
          800: "#0D1424",
          700: "#121A2E",
          600: "#1A2440",
        },
        gold: {
          DEFAULT: "#F5C04E", // signal-gold — fit / must-haves
          dim: "#8C7330",
        },
        cyan: {
          DEFAULT: "#5BE0E6", // behavioral-cyan
          dim: "#2E7478",
        },
        trap: {
          DEFAULT: "#FF5C6C", // trap-red — real flags only
          dim: "#7A2E36",
        },
        ink: {
          DEFAULT: "#E6EAF2", // primary text
          mute: "#9AA4BC", // secondary text
          faint: "#5B6480", // tertiary / disabled
        },
        glass: {
          border: "rgba(230,234,242,0.10)",
          fill: "rgba(255,255,255,0.04)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.45)",
        glow: "0 0 24px rgba(245,192,78,0.18)",
        glowCyan: "0 0 24px rgba(91,224,230,0.18)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-pill": {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease-out both",
        "pulse-pill": "pulse-pill 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
