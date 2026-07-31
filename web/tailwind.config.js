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
          "0%": { opacity: "0", transform: "translateY(12px)" },
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
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        scan: {
          "0%": { transform: "translateY(-200%)" },
          "100%": { transform: "translateY(200%)" },
        },
        "stamp-in": {
          "0%": { opacity: "0", transform: "scale(1.5) rotate(-5deg)" },
          "100%": { opacity: "1", transform: "scale(1) rotate(0deg)" },
        },
        "type-reveal": {
          "0%": { clipPath: "inset(0 100% 0 0)" },
          "100%": { clipPath: "inset(0 0 0 0)" },
        },
        fadeIn: {
          "0%": { opacity: "0", filter: "blur(4px)" },
          "100%": { opacity: "1", filter: "blur(0)" },
        },
        "tracking-in": {
          "0%": { opacity: "0", letterSpacing: "-0.1em", filter: "blur(8px)" },
          "100%": { opacity: "1", letterSpacing: "normal", filter: "blur(0)" },
        },
        "slide-in-left": {
          "0%": { opacity: "0", transform: "translateX(-40px) scale(0.95)", filter: "blur(4px)" },
          "100%": { opacity: "1", transform: "translateX(0) scale(1)", filter: "blur(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(40px) scale(0.95)", filter: "blur(4px)" },
          "100%": { opacity: "1", transform: "translateX(0) scale(1)", filter: "blur(0)" },
        },
      },
      animation: {
        rise: "rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        sweep: "sweep 0.7s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 2.5s linear infinite",
        "pulse-soft": "pulse-soft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scan": "scan 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "stamp-in": "stamp-in 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) both",
        "type-reveal": "type-reveal 1.5s cubic-bezier(0.4, 0, 0.2, 1) both",
        "fade-in": "fadeIn 0.5s ease-out both",
        "tracking-in": "tracking-in 1.2s cubic-bezier(0.4, 0, 0.2, 1) both",
        "slide-left": "slide-in-left 1.5s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-right": "slide-in-right 1.5s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
};
