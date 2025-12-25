/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/web/templates/**/*.html",
    "./app/web/static/**/*.js",
  ],
  theme: {
    extend: {
      borderRadius: {
        theme: "var(--radius)",
      },
    },
  },
  plugins: [],
};
