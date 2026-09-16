"""Data profiling."""
import pandas as pd
from etsidqcli.report import ProfileResult

def profile(df):
    cols = {}
    for col in df.columns:
        s = df[col]
        info = {"dtype": str(s.dtype), "missing": int(s.isnull().sum()), "missing_pct": round(s.isnull().mean(), 4), "unique": int(s.nunique())}
        if pd.api.types.is_numeric_dtype(s):
            c = s.dropna()
            if len(c): info.update({"min": float(c.min()), "max": float(c.max()), "mean": round(float(c.mean()), 4)})
        cols[col] = info
    return ProfileResult(row_count=len(df), column_count=len(df.columns), columns=cols, missing_total=int(df.isnull().sum().sum()), duplicate_rows=int(df.duplicated().sum()))
