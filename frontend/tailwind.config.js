/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      keyframes: {
        catNod: {
          "0%, 100%": { transform: "translateY(0)" },
          "25%": { transform: "translateY(7px)" },
          "50%": { transform: "translateY(-1px)" },
          "75%": { transform: "translateY(4px)" },
        },
      },
      animation: {
        "cat-nod": "catNod 0.8s cubic-bezier(.45,.05,.55,.95) infinite",
      },
    },
  },
  plugins: [],
};
