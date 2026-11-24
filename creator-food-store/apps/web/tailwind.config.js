/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0a0a0a",
        cream: "#faf9f7",
        muted: "#6b6b6b",
        border: "#e8e6e3",
        accent: "#1B7F5C",
        brand: {
          DEFAULT: "#1B7F5C",
          light: "#A8E6CF",
          dark: "#145C43",
          muted: "#E8F5EF",
        },
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #1B7F5C 0%, #2D9B6F 50%, #145C43 100%)",
        "hero-pattern":
          "radial-gradient(circle at 20% 80%, rgba(27,127,92,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(168,230,207,0.15) 0%, transparent 50%)",
      },
      boxShadow: {
        card: "0 1px 3px rgba(10,10,10,0.04), 0 8px 24px rgba(10,10,10,0.06)",
        "card-hover": "0 4px 12px rgba(10,10,10,0.08), 0 16px 40px rgba(27,127,92,0.12)",
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["DM Serif Display", "Georgia", "serif"],
      },
      letterSpacing: {
        widest: "0.2em",
      },
    },
  },
  plugins: [],
};
