/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}", // This tells Tailwind to scan all JS/JSX/TS/TSX files in your src/ directory
    "./public/index.html",       // Include your main HTML file if you use Tailwind classes there
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}