import io
import os
from typing import Annotated
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from langchain_core.tools import tool

from .decorators import log_io

_SUPPORTED_TABULAR_SUFFIXES = {".csv", ".xlsx", ".xls"}
_CSV_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk", "latin1")


def _normalize_dataframe(df):
    return df.fillna("").astype(str)


def _normalize_io_target(target: str) -> str:
    if not isinstance(target, str):
        return target

    parsed = urlsplit(target)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return target

    encoded_path = quote(unquote(parsed.path), safe="/:@")
    return urlunsplit(
        (parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment)
    )


def _render_sheet_block(sheet_name: str, df) -> str:
    normalized = _normalize_dataframe(df)
    csv_text = normalized.to_csv(index=False, lineterminator="\n")
    return (
        f"## Sheet: {sheet_name}\n"
        f"Rows: {len(normalized)}\n"
        f"Columns: {len(normalized.columns)}\n"
        f"Column Names: {list(normalized.columns)}\n"
        "Full Content (CSV):\n"
        f"```csv\n{csv_text}```"
    )


def _read_csv_bytes_with_fallbacks(raw_bytes: bytes):
    import pandas as pd

    last_error = None
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(
                io.BytesIO(raw_bytes),
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
        except Exception as exc:  # pragma: no cover - fallback loop
            last_error = exc
    raise ValueError(f"Unable to decode CSV with supported encodings: {last_error}")


def _read_remote_csv(file_path: str):
    import requests

    response = requests.get(_normalize_io_target(file_path), timeout=30)
    response.raise_for_status()
    return _read_csv_bytes_with_fallbacks(response.content)


def _read_local_csv(file_path: str):
    import pandas as pd

    last_error = None
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(
                file_path,
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
        except Exception as exc:  # pragma: no cover - fallback loop
            last_error = exc
    raise ValueError(f"Unable to decode CSV with supported encodings: {last_error}")


def _read_csv(file_path: str):
    if file_path.lower().startswith(("http://", "https://")):
        return _read_remote_csv(file_path)
    return _read_local_csv(file_path)


def _read_excel(file_path: str):
    import pandas as pd

    return pd.read_excel(
        _normalize_io_target(file_path),
        sheet_name=None,
        dtype=str,
        keep_default_na=False,
    )


@tool
@log_io
def read_full_tabular_file(
    file_path: Annotated[
        str,
        (
            "Exact CSV/XLS/XLSX path or URL to read in full. Use this only after"
            " resolving the precise file path from get_kb_files."
        ),
    ],
):
    """Read the full content of one CSV or Excel file without doing any analysis."""

    normalized_path = str(file_path or "").strip()
    if not normalized_path:
        return "Error: file_path is required."

    suffix = os.path.splitext(normalized_path.split("?", 1)[0])[1].lower()
    if suffix not in _SUPPORTED_TABULAR_SUFFIXES:
        return (
            "Error: unsupported tabular file type. "
            "Only .csv, .xlsx, and .xls are supported."
        )

    try:
        if suffix == ".csv":
            dataframe = _read_csv(normalized_path)
            body = _render_sheet_block("CSV", dataframe)
            sheet_names = ["CSV"]
        else:
            sheets = _read_excel(normalized_path)
            sheet_names = list(sheets.keys())
            body = "\n\n".join(
                _render_sheet_block(sheet_name, df)
                for sheet_name, df in sheets.items()
            )

        return (
            "# Full Tabular File Content\n"
            f"Path: {normalized_path}\n"
            f"Type: {suffix}\n"
            f"Sheet Names: {sheet_names}\n\n"
            f"{body}"
        )
    except Exception as exc:
        return f"Error reading tabular file '{normalized_path}': {exc}"
