// The checker page: starts the checker (worker.js) as the page opens, reads the chosen file
// here in the browser, then shows the steps that need it and the result.
// The file's text goes to the worker by postMessage; it is never sent over the network.
import { CAPTION, promotionDaily } from "./chart.js";

const $ = (id) => document.getElementById(id);
let worker = null;
let ready = false;

// Step counting, with Cloudflare Web Analytics and nothing else: each step is a page view of a
// tiny page in /checker-steps/ that carries only Cloudflare's beacon, loaded in a hidden frame.
// The step's name is all it says, never a figure, a file name or an email. The names are this
// fixed list: scripts/make_checker_steps.py makes their pages, and tests/test_sale_checker.py
// checks each is plain words.
const STEPS = new Set([
  "sample", "file", "check", "pdf", "email",
  "file-error-not-daily", "file-error-not-report", "file-error-bad-days", "file-error-no-days", "file-error-other",
  "result-made", "result-lost", "result-unclear", "result-insufficient",
]);
function step(name) {
  if (!STEPS.has(name)) return;
  const frame = document.createElement("iframe");
  frame.src = `/checker-steps/${name}`;  // set before the frame is added, so Back doesn't stop on it
  frame.hidden = true;
  frame.tabIndex = -1;
  frame.setAttribute("aria-hidden", "true");
  // The beacon reports just after the frame's load: give it time, then tidy up.
  frame.addEventListener("load", () => setTimeout(() => frame.remove(), 10_000));
  document.body.append(frame);
}

// About 32 MB the first time, fetched quietly while the visitor exports their report. With
// Save-Data on, it waits until a file or the sample is chosen.
function startChecker() {
  if (worker) return;
  worker = new Worker("/assets/checker/worker.js");
  worker.onmessage = onMessage;
}
const saveData = Boolean(navigator.connection && navigator.connection.saveData);
if (!saveData) startChecker();

// Progress shows only if the visitor is waiting for it: a file chosen before the checker is ready.
let waiting = false;
function wait() {
  startChecker();
  if (ready) return;
  waiting = true;
  $("status").hidden = false;
}

function onMessage({ data }) {
  if (data.type === "progress") {
    $("status").textContent = `Getting the calculator ready: ${data.loadedMb} of about ${data.totalMb} MB…`;
  } else if (data.type === "ready") {
    ready = true;
    $("status").textContent = "Reading your file…";
    findSales();
  } else if (data.type === "found") {
    $("status").hidden = true;
    loaded(data.sales);
  } else if (data.type === "file-error") {
    $("status").hidden = true;
    fileError(data.message, data.code);
  } else if (data.type === "discount") {
    // Only for the dates still chosen: the merchant may have moved on.
    if (data.start === $("start").value && data.end === $("end").value) showCutHint(!data.found);
  } else if (data.type === "result") {
    show(data.data);
  } else if (data.type === "error") {
    if (!ready) {
      $("status").hidden = !waiting;
      $("status").textContent = data.message;
    } else showError(data.message);
  }
}

// A report that can't be used is said at once, under the file box, and the steps stay hidden.
function fileError(message, code) {
  $("form").hidden = true;
  $("file-error-text").textContent = message;
  $("file-error").hidden = false;
  step(STEPS.has(`file-error-${code}`) ? `file-error-${code}` : "file-error-other");
}

// Errors from a check: one plain sentence and "Try again". The details, when there are any, are in the console.
function showError(message) {
  $("check").disabled = false;
  $("check").textContent = "Check my sale";
  $("error-text").textContent = message;
  $("error").hidden = false;
}
$("retry").addEventListener("click", () => {
  $("error").hidden = true;
  $("form").requestSubmit();
});

// What's wrong or missing before a check, naming the field, said on the click rather than by
// a greyed-out button. Nothing goes to the checker until it's all valid.
function invalid() {
  if (!$("file").files.length) return { message: "Choose your report first." };
  if (!ready) return { message: "The calculator is still getting ready: it'll take a moment." };
  if (!$("start").value || !$("end").value) return { message: "Choose which sale to check, or enter its first and last day." };
  if ($("end").value < $("start").value) return { message: "The sale's last day is before its first day.", field: "end" };
  const margin = $("margin");
  if (margin.validity.badInput || margin.value.trim() === "" || !(Number(margin.value) >= 1 && Number(margin.value) <= 99)) {
    return { message: "Enter your margin: a number from 1 to 99.", field: "margin" };
  }
  const ads = $("ads");
  if (ads.validity.badInput || (ads.value !== "" && !(Number(ads.value) >= 0))) {
    return { message: `Enter the ad spend as an amount in ${$("currency").value}, or leave it blank.`, field: "ads" };
  }
  const cut = $("cut");
  if (cut.validity.badInput || (cut.value !== "" && !(Number(cut.value) >= 0 && Number(cut.value) <= 95))) {
    $("more").open = true;
    return { message: "Enter the price cut as a number from 0 to 95, or leave it blank.", field: "cut" };
  }
  return null;
}
for (const id of ["margin", "ads", "cut", "start", "end"]) $(id).addEventListener("input", () => $(id).removeAttribute("aria-invalid"));
for (const id of ["start", "end"]) $(id).addEventListener("input", () => { $("hint").hidden = true; });

// A sale run by lowering prices shows no discount in the report: when the chosen dates
// show none, the price-cut field is pointed out (More options opens), so break-even doesn't
// read full price.
async function checkDiscount() {
  if (!ready || !$("file").files.length || !$("start").value || !$("end").value) {
    showCutHint(false);
    return;
  }
  const csv = await $("file").files[0].text();
  worker.postMessage({ type: "discount", csv, start: $("start").value, end: $("end").value, today: new Date().toLocaleDateString("en-CA") });
}
function showCutHint(on) {
  $("cut-hint").hidden = !on;
  if (on) $("more").open = true;
  for (const c of ["tw-border", "tw-border-amber-300", "tw-bg-amber-50", "tw-p-3"]) $("cut-box").classList.toggle(c, on);
}
for (const id of ["start", "end"]) $(id).addEventListener("input", checkDiscount);

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
const dayMonth = (iso) => {
  const [, m, d] = parts(iso);
  return `${d} ${MONTHS[m - 1]}`;
};

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

// A chosen file is read at once: the sales its discounts show, or why it can't be used.
async function findSales() {
  if (!ready || !$("file").files.length) return;
  const csv = await $("file").files[0].text();
  worker.postMessage({ type: "find", csv, today: new Date().toLocaleDateString("en-CA") });
}

// A new file: the steps that need it, and any result, wait until it's read.
function chosen() {
  $("form").hidden = true;
  $("result").hidden = true;
  $("file-error").hidden = true;
  $("hint").hidden = true;
  $("error").hidden = true;
  wait();
  if (ready) {
    $("status").hidden = false;
    $("status").textContent = "Reading your file…";
    findSales();
  }
}
$("file").addEventListener("change", () => {
  sample = false;
  // The sample's margin gives way to the default for the visitor's own file, unless they changed it.
  if ("auto" in $("margin").dataset) $("margin").value = $("margin").defaultValue;
  delete $("margin").dataset.auto;
  step("file");
  chosen();
});

let found = [];

// The report is read: the sales it shows are offered as the sale to check, and as the other
// sales the merchant removes any that weren't. The sale being checked is never one of them.
function loaded(sales) {
  found = sales;
  for (const row of $("others").querySelectorAll("[data-found]")) row.remove();
  for (const s of sales) addOther(s.start, s.end, true);
  offerChoices();
  showFound();
  $("form").hidden = false;
  // The sample: its Black Friday, ready to check.
  const friday = sample ? found.findIndex((s) => s.start === SAMPLE_SALE) : -1;
  if (friday >= 0) {
    select(String(friday));
    $("name").value = "Black Friday (sample)";
    $("name").dataset.auto = "";  // filled in, so it gives way to the next report's sale
  }
  if (waiting || sample) $("form").scrollIntoView({ behavior: "smooth", block: "start" });
  waiting = false;
}

// "Try a sample": a made-up store's export (scripts/make_checker_sample.py), read like any other file.
const SAMPLE_SALE = "2025-11-28";
let sample = false;
$("try-sample").addEventListener("click", async () => {
  step("sample");
  const text = await (await fetch("/assets/checker/sample-export.csv")).text();
  const files = new DataTransfer();
  files.items.add(new File([text], "sample-export.csv", { type: "text/csv" }));
  $("file").files = files.files;
  sample = true;
  $("margin").value = "45";  // the sample store's margin
  $("margin").dataset.auto = "";
  chosen();
});

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
  $("found-lead").hidden = found.length === 0;
  $("none-lead").hidden = found.length > 0;
  if (!found.length) {
    $("dates").hidden = false;
    return;
  }
  const add = (value, text) => {
    const row = $("choice-row").content.firstElementChild.cloneNode(true);
    row.querySelector("input").value = value;
    row.querySelector("[data-span]").textContent = text;
    list.append(row);
  };
  found.forEach((s, i) => add(String(i), span(s.start, s.end)));
  add("other", "A different sale or period");
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
  checkDiscount();
}
$("choice-list").addEventListener("change", (event) => choose(event.target.value));
for (const id of ["start", "end"]) $(id).addEventListener("input", () => delete $("start").dataset.found);
$("name").addEventListener("input", () => delete $("name").dataset.auto);
$("margin").addEventListener("input", () => delete $("margin").dataset.auto);

function markChosen() {
  for (const row of $("choice-list").children) {
    const on = row.querySelector("input").checked;
    row.classList.toggle("tw-border-black", on);
    row.classList.toggle("tw-bg-gray-50", on);
    row.classList.toggle("tw-border-gray-300", !on);
  }
}

// A found sale overlapping the dates being checked is that sale: it's hidden, and not sent.
// Until the sale to check is known, found sales are only offered as choices, and the
// other sales block waits.
function showFound() {
  const start = $("start").value;
  const end = $("end").value || start;
  $("other-sales").hidden = !start;
  let shown = 0;
  for (const row of $("others").querySelectorAll("[data-found]")) {
    const a = row.querySelector("[data-start]").value;
    const b = row.querySelector("[data-end]").value || a;
    row.hidden = !start || (a <= end && b >= start);
    row.style.display = row.hidden ? "none" : "";  // the row's grid class would otherwise outrank [hidden]
    if (!row.hidden) shown += 1;
  }
  $("found-note").hidden = shown === 0;
  $("none-note").hidden = shown > 0;
  $("add-other").textContent = shown > 0 ? "+ Add a sale we missed" : "+ Add a sale";
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
  step("check");
  $("error").hidden = true;
  const problem = invalid();
  $("hint").textContent = problem ? problem.message : "";
  $("hint").hidden = !problem;
  if (problem) {
    if (problem.field) {
      $(problem.field).setAttribute("aria-invalid", "true");
      $(problem.field).focus();
    }
    return;
  }
  try {
    await send();
  } catch (err) {
    console.error("The check couldn't start:", err);
    showError("Something went wrong while checking this file.");
  }
});

async function send() {
  let others;
  try {
    others = otherSales();
  } catch (err) {
    $("more").open = true;
    $("hint").textContent = err.message;
    $("hint").hidden = false;
    return;
  }
  $("result").hidden = true;
  $("check").disabled = true;
  $("check").textContent = "Checking…";
  const csv = await $("file").files[0].text();
  const margin = $("margin").value === "" ? null : Number($("margin").value);
  // Today's date here: its row in the export is a day still under way.
  const today = new Date().toLocaleDateString("en-CA");
  const ads = $("ads").value === "" ? null : Math.max(0, Number($("ads").value));
  const cut = $("cut").value === "" ? null : Math.min(95, Math.max(0, Number($("cut").value)));
  worker.postMessage({ csv, start: $("start").value, end: $("end").value, margin, currency: $("currency").value, name: $("name").value.trim(), today, others, ads, cut });
}

// The ad spend is in the store's currency.
$("currency").addEventListener("change", () => { $("ads-symbol").textContent = $("currency").value; });

// The one email ask, after the result. While the result isn't complete (the sale may still be
// running, or the 3 weeks after aren't in the report), a reminder to check again, with early
// access as a separate, unticked box; otherwise, early access. The form posts the email and
// that case's Buttondown tags in a new tab (the browser checks the email, and any required box,
// first); controls for the other cases are disabled, so they send nothing.
let remindOn = "";  // the reminder's date, "22 December", or "" for early access
function ask(remind) {
  const kind = remind ? remind.kind : "early";
  for (const text of document.querySelectorAll("[data-ask]")) text.hidden = text.dataset.ask !== kind;
  for (const label of document.querySelectorAll("[data-label]")) label.textContent = remind ? remind.label : "";
  const tags = remind ? remind.tags : ["early-access", "checker"];
  $("ask-kind").value = tags[0];
  $("ask-tag").value = tags[1];
  $("ask-button").textContent = remind ? `Remind me on ${remind.label}` : "Join the list";
  $("ask-once").hidden = !remind;
  $("ask-also").hidden = !remind;
  $("ask-also-box").disabled = !remind;
  $("ask-also-box").checked = false;  // consent is asked afresh for each result
  $("ask-consent-box").checked = false;
  $("ask-consent").hidden = Boolean(remind);
  $("ask-consent-box").disabled = Boolean(remind);
  remindOn = remind ? remind.label : "";
  $("ask-form").hidden = false;
  $("ask-done").hidden = true;
}
$("ask-form").addEventListener("submit", () => {
  step("email");
  const on = remindOn;
  setTimeout(() => {
    $("ask-form").hidden = true;
    $("ask-done").textContent = on
      ? `Check your inbox to confirm, and we'll email you on ${on}.`
      : "Check your inbox to confirm. Buttondown, which keeps our list, opened in a new tab: if it asks for anything more, finish there.";
    $("ask-done").hidden = false;
  });
});

// "Save as PDF": the browser's print window, with only the result (see the page's print styles).
$("pdf-open").addEventListener("click", () => $("pdf-dialog").showModal());
$("pdf-cancel").addEventListener("click", () => $("pdf-dialog").close());
$("pdf-print").addEventListener("click", () => {
  step("pdf");
  const by = $("prepared-by").value.trim();
  const today = new Date().toLocaleDateString("en-CA");
  $("print-meta").textContent = `${by ? `Prepared by ${by} · ` : ""}Checked on ${dayMonth(today)} ${today.slice(0, 4)}`;
  $("worked-box").open = true;
  $("pdf-dialog").close();
  setTimeout(() => window.print(), 100);
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
  // The dates once, in the title, after the merchant's own name for the sale if they gave one.
  const own = $("name").value.trim() && !("auto" in $("name").dataset);
  $("result-title").textContent = own ? `${$("name").value.trim()} · ${r.span}` : r.span;
  // The headline: did it make money? Break-even against the likely range of what it brought.
  const PROFIT = { yes: "tw-text-green-800", no: "tw-text-red-800", unclear: "tw-text-gray-900" };
  $("profit-box").hidden = !r.profit;
  if (r.profit) {
    $("profit").textContent = r.profit.headline;
    $("profit").className = `tw-text-3xl tw-font-semibold tw-leading-tight ${PROFIT[r.profit.call]}`;
    // "(likely 1.69–2.64×)" kept on one line, so a narrow screen doesn't break the range at its dash.
    const [before, likely = "", after = ""] = r.profit.sub.split(/(\(likely [^)]*\))/);
    const range = Object.assign(document.createElement("span"), { className: "tw-whitespace-nowrap", textContent: likely });
    $("profit-sub").replaceChildren(before, range, after);
  }
  $("verdict").textContent = r.label;
  $("verdict").className = `tw-inline-block tw-rounded-full tw-px-3 tw-py-1 tw-text-sm tw-font-semibold ${BADGE[r.verdict] || BADGE.expected}`;
  // What the sale added, with the weeks after.
  $("added").textContent = r.added || r.summary;
  $("after").textContent = r.after_line || "";
  $("after").hidden = !r.after_line;
  $("reexport").hidden = !(r.remind && r.remind.reexport);
  $("chart").replaceChildren();
  $("caption").hidden = true;
  if (r.chart && r.chart.length) {
    $("chart").append(promotionDaily(window.Plot, r.chart, { label: r.name, symbol: $("currency").value }));
    $("caption").textContent = CAPTION;
    $("caption").hidden = false;
  }
  $("margin-note").textContent = r.margin_note || "";
  $("margin-note").hidden = !r.margin_note;
  // How this was worked out: break-even's sentence, the discount, and any notes.
  const b = r.break_even;
  $("worked").textContent = b ? b.sentence : "";
  $("worked").hidden = !b;
  $("discount").textContent = r.discount_line || "";
  $("discount").hidden = !r.discount_line;
  const notes = r.warnings || [];
  $("notes").replaceChildren(...notes.map((w) => Object.assign(document.createElement("li"), { textContent: w })));
  $("notes").hidden = !notes.length;
  $("worked-box").hidden = !(b || r.discount_line || notes.length);
  ask(r.remind && !r.remind.reexport ? r.remind : null);
  $("result").hidden = false;
  step(`result-${r.outcome}`);
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}
