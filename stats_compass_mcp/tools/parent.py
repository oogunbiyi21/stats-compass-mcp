"""
Parent tools for Stats Compass MCP server.

These wrap the describe_* and execute_* pattern from stats-compass-core.
"""

from typing import Any, Dict, Optional

from fastmcp import Context, FastMCP
from stats_compass_core.parent.schemas import ExecuteCategoryInput
from stats_compass_core.parent.tools import (
    DescribeCategoryInput,
    describe_cleaning,
    describe_data,
    describe_eda,
    describe_ml,
    describe_plots,
    describe_transforms,
    execute_cleaning,
    execute_data,
    execute_eda,
    execute_ml,
    execute_plots,
    execute_transforms,
)

from stats_compass_mcp.image_utils import with_images
from stats_compass_mcp.session import SessionManager, get_session


def register_parent_tools(mcp: FastMCP, session_manager: SessionManager):
    """Register all parent describe/execute tools with the FastMCP server."""

    # ========================================================================
    # EDA Tools
    # ========================================================================

    @mcp.tool()
    def describe_eda_tools(ctx: Context) -> dict:
        """
        Get schemas for all EDA sub-tools.
        
        Returns available tools: describe, correlations, hypothesis_test,
        data_quality, missing_data_analysis, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_eda(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_eda_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> dict:
        """
        Execute an EDA sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "describe", "correlations")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_eda(state=session.state, params=input_params)
        return result.model_dump()

    # ========================================================================
    # Cleaning Tools
    # ========================================================================

    @mcp.tool()
    def describe_cleaning_tools(ctx: Context) -> dict:
        """
        Get schemas for all cleaning sub-tools.
        
        Returns available tools: drop_na, impute, dedupe, handle_outliers, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_cleaning(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_cleaning_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> dict:
        """
        Execute a cleaning sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "drop_na", "impute")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_cleaning(state=session.state, params=input_params)
        return result.model_dump()

    # ========================================================================
    # Transform Tools
    # ========================================================================

    @mcp.tool()
    def describe_transform_tools(ctx: Context) -> dict:
        """
        Get schemas for all transform sub-tools.
        
        Returns available tools: filter, groupby, pivot, encode, scale, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_transforms(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_transform_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> dict:
        """
        Execute a transform sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "filter", "groupby")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_transforms(state=session.state, params=input_params)
        return result.model_dump()

    # ========================================================================
    # Data Tools
    # ========================================================================

    @mcp.tool()
    def describe_data_tools(ctx: Context) -> dict:
        """
        Get schemas for all data manipulation sub-tools.
        
        Returns available tools: get_sample, get_schema, add_column,
        drop_columns, rename_columns, merge, concat, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_data(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_data_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> dict:
        """
        Execute a data manipulation sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "get_sample", "add_column")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_data(state=session.state, params=input_params)
        return result.model_dump()

    # ========================================================================
    # ML Tools
    # ========================================================================

    @mcp.tool()
    def describe_ml_tools(ctx: Context) -> dict:
        """
        Get schemas for all ML sub-tools.
        
        Returns available tools: train_model, evaluate, predict, 
        cross_validate, save_model, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_ml(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_ml_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> dict:
        """
        Execute an ML sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "train_model", "predict")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_ml(state=session.state, params=input_params)
        return result.model_dump()

    # ========================================================================
    # Plot Tools
    # ========================================================================

    @mcp.tool()
    def describe_plot_tools(ctx: Context) -> dict:
        """
        Get schemas for all visualization sub-tools.
        
        Returns available tools: histogram, scatter, bar, line, box,
        heatmap, roc_curve, confusion_matrix, etc.
        """
        session = get_session(ctx, session_manager)
        params = DescribeCategoryInput()
        result = describe_plots(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def execute_plot_tool(
        ctx: Context,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        dataframe_name: Optional[str] = None
    ) -> Any:
        """
        Execute a visualization sub-tool.
        
        Args:
            tool_name: Name of sub-tool (e.g., "histogram", "scatter")
            params: Parameters for the sub-tool
            dataframe_name: Override active DataFrame
        
        Returns:
            Plot result with image and download_url (if remote).
        """
        session = get_session(ctx, session_manager)
        input_params = ExecuteCategoryInput(
            tool_name=tool_name,
            params=params or {},
            dataframe_name=dataframe_name
        )
        result = execute_plots(state=session.state, params=input_params)
        result_dict = result.model_dump()

        # Save plot to exports directory if there's an image
        if result_dict.get("result") and result_dict["result"].get("image_base64"):
            from stats_compass_mcp.exports import save_plot_export

            export_info = save_plot_export(
                session_id=session.session_id,
                image_base64=result_dict["result"]["image_base64"],
                name_prefix=tool_name,
            )

            if export_info["download_url"]:
                result_dict["result"]["download_url"] = export_info["download_url"]
                result_dict["result"]["filename"] = export_info["filename"]

        return with_images(result_dict)
