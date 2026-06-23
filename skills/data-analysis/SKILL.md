---
name: data-analysis
description: Guides Claude through correct Stats Compass MCP tool usage — calling describe tools before using a category, reshaping data before hypothesis tests, presenting download links, and following optimal workflows for EDA, ML, and time series analysis.
---

# Stats Compass — Data Analysis Skill

Use this skill whenever working with Stats Compass MCP tools.

## Core Rules

1. **Call `describe_*_tools` once before using any new tool category.** The schemas are authoritative — do not guess parameter names. Available: `describe_eda_tools`, `describe_data_tools`, `describe_cleaning_tools`, `describe_transform_tools`, `describe_ml_tools`, `describe_plot_tools`.

2. **Read errors, don't retry blindly.** `ValidationError` messages list exactly which fields are missing or forbidden. Fix the call based on the error.

3. **`inspect_data` is for scalar expressions only.** It does not support `value_counts()`, `groupby()`, or any expression returning a Series/DataFrame. Use instead:
   - Value counts / distributions → `bar_chart` or `describe` with `include: "all"`
   - Group aggregations → `groupby_aggregate`
   - Filtering → `filter_dataframe`

4. **Always present `download_url` fields** from tool results as clickable links to the user.

5. **Axis labels:** When calling plot tools, always set `xlabel` and `ylabel` to descriptive labels. Include units when known (e.g. "Price (USD)"). Never leave axis labels as raw column names.

## Hypothesis Tests (t-test, z-test)

Stats Compass uses **wide-format** input. Both `t_test` and `z_test` require two separate columns (`column_a`, `column_b`). They do NOT accept a `group_column` parameter.

**Workflow for group comparisons:**

Step 1 — Reshape with `split_column_by_group`:
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

Step 2 — Run the test on the new columns:
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

Use `equal_var: false` (Welch's t-test) when sample sizes differ. Use `z_test` only when population standard deviations are known.

## Finding Files

Use the `list_files` MCP tool to locate files. **Never use bash or shell commands** — they run in a sandbox without access to the user's filesystem.

`list_files` is a top-level tool (not a sub-tool of `execute_data_tool`):
```json
{ "directory": "~/Downloads" }
```

Note: `list_files` only works when Stats Compass runs locally. On the hosted version, files must be uploaded via the upload link.

## Loading Data

- If loading fails with a codec error, retry with `encoding: "latin-1"`.
- Use `get_schema` after loading to confirm column names and dtypes.

## EDA

- Use `run_eda_report_workflow` for a full automated report (stats, correlations, missing data, charts) in one call.
- Use `describe` with `include: "all"` for both numeric and categorical column stats.

## Preprocessing

- Use `run_preprocessing_workflow` for automated cleaning (imputation, outliers, deduplication).
- The cleaned DataFrame is saved under a **new name** returned in the result. Use that name for subsequent analysis, not the original.

## Time Series Forecasting

Always use fast defaults to avoid timeouts. ARIMA grid search and stationarity tests add 20–60 seconds on large datasets.

Step 1 — Pre-filter to recent data:
```json
{
  "tool_name": "filter_dataframe",
  "params": { "tail": 500, "save_as": "ts_recent" }
}
```

Step 2 — Run with fast config:
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
