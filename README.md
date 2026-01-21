<div align="center">
  <img src="./assets/logo/logo1.png" alt="Stats Compass Logo" width="200"/>
  
  <h1>stats-compass-mcp</h1>
  
  <p>A stateful, MCP-compatible toolkit of pandas-based data tools for AI-powered data analysis.</p>

  [![PyPI version](https://badge.fury.io/py/stats-compass-mcp.svg)](https://badge.fury.io/py/stats-compass-mcp)
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

> ⚠️ **Status: Early developer release (v0.2)**  
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
| VS Code Copilot Chat | ✅ Supported | Native MCP integration. |
| Cursor | ⚠️ Experimental | Pending official MCP release. |
| GPT / ChatGPT | ⚠️ Partial | Tool calling may be inconsistent with large toolsets. |
| Gemini | ⚠️ Unstable | May throw errors with complex schemas. |

## Installation

```bash
pip install stats-compass-mcp
```

> **Prerequisite:** The MCP configurations below use `uvx`, which requires [uv](https://docs.astral.sh/uv/getting-started/installation/) to be installed.

### ⚠️ Important Note on Data Loading

**Local Mode:** You must provide the **absolute file path** to files on your local machine.
- ✅ "Load the file at `/Users/me/data.csv`"
- ❌ Dragging files into the chat window (not supported)

**Remote/HTTP Mode:** Use the built-in file upload feature (see [File Uploads](#file-uploads-remote-mode)).

## Quick Start

### Local Mode (Recommended for most users)

Start the server via stdio for direct use with Claude Desktop or VS Code:

```bash
stats-compass-mcp run
```

### Remote/HTTP Mode (For Docker/hosting)

Start the server as an HTTP endpoint:

```bash
stats-compass-mcp serve --port 8000
```

## Configure Your MCP Client

### Claude Desktop

Auto-configure:

```bash
stats-compass-mcp install --client claude
```

To also add a remote server config:

```bash
stats-compass-mcp install --client claude --remote-url http://localhost:8000/mcp
```

Or manually add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stats-compass": {
      "command": "uvx",
      "args": ["stats-compass-mcp", "run"]
    }
  }
}
```

### VS Code (GitHub Copilot)

Auto-configure:

```bash
stats-compass-mcp install --client vscode
```

To also add a remote server config:

```bash
stats-compass-mcp install --client vscode --remote-url http://localhost:8000/mcp
```

Or manually add to your VS Code `mcp.json`:

```json
{
  "servers": {
    "stats-compass": {
      "command": "uvx",
      "args": ["stats-compass-mcp", "run"]
    }
  }
}
```

### Claude Code (CLI)

```bash
claude mcp add stats-compass -- uvx stats-compass-mcp run
```

## Remote Server Mode

For multi-client setups, Docker deployments, or running the server on a different machine, use HTTP mode:

```bash
stats-compass-mcp serve --port 8000
```

### Docker

```bash
docker build -t stats-compass-mcp .
docker run -p 8000:8000 stats-compass-mcp
```

### Configure Clients for Remote Mode

#### VS Code (Direct HTTP)

VS Code can connect directly to HTTP MCP servers:

```json
{
  "servers": {
    "stats-compass": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

#### Claude Desktop (via mcp-proxy)

Claude Desktop only supports stdio. Use [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) to bridge:

```json
{
  "mcpServers": {
    "stats-compass": {
      "command": "uvx",
      "args": ["mcp-proxy", "--transport", "streamablehttp", "http://localhost:8000/mcp"]
    }
  }
}
```

### Remote Server Benefits

- **Session isolation**: Each client gets its own isolated session
- **Multi-client support**: Multiple clients can connect simultaneously
- **Deployment flexibility**: Run on a remote machine or container
- **File uploads**: Browser-based file upload for remote users

## File Uploads (Remote Mode)

When running in HTTP mode, users can upload files via a web interface:

<img src="./assets/demos/upload_screenshot.png" alt="File Upload Interface" width="500"/>

### How It Works

1. **Request an upload URL** - Tell the AI you want to upload a file
2. **Open the URL in your browser** - A simple upload page appears
3. **Select and upload your file** - Supports CSV and Excel files (max 50MB)
4. **Tell the AI to load it** - The AI calls `register_uploaded_file()` to load your data

### Example Conversation

```
You: I want to upload a CSV file
AI: Open this link to upload: http://localhost:8000/upload?session_id=abc123

[You upload the file in your browser]

You: I uploaded titanic.csv
AI: [Loads the file] ✅ Loaded titanic.csv with 891 rows and 12 columns
```

### Configuration

Set the server URL for the upload page (required for non-localhost deployments):

| Variable | Default | Description |
|----------|---------|-------------|
| `STATS_COMPASS_SERVER_URL` | `http://localhost:8000` | Base URL shown in upload links |
| `STATS_COMPASS_MAX_UPLOAD_MB` | `50` | Maximum upload file size in MB |

Example for cloud deployment:

```bash
# Render, Railway, etc.
docker run -p 8000:8000 \
  -e STATS_COMPASS_SERVER_URL=https://your-app.onrender.com \
  stats-compass-mcp
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STATS_COMPASS_PORT` | `8000` | Server port |
| `STATS_COMPASS_HOST` | `0.0.0.0` | Server host |
| `STATS_COMPASS_MAX_SESSIONS` | `100` | Maximum concurrent sessions |
| `STATS_COMPASS_MEMORY_LIMIT_MB` | `500` | Memory limit per session (MB) |
| `STATS_COMPASS_SERVER_URL` | `http://localhost:8000` | Base URL for upload links |
| `STATS_COMPASS_MAX_UPLOAD_MB` | `50` | Maximum upload file size (MB) |

## Available Tools

<img src="./assets/demos/stats_compass_mcp_2.gif" alt="Demo 2: Cleaning and transforming data" width="800"/>

Once connected, 30+ tools are available:

### Data Loading & Management
- `load_csv` - Load CSV files (local mode)
- `load_excel` - Load Excel files (local mode)
- `load_dataset` - Load built-in sample datasets (Housing, TATASTEEL, etc.)
- `get_upload_url` - Get a URL to upload files (remote mode)
- `register_uploaded_file` - Load an uploaded file (remote mode)
- `list_dataframes` - List all DataFrames in session
- `get_schema` - Get column types and info
- `get_sample` - Preview rows from a DataFrame

### Data Cleaning
- `execute_cleaning_tool` - Access all cleaning sub-tools:
  - `drop_na` - Remove missing values
  - `impute` - Fill missing values
  - `dedupe` - Remove duplicates
  - `handle_outliers` - Detect and handle outliers

### Transforms
- `execute_transform_tool` - Access all transform sub-tools:
  - `filter` - Filter rows by condition
  - `groupby` - Group and aggregate
  - `pivot` - Pivot tables
  - `add_column` - Calculated columns
  - `encode` - Categorical encoding

### EDA & Statistics
- `execute_eda_tool` - Access all EDA sub-tools:
  - `describe` - Summary statistics
  - `correlations` - Correlation matrix
  - `hypothesis_test` - T-tests, chi-square, etc.
  - `data_quality` - Quality report

### Visualization
- `execute_plot_tool` - Access all plot sub-tools:
  - `histogram` - Distribution plots
  - `scatter` - Scatter plots
  - `bar` - Bar charts
  - `line` - Line plots
  - `confusion_matrix` - Classification confusion matrix
  - `roc_curve` - ROC curves
  - `precision_recall_curve` - PR curves
  - `feature_importance` - Feature importance charts

### Machine Learning
- `execute_ml_tool` - Access all ML sub-tools:
  - `train_model` - Train classifiers/regressors
  - `evaluate` - Model evaluation
  - `predict` - Make predictions

### Workflows (High-Level)
- `run_eda_report_workflow` - Complete EDA report
- `run_preprocessing_workflow` - Data cleaning pipeline
- `run_classification_workflow` - Full classification pipeline
- `run_regression_workflow` - Full regression pipeline
- `run_timeseries_workflow` - ARIMA forecasting

## CLI Commands

```bash
# Start local server (stdio)
stats-compass-mcp run

# Start HTTP server
stats-compass-mcp serve --port 8000

# List all tools
stats-compass-mcp list-tools

# Install for Claude Desktop or VS Code
stats-compass-mcp install --client claude
stats-compass-mcp install --client vscode
```

## Development

```bash
# Clone the repo
git clone https://github.com/oogunbiyi21/stats-compass-mcp.git
cd stats-compass-mcp

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run locally
poetry run stats-compass-mcp run
```

## License

MIT
