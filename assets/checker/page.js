// The checker page: starts the calculator (worker.js) as soon as the page opens,
// reads the chosen file here in the browser, and shows the result. The file's
// text goes to the worker by postMessage; it is never sent over the network.
import { CAPTION, promotionDaily } from "./chart.js";

const $ = (id) => document.getElementById(id);
const worker = new Worker("/assets/checker/worker.js");
let ready = false;

worker.onmessage = ({ data }) => {
  if (data.type === "progress") {
    $("status").textContent = `Getting the calculator ready… ${data.loadedMb} of about ${data.totalMb} MB`;
  } else if (data.type === "ready") {
    ready = true;
    $("status").textContent = "The calculator is ready. You can disconnect from the internet now if you like: your file stays on this computer.";
    $("status").classList.add("tw-text-green-700");
    update();
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
$("add-other").addEventListener("click", () => {
  const row = $("other-row").content.firstElementChild.cloneNode(true);
  row.querySelector("[data-remove]").addEventListener("click", () => row.remove());
  $("others").append(row);
  row.querySelector("[data-start]").focus();
});

function otherSales() {
  const rows = [...$("others").children].map((row) => ({
    start: row.querySelector("[data-start]").value,
    end: row.querySelector("[data-end]").value,
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
