# Stats Compass — Agent Skills Guide

Guidance for agents on how to use Stats Compass tools correctly and efficiently.

---

## General Rules

- **Call `describe_*_tools` once before using a new tool category.**
  The schemas are authoritative. Do not guess parameter names.
  Available describe tools: `describe_eda_tools`, `describe_data_tools`,
  `describe_cleaning_tools`, `describe_transform_tools`, `describe_ml_tools`,
  `describe_plot_tools`.

- **One failed call = read the error, then fix.** Do not retry variants.
  `ValidationError` messages list exactly which fields are missing or forbidden.

- **`inspect_data` is for scalar expressions only.**
  It does not support operations that return a Series or DataFrame
  (e.g. `value_counts()`, `groupby()`, `df[col]`). Quote characters inside
  expressions also cause parse failures. Use dedicated tools instead:
  - Value counts / distributions → `bar_chart` or `describe` with `include: "all"`
  - Group aggregations → `groupby_aggregate`
  - Filtering → `filter_dataframe`

---

## Hypothesis Tests (t-test, z-test)

Stats Compass uses a **wide-format** interface. Both `t_test` and `z_test`
require the two samples to be in **separate columns** (`column_a`, `column_b`).
They do NOT accept a grouped format (`column` + `group_column`).

### Workflow for group comparisons

**Step 1 — Reshape with `split_column_by_group`:**

```json
{
  "tool_name": "split_column_by_group",
  "params": {
    "value_column": "IMDB Score",
    "group_column": "Language",
    "groups": ["English", "Spanish"],
    "save_as": "scores_wide"
  }
}
```

**Step 2 — Run the test using the new column names:**

```json
{
  "tool_name": "t_test",
  "dataframe_name": "scores_wide",
  "params": {
    "column_a": "English",
    "column_b": "Spanish",
    "alternative": "two-sided",
    "equal_var": false
  }
}
```

> Use `equal_var: false` (Welch's t-test) when sample sizes differ significantly.
> Use `z_test` only when population standard deviations are known.

---

## Finding Files

To locate files on the user's local machine, always use the `list_files` MCP tool.

**Never use bash, shell commands, or code execution** — these run in a cloud sandbox with no access to the user's filesystem, even in Claude Desktop.

Call `list_files` directly — it is a top-level tool, NOT a sub-tool of `execute_data_tool`:

```json
{ "directory": "~/Downloads" }
```

Supports `~` expansion. Once you have the filename, pass the full path to `load_csv` or `load_excel`.

> Note: `list_files` only works when the MCP server is running locally (Claude Desktop, Claude Code, Cursor). On Claude.ai web, files must be uploaded directly.

## Loading Data

- Default encoding is `utf-8`. If loading fails with a codec error, retry with `encoding: "latin-1"`.
- Use `get_schema` after loading to confirm column names and dtypes before analysis.

---

## EDA

- Use `run_eda_report_workflow` for a full automated report (stats, correlations,
  missing data, charts) in a single call.
- Use `describe` with `include: "all"` to get stats for both numeric and
  categorical columns together.

---

## Preprocessing

- Use `run_preprocessing_workflow` for a full automated pipeline (imputation,
  outlier handling, deduplication) in a single call.
- The cleaned DataFrame is saved under a new name returned in the result.
  Use that name for subsequent analysis, not the original.

---

## Time Series Forecasting

**Always use fast defaults** to avoid timeouts. ARIMA grid search (`auto_find_params: true`) and stationarity tests add 20–60 seconds on large datasets.

### Step 1 — Pre-filter to the most recent ~500 rows

```json
{
  "tool_name": "filter_dataframe",
  "params": {
    "tail": 500,
    "save_as": "ts_recent"
  }
}
```

Or use `tail_dataframe` / slice with `filter_dataframe` as appropriate for the dataset.

### Step 2 — Run the forecast with fast config

```json
{
  "dataframe_name": "ts_recent",
  "target_column": "Close",
  "date_column": "Date",
  "config": {
    "auto_find_params": false,
    "arima_order": [1, 1, 1],
    "check_stationarity": false,
    "forecast_periods": 30
  }
}
```

Only enable `auto_find_params: true` or `check_stationarity: true` if the user explicitly requests optimised parameters or stationarity diagnostics.
