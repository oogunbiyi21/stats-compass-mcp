// The promotion's daily chart, as the Stats Compass app draws it: commerce's
// packages/charts promotionDaily (LR.27, LR.30), ported to the browser with the
// same Observable Plot (0.6.17), theme and marks. Daily sales (dark) against what
// was expected without the sale (grey, dotted during it), a normal day's range
// (the band), and the sale's first and last days marked.

const WIDTH = 360;
const HEIGHT = 240;
const MARGIN_RIGHT = 32;
const AXIS_FONT_SIZE = 14;
const FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const COLOUR = { line: "#303030", band: "#cfe6ff", windowEdge: "#d9a400", muted: "#8a8a8a" };
const MIN_LABEL_GAP = 64;
const MONTH_STEPS = [1, 2, 3, 4, 6, 12, 24, 36];

export const CAPTION =
  "Daily sales (dark line) against what we'd expect without the promotion (grey line), based on the store's usual pattern. The grey line is dotted while the promotion ran, where it's an estimate of what would have happened. The shaded band is a normal day's range.";

function monthTickInterval(dates, marginLeft) {
  const times = dates.map((d) => d.getTime());
  const spanMonths = Math.max((Math.max(...times) - Math.min(...times)) / (30.44 * 86_400_000), 1);
  const plotWidth = WIDTH - marginLeft - MARGIN_RIGHT;
  const step = MONTH_STEPS.find((k) => (k * plotWidth) / spanMonths >= MIN_LABEL_GAP) ?? 36;
  if (step === 1) return "month";
  if (step % 12 === 0) return step === 12 ? "year" : `${step / 12} years`;
  return `${step} months`;
}

const monthYear = (d) => new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(d);

function compactMoney(symbol) {
  // The app's money(…, {compact: true}): "£1k", "£2.5k", with a true minus.
  const f = new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 });
  return (v) => (v < 0 ? "−" : "") + symbol + f.format(Math.abs(v));
}

/** points: [{date: "2026-11-27", actual, expected, low, high, in_promotion}] */
export function promotionDaily(Plot, points, { label, symbol }) {
  const days = points.map((p) => ({ ...p, date: new Date(`${p.date}T12:00:00Z`), low: Math.max(0, p.low) }));
  const first = days.findIndex((d) => d.in_promotion);
  const last = days.findLastIndex((d) => d.in_promotion);
  const part = (i) => (first === -1 || i < first ? "expected-before" : i > last ? "expected-after" : "expected-in");
  const expected = (d, series) => ({ date: d.date, value: d.expected, series, colour: COLOUR.muted });
  const lines = [
    ...days.flatMap((d) => (d.actual === null || d.actual === undefined ? [] : [{ date: d.date, value: d.actual, series: "actual", colour: COLOUR.line }])),
    ...days.map((d, i) => expected(d, part(i))).filter((e) => e.series === "expected-before"),
    ...(first === -1 ? [] : days.slice(Math.max(0, first - 1), last + 2).map((d) => expected(d, "expected-in"))),
    ...days.map((d, i) => expected(d, part(i))).filter((e) => e.series === "expected-after"),
  ];
  const start = first === -1 ? null : new Date(days[first].date.getTime() - 43_200_000);
  const end = first === -1 ? null : new Date(days[last].date.getTime() + 43_200_000);
  const svg = Plot.plot({
    width: WIDTH,
    height: HEIGHT,
    marginRight: MARGIN_RIGHT,
    marginLeft: 56,
    marginTop: 28,
    style: "background: transparent; overflow: visible;",
    x: { type: "utc" },
    y: { nice: true, zero: true },
    color: { type: "identity" },
    marks: [
      Plot.areaY(days, { x: "date", y1: "low", y2: "high", fill: COLOUR.band }),
      ...(start ? [Plot.ruleX([start, end], { stroke: COLOUR.windowEdge, strokeWidth: 1 })] : []),
      Plot.line(lines, {
        x: "date", y: "value", z: "series", stroke: "colour", strokeWidth: 1.5,
        render(index, scales, values, dimensions, context, next) {
          const g = next?.(index, scales, values, dimensions, context);
          const order = [...new Set(Array.from(index, (i) => String(values.z?.[i])))];
          const at = order.indexOf("expected-in");
          const path = g?.querySelectorAll("path")[at];
          if (at !== -1 && path) path.setAttribute("stroke-dasharray", "1.5 2.5");
          return g ?? null;
        },
      }),
      Plot.text([label], {
        frameAnchor: "top-left", textAnchor: "start", lineAnchor: "bottom", dx: -48, dy: -6,
        text: (d) => d, fontSize: AXIS_FONT_SIZE, fontWeight: 600, fill: COLOUR.line,
      }),
      Plot.axisX({ ticks: monthTickInterval(days.map((d) => d.date), 56), tickFormat: monthYear, fontSize: AXIS_FONT_SIZE, tickSize: 0 }),
      Plot.axisY({ ticks: 3, tickFormat: compactMoney(symbol), fontSize: AXIS_FONT_SIZE, tickSize: 0, label: null }),
    ],
  });
  svg.setAttribute("font-size", String(AXIS_FONT_SIZE));
  svg.setAttribute("font-family", FONT_FAMILY);
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.style.width = "100%";
  svg.style.height = "auto";
  return svg;
}
