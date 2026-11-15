// Tailwind for the site, compiled (scripts/build-css.sh) instead of the Play CDN.
// The two commerce-* pages stay on the CDN while the Shopify App Store review is open.
module.exports = {
  prefix: "tw-",
  content: ["./*.html", "./blog/**/*.html", "./assets/**/*.js", "./index.js"],
};
