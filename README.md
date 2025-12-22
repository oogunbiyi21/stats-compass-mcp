<div align="center">
  <img src="./assets/logo/logo1.png" alt="Stats Compass Logo" width="200"/>
  
  <h1>stats-compass-mcp</h1>
  
  <p>A stateful, MCP-compatible toolkit of pandas-based data tools for AI-powered data analysis.</p>

  [![PyPI version](https://badge.fury.io/py/stats-compass-mcp.svg)](https://badge.fury.io/py/stats-compass-mcp)
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

> ⚠️ **Status: Early developer release (v0.1)**  
> Optimized for Claude models  
> Gemini and GPT tool calling may be inconsistent.

# stats-compass-mcp

<img src="./assets/demos/stats_compass_mcp_1.gif" alt="Demo 1: Loading and exploring data" width="800"/>

Stats Compass MCP turns the [stats-compass-core](https://github.com/oogunbiyi21/stats-compass-core/) toolkit into an MCP server that AI agents can call in a reproducible, stateful way across workflows.

## What is this?

This package turns the `stats-compass-core` toolkit into an MCP (Model Context Protocol) server. Once running, any MCP-compatible client can use your data analysis tools directly.

### Client Compatibility

| Client | Status | Notes |
|--------|--------|-------|
| Claude Desktop | ✅ Supported | Recommended. Best tool selection. |
| VS Code Copilot Chat | ✅ Supported (Beta) | Native MCP integration. May need restart after config changes. |
| Cursor | ⚠️ Experimental | Pending official MCP release. |
| GPT / ChatGPT | ⚠️ Partial | Tool calling may be inconsistent with large toolsets. |
| Gemini | ⚠️ Unstable | May throw errors with complex schemas. |
| Roo Code | ❌ Unsupported | Incompatible JSON Schema validation. |

## Installation

```bash
pip install stats-compass-mcp
```

> **Prerequisite:** The MCP configurations below use `uvx`, which requires [uv](https://docs.astral.sh/uv/getting-started/installation/) to be installed.

### ⚠️ Important Note on Data Loading
**Drag-and-drop file uploads are NOT supported.** 
To load data, you must provide the **absolute file path** to the file on your local machine.
- ✅ "Load the file at `/Users/me/data.csv`"
- ❌ Dragging `data.csv` into the chat window

## Quick Start

### Start the server

```bash
stats-compass-mcp serve
```

### Configure your MCP client

#### 1. Claude Desktop (Recommended)

You can configure Claude Desktop automatically:

```bash
# Install the package
pip install stats-compass-mcp

# Run the auto-configuration
stats-compass-mcp install
```

Or manually add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stats-compass": {
      "command": "uvx",
      "args": ["stats-compass-mcp", "serve"]
    }
  }
}
```

#### 2. VS Code (GitHub Copilot)

VS Code has native MCP support via GitHub Copilot:

```bash
# Install the package
pip install stats-compass-mcp

# Run the auto-configuration
stats-compass-mcp install-vscode
```

Or manually add this to your VS Code `mcp.json` (located at `~/Library/Application Support/Code/User/mcp.json` on macOS):

```json
{
  "servers": {
    "stats-compass": {
      "command": "uvx",
      "args": ["stats-compass-mcp", "serve"]
    }
  }
}
```

#### 3. Claude Code (CLI)

To use Stats Compass with the Claude CLI:

```bash
claude mcp add stats-compass -- uvx stats-compass-mcp serve
```

## Available Tools

<img src="./assets/demos/stats_compass_mcp_2.gif" alt="Demo 2: Cleaning and transforming data" width="800"/>

Once connected, the following tools are available to LLMs:

### Data Loading & Management
- `load_csv` - Load CSV files into state
- `load_dataset` - Load built-in sample datasets
- `list_dataframes` - List all DataFrames in state
- `get_schema` - Get column types and info
- `get_sample` - Preview rows from a DataFrame

### Data Cleaning
- `dropna` - Remove missing values
- `apply_imputation` - Fill missing values
- `dedupe` - Remove duplicate rows
- `handle_outliers` - Detect and handle outliers

### Transforms
- `filter_dataframe` - Filter rows by condition
- `groupby_aggregate` - Group and aggregate data
- `pivot` - Pivot tables
- `add_column` - Add calculated columns
- `rename_columns` - Rename columns
- `drop_columns` - Remove columns

### EDA & Statistics
- `describe` - Summary statistics
- `correlations` - Correlation matrix
- `hypothesis_tests` - T-tests, chi-square, etc.
- `data_quality` - Data quality report

### Visualization
- `histogram` - Distribution plots
- `scatter_plot` - Scatter plots
- `bar_chart` - Bar charts
- `lineplot` - Line plots
- `confusion_matrix_plot` - Confusion matrix heatmap
- `roc_curve_plot` - ROC curves for classification
- `precision_recall_curve_plot` - Precision-recall curves
- `feature_importance` - Feature importance bar charts

### Machine Learning
- `train_linear_regression` - Linear regression
- `train_logistic_regression` - Logistic regression
- `train_random_forest_classifier` - Random forest classification
- `train_random_forest_regressor` - Random forest regression
- `train_gradient_boosting_classifier` - Gradient boosting classification
- `train_gradient_boosting_regressor` - Gradient boosting regression
- `evaluate_classification_model` - Classification metrics (accuracy, precision, recall, F1)
- `evaluate_regression_model` - Regression metrics (R², MAE, RMSE)


### Time Series (ARIMA)
- `check_stationarity` - ADF/KPSS tests
- `fit_arima` - Fit ARIMA models
- `forecast_arima` - Generate forecasts
- `find_optimal_arima` - Auto parameter search

<img src="./assets/demos/stats_compass_mcp_3.gif" alt="Demo 3: Visualization and ML" width="800"/>

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client                               │
│         (ChatGPT, Claude, Cursor, VS Code)                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                stats-compass-mcp                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              MCP Server (this package)              │    │
│  │  • Registers tools from stats-compass-core          │    │
│  │  • Manages DataFrameState per session               │    │
│  │  • Converts tool results to MCP responses           │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           stats-compass-core (PyPI)                 │    │
│  │  • DataFrameState (server-side state)               │    │
│  │  • 40+ deterministic tools                          │    │
│  │  • Pydantic schemas for all inputs/outputs          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Contributing

### Architecture Overview

If you want to contribute to `stats-compass-mcp`, it helps to understand how the pieces fit together:

1.  **Entry Point**: The `pyproject.toml` defines the script `stats-compass-mcp = "stats_compass_mcp.cli:main"`. This is what runs when you execute the command.
2.  **CLI (`cli.py`)**: Parses command-line arguments and launches the server.
3.  **Server (`server.py`)**:
    *   Initializes a `DataFrameState` (from `stats-compass-core`) to hold data in memory during the session.
    *   Discovers tools dynamically using `registry.auto_discover()` and `get_all_tools()`.
    *   Registers `list_tools` and `call_tool` handlers to communicate with the MCP client.
    *   Executes tools by injecting the session `state` into the function calls.
4.  **Communication**: Uses `stdio` transport to exchange JSON-RPC messages with the client (Claude, etc.).

### Local Development

1.  **Clone and Install**:
    ```bash
    git clone https://github.com/oogunbiyi21/stats-compass-mcp.git
    cd stats-compass-mcp
    poetry install
    ```

2.  **Configure for Development**:
    You can automatically configure your MCP clients to use your local development version (instead of the published PyPI version):
    
    ```bash
    # For Claude Desktop
    poetry run stats-compass-mcp install --dev
    
    # For VS Code (GitHub Copilot)
    poetry run stats-compass-mcp install-vscode --dev
    ```

3.  **Run the Server**:
    ```bash
    poetry run stats-compass-mcp serve
    ```

3.  **Test with MCP Inspector**:
    You can use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to test the server interactively:
    ```bash
    npx @modelcontextprotocol/inspector poetry run stats-compass-mcp serve
    ```

## Known Limitations

- **Local files only**: The MCP server runs on your machine. It cannot access files in cloud sandboxes or drag-and-drop uploads. You must provide absolute file paths.
- **One MCP client at a time**: Running multiple clients connected to the same server may cause state conflicts.
- **VS Code schema caching**: VS Code caches tool schemas aggressively. After updating the package, restart VS Code or run `stats-compass-mcp install-vscode` again.
- **Gemini instability**: Gemini clients may fail with 400 errors on complex tool schemas. This is a known Gemini limitation, not a Stats Compass bug.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tools don't appear in VS Code | Restart VS Code. Check `mcp.json` path is correct. |
| "File not found" errors | Use absolute paths, not relative. Check file exists with `list_files`. |
| Schema validation errors | Ensure you're on the latest version. Run `pip install --upgrade stats-compass-mcp`. |
| Gemini 400 errors | Known issue. Use Claude Desktop or VS Code Copilot instead. |
| Stale tools after update | Run `stats-compass-mcp install-vscode --dev` to refresh config. Restart VS Code. |

## Related Projects

- [stats-compass-core](https://github.com/oogunbiyi21/stats-compass-core) - The underlying toolkit
- [stats-compass](https://github.com/oogunbiyi21/stats-compass) - Streamlit chat UI for data analysis

## License

MIT
