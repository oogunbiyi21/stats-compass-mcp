"""The sale checker's step pages: one tiny page per step in checker-steps/, for counting.

Cloudflare Web Analytics counts page views and nothing else, so each step of the checker
(the sample tried, a file chosen, a result shown, ...) is a page view of its own page,
which the checker loads in a hidden frame (assets/checker/page.js, step()). Each page
carries only Cloudflare's beacon, is noindex and stays out of the sitemap. The step's
name is all it records: never a figure, a file name or an email.

The names come from STEPS in assets/checker/page.js. Run this after changing them:
python scripts/make_checker_steps.py  (writes checker-steps/<name>.html, removes any others)
"""

import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PAGE = """<!doctype html>
<html lang="en">

<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex" />
    <title>Sale checker step: {name}</title>
    <!-- One step of the sale checker, counted as a page view: made by scripts/make_checker_steps.py. -->
    <!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{{"token": "5acfd6a4cd23427cbea5c6c689599dfc"}}'></script><!-- End Cloudflare Web Analytics -->
</head>

<body></body>

</html>
"""


def steps() -> list[str]:
    page = (SITE / "assets" / "checker" / "page.js").read_text()
    listed = re.search(r"const STEPS = new Set\(\[(.*?)\]\)", page, re.S).group(1)
    names = re.findall(r'"([^"]*)"', listed)
    for name in names:
        if not re.fullmatch(r"[a-z]+(-[a-z]+)*", name):
            raise SystemExit(f"Not a step name: {name!r} (lowercase words and hyphens only)")
    return names


def main() -> None:
    out = SITE / "checker-steps"
    out.mkdir(exist_ok=True)
    names = steps()
    for old in out.glob("*.html"):
        if old.stem not in names:
            old.unlink()
    for name in names:
        (out / f"{name}.html").write_text(PAGE.format(name=name))
    print(f"{len(names)} step pages in {out.relative_to(SITE)}/")


if __name__ == "__main__":
    main()
