"""Configuration loader."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
try:
    import yaml
except ImportError:
    yaml = None

class MetricConfig(BaseModel):
    enabled: bool = True
    threshold: float = 0.8
    params: dict[str, Any] = Field(default_factory=dict)

class ScoringConfig(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
    grading: dict[str, float] = Field(default_factory=lambda: {"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.6})

class Config(BaseModel):
    metrics: dict[str, MetricConfig] = Field(default_factory=dict)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)

    @classmethod
    def load(cls, source=None):
        if source is None: return cls()
        if isinstance(source, dict): return cls(**source)
        path = Path(source)
        if not path.exists(): raise FileNotFoundError(f"Config not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f) if yaml and path.suffix in (".yaml",".yml") else json.load(f)
        return cls(**(data or {}))

    def get_metric_config(self, name): return self.metrics.get(name, MetricConfig())
    def get_weight(self, name, default=1.0): return self.scoring.weights.get(name, default)
