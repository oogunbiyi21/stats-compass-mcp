// The checker's engine: Python (Pyodide) in a Web Worker, so the page stays
// responsive while it loads. It starts loading as soon as the page opens.
//
// Everything is fetched here, at load: Pyodide and its packages from jsdelivr
// (pinned), stats-compass-core and joblib from this site (/assets/wheels/,
// pinned), and the glue (checker.py). After "ready", nothing is fetched: the
// visitor's file arrives by postMessage and never leaves the browser.

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";
const WHEELS = [
  // core 0.1.44 needs joblib >=1.5.2; Pyodide 0.29.5 bundles 1.4.2.
  "/assets/wheels/joblib-1.6.0-py3-none-any.whl",
  "/assets/wheels/stats_compass_core-0.1.44-py3-none-any.whl",
];
const PACKAGES = ["numpy", "pandas", "scipy", "pydantic", "micropip"];
// Approximate download sizes in MB, for the progress line (measured 1 Nov 2026).
const SIZES = { python: 5.4, numpy: 2.8, pandas: 5.0, scipy: 16.3, pydantic: 1.9, micropip: 0.1, core: 0.8 };
const TOTAL = Object.values(SIZES).reduce((a, b) => a + b, 0);

importScripts(PYODIDE + "pyodide.js");

let loaded = 0;
const progress = (stage) => postMessage({ type: "progress", loadedMb: Math.round(loaded), totalMb: Math.round(TOTAL), stage });

const ready = (async () => {
  progress("Python");
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  loaded += SIZES.python;
  progress("libraries");
  const seen = new Set();
  await pyodide.loadPackage(PACKAGES, {
    messageCallback: (msg) => {
      // "Loaded numpy, pandas": count each package once, as it finishes.
      const m = /^Loaded (.+)$/.exec(msg);
      if (!m) return;
      for (const name of m[1].split(",").map((s) => s.trim())) {
        if (SIZES[name] && !seen.has(name)) {
          seen.add(name);
          loaded += SIZES[name];
          progress("libraries");
        }
      }
    },
  });
  const micropip = pyodide.pyimport("micropip");
  for (const wheel of WHEELS) {
    // deps=False: every dependency is already loaded, so nothing goes to PyPI.
    await micropip.install.callKwargs(self.location.origin + wheel, { deps: false });
  }
  loaded += SIZES.core;
  progress("checker");
  const glue = await (await fetch("/assets/checker/checker.py")).text();
  pyodide.FS.writeFile("/home/pyodide/checker.py", glue);
  await pyodide.runPythonAsync("import sys; sys.path.insert(0, '/home/pyodide'); import checker");
  postMessage({ type: "ready" });
  return pyodide;
})().catch((err) => {
  postMessage({ type: "error", message: "The checker couldn't load: " + String(err && err.message || err) });
  throw err;
});

// One job at a time: a check and a search for other sales share Python's globals.
let queue = ready.catch(() => {});
onmessage = (event) => {
  queue = queue.then(() => (event.data.type === "find" ? find(event.data) : check(event.data)));
};

// The other sales in a chosen report, found from its discounts, to suggest on the page.
async function find({ csv, today }) {
  try {
    const pyodide = await ready;
    pyodide.globals.set("_csv", csv);
    pyodide.globals.set("_today", today);
    const json = await pyodide.runPythonAsync("import json\njson.dumps(checker.detect(_csv, _today))");
    postMessage({ type: "found", sales: JSON.parse(json) });
  } catch {
    postMessage({ type: "found", sales: [] });
  }
}

async function check({ csv, start, end, margin, currency, name, today, others }) {
  try {
    const pyodide = await ready;
    pyodide.globals.set("_csv", csv);
    pyodide.globals.set("_args", pyodide.toPy({ start, end, margin, currency, name, today, others }));
    const json = await pyodide.runPythonAsync(`
import json
_a = _args.to_py() if hasattr(_args, "to_py") else _args
json.dumps(checker.analyse(_csv, _a["start"], _a["end"], _a["margin"], _a["currency"], _a["name"] or None, _a["today"], _a["others"]), default=str)
`);
    postMessage({ type: "result", data: JSON.parse(json) });
  } catch (err) {
    // A ValueError from the glue is written for the merchant: show its last line.
    const text = String(err && err.message || err);
    const line = text.trim().split("\n").pop().replace(/^ValueError: /, "");
    postMessage({ type: "error", message: line });
  }
}
