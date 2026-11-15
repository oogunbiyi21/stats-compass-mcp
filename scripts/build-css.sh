#!/usr/bin/env bash
# Compile the site's Tailwind classes into css/tailwind.css. Run after changing any page's
# classes; CI checks the committed file is up to date.
set -euo pipefail
cd "$(dirname "$0")/.."
npx --yes tailwindcss@3.4.17 -c tailwind.config.js -i css/tailwind.src.css -o css/tailwind.css --minify
