# Contributing to stats-compass-mcp

Thanks for your interest in contributing!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/oogunbiyi21/stats-compass-mcp.git
cd stats-compass-mcp

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run locally (stdio mode)
poetry run stats-compass-mcp run

# Run locally (HTTP mode)
poetry run stats-compass-mcp serve --port 8000
```

## Local Development with stats-compass-core

To develop against a local copy of stats-compass-core:

```toml
# In pyproject.toml, temporarily change:
stats-compass-core = {path = "../stats-compass-core", develop = true}
```

Then run `poetry lock && poetry install`.

## Project Structure

```
stats_compass_mcp/
├── server.py          # MCP server implementation
├── session.py         # Session management
├── cli.py             # CLI commands (run, serve, install)
├── config.py          # Configuration and env vars
└── upload/            # File upload handling
```

## Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=stats_compass_mcp

# Specific test file
poetry run pytest tests/test_server.py -v
```

## Code Style

- Use `ruff` for linting and formatting
- Type hints required for all functions
- Docstrings for public functions

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `poetry run pytest` to ensure tests pass
5. Submit a pull request

## Questions?

Open an issue on GitHub.
