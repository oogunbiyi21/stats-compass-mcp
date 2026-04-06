"""
Workflow tools for Stats Compass MCP server.

These wrap stats-compass-core workflow functions with session isolation.
"""

import logging
from typing import Any, List, Optional

from fastmcp import Context, FastMCP
from stats_compass_core.workflows import (
    ClassificationConfig,
    EDAConfig,
    PreprocessingConfig,
    RegressionConfig,
    TimeSeriesConfig,
    run_classification,
    run_eda_report,
    run_preprocessing,
    run_regression,
    run_timeseries_forecast,
)
from stats_compass_core.workflows.classification import RunClassificationInput
from stats_compass_core.workflows.eda_report import RunEDAReportInput
from stats_compass_core.workflows.preprocessing import RunPreprocessingInput
from stats_compass_core.workflows.regression import RunRegressionInput
from stats_compass_core.workflows.timeseries import RunTimeseriesForecastInput

from stats_compass_mcp.exports import save_plot_export
from stats_compass_mcp.image_utils import with_images
from stats_compass_mcp.session import Session, SessionManager, get_session

logger = logging.getLogger(__name__)


def save_workflow_exports(result_dict: dict, session: Session, workflow_name: str) -> dict:
    """
    Save all exportable artifacts from a workflow result.
    
    - Saves plots (base64 images) to exports/plots/
    - Returns modified result with download_urls added
    """
    downloads = []

    # Process steps to find and save images
    steps = result_dict.get("steps", [])
    for i, step in enumerate(steps):
        # image_base64 is a top-level field on WorkflowStepResult, not inside "result"
        image_b64 = step.get("image_base64")
        if image_b64:
            step_name = step.get("step_name", f"step_{i}")
            name_prefix = f"{workflow_name}_{step_name}"

            export_info = save_plot_export(
                session_id=session.session_id,
                image_base64=image_b64,
                name_prefix=name_prefix,
            )

            if export_info["download_url"]:
                # Add download info to the step
                step["download_url"] = export_info["download_url"]
                step["filename"] = export_info["filename"]
                downloads.append({
                    "type": "plot",
                    "name": export_info["filename"],
                    "step": step_name,
                    "url": export_info["download_url"],
                })

    # Add downloads summary to result
    if downloads:
        result_dict["downloads"] = downloads

    return result_dict


def register_workflow_tools(mcp: FastMCP, session_manager: SessionManager):
    """Register all workflow tools with the FastMCP server."""

    @mcp.tool()
    def run_eda_report_workflow(
        ctx: Context,
        dataframe_name: Optional[str] = None,
        config: Optional[dict] = None
    ) -> Any:
        """
        Run comprehensive EDA report: descriptive stats, correlations, 
        missing data analysis, and auto-generated visualizations.
        
        Args:
            dataframe_name: Name of DataFrame to analyze (default: active)
            config: Optional EDA configuration dict
        
        Returns:
            Workflow result with steps, metrics, and charts.
        """
        session = get_session(ctx, session_manager)
        eda_config = EDAConfig(**config) if config else None
        params = RunEDAReportInput(dataframe_name=dataframe_name, config=eda_config)
        result = run_eda_report(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "eda")
        return with_images(result_dict, summarize=True)

    @mcp.tool()
    def run_preprocessing_workflow(
        ctx: Context,
        dataframe_name: Optional[str] = None,
        save_as: Optional[str] = None,
        config: Optional[dict] = None
    ) -> Any:
        """
        Run data preprocessing pipeline: analyze missing data, apply imputation,
        handle outliers, and remove duplicates.
        
        Args:
            dataframe_name: Name of DataFrame to preprocess (default: active)
            save_as: Name for the cleaned DataFrame (default: auto-generated)
            config: Optional preprocessing configuration dict
        
        Returns:
            Workflow result with steps and cleaned DataFrame name.
        """
        session = get_session(ctx, session_manager)
        preproc_config = PreprocessingConfig(**config) if config else None
        params = RunPreprocessingInput(
            dataframe_name=dataframe_name, save_as=save_as, config=preproc_config
        )
        result = run_preprocessing(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "preprocessing")
        return with_images(result_dict, summarize=True)

    @mcp.tool()
    def run_classification_workflow(
        ctx: Context,
        target_column: str,
        dataframe_name: Optional[str] = None,
        feature_columns: Optional[List[str]] = None,
        config: Optional[dict] = None
    ) -> Any:
        """
        Run classification workflow: train model, evaluate performance,
        generate confusion matrix, ROC curve, and feature importance plots.
        
        Args:
            target_column: Column with class labels to predict
            dataframe_name: Name of DataFrame (default: active)
            feature_columns: Feature columns (default: all numeric except target)
            config: Optional classification configuration dict
        
        Returns:
            Workflow result with metrics, model ID, and diagnostic charts.
        """
        session = get_session(ctx, session_manager)
        class_config = ClassificationConfig(**config) if config else None
        params = RunClassificationInput(
            dataframe_name=dataframe_name,
            target_column=target_column,
            feature_columns=feature_columns,
            config=class_config
        )
        result = run_classification(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "classification")
        return with_images(result_dict, summarize=True)

    @mcp.tool()
    def run_regression_workflow(
        ctx: Context,
        target_column: str,
        dataframe_name: Optional[str] = None,
        feature_columns: Optional[List[str]] = None,
        config: Optional[dict] = None
    ) -> Any:
        """
        Run regression workflow: train model, evaluate with RMSE/MAE/R²,
        generate feature importance plots.
        
        Args:
            target_column: Column with continuous values to predict
            dataframe_name: Name of DataFrame (default: active)
            feature_columns: Feature columns (default: all numeric except target)
            config: Optional regression configuration dict
        
        Returns:
            Workflow result with metrics, model ID, and charts.
        """
        session = get_session(ctx, session_manager)
        reg_config = RegressionConfig(**config) if config else None
        params = RunRegressionInput(
            dataframe_name=dataframe_name,
            target_column=target_column,
            feature_columns=feature_columns,
            config=reg_config
        )
        result = run_regression(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "regression")
        return with_images(result_dict, summarize=True)

    @mcp.tool()
    def run_timeseries_workflow(
        ctx: Context,
        target_column: str,
        dataframe_name: Optional[str] = None,
        date_column: Optional[str] = None,
        config: Optional[dict] = None
    ) -> Any:
        """
        Run time series forecasting: check stationarity, fit ARIMA model,
        generate forecasts and visualization.

        Args:
            target_column: Column with values to forecast
            dataframe_name: Name of DataFrame (default: active)
            date_column: Column with dates (default: uses index)
            config: Optional time series configuration dict

        Returns:
            Workflow result with forecasts and forecast chart.

        Large datasets are automatically sliced to the most recent 500 rows
        before fitting to keep ARIMA fast. Pass config to override defaults,
        e.g. auto_find_params=True for grid search or check_stationarity=True
        for ADF diagnostics.
        """
        MAX_ROWS = 500
        session = get_session(ctx, session_manager)

        # Auto-slice to last MAX_ROWS rows to keep ARIMA fitting fast
        temp_name = None
        try:
            df = session.state.get_dataframe(dataframe_name)
            if len(df) > MAX_ROWS:
                sliced = df.tail(MAX_ROWS).reset_index(drop=False)
                temp_name = f"__ts_slice_{session.session_id[:8]}"
                session.state.set_dataframe(temp_name, sliced)
                logger.info(
                    f"Timeseries: sliced {dataframe_name or 'active'} "
                    f"from {len(df)} to {MAX_ROWS} rows"
                )
                dataframe_name = temp_name
        except Exception:
            pass  # If slicing fails, let the workflow handle it normally

        try:
            ts_config = TimeSeriesConfig(**config) if config else None
            params = RunTimeseriesForecastInput(
                dataframe_name=dataframe_name,
                target_column=target_column,
                date_column=date_column,
                config=ts_config
            )
            result = run_timeseries_forecast(state=session.state, params=params)
            result_dict = save_workflow_exports(result.model_dump(), session, "timeseries")
            return with_images(result_dict, summarize=True)
        finally:
            if temp_name:
                session.state.remove_dataframe(temp_name)
