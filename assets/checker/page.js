// The checker page: starts the checker (worker.js) as soon as the page opens,
// reads the chosen file here in the browser, and shows the result. The file's
// text goes to the worker by postMessage; it is never sent over the network.
import { CAPTION, promotionDaily } from "./chart.js";

const $ = (id) => document.getElementById(id);
const worker = new Worker("/assets/checker/worker.js");
let ready = false;

worker.onmessage = ({ data }) => {
  if (data.type === "progress") {
    $("status").textContent = `Getting the checker ready… ${data.loadedMb} of about ${data.totalMb} MB`;
  } else if (data.type === "ready") {
    ready = true;
    $("status").textContent = "The checker is ready.";
    $("first-visit").hidden = true;
    $("status").classList.add("tw-text-green-700");
    $("hint").hidden = true;
    findSales();
  } else if (data.type === "found") {
    suggest(data.sales);
  } else if (data.type === "result") {
    show(data.data);
  } else if (data.type === "error") {
    $("check").disabled = false;
    $("check").textContent = "Check my sale";
    $("error").textContent = data.message;
    $("error").hidden = false;
  }
};

// What's still missing before a check, said on the click rather than by a greyed-out button.
function missing() {
  if (!ready) return "The checker is still getting ready: it'll take a moment.";
  if (!$("file").files.length) return "Choose your report first.";
  if (!$("start").value || !$("end").value) return "Choose which sale to check, or enter its first and last day.";
  return null;
}
for (const id of ["file", "start", "end"]) $(id).addEventListener("input", () => { $("hint").hidden = true; });

// Dates as the app writes them: "15–21 June 2026", "14 May – 3 June 2026".
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const parts = (iso) => iso.split("-").map(Number);
function span(a, b) {
  const [ya, ma, da] = parts(a);
  const [yb, mb, db] = parts(b);
  const last = `${db} ${MONTHS[mb - 1]} ${yb}`;
  if (a === b) return last;
  if (ya === yb && ma === mb) return `${da}–${last}`;
  if (ya === yb) return `${da} ${MONTHS[ma - 1]} – ${last}`;
  return `${da} ${MONTHS[ma - 1]} ${ya} – ${last}`;
}

// Other sales in the period: each a row of two dates, left out of the comparison.
function addOther(start = "", end = "", found = false) {
  const row = $("other-row").content.firstElementChild.cloneNode(true);
  row.querySelector("[data-start]").value = start;
  row.querySelector("[data-end]").value = end;
  if (found) row.dataset.found = "";
  row.querySelector("[data-remove]").addEventListener("click", () => {
    row.remove();
    showFound();
  });
  $("others").append(row);
  return row;
}
$("add-other").addEventListener("click", () => addOther().querySelector("[data-start]").focus());

// When a report is chosen, the sales its discounts show are suggested as other sales:
// the merchant removes any that weren't. The sale being checked is never one of them.
async function findSales() {
  if (!ready || !$("file").files.length) return;
  const csv = await $("file").files[0].text();
  worker.postMessage({ type: "find", csv, today: new Date().toLocaleDateString("en-CA") });
}
$("file").addEventListener("input", findSales);

let found = [];

function suggest(sales) {
  found = sales;
  for (const row of $("others").querySelectorAll("[data-found]")) row.remove();
  for (const s of sales) addOther(s.start, s.end, true);
  offerChoices();
  showFound();
}

// The found sales are offered as the sale to check. The one chosen fills the dates
// (still editable); the rest stay other sales. A lone sale is chosen for the merchant.
function offerChoices() {
  const list = $("choice-list");
  list.replaceChildren();
  // Dates and a name filled from a sale in an earlier report don't carry over to this one.
  const kept = found.some((s) => s.start === $("start").value && s.end === $("end").value);
  if ("found" in $("start").dataset && !kept) {
    $("start").value = "";
    $("end").value = "";
    delete $("start").dataset.found;
    if ("auto" in $("name").dataset) $("name").value = "";
    delete $("name").dataset.auto;
  }
  $("choices").hidden = found.length === 0;
  if (!found.length) {
    $("dates").hidden = false;
    return;
  }
  const add = (value, text, action) => {
    const row = $("choice-row").content.firstElementChild.cloneNode(true);
    row.querySelector("input").value = value;
    row.querySelector("[data-span]").textContent = text;
    row.querySelector("[data-action]").textContent = action;
    list.append(row);
  };
  found.forEach((s, i) => add(String(i), span(s.start, s.end), " · Check this one"));
  add("other", "A different sale or period", "");
  const same = found.findIndex((s) => s.start === $("start").value && s.end === $("end").value);
  if (same >= 0) select(String(same));
  else if (found.length === 1 && !$("start").value && !$("end").value) select("0");
  else $("dates").hidden = !($("start").value || $("end").value);
  markChosen();
}

function select(value) {
  $("choice-list").querySelector(`input[value="${value}"]`).checked = true;
  choose(value);
}

function choose(value) {
  if (value === "other") {
    // Dates and a name that came from a found sale give way to the merchant's own.
    if ("found" in $("start").dataset) {
      $("start").value = "";
      $("end").value = "";
    }
    if ("auto" in $("name").dataset) $("name").value = "";
    delete $("start").dataset.found;
    delete $("name").dataset.auto;
  } else {
    const s = found[Number(value)];
    $("start").value = s.start;
    $("end").value = s.end;
    $("start").dataset.found = "";
    if (!$("name").value || "auto" in $("name").dataset) {
      const [, m, d] = parts(s.start);
      $("name").value = `Sale from ${d} ${MONTHS[m - 1]}`;
      $("name").dataset.auto = "";
    }
  }
  $("dates").hidden = false;
  $("hint").hidden = true;
  markChosen();
  showFound();
}
$("choice-list").addEventListener("change", (event) => choose(event.target.value));
for (const id of ["start", "end"]) $(id).addEventListener("input", () => delete $("start").dataset.found);
$("name").addEventListener("input", () => delete $("name").dataset.auto);

function markChosen() {
  for (const row of $("choice-list").children) {
    const on = row.querySelector("input").checked;
    row.classList.toggle("tw-border-black", on);
    row.classList.toggle("tw-bg-gray-50", on);
    row.classList.toggle("tw-border-gray-300", !on);
  }
}

// A found sale overlapping the dates being checked is that sale: it's hidden, and not sent.
// Until the sale to check is known, found sales are only offered as choices.
function showFound() {
  const start = $("start").value;
  const end = $("end").value || start;
  let shown = 0;
  for (const row of $("others").querySelectorAll("[data-found]")) {
    const a = row.querySelector("[data-start]").value;
    const b = row.querySelector("[data-end]").value || a;
    row.hidden = !start || (a <= end && b >= start);
    row.style.display = row.hidden ? "none" : "";  // the row's grid class would otherwise outrank [hidden]
    if (!row.hidden) shown += 1;
  }
  $("found-note").hidden = shown === 0;
}
for (const id of ["start", "end"]) $(id).addEventListener("input", showFound);

function otherSales() {
  const rows = [...$("others").children].filter((row) => !row.hidden).map((row) => ({
    start: row.querySelector("[data-start]").value,
    end: row.querySelector("[data-end]").value,
    auto: "found" in row.dataset,
  }));
  if (rows.some((r) => !r.start !== !r.end)) throw new Error("Give each other sale a first and last day, or remove it.");
  return rows.filter((r) => r.start && r.end);
}

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("error").hidden = true;
  const needs = missing();
  $("hint").textContent = needs || "";
  $("hint").hidden = !needs;
  if (needs) return;
  let others;
  try {
    others = otherSales();
  } catch (err) {
    $("error").textContent = err.message;
    $("error").hidden = false;
    return;
  }
  $("result").hidden = true;
  $("check").disabled = true;
  $("check").textContent = "Checking…";
  const csv = await $("file").files[0].text();
  const margin = $("margin").value === "" ? null : Number($("margin").value);
  // Today's date here: its row in the export is a day still under way.
  const today = new Date().toLocaleDateString("en-CA");
  worker.postMessage({ csv, start: $("start").value, end: $("end").value, margin, currency: $("currency").value, name: $("name").value.trim(), today, others });
});

// The early-access list: the form posts the visitor's email to Buttondown in a new tab
// (the browser checks the email and the consent box first), and this page keeps the result.
// Only this form sends anything, and only when the visitor joins.
$("list-form").addEventListener("submit", (event) => {
  const form = event.currentTarget;
  setTimeout(() => {
    form.hidden = true;
    $("list-done").hidden = false;
  });
});

const BADGE = {
  "real change": "tw-bg-blue-100 tw-text-blue-900",
  expected: "tw-bg-gray-100 tw-text-gray-800",
  noise: "tw-bg-gray-100 tw-text-gray-800",
  insufficient: "tw-bg-amber-100 tw-text-amber-900",
};

function show(r) {
  $("check").disabled = false;
  $("check").textContent = "Check my sale";
  // The headline: did it make money? Break-even against the likely range of what it brought.
  const PROFIT = { yes: "tw-text-green-800", no: "tw-text-red-800", unclear: "tw-text-gray-900" };
  $("profit-box").hidden = !r.profit;
  if (r.profit) {
    $("profit").textContent = r.profit.headline;
    $("profit").className = `tw-text-3xl tw-font-semibold tw-leading-tight ${PROFIT[r.profit.call]}`;
    $("profit-sub").textContent = r.profit.sub;
  }
  $("verdict").textContent = r.label;
  $("verdict").className = `tw-inline-block tw-rounded-full tw-px-3 tw-py-1 tw-text-sm tw-font-semibold ${BADGE[r.verdict] || BADGE.expected}`;
  // The dip after the sale is in the summary when it's beyond the usual; otherwise say it plainly.
  $("summary").textContent = r.after && !r.summary.includes(r.after) ? `${r.summary} ${r.after}` : r.summary;
  const b = r.break_even;
  $("needed").textContent = r.break_even_headline || "";
  $("needed").hidden = !r.break_even_headline;
  $("be-sentence").textContent = b ? b.sentence : "";
  $("be-discount").textContent = b && b.max_discount ? b.max_discount : "";
  $("no-margin").hidden = !(r.verdict !== "insufficient" && !b && $("margin").value === "");
  $("chart").replaceChildren();
  $("caption").hidden = true;
  if (r.chart && r.chart.length) {
    $("chart").append(promotionDaily(window.Plot, r.chart, { label: r.name, symbol: $("currency").value }));
    $("caption").textContent = CAPTION;
    $("caption").hidden = false;
  }
  $("notes").replaceChildren(...(r.warnings || []).map((w) => Object.assign(document.createElement("li"), { textContent: w })));
  $("notes-box").hidden = !(r.warnings && r.warnings.length);
  $("result").hidden = false;
  $("signup").hidden = false;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}
