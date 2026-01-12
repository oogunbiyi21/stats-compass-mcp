"""
Workflow FastMCP tools for remote Stats Compass server.

These wrap stats-compass-core workflow functions with session isolation.
"""

from typing import Optional, List, Any
from fastmcp import FastMCP, Context

from stats_compass_core.workflows import (
    run_eda_report,
    run_preprocessing,
    run_classification,
    run_regression,
    run_timeseries_forecast,
    EDAConfig,
    PreprocessingConfig,
    ClassificationConfig,
    RegressionConfig,
    TimeSeriesConfig,
)
from stats_compass_core.workflows.eda_report import RunEDAReportInput
from stats_compass_core.workflows.preprocessing import RunPreprocessingInput
from stats_compass_core.workflows.classification import RunClassificationInput
from stats_compass_core.workflows.regression import RunRegressionInput
from stats_compass_core.workflows.timeseries import RunTimeseriesForecastInput

from stats_compass_mcp.remote.session import SessionManager, get_session
from stats_compass_mcp.remote.image_utils import with_images


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
        """
        session = get_session(ctx, session_manager)
        eda_config = EDAConfig(**config) if config else None
        params = RunEDAReportInput(dataframe_name=dataframe_name, config=eda_config)
        result = run_eda_report(state=session.state, params=params)
        return with_images(result.model_dump(), summarize=True)
    
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
        """
        session = get_session(ctx, session_manager)
        preproc_config = PreprocessingConfig(**config) if config else None
        params = RunPreprocessingInput(
            dataframe_name=dataframe_name, save_as=save_as, config=preproc_config
        )
        result = run_preprocessing(state=session.state, params=params)
        return with_images(result.model_dump(), summarize=True)
    
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
        return with_images(result.model_dump(), summarize=True)
    
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
        return with_images(result.model_dump(), summarize=True)
    
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
        """
        session = get_session(ctx, session_manager)
        ts_config = TimeSeriesConfig(**config) if config else None
        params = RunTimeseriesForecastInput(
            dataframe_name=dataframe_name,
            target_column=target_column,
            date_column=date_column,
            config=ts_config
        )
        result = run_timeseries_forecast(state=session.state, params=params)
        return with_images(result.model_dump(), summarize=True)
