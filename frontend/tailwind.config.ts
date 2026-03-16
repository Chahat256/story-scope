import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f8f6f1",
          100: "#ede9df",
          200: "#d9d0bc",
          300: "#c2b494",
          400: "#a8946b",
          500: "#8f7a52",
          600: "#736143",
          700: "#5a4b36",
          800: "#3d3325",
          900: "#231d16",
          950: "#120f0b",
        },
        parchment: "#faf8f3",
        "deep-ink": "#1a1208",
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "Times", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
