/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/admin/booking/restaurant_dashboard.html',
    './templates/admin/booking/ec_dashboard.html',
  ],
  theme: {
    extend: {},
  },
  corePlugins: {
    preflight: false,
  },
  plugins: [],
}
