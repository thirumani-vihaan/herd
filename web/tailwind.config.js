/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FDFDFC",
        card: "#FFFFFF",
        ink: "#131416",
        muted: "#5C5F66",
        faint: "#8E9199",
        rule: "#E2E3E6",
        rulesoft: "#EFEFF1",
        false: "#C0322A",
        misleading: "#9A6510",
        true: "#0E7150",
        unverified: "#5C5F66",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["IBM Plex Sans", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "Cascadia Code", "Consolas", "monospace"],
      },
      boxShadow: {
        plate: "none",
      },
      letterSpacing: {
        tightest: "-0.045em",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        sweep: {
          "0%": { transform: "scaleX(0)" },
          "100%": { transform: "scaleX(1)" },
        },
        draw: {
          "0%": { strokeDashoffset: "1" },
          "100%": { strokeDashoffset: "0" },
        },
      },
      animation: {
        rise: "rise .5s cubic-bezier(.2,.7,.2,1) both",
        sweep: "sweep .7s cubic-bezier(.2,.7,.2,1) both",
      },
    },
  },
  plugins: [],
};
