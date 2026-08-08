import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0b0f17",
        panel: "#131a26",
        edge: "#1f2a3a",
        muted: "#8b9bb4",
      },
    },
  },
  plugins: [],
};

export default config;
