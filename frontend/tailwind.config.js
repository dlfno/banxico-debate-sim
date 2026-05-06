/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
      },
      colors: {
        // Paleta institucional Banxico: azul marino profundo del banner + variantes
        banxico: {
          50: "#eef2f8",
          100: "#d6dfee",
          200: "#a8b8d4",
          500: "#2a4373",
          600: "#1a3057",
          700: "#14284a",
          800: "#0c1d3a",
          900: "#08152b",
        },
        // Acento institucional (teal/verde azulado del menú y los íconos)
        accent: {
          50: "#e6f1f1",
          100: "#cce4e4",
          500: "#1d7a7a",
          600: "#15605f",
          700: "#0f4847",
        },
        // Tonos cálidos: tarjetas indicadores y fondos suaves
        sand: {
          50: "#faf6ee",
          100: "#f4ede0",
          200: "#e8dfc8",
          300: "#d6c9a4",
        },
        gold: {
          500: "#b88a44",
          600: "#9a7236",
        },
      },
      boxShadow: {
        institutional:
          "0 1px 0 rgba(20,40,74,0.04), 0 4px 14px -6px rgba(20,40,74,0.12)",
      },
    },
  },
  plugins: [],
};
