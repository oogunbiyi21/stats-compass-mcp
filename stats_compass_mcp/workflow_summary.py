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
    # Build step summaries - just name, status, and key metrics
    step_summaries = []
    for step in result_data.get("steps", []):
        summary = {
            "step": step.get("step_name"),
            "status": step.get("status"),
        }
        # Include error if failed
        if step.get("status") == "failed" and step.get("error"):
            summary["error"] = step["error"]
        # Include key metrics from result if present
        if step.get("result") and isinstance(step["result"], dict):
            # Cherry-pick useful fields
            result = step["result"]
            if "accuracy" in result:
                summary["accuracy"] = result["accuracy"]
            if "rmse" in result:
                summary["rmse"] = result["rmse"]
            if "r2" in result:
                summary["r2"] = result["r2"]
            if "is_stationary" in result:
                summary["is_stationary"] = result["is_stationary"]
        step_summaries.append(summary)
    
    # Build compact summary
    artifacts = result_data.get("artifacts", {})
    return {
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
