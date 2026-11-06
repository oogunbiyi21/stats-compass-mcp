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
    update();
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

function update() {
  $("check").disabled = !(ready && $("file").files.length && $("start").value && $("end").value);
}
for (const id of ["file", "start", "end"]) $(id).addEventListener("input", update);

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

function suggest(sales) {
  for (const row of $("others").querySelectorAll("[data-found]")) row.remove();
  for (const s of sales) addOther(s.start, s.end, true);
  showFound();
}

// A found sale overlapping the dates being checked is that sale: it's hidden, and not sent.
function showFound() {
  const start = $("start").value;
  const end = $("end").value || start;
  let shown = 0;
  for (const row of $("others").querySelectorAll("[data-found]")) {
    const a = row.querySelector("[data-start]").value;
    const b = row.querySelector("[data-end]").value || a;
    row.hidden = Boolean(start && a <= end && b >= start);
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
