import logging
import os
from textwrap import dedent
from typing import Annotated, Optional

from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

from .decorators import log_io


def _is_python_repl_enabled() -> bool:
    """Check if Python REPL tool is enabled from configuration."""
    # Check environment variable first
    env_enabled = os.getenv("ENABLE_PYTHON_REPL", "false").lower()
    if env_enabled in ("true", "1", "yes", "on"):
        return True
    return False


# Initialize REPL and logger
repl: Optional[PythonREPL] = PythonREPL() if _is_python_repl_enabled() else None
logger = logging.getLogger(__name__)

_PYTHON_REPL_BOOTSTRAP = dedent(
    """
    from urllib.parse import quote, unquote, urlsplit, urlunsplit

    def _omniknow_encode_remote_url(
        url,
        _quote=quote,
        _unquote=unquote,
        _urlsplit=urlsplit,
        _urlunsplit=urlunsplit,
    ):
        if not isinstance(url, str):
            return url
        parsed = _urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            return url
        encoded_path = _quote(_unquote(parsed.path), safe="/:@")
        return _urlunsplit(
            (parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment)
        )

    try:
        import pandas as _omniknow_pd

        if not getattr(_omniknow_pd, "_omniknow_remote_url_patch", False):
            def _omniknow_patch_io_target(
                target,
                _encoder=_omniknow_encode_remote_url,
            ):
                if isinstance(target, str):
                    return _encoder(target)
                return target

            def _omniknow_read_excel(
                io,
                *args,
                _original=_omniknow_pd.read_excel,
                _patch_target=_omniknow_patch_io_target,
                **kwargs,
            ):
                return _original(_patch_target(io), *args, **kwargs)

            def _omniknow_read_csv(
                filepath_or_buffer,
                *args,
                _original=_omniknow_pd.read_csv,
                _patch_target=_omniknow_patch_io_target,
                **kwargs,
            ):
                return _original(_patch_target(filepath_or_buffer), *args, **kwargs)

            def _omniknow_excel_file(
                path_or_buffer,
                *args,
                _original=_omniknow_pd.ExcelFile,
                _patch_target=_omniknow_patch_io_target,
                **kwargs,
            ):
                return _original(_patch_target(path_or_buffer), *args, **kwargs)

            _omniknow_pd.read_excel = _omniknow_read_excel
            _omniknow_pd.read_csv = _omniknow_read_csv
            _omniknow_pd.ExcelFile = _omniknow_excel_file
            _omniknow_pd._omniknow_remote_url_patch = True
    except Exception:
        pass
    """
).strip()


def _prepare_python_repl_code(code: str) -> str:
    if not code.strip():
        return _PYTHON_REPL_BOOTSTRAP
    return f"{_PYTHON_REPL_BOOTSTRAP}\n\n{code}"


@tool
@log_io
def python_repl_tool(
    code: Annotated[
        str, "The python code to execute to do further analysis or calculation."
    ],
):
    """Use this to execute python code and do data analysis or calculation. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""

    # Check if the tool is enabled
    if not _is_python_repl_enabled():
        error_msg = "Python REPL tool is disabled. Please enable it in environment configuration."
        logger.warning(error_msg)
        return f"Tool disabled: {error_msg}"

    if not isinstance(code, str):
        error_msg = f"Invalid input: code must be a string, got {type(code)}"
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    logger.info("Executing Python code")
    prepared_code = _prepare_python_repl_code(code)
    try:
        result = repl.run(prepared_code)
        # Check if the result is an error message by looking for typical error patterns
        if isinstance(result, str) and ("Error" in result or "Exception" in result):
            logger.error(result)
            return f"Error executing code:\n```python\n{code}\n```\nError: {result}"
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = repr(e)
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str
