"""Pipeline — 계산을 공통 수식 라이브러리(친구 etsi_dq)로 위임한다."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

from etsidqcli.io import load_data
from etsidqcli.report import CheckResult, MetricResult, ProfileResult


def _ensure_shared_lib() -> None:
    if "etsi_dq" in sys.modules:
        return
    cwd = os.getcwd()
    candidates = [
        os.environ.get("ETSI_DQ_LIB"),
        os.path.join(cwd, "etsi-dq-lib"),
        os.path.join(cwd, "..", "etsi-dq-lib"),
        os.path.join(os.path.dirname(cwd), "etsi-dq-lib"),
    ]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "etsi_dq")):
            c = os.path.abspath(c)
            if c not in sys.path:
                sys.path.insert(0, c)
            return


def _load_shared():
    _ensure_shared_lib()
    try:
        from etsi_dq.pipeline import run_analysis
        from etsi_dq.schemas import AnalysisRequest
        from etsi_dq.utils import clean_dataset
    except ImportError as e:
        raise ImportError(
            "공통 수식 라이브러리(etsi-dq-lib)를 찾지 못했습니다.\n"
            "  → etsi-dq-lib 폴더가 있는 위치에서 실행하거나,\n"
            "  → export ETSI_DQ_LIB=/경로/etsi-dq-lib\n"
            f"(원본 오류: {e})"
        )
    return run_analysis, AnalysisRequest, clean_dataset


_METRIC_KEYS = ["Completeness", "Accuracy", "Consistency", "Timeliness", "Reliability", "Uniqueness"]
_GRADES = {"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.6}


def _grade(score01: float) -> str:
    for letter, cutoff in sorted(_GRADES.items(), key=lambda x: -x[1]):
        if score01 >= cutoff:
            return letter
    return "F"


def _detect_event_col(df: pd.DataFrame):
    for c in df.columns:
        if c == "__ingested_at":
            continue
        s = df[c]
        try:
            if pd.api.types.is_datetime64_any_dtype(s):
                return c
            if s.dtype == object and pd.to_datetime(s, errors="coerce").notna().mean() > 0.8:
                return c
        except Exception:
            pass
    return None


def _load_rules(config_path):
    if not config_path:
        return {}
    p = Path(config_path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text) or {}
    except Exception:
        try:
            import yaml
            return yaml.safe_load(text) or {}
        except Exception:
            return {}


def _build_config(df: pd.DataFrame, rules: dict) -> dict:
    num_cols = df.select_dtypes("number").columns.tolist()
    rel = rules.get("reliability", {}) or {}
    rel_cols = rel.get("columns") if isinstance(rel, dict) else None
    rel_cols = [c for c in (rel_cols or []) if c in df.columns] or num_cols
    cfg = {
        "comp_required_cols": [],
        "comp_granularity": "Dataset",
        "uniq_cols": rules.get("uniqueness_keys", []) or [],
        "reliability_cols": rel_cols,
        "acc_rules": rules.get("accuracy", []) or [],
        "cons_rules": rules.get("consistency", []) or [],
    }
    t = rules.get("timeliness", {}) or {}
    event = t.get("event_column") or _detect_event_col(df)
    if event:
        cfg["t_event"] = event
        cfg["t_system"] = t.get("system_column", "__ingested_at")
        cfg["t_reference_mode"] = "column"
        if t.get("sla_seconds"):
            cfg["t_sla_seconds"] = float(t["sla_seconds"])
    for _rule in cfg["acc_rules"]:
        _rf = _rule.get("reference_file")
        if _rf and Path(_rf).exists():
            cfg["acc_ref_df"] = pd.read_csv(_rf)
    for _rule in cfg["cons_rules"]:
        _rf = _rule.get("reference_file")
        if _rf and Path(_rf).exists():
            cfg["cons_ref_df"] = pd.read_csv(_rf)
    return cfg


def _profile(df: pd.DataFrame) -> ProfileResult:
    return ProfileResult(
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        missing_total=int(df.isnull().sum().sum()),
        duplicate_rows=int(df.duplicated().sum()),
    )


def _na_reason(resp, key: str) -> str:
    for msg in resp.messages:
        if msg.lower().startswith(key.lower()):
            return msg
    return "검사 규칙이 필요합니다 (--config 규칙 파일에 정의)."


def check(data, *, reference=None, config=None, metrics=None, rules_dict=None):
    run_analysis, AnalysisRequest, clean_dataset = _load_shared()
    df = load_data(data)
    df = clean_dataset(df)
    rules = rules_dict if rules_dict is not None else _load_rules(config)
    cfg = _build_config(df, rules)

    selected = _METRIC_KEYS
    if metrics:
        wanted = {m.strip().lower() for m in (metrics if isinstance(metrics, list) else [metrics])}
        selected = [k for k in _METRIC_KEYS if k.lower() in wanted] or _METRIC_KEYS

    resp = run_analysis(AnalysisRequest(df=df, selected_metrics=selected, config=cfg))

    results = {}
    for key in selected:
        raw = resp.results.get(key)
        name = key.lower()
        if raw is None:
            results[name] = MetricResult(
                name=name, score=None, grade="N/A",
                details={"na_reason": _na_reason(resp, key)},
                threshold=0.8, passed=False,
            )
        else:
            s01 = max(0.0, min(1.0, float(raw) / 100.0))
            results[name] = MetricResult(
                name=name, score=round(s01, 4), grade=_grade(s01),
                threshold=0.8, passed=s01 >= 0.8,
            )

    def _rel_bucket(s01):
        s = s01 * 100
        if s <= 5: return 1.00
        if s <= 15: return 0.80
        if s <= 30: return 0.60
        if s <= 50: return 0.40
        return 0.20

    valid = []
    for _name, _m in results.items():
        if _m.score is None:
            continue
        valid.append(_rel_bucket(_m.score) if _name == "reliability" else _m.score)
    overall = round(sum(valid) / len(valid), 4) if valid else 0.0
    return CheckResult(
        overall_score=overall, overall_grade=_grade(overall),
        metrics=results, profile=_profile(df),
    )


def profile(data):
    _run, _req, clean_dataset = _load_shared()
    df = load_data(data)
    return _profile(clean_dataset(df))
