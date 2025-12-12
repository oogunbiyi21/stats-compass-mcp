# stats-compass-mcp

MCP server that exposes [stats-compass-core](https://pypi.org/project/stats-compass-core/) tools to LLMs like ChatGPT, Claude, and Gemini.

## What is this?

This package turns the `stats-compass-core` toolkit into an MCP (Model Context Protocol) server. Once running, any MCP-compatible client (ChatGPT, Claude, Cursor, VS Code, etc.) can use your data analysis tools directly.

## Installation

```bash
pip install stats-compass-mcp
```

## Quick Start

### Start the server

```bash
stats-compass-mcp serve
```

### Configure your MCP client

#### For Claude Desktop (Recommended)

The easiest way to run this server is using `uvx` (part of the [uv](https://github.com/astral-sh/uv) toolkit), which downloads and runs the server in an isolated environment without installation.

Add this to your `claude_desktop_config.json`:

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

#### Manual Installation

If you prefer to install it globally:

```bash
pip install stats-compass-mcp
```

Then configure your client:

```json
{
  "mcpServers": {
    "stats-compass": {
      "command": "stats-compass-mcp",
      "args": ["serve"]
    }
  }
}
```

## Available Tools

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

### Machine Learning
- `train_linear_regression` - Linear regression
- `train_logistic_regression` - Logistic regression
- `train_random_forest_classifier` - Random forest classification
- `train_random_forest_regressor` - Random forest regression
- `evaluate_model` - Model evaluation metrics

### Time Series (ARIMA)
- `check_stationarity` - ADF/KPSS tests
- `fit_arima` - Fit ARIMA models
- `forecast_arima` - Generate forecasts
- `find_optimal_arima` - Auto parameter search

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

## Development

```bash
# Clone and install
git clone https://github.com/oogunbiyi21/stats-compass-mcp.git
cd stats-compass-mcp
poetry install

# Run tests
poetry run pytest

# Run the server locally
poetry run stats-compass-mcp serve
```

## Related Projects

- [stats-compass-core](https://github.com/oogunbiyi21/stats-compass-core) - The underlying toolkit
- [stats-compass](https://github.com/oogunbiyi21/stats-compass) - Streamlit chat UI for data analysis

## License

MIT
