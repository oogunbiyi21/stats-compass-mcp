"""
Workflow tools for Stats Compass MCP server.

These wrap stats-compass-core workflow functions with session isolation.
"""

import logging
import warnings
from typing import Any, List, Optional

import pandas as pd
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
from stats_compass_mcp.safety import refuse_write_paths
from stats_compass_mcp.session import Session, SessionManager, get_session

logger = logging.getLogger(__name__)

# run_timeseries_workflow fits ARIMA on at most this many rows, the most recent.
TIMESERIES_MAX_ROWS = 500


def most_recent_rows(df: pd.DataFrame, date_column: Optional[str], n: int) -> pd.DataFrame:
    """The last n rows, by date when there is a date column: rows may not be in date order.

    Rows whose date can't be read sort first, so they are the first dropped. Unless
    the index holds dates, the rows are renumbered from 0, as a whole series would
    be: statsmodels can't forecast from an integer index that starts part-way.
    """
    if date_column and date_column in df.columns:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # pandas guessing a date format
            dates = pd.to_datetime(df[date_column], errors="coerce")
        order = dates.reset_index(drop=True).sort_values(kind="stable", na_position="first").index
        df = df.iloc[order]
    recent = df.tail(n)
    if not isinstance(recent.index, (pd.DatetimeIndex, pd.PeriodIndex)):
        recent = recent.reset_index(drop=True)
    return recent


def unused_name(state: Any, base: str) -> str:
    """base, or base_2, base_3... whichever no DataFrame in state already has."""
    taken = {info.name for info in state.list_dataframes()}
    name, i = base, 2
    while name in taken:
        name, i = f"{base}_{i}", i + 1
    return name


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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        if session.confined:
            refuse_write_paths(config or {}, "config")
        eda_config = EDAConfig(**config) if config else None
        params = RunEDAReportInput(dataframe_name=dataframe_name, config=eda_config)
        result = run_eda_report(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "eda")
        return with_images(result_dict, summarize=True)

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        if session.confined:
            refuse_write_paths(config or {}, "config")
        preproc_config = PreprocessingConfig(**config) if config else None
        params = RunPreprocessingInput(
            dataframe_name=dataframe_name, save_as=save_as, config=preproc_config
        )
        result = run_preprocessing(state=session.state, params=params)
        result_dict = save_workflow_exports(result.model_dump(), session, "preprocessing")
        return with_images(result_dict, summarize=True)

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        if session.confined:
            refuse_write_paths(config or {}, "config")
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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        if session.confined:
            refuse_write_paths(config or {}, "config")
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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
    def run_timeseries_workflow(
        ctx: Context,
        target_column: str,
        dataframe_name: Optional[str] = None,
        date_column: Optional[str] = None,
        forecast_periods: int = 30,
        check_stationarity: bool = False,
        auto_find_params: bool = False,
    ) -> Any:
        """
        Run time series forecasting: fit ARIMA model, generate forecasts and
        visualization. Datasets larger than 500 rows are fitted on their most
        recent 500 rows (by date_column when given), to keep the fit fast; the
        forecast DataFrame is then named <name>_last500_forecast.

        Args:
            target_column: Column with values to forecast
            dataframe_name: Name of DataFrame (default: active)
            date_column: Column containing dates (default: uses row index)
            forecast_periods: Number of future periods to forecast (default: 30)
            check_stationarity: Run ADF stationarity test before fitting (default: False)
            auto_find_params: Grid-search for best ARIMA(p,d,q) order (default: False).
                Slower but may improve accuracy. Uses stationarity result to fix d,
                then searches p and q over 0-3.

        Returns:
            Workflow result with model info, forecast values, and chart download URL.
        """
        session = get_session(ctx, session_manager)

        # Fit only the most recent rows, to keep ARIMA fitting fast. The slice is
        # stored under a name that says so; the forecast DataFrame is named after it.
        temp_name = None
        try:
            df = session.state.get_dataframe(dataframe_name)
            source_name = dataframe_name or session.state.get_active_dataframe_name()
        except ValueError:
            df = None  # No such DataFrame: the workflow reports it
        if df is not None and len(df) > TIMESERIES_MAX_ROWS:
            sliced_name = unused_name(session.state, f"{source_name}_last{TIMESERIES_MAX_ROWS}")
            try:
                session.state.set_dataframe(
                    most_recent_rows(df, date_column, TIMESERIES_MAX_ROWS),
                    name=sliced_name,
                    operation="timeseries_slice",
                    set_active=False,
                )
            except MemoryError as e:
                logger.warning(
                    f"Timeseries: could not store the last {TIMESERIES_MAX_ROWS} rows of "
                    f"{source_name}, so fitting all {len(df)}: {e}"
                )
            else:
                temp_name = dataframe_name = sliced_name
                logger.info(
                    f"Timeseries: fitting the last {TIMESERIES_MAX_ROWS} of {len(df)} rows of {source_name}"
                )

        try:
            ts_config = TimeSeriesConfig(
                forecast_periods=forecast_periods,
                check_stationarity=check_stationarity,
                auto_find_params=auto_find_params,
            )
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
                try:
                    session.state.remove_dataframe(temp_name)
                except ValueError:
                    pass  # Already gone
