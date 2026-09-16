"""Result data models."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from pydantic import BaseModel, Field

class MetricResult(BaseModel):
    name: str
    score: Optional[float] = None
    grade: str
    details: dict[str, Any] = Field(default_factory=dict)
    column_scores: dict[str, float] = Field(default_factory=dict)
    threshold: float = 0.8
    passed: bool = True

class ProfileResult(BaseModel):
    row_count: int = 0
    column_count: int = 0
    columns: dict[str, dict[str, Any]] = Field(default_factory=dict)
    missing_total: int = 0
    duplicate_rows: int = 0

class CheckResult(BaseModel):
    overall_score: float
    overall_grade: str
    metrics: dict[str, MetricResult]
    profile: ProfileResult
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self, path=None):
        text = json.dumps(self.model_dump(), indent=2, ensure_ascii=False)
        if path: Path(path).write_text(text, encoding="utf-8")
        return text

    def to_dict(self): return self.model_dump()

    def to_dataframe(self):
        return pd.DataFrame([{"metric": n, "score": m.score, "grade": m.grade, "passed": m.passed} for n, m in self.metrics.items()])

    def summary(self):
        lines = ["", "=" * 50, "  ETSI Data Quality Report", "=" * 50]
        lines.append(f"  Overall: {self.overall_score:.1%}  ({self.overall_grade})")
        lines.append("-" * 50)
        for name, m in self.metrics.items():
            if m.score is None:
                lines.append(f"  – {name:<16s} {'N/A':>6s}  (검사 규칙 필요)")
                continue
            bar = "█" * int(m.score * 20) + "░" * (20 - int(m.score * 20))
            status = "✓" if m.passed else "✗"
            lines.append(f"  {status} {name:<16s} {m.score:.1%}  {bar}  {m.grade}")
        lines.append("=" * 50)
        lines.append(f"  {self.profile.row_count:,} rows · {self.profile.column_count} columns")
        lines.append("")
        return "\n".join(lines)

    def failed_checks(self):
        return [{"metric": n, "score": m.score, "threshold": m.threshold} for n, m in self.metrics.items() if not m.passed]
