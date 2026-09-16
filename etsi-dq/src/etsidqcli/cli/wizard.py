"""Interactive configuration wizard.

대시보드의 'Configure' 단계를 터미널에서 재현한다.
컬럼 목록을 보여주고 번호로 선택하게 해서 rules.json 을 만든다.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

C_TITLE = typer.style
_BULLET = "  "


def _hr(char: str = "=", n: int = 58) -> str:
    return char * n


def _header(text: str) -> None:
    typer.echo("")
    typer.echo(_hr())
    typer.secho(f"  {text}", bold=True)
    typer.echo(_hr())


def _list_columns(cols: list[str], only: list[str] | None = None) -> list[str]:
    """번호가 매겨진 컬럼 목록을 출력하고, 선택 가능한 목록을 반환."""
    shown = only if only is not None else cols
    for i, c in enumerate(shown, 1):
        typer.echo(f"{_BULLET}[{i:>2}] {c}")
    return shown


def _pick_one(cols: list[str], prompt: str, default: str | None = None) -> str | None:
    """번호 하나를 골라 컬럼명을 반환. 빈 입력이면 default(or None)."""
    default_idx = ""
    if default and default in cols:
        default_idx = str(cols.index(default) + 1)
    raw = typer.prompt(f"{_BULLET}{prompt}", default=default_idx, show_default=bool(default_idx))
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        idx = int(raw)
        if 1 <= idx <= len(cols):
            return cols[idx - 1]
    except ValueError:
        if raw in cols:
            return raw
    typer.secho(f"{_BULLET}Invalid choice, skipping.", fg="yellow")
    return None


def _pick_many(cols: list[str], prompt: str, default: str = "") -> list[str]:
    """'1,3,5' 형식으로 여러 개 선택."""
    raw = typer.prompt(f"{_BULLET}{prompt}", default=default, show_default=bool(default))
    raw = (raw or "").strip()
    if not raw:
        return []
    picked: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
            if 1 <= idx <= len(cols):
                picked.append(cols[idx - 1])
        except ValueError:
            if part in cols:
                picked.append(part)
    return picked


def _find_csvs(exclude: Path) -> list[str]:
    files = sorted(p.name for p in Path(".").glob("*.csv") if p.resolve() != exclude.resolve())
    return files


# ---------------------------------------------------------------------------
# 각 지표 설정
# ---------------------------------------------------------------------------
def _configure_accuracy(df, data_path: Path) -> list[dict]:
    _header("Accuracy — how should values be validated?")
    typer.echo(f"{_BULLET}[1] Compare against a reference file (with tolerance)")
    typer.echo(f"{_BULLET}[2] Check a numeric range (min / max)")
    typer.echo(f"{_BULLET}[3] Skip")
    choice = typer.prompt(f"{_BULLET}Select", default="1")

    cols = list(df.columns)

    if choice.strip() == "1":
        refs = _find_csvs(data_path)
        if not refs:
            typer.secho(f"{_BULLET}No reference CSV found in this folder.", fg="yellow")
            return []
        typer.echo("")
        typer.echo(f"{_BULLET}Reference file:")
        for i, f in enumerate(refs, 1):
            typer.echo(f"{_BULLET}[{i:>2}] {f}")
        ridx = typer.prompt(f"{_BULLET}Select file", default="1")
        try:
            ref_file = refs[int(ridx) - 1]
        except Exception:
            typer.secho(f"{_BULLET}Invalid choice, skipping accuracy.", fg="yellow")
            return []

        import pandas as pd
        ref_df = pd.read_csv(ref_file)
        ref_cols = list(ref_df.columns)

        typer.echo("")
        typer.echo(f"{_BULLET}Column to validate (from {data_path.name}):")
        _list_columns(cols)
        target = _pick_one(cols, "Select column", default="Delivery_Time")
        if not target:
            return []

        typer.echo("")
        typer.echo(f"{_BULLET}Join key (must exist in both files):")
        _list_columns(cols)
        key = _pick_one(cols, "Select key", default="Order_ID")
        if not key:
            return []

        typer.echo("")
        typer.echo(f"{_BULLET}Expected-value column (from {ref_file}):")
        _list_columns(ref_cols)
        val_col = _pick_one(ref_cols, "Select column",
                            default=next((c for c in ref_cols if c != key), None))
        if not val_col:
            return []

        tol = typer.prompt(f"{_BULLET}Tolerance (absolute)", default="5")
        try:
            tol_v = float(tol)
        except ValueError:
            tol_v = 5.0

        typer.secho(f"{_BULLET}→ {target} vs {val_col} (join on {key}, ±{tol_v:g})", fg="green")
        return [{
            "method": "Reference Mapping",
            "column": target,
            "ref_mode": "External Reference File",
            "reference_file": ref_file,
            "meas_keys": [key],
            "ref_keys": [key],
            "reference_value_col": val_col,
            "tol_type": "absolute",
            "tol_value": tol_v,
        }]

    if choice.strip() == "2":
        num_cols = df.select_dtypes("number").columns.tolist()
        if not num_cols:
            typer.secho(f"{_BULLET}No numeric columns available.", fg="yellow")
            return []
        typer.echo("")
        typer.echo(f"{_BULLET}Numeric columns:")
        _list_columns(num_cols)
        picked = _pick_many(num_cols, "Select columns (e.g. 1,2)")
        rules = []
        for c in picked:
            lo = typer.prompt(f"{_BULLET}  {c} — min", default="0")
            hi = typer.prompt(f"{_BULLET}  {c} — max", default="100")
            try:
                rules.append({
                    "method": "Threshold (Min/Max)", "column": c,
                    "thr_min": float(lo), "thr_max": float(hi), "thr_inclusive": True,
                })
            except ValueError:
                typer.secho(f"{_BULLET}  Invalid number, skipping {c}.", fg="yellow")
        return rules

    return []


def _configure_consistency(df, data_path: Path) -> list[dict]:
    _header("Consistency — how should records be checked?")
    typer.echo(f"{_BULLET}[1] Referential integrity (values must exist in a valid-list file)")
    typer.echo(f"{_BULLET}[2] Expression rule (e.g. `Delivery_Time` >= 0)")
    typer.echo(f"{_BULLET}[3] Skip")
    choice = typer.prompt(f"{_BULLET}Select", default="1")

    cols = list(df.columns)

    if choice.strip() == "1":
        refs = _find_csvs(data_path)
        if not refs:
            typer.secho(f"{_BULLET}No reference CSV found in this folder.", fg="yellow")
            return []
        typer.echo("")
        typer.echo(f"{_BULLET}Valid-list file:")
        for i, f in enumerate(refs, 1):
            typer.echo(f"{_BULLET}[{i:>2}] {f}")
        default_idx = "1"
        for i, f in enumerate(refs, 1):
            if "categor" in f.lower():
                default_idx = str(i)
        ridx = typer.prompt(f"{_BULLET}Select file", default=default_idx)
        try:
            ref_file = refs[int(ridx) - 1]
        except Exception:
            typer.secho(f"{_BULLET}Invalid choice, skipping consistency.", fg="yellow")
            return []

        import pandas as pd
        ref_cols = list(pd.read_csv(ref_file).columns)

        typer.echo("")
        typer.echo(f"{_BULLET}Column to check (from {data_path.name}):")
        _list_columns(cols)
        src = _pick_one(cols, "Select column", default="Category")
        if not src:
            return []

        typer.echo("")
        typer.echo(f"{_BULLET}Valid-values column (from {ref_file}):")
        _list_columns(ref_cols)
        ref_col = _pick_one(ref_cols, "Select column", default=ref_cols[0] if ref_cols else None)
        if not ref_col:
            return []

        typer.secho(f"{_BULLET}→ {src} must exist in {ref_file}:{ref_col}", fg="green")
        return [{
            "mode": "Referential Integrity",
            "source_column": src,
            "reference_column": ref_col,
            "reference_file": ref_file,
            "ref_allow_empty": True,
        }]

    if choice.strip() == "2":
        typer.echo("")
        typer.echo(f"{_BULLET}Available columns:")
        _list_columns(cols)
        typer.echo(f"{_BULLET}Example:  `Delivery_Time` >= 0")
        expr = typer.prompt(f"{_BULLET}Expression", default="`Delivery_Time` >= 0")
        return [{"mode": "Expression", "column": "(None)", "rule": expr}]

    return []


def _configure_timeliness(df) -> dict:
    _header("Timeliness — measure delay between two timestamps")
    cols = [c for c in df.columns if c != "__ingested_at"]
    typer.echo(f"{_BULLET}Available columns:")
    _list_columns(cols)
    ev = _pick_one(cols, "Event time column (earlier)", default="Order_Time")
    if not ev:
        return {}
    sy = _pick_one(cols, "System time column (later)", default="Pickup_Time")
    if not sy:
        return {}
    sla = typer.prompt(f"{_BULLET}SLA threshold in seconds", default="3600")
    try:
        sla_v = float(sla)
    except ValueError:
        sla_v = 3600.0
    typer.secho(f"{_BULLET}→ {ev} → {sy}, SLA {sla_v:g}s", fg="green")
    return {"event_column": ev, "system_column": sy, "sla_seconds": sla_v}


def _configure_reliability(df) -> dict:
    _header("Reliability — which numeric columns should be measured?")
    num_cols = df.select_dtypes("number").columns.tolist()
    if not num_cols:
        return {}
    typer.echo(f"{_BULLET}Numeric columns:")
    _list_columns(num_cols)
    default = str(num_cols.index("Delivery_Time") + 1) if "Delivery_Time" in num_cols else ""
    picked = _pick_many(num_cols, "Select columns (e.g. 1,2)", default=default)
    if not picked:
        typer.secho(f"{_BULLET}→ using all numeric columns", fg="green")
        return {}
    typer.secho(f"{_BULLET}→ {', '.join(picked)}", fg="green")
    return {"columns": picked}


def _configure_uniqueness(df) -> list[str]:
    _header("Uniqueness — key columns for duplicate detection")
    cols = list(df.columns)
    _list_columns(cols)
    default = str(cols.index("Order_ID") + 1) if "Order_ID" in cols else ""
    picked = _pick_many(cols, "Select key columns (blank = whole row)", default=default)
    if picked:
        typer.secho(f"{_BULLET}→ {', '.join(picked)}", fg="green")
    return picked


# ---------------------------------------------------------------------------
# 메인 마법사
# ---------------------------------------------------------------------------
_ALL_METRICS = ["completeness", "accuracy", "consistency", "timeliness", "reliability", "uniqueness"]


def run_wizard(data_path: Path, out_path: Path) -> dict:
    """대화형으로 규칙을 구성하고 rules 딕셔너리를 반환한다."""
    import pandas as pd

    df = pd.read_csv(data_path)

    _header(f"Dataset — {data_path.name}")
    typer.echo(f"{_BULLET}{len(df):,} rows x {df.shape[1]} columns")
    typer.echo("")
    typer.echo(f"{_BULLET}Columns:")
    _list_columns(list(df.columns))

    _header("Metric Selector — which metrics do you want?")
    for i, m in enumerate(_ALL_METRICS, 1):
        typer.echo(f"{_BULLET}[{i}] {m.capitalize()}")
    raw = typer.prompt(f"{_BULLET}Select (e.g. 1,2,3 — blank = all)", default="", show_default=False)
    raw = (raw or "").strip()
    if raw:
        selected = []
        for part in raw.split(","):
            try:
                idx = int(part.strip())
                if 1 <= idx <= len(_ALL_METRICS):
                    selected.append(_ALL_METRICS[idx - 1])
            except ValueError:
                pass
        selected = selected or _ALL_METRICS
    else:
        selected = list(_ALL_METRICS)
    typer.secho(f"{_BULLET}→ {', '.join(selected)}", fg="green")

    rules: dict = {}
    if "accuracy" in selected:
        r = _configure_accuracy(df, data_path)
        if r:
            rules["accuracy"] = r
    if "consistency" in selected:
        r = _configure_consistency(df, data_path)
        if r:
            rules["consistency"] = r
    if "timeliness" in selected:
        r = _configure_timeliness(df)
        if r:
            rules["timeliness"] = r
    if "reliability" in selected:
        r = _configure_reliability(df)
        if r:
            rules["reliability"] = r
    if "uniqueness" in selected:
        r = _configure_uniqueness(df)
        if r:
            rules["uniqueness_keys"] = r

    rules["_metrics"] = selected

    out_path.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    _header("Configuration saved")
    typer.echo(f"{_BULLET}Saved to {out_path}")
    typer.echo(f"{_BULLET}Metrics: {', '.join(selected)}")
    return rules
