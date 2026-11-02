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

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("error").hidden = true;
  $("result").hidden = true;
  $("check").disabled = true;
  $("check").textContent = "Checking…";
  const csv = await $("file").files[0].text();
  const margin = $("margin").value === "" ? null : Number($("margin").value);
  // Today's date here: its row in the export is a day still under way.
  const today = new Date().toLocaleDateString("en-CA");
  worker.postMessage({ csv, start: $("start").value, end: $("end").value, margin, currency: $("currency").value, name: $("name").value.trim(), today });
});

// The early-access list: the visitor's email and consent, posted to the list's endpoint
// (hosted). Only this form sends anything, and only when the visitor joins.
$("list-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!$("list-consent").checked) return;
  $("list-error").hidden = true;
  $("list-join").disabled = true;
  try {
    const response = await fetch(form.dataset.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: $("list-email").value.trim(), consent: true, consent_version: form.dataset.consentVersion }),
    });
    if (!response.ok) throw new Error(String(response.status));
    form.hidden = true;
    $("list-done").hidden = false;
  } catch {
    $("list-error").hidden = false;
    $("list-join").disabled = false;
  }
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
  $("signup").hidden = !$("list-form").dataset.endpoint;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}
