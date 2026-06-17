import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "monospace"],
      },
      colors: {
        ink: {
          950: "#070a0f",
          900: "#0a0e15",
          850: "#0e131c",
          800: "#131a25",
          700: "#1b2433",
          600: "#27324428",
        },
        sev: {
          p1: "#ff3b3b",
          p2: "#ff9f1c",
          p3: "#3a9bff",
          p4: "#3ad29f",
        },
        beacon: "#ffb02e",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,59,59,.4), 0 0 30px -4px rgba(255,59,59,.45)",
        panel: "0 1px 0 0 rgba(255,255,255,.04) inset, 0 20px 50px -20px rgba(0,0,0,.7)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px) scale(.99)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        pulseGlow: {
          "0%,100%": { boxShadow: "0 0 0 1px rgba(255,59,59,.35), 0 0 18px -6px rgba(255,59,59,.5)" },
          "50%": { boxShadow: "0 0 0 1px rgba(255,59,59,.7), 0 0 34px -2px rgba(255,59,59,.8)" },
        },
        sweep: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(220%)" },
        },
        blink: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".25" } },
      },
      animation: {
        rise: "rise .45s cubic-bezier(.2,.7,.2,1) both",
        pulseGlow: "pulseGlow 2.4s ease-in-out infinite",
        sweep: "sweep 2.2s ease-in-out infinite",
        blink: "blink 1.3s steps(2,end) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
