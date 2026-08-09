/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./core/templates/**/*.html",
    "./templates/**/*.html",
    "./core/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        mhw: {
          amber: "#f59e0b",
          slate: "#0f172a",
          bone: "#e7e0d0",
        },
      },
    },
  },
  plugins: [],
};
