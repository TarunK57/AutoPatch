import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        sentry: {
          bg: "#0a0c10",
          card: "#161922",
          cardHover: "#1f2330",
          border: "#262c3a",
          subtle: "#1c212c",
          purple: "#7c3aed",
          purpleHover: "#6d28d9",
          red: "#f85149",
          orange: "#f0883e",
          amber: "#d29922",
          green: "#3fb950",
          blue: "#58a6ff",
          muted: "#8b949e",
        },
        slate: {
          850: "#131722",
          900: "#0f1117",
          950: "#0a0c10",
        },
      },
      fontFamily: {
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
    },
  },
  plugins: [],
};

export default config;
