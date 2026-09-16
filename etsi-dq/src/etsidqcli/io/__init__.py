"""Data loader."""
from pathlib import Path
import pandas as pd

def load_data(source):
    if isinstance(source, pd.DataFrame): return source
    path = Path(source)
    if not path.exists(): raise FileNotFoundError(f"Data file not found: {path}")
    s = path.suffix.lower()
    if s == ".csv": return pd.read_csv(path)
    elif s == ".parquet": return pd.read_parquet(path)
    elif s in (".xlsx", ".xls"): return pd.read_excel(path)
    elif s == ".json": return pd.read_json(path)
    elif s == ".tsv": return pd.read_csv(path, sep="\t")
    else: raise ValueError(f"Unsupported format: {s}")
