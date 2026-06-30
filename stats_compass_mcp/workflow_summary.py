"""
Workflow result summarization for MCP responses.

Creates compact summaries of workflow results to reduce response sizes.
"""


def summarize_workflow_result(result_data: dict) -> dict:
    """
    Create a compact summary of workflow results for MCP responses.
    
    Returns a much smaller JSON payload that still captures the key information
    without the verbose step-by-step details.
    """
    _CHART_STEPS = {"histogram_", "bar_chart_", "scatter_", "line_chart_", "box_plot_"}

    # Build step summaries - just name, status, and key metrics
    step_summaries = []
    for step in result_data.get("steps", []):
        step_name = step.get("step_name", "")
        summary = {
            "step": step_name,
            "status": step.get("status"),
        }
        # Include error if failed
        if step.get("status") == "failed" and step.get("error"):
            summary["error"] = step["error"]
        # Include full result for analysis steps (describe, correlations, etc.)
        # but not for chart steps which are just images
        is_chart = any(step_name.startswith(prefix) for prefix in _CHART_STEPS)
        if step.get("result") and isinstance(step["result"], dict) and not is_chart:
            summary["result"] = step["result"]
        # Include download URL if present (added by save_workflow_exports)
        if step.get("download_url"):
            summary["download_url"] = step["download_url"]
        if step.get("filename"):
            summary["filename"] = step["filename"]
        step_summaries.append(summary)

    # Build compact summary
    artifacts = result_data.get("artifacts", {})
    summary = {
        "workflow": result_data.get("workflow_name"),
        "status": result_data.get("status"),
        "duration_ms": result_data.get("total_duration_ms"),
        "input_dataframe": result_data.get("input_dataframe"),
        "steps": step_summaries,
        "outputs": {
            "dataframes_created": artifacts.get("dataframes_created", []),
            "models_created": artifacts.get("models_created", []),
            "charts_generated": artifacts.get("charts_generated", 0),
            "final_dataframe": artifacts.get("final_dataframe"),
        },
        "error_summary": result_data.get("error_summary"),
        "suggestion": result_data.get("suggestion"),
    }

    # Preserve downloads array (added by save_workflow_exports)
    if result_data.get("downloads"):
        summary["downloads"] = result_data["downloads"]

    return summary
