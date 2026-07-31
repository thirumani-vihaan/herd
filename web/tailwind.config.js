/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F5F2EB",
        card: "#FCFBF8",
        ink: "#12110C",
        muted: "#57544A",
        faint: "#8B8779",
        rule: "#DFDBCC",
        rulesoft: "#EBE7DA",
        false: "#A32017",
        misleading: "#A56A00",
        true: "#14624A",
        unverified: "#55524A",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Instrument Serif", "Iowan Old Style", "Georgia", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Cascadia Code", "Consolas", "monospace"],
      },
      boxShadow: {
        plate: "0 1px 0 rgba(18,17,12,.04), 0 18px 40px -32px rgba(18,17,12,.45)",
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
