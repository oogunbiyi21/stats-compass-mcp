"""
Data tools for Stats Compass MCP server.

Handles data loading, listing, and management.
"""

from typing import Optional

import pandas as pd
from fastmcp import Context, FastMCP
from stats_compass_core import data as core_data
from stats_compass_core.data.load_dataset import LoadDatasetInput

from stats_compass_mcp.safety import check_file_key
from stats_compass_mcp.session import SessionManager, get_session


def _export_target(session, filepath: str, category: str, extension: str):
    """Where a save tool writes, and the file name to link to.

    A confined (served) session always writes into its own exports folder,
    whatever path the caller gave: deciding this from STATS_COMPASS_SERVER_URL
    let a deployment that left it unset write wherever the caller chose
    (security scan, 8 Oct 2026, F9/F10). A local session may name any path.
    """
    from pathlib import Path as PathLib

    if not session.confined and (filepath.startswith("/") or filepath.startswith("~")):
        export_path = PathLib(filepath).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        return export_path
    filename = PathLib(filepath).name
    if not filename:
        raise ValueError(f"'{filepath}' does not name a file.")
    if not filename.endswith(extension):
        filename = f"{filename}{extension}"
    return session.export_path(category, filename)


def _without_server_paths(session, result: dict) -> dict:
    """A load result as a served session sees it: the file's name, not its server path.

    The path holds the session's folder, which in serve mode used to be the
    session id, its credential (re-scan of 0.3.32, F6).
    """
    if session.confined and result.get("source"):
        from pathlib import Path as PathLib

        name = PathLib(str(result["source"])).name
        result["source"] = name
        result["message"] = f"Loaded '{name}' as '{result.get('dataframe_name')}'"
    return result


def register_data_tools(
    mcp: FastMCP,
    session_manager: SessionManager,
    storage=None,
    include_admin: bool = False,
):
    """Register all data management tools with the FastMCP server.

    ``server_stats`` lists every session, so it is registered only for a
    local operator (``include_admin``), never on a shared server (security
    scan, 8 Oct 2026, F11).
    """

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
    def ping() -> dict:
        """Health check - verify server is running."""
        return {
            "status": "ok",
            "server": "stats-compass",
            "message": "Server is running. Sessions are created automatically."
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
    def session_info(ctx: Context) -> dict:
        """
        Get information about your current session.

        Returns:
            Session info including created_at, dataframes, models and exports.
        """
        session = get_session(ctx, session_manager)
        return session.get_info()

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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

        If you do not know the exact path, call list_files first
        (e.g. list_files(directory="~/Downloads")) to find the file.
        Do NOT use bash or shell commands — they cannot access the user's machine.

        Args:
            path: Absolute path to the CSV file. Supports ~ expansion.
            name: Name for the DataFrame (default: filename without extension)
            delimiter: Field delimiter (default: comma)
            encoding: File encoding (default: utf-8, retry with latin-1 on errors)
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
        return _without_server_paths(session, result.model_dump())

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
    def load_excel(
        ctx: Context,
        path: str,
        name: Optional[str] = None,
        sheet_name: Optional[str] = None,
        set_active: bool = True
    ) -> dict:
        """
        Load an Excel file from a local path.

        If you do not know the exact path, call list_files first
        (e.g. list_files(directory="~/Downloads")) to find the file.
        Do NOT use bash or shell commands — they cannot access the user's machine.

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
        return _without_server_paths(session, result.model_dump())

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
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
        result_dict = result.model_dump()
        if session.confined:
            result_dict["directory"] = "uploads"
            result_dict["message"] = f"Found {result_dict.get('count', 0)} file(s) in your uploads"
        return result_dict

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
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

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
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

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        export_path = _export_target(session, filepath, "data", ".csv")

        from pathlib import Path as PathLib

        from stats_compass_core.data.save_csv import SaveCSVInput
        from stats_compass_core.data.save_csv import save_csv as core_save_csv
        input_data = SaveCSVInput(dataframe_name=dataframe_name, filepath=str(export_path), index=index)
        result = core_save_csv(state=session.state, input_data=input_data)

        # Link to the file actually written: core never overwrites, so a second
        # save of x.csv is x_1.csv. A served session sees the name, never the
        # server path, which holds its session folder (re-scan of 0.3.32, F6).
        result_dict = result if isinstance(result, dict) else result.model_dump()
        if session.confined:
            name = PathLib(result_dict["filepath"]).name
            result_dict["filepath"] = name
            result_dict["message"] = f"DataFrame '{dataframe_name}' saved as '{name}'"
            download_url = session.download_url("data", name)
            if download_url:
                result_dict["download_url"] = download_url

        return result_dict

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
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
        export_path = _export_target(session, filepath, "models", ".joblib")

        from pathlib import Path as PathLib

        from stats_compass_core.ml.save_model import SaveModelInput
        from stats_compass_core.ml.save_model import save_model as core_save_model
        input_data = SaveModelInput(model_id=model_id, filepath=str(export_path))
        result = core_save_model(state=session.state, input_data=input_data)

        # Link to the file actually written (core adds _1 rather than overwrite);
        # a served session sees the name, not the server path (re-scan F6).
        result_dict = result if isinstance(result, dict) else result
        if session.confined:
            name = PathLib(result_dict["filepath"]).name
            result_dict["filepath"] = name
            result_dict["message"] = f"Model '{model_id}' saved as '{name}'"
            download_url = session.download_url("models", name)
            if download_url:
                result_dict["download_url"] = download_url

        return result_dict

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": True})
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

    if include_admin:
        @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
        def server_stats() -> dict:
            """
            Get server statistics (admin tool).

            Returns:
                Active sessions count, configuration, and session details.
            """
            return session_manager.get_stats()

    # Remote-only tools (only if storage is provided)
    if storage is not None:
        @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
        def get_upload_url(
            ctx: Context,
            filename: Optional[str] = None,
            content_type: str = "text/csv"
        ) -> dict:
            """
            Get a URL for the user to upload a CSV or Excel file in their browser.

            When sharing the upload_url with the user, always include the raw URL as
            plain text (not as a markdown hyperlink) so the user can see and copy it
            directly. You may add brief instructions around it. After they confirm
            the upload is done, call register_uploaded_file() with no arguments.

            Args:
                filename: Optional suggested filename — leave blank, the user picks the file
                content_type: MIME type (default: text/csv)

            Returns:
                Upload info with upload_url and instructions.
            """
            session = get_session(ctx, session_manager)

            return storage.get_upload_url(
                session_id=session.session_id,
                filename=filename or "",
                content_type=content_type
            )

        @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": False, "destructiveHint": False})
        def register_uploaded_file(
            ctx: Context,
            file_key: Optional[str] = None,
            dataframe_name: Optional[str] = None,
            file_type: Optional[str] = None,
            encoding: str = "utf-8"
        ) -> dict:
            """
            Load an uploaded file as a DataFrame.

            Call this after the user confirms they have uploaded their file.
            If file_key is omitted, automatically loads the most recently uploaded file.
            File type is auto-detected from the file extension (csv, xlsx, xls).

            Args:
                file_key: Filename to load (optional — omit to auto-load the latest upload)
                dataframe_name: Name for the DataFrame (default: filename without extension)
                file_type: File type override - "csv" or "excel" (auto-detected from extension if omitted)
                encoding: File encoding (default: utf-8). Try "latin-1" if you get codec errors.

            Returns:
                DataFrame info with name, shape, columns, dtypes.
            """
            session = get_session(ctx, session_manager)

            if file_key:
                # A plain name inside this session's uploads, nothing else.
                try:
                    file_key = check_file_key(file_key)
                except ValueError:
                    return {"error": f"'{file_key}' isn't one of your uploaded files."}
            else:
                uploads = storage.list_uploads(session.session_id)
                if not uploads:
                    return {"error": "No uploaded files found. Please upload a file first."}
                file_key = uploads[0]

            if not storage.file_exists(session.session_id, file_key):
                return {"error": f"File not found: {file_key}. Did you upload it?"}

            file_path = storage.get_file_path(session.session_id, file_key)

            # Determine DataFrame name
            if not dataframe_name:
                dataframe_name = file_key.rsplit(".", 1)[0]

            # Auto-detect file type from extension if not specified
            if not file_type:
                ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
                file_type = "excel" if ext in ("xlsx", "xls") else "csv"

            # Load file with automatic encoding fallback for CSVs
            try:
                if file_type.lower() == "excel":
                    df = pd.read_excel(file_path)
                else:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, encoding="latin-1")
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
