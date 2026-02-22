"""
Data tools for Stats Compass MCP server.

Handles data loading, listing, and management.
"""

from typing import Optional

import pandas as pd
from fastmcp import Context, FastMCP
from stats_compass_core import data as core_data
from stats_compass_core.data.load_dataset import LoadDatasetInput

from stats_compass_mcp.session import SessionManager, get_session


def register_data_tools(mcp: FastMCP, session_manager: SessionManager, storage=None):
    """Register all data management tools with the FastMCP server."""

    @mcp.tool(annotations={"readOnlyHint": True})
    def ping() -> dict:
        """Health check - verify server is running."""
        return {
            "status": "ok",
            "server": "stats-compass",
            "message": "Server is running. Sessions are created automatically."
        }

    @mcp.tool(annotations={"readOnlyHint": True})
    def session_info(ctx: Context) -> dict:
        """
        Get information about your current session.
        
        Returns:
            Session info including session_id, created_at, dataframes, models.
        """
        session = get_session(ctx, session_manager)
        return session.get_info()

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_dataframes(ctx: Context) -> dict:
        """
        List all DataFrames in your session.
        
        Returns:
            List of DataFrames with name, shape, columns, and active status.
        """
        session = get_session(ctx, session_manager)

        dataframes = session.state.list_dataframes()
        active_name = session.state.get_active_dataframe_name()

        return {
            "dataframes": [
                {
                    "name": df.name,
                    "shape": list(df.shape),
                    "columns": list(df.columns),
                    "is_active": df.name == active_name
                }
                for df in dataframes
            ],
            "active_dataframe": active_name,
            "count": len(dataframes)
        }

    @mcp.tool()
    def load_dataset(
        ctx: Context,
        name: str,
        set_active: bool = True
    ) -> dict:
        """
        Load a built-in sample dataset.
        
        Available datasets: TATASTEEL, Housing, Bukayo_Saka_7322
        
        Args:
            name: Dataset name
            set_active: Whether to set as active DataFrame (default: True)
        
        Returns:
            DataFrame info with name, shape, columns.
        """
        session = get_session(ctx, session_manager)

        params = LoadDatasetInput(name=name, set_active=set_active)
        result = core_data.load_dataset(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def load_csv(
        ctx: Context,
        path: str,
        name: Optional[str] = None,
        delimiter: str = ",",
        encoding: str = "utf-8",
        set_active: bool = True
    ) -> dict:
        """
        Load a CSV file from a local path.
        
        Args:
            path: Absolute path to the CSV file. Supports ~ expansion.
            name: Name for the DataFrame (default: filename without extension)
            delimiter: Field delimiter (default: comma)
            encoding: File encoding (default: utf-8)
            set_active: Whether to set as active DataFrame (default: True)
        
        Returns:
            DataFrame info with name, shape, columns, dtypes.
        """
        session = get_session(ctx, session_manager)

        from stats_compass_core.data.load_csv import LoadCSVInput
        from stats_compass_core.data.load_csv import load_csv as core_load_csv
        params = LoadCSVInput(
            path=path,
            name=name,
            delimiter=delimiter,
            encoding=encoding,
            set_active=set_active
        )
        result = core_load_csv(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def load_excel(
        ctx: Context,
        path: str,
        name: Optional[str] = None,
        sheet_name: Optional[str] = None,
        set_active: bool = True
    ) -> dict:
        """
        Load an Excel file from a local path.
        
        Args:
            path: Absolute path to the Excel file. Supports ~ expansion.
            name: Name for the DataFrame (default: filename without extension)
            sheet_name: Sheet to load (default: first sheet)
            set_active: Whether to set as active DataFrame (default: True)
        
        Returns:
            DataFrame info with name, shape, columns, dtypes.
        """
        session = get_session(ctx, session_manager)

        from stats_compass_core.data.load_excel import LoadExcelInput
        from stats_compass_core.data.load_excel import load_excel as core_load_excel
        params = LoadExcelInput(
            path=path,
            name=name,
            sheet_name=sheet_name,
            set_active=set_active
        )
        result = core_load_excel(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_files(
        ctx: Context,
        directory: str = "."
    ) -> dict:
        """
        List files in a directory. Useful for finding data files.
        
        Args:
            directory: Directory path. Supports ~ expansion (e.g., ~/Downloads).
        
        Returns:
            List of files in the directory.
        """
        session = get_session(ctx, session_manager)
        from stats_compass_core.data.list_files import ListFilesInput
        from stats_compass_core.data.list_files import list_files as core_list_files
        params = ListFilesInput(directory=directory)
        result = core_list_files(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_sample(
        ctx: Context,
        dataframe_name: Optional[str] = None,
        n: int = 10,
        method: str = "head"
    ) -> dict:
        """
        Get sample rows from a DataFrame.
        
        Args:
            dataframe_name: Name of DataFrame (default: active)
            n: Number of rows (default: 10)
            method: 'head', 'tail', or 'random'
        
        Returns:
            Sample rows as records.
        """
        session = get_session(ctx, session_manager)

        from stats_compass_core.data.get_sample import GetSampleInput
        from stats_compass_core.data.get_sample import get_sample as core_get_sample
        params = GetSampleInput(dataframe_name=dataframe_name, n=n, method=method)
        result = core_get_sample(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_schema(
        ctx: Context,
        dataframe_name: Optional[str] = None,
        sample_values: int = 3
    ) -> dict:
        """
        Get the schema and metadata of a DataFrame.
        
        Args:
            dataframe_name: Name of DataFrame (default: active)
            sample_values: Number of sample values per column
        
        Returns:
            Schema with columns, dtypes, nulls, and sample values.
        """
        session = get_session(ctx, session_manager)

        from stats_compass_core.data.get_schema import GetSchemaInput
        from stats_compass_core.data.get_schema import get_schema as core_get_schema
        params = GetSchemaInput(dataframe_name=dataframe_name, sample_values=sample_values)
        result = core_get_schema(state=session.state, params=params)
        return result.model_dump()

    @mcp.tool()
    def save_csv(
        ctx: Context,
        dataframe_name: str,
        filepath: str,
        index: bool = False
    ) -> dict:
        """
        Save a DataFrame to a CSV file.
        
        Args:
            dataframe_name: Name of the DataFrame to save
            filepath: Path where the CSV file will be saved. 
                      For local mode: can be absolute path (e.g., ~/Downloads/data.csv)
                      For remote mode: filename only, saved to session exports
            index: Whether to write row index (default: False)
        
        Returns:
            Save result with filepath and download_url (if remote).
        """
        session = get_session(ctx, session_manager)

        from pathlib import Path as PathLib
        
        # Check if running in remote mode (SERVER_URL is set)
        import os
        is_remote = bool(os.getenv("STATS_COMPASS_SERVER_URL", ""))
        
        # For local mode with absolute/home paths, use the path directly
        # For remote mode, always use the exports directory
        if not is_remote and (filepath.startswith("/") or filepath.startswith("~")):
            # Expand ~ and use the path as-is
            export_path = PathLib(filepath).expanduser()
            # Ensure parent directory exists
            export_path.parent.mkdir(parents=True, exist_ok=True)
            filename = export_path.name
        else:
            # Remote mode or relative path - use exports directory
            filename = PathLib(filepath).name
            if not filename.endswith('.csv'):
                filename = f"{filename}.csv"
            export_path = session.export_path("data", filename)

        from stats_compass_core.data.save_csv import SaveCSVInput
        from stats_compass_core.data.save_csv import save_csv as core_save_csv
        input_data = SaveCSVInput(dataframe_name=dataframe_name, filepath=str(export_path), index=index)
        result = core_save_csv(state=session.state, input_data=input_data)

        # Add download URL if available (remote mode only)
        result_dict = result if isinstance(result, dict) else result.model_dump()
        if is_remote:
            download_url = session.download_url("data", filename)
            if download_url:
                result_dict["download_url"] = download_url

        return result_dict

    @mcp.tool()
    def save_model(
        ctx: Context,
        model_id: str,
        filepath: str
    ) -> dict:
        """
        Save a trained model to a file.
        
        Args:
            model_id: ID of the model to save
            filepath: Path where the model will be saved.
                      For local mode: can be absolute path (e.g., ~/Downloads/model.joblib)
                      For remote mode: filename only, saved to session exports
        
        Returns:
            Save result with filepath and download_url (if remote).
        """
        session = get_session(ctx, session_manager)

        from pathlib import Path as PathLib
        import os
        is_remote = bool(os.getenv("STATS_COMPASS_SERVER_URL", ""))
        
        # For local mode with absolute/home paths, use the path directly
        if not is_remote and (filepath.startswith("/") or filepath.startswith("~")):
            export_path = PathLib(filepath).expanduser()
            export_path.parent.mkdir(parents=True, exist_ok=True)
            filename = export_path.name
        else:
            filename = PathLib(filepath).name
            if not filename.endswith('.joblib'):
                filename = f"{filename}.joblib"
            export_path = session.export_path("models", filename)

        from stats_compass_core.ml.save_model import SaveModelInput
        from stats_compass_core.ml.save_model import save_model as core_save_model
        input_data = SaveModelInput(model_id=model_id, filepath=str(export_path))
        result = core_save_model(state=session.state, input_data=input_data)

        # Add download URL if available (remote mode only)
        result_dict = result if isinstance(result, dict) else result
        if is_remote:
            download_url = session.download_url("models", filename)
            if download_url:
                result_dict["download_url"] = download_url

        return result_dict

    @mcp.tool(annotations={"destructiveHint": True})
    def delete_session(ctx: Context) -> dict:
        """
        Delete your current session and all its data.
        
        Returns:
            Deletion result.
        """
        session = get_session(ctx, session_manager)
        session_id = session.session_id

        files_deleted = 0
        if storage:
            files_deleted = storage.delete_session_files(session_id)
        session_deleted = session_manager.delete(session_id)

        return {
            "success": session_deleted,
            "files_deleted": files_deleted,
            "message": "Session deleted" if session_deleted else "Session not found"
        }

    @mcp.tool(annotations={"readOnlyHint": True})
    def server_stats() -> dict:
        """
        Get server statistics (admin tool).
        
        Returns:
            Active sessions count, configuration, and session details.
        """
        return session_manager.get_stats()

    # Remote-only tools (only if storage is provided)
    if storage is not None:
        @mcp.tool(annotations={"readOnlyHint": True})
        def get_upload_url(
            ctx: Context,
            filename: str,
            content_type: str = "text/csv"
        ) -> dict:
            """
            Get a presigned URL for uploading a file.
            
            For S3 storage: Returns a presigned PUT URL.
            For local storage: Returns a file path.
            
            Args:
                filename: Desired filename (e.g., "my_data.csv")
                content_type: MIME type (default: text/csv)
            
            Returns:
                Upload info with url, method, headers, file_key.
            """
            session = get_session(ctx, session_manager)

            return storage.get_upload_url(
                session_id=session.session_id,
                filename=filename,
                content_type=content_type
            )

        @mcp.tool()
        def register_uploaded_file(
            ctx: Context,
            file_key: str,
            dataframe_name: Optional[str] = None,
            file_type: str = "csv"
        ) -> dict:
            """
            Register an uploaded file and load it as a DataFrame.
            
            After uploading to the URL from get_upload_url(), call this
            to load the file into your session.
            
            Args:
                file_key: The file_key returned from get_upload_url()
                dataframe_name: Name for the DataFrame (default: filename without extension)
                file_type: File type - "csv" or "excel"
            
            Returns:
                DataFrame info with name, shape, columns, dtypes.
            """
            session = get_session(ctx, session_manager)

            if not storage.file_exists(session.session_id, file_key):
                return {"error": f"File not found: {file_key}. Did you upload it?"}

            file_path = storage.get_file_path(session.session_id, file_key)

            # Determine DataFrame name
            if not dataframe_name:
                dataframe_name = file_key.rsplit(".", 1)[0]

            # Load file
            try:
                if file_type.lower() == "excel":
                    df = pd.read_excel(file_path)
                else:
                    df = pd.read_csv(file_path)
            except Exception as e:
                return {"error": f"Failed to load file: {str(e)}"}

            # Register in session
            session.state.set_dataframe(df, name=dataframe_name, operation="upload")

            return {
                "success": True,
                "dataframe_name": dataframe_name,
                "shape": list(df.shape),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            }
