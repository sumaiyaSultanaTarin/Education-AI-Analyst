"""pandas-based analysis over ingested XLSX enrollment/results data, used by
the Data Analyst Agent."""

import pandas as pd


def sheets_to_dataframes(sheets: dict[str, list[dict]]) -> dict[str, pd.DataFrame]:
    """Turn the Document Ingestion Agent's {sheet_name: list[row-dict]} shape into DataFrames."""
    return {name: pd.DataFrame(rows) for name, rows in sheets.items()}


def summarize_numeric_columns(df: pd.DataFrame, passing_mark: float = 40) -> dict:
    """Compute count/mean/min/max/pass-rate for every numeric column in a sheet.

    `pass_rate` assumes a numeric column represents a score where
    `>= passing_mark` counts as a pass — a reasonable default for the sample
    result-sheet data, not a universal grading rule. Non-score numeric
    columns (e.g. a roll number) will get a pass_rate too; callers reading
    the report should treat pass_rate as meaningful only for score columns.
    """
    numeric = df.select_dtypes(include="number")
    stats = {}
    for column in numeric.columns:
        series = numeric[column].dropna()
        if series.empty:
            continue
        stats[column] = {
            "count": int(series.count()),
            "mean": round(float(series.mean()), 2),
            "min": float(series.min()),
            "max": float(series.max()),
            "pass_rate": round(float((series >= passing_mark).mean() * 100), 2),
        }
    return stats
