/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        banxico: {
          50: "#f1f7f3",
          100: "#dceee2",
          500: "#1f7a4d",
          600: "#196239",
          700: "#114a2a",
        },
      },
    },
  },
  plugins: [],
};
