"""
VERIDEXA data ingestion.
Reads an uploaded file into a pandas DataFrame with validation and
sane defaults (encoding sniffing, delimiter sniffing, size limits).
"""
from __future__ import annotations

import io

import pandas as pd

from config.settings import UPLOAD_MAX_MB
from utils.logger import get_logger
from utils.validators import allowed_upload_extension, sanitize_identifier

log = get_logger(__name__)


class DataLoadError(Exception):
    pass


def load_uploaded_file(uploaded_file) -> pd.DataFrame:
    """`uploaded_file` is a Streamlit UploadedFile object."""
    if uploaded_file is None:
        raise DataLoadError("No file provided.")

    name = uploaded_file.name
    if not allowed_upload_extension(name):
        raise DataLoadError(
            "Unsupported file type. Please upload a .csv, .xlsx, .xls, .json, or .parquet file."
        )

    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > UPLOAD_MAX_MB:
        raise DataLoadError(f"File is {size_mb:.1f} MB, which exceeds the {UPLOAD_MAX_MB} MB limit.")

    ext = name.rsplit(".", 1)[-1].lower()
    raw = uploaded_file.getvalue()

    try:
        if ext == "csv":
            df = _read_csv_robust(raw)
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(raw))
        elif ext == "json":
            df = pd.read_json(io.BytesIO(raw))
        elif ext == "parquet":
            df = pd.read_parquet(io.BytesIO(raw))
        else:  # pragma: no cover — guarded above already
            raise DataLoadError("Unsupported file type.")
    except DataLoadError:
        raise
    except Exception as e:
        log.exception("Failed to parse uploaded file %s", name)
        raise DataLoadError(f"Could not read this file it may be corrupted or malformed ({e}).") from e

    if df.empty:
        raise DataLoadError("The uploaded file has no rows.")
    if df.shape[1] == 0:
        raise DataLoadError("The uploaded file has no columns.")

    df = _clean_column_names(df)
    df = _infer_dtypes(df)
    log.info("Loaded file %s: %d rows x %d cols", name, *df.shape)
    return df


def _read_csv_robust(raw: bytes) -> pd.DataFrame:
    """Try common encodings/delimiters before giving up."""
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    last_err = None
    for enc in encodings:
        try:
            text = raw.decode(enc)
            return pd.read_csv(io.StringIO(text), sep=None, engine="python")
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise DataLoadError(f"Could not decode CSV with common encodings ({last_err}).")


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict[str, int] = {}
    new_cols = []
    for col in df.columns:
        clean = sanitize_identifier(str(col).strip().lower().replace(" ", "_"))
        if clean in seen:
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 0
        new_cols.append(clean)
    df.columns = new_cols
    return df


def _infer_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Attempt to coerce object columns that are actually dates or numbers."""
    for col in df.columns:
        if df[col].dtype != object:
            continue
        sample = df[col].dropna().astype(str).head(50)
        if sample.empty:
            continue

        # Try numeric
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() >= 0.9 * df[col].notna().sum() and df[col].notna().sum() > 0:
            df[col] = numeric
            continue

        # Try datetime (only if column name hints at a date, to avoid
        # false positives on things like ID strings)
        if any(hint in col for hint in ("date", "time", "day", "month", "year", "created", "updated")):
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if parsed.notna().sum() >= 0.8 * df[col].notna().sum():
                df[col] = parsed
    return df
