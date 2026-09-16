"""Metric registry."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from etsidqcli.metrics.base import BaseMetric

class MetricRegistry:
    _metrics: dict[str, type[BaseMetric]] = {}

    @classmethod
    def register(cls, metric_cls):
        cls._metrics[metric_cls.name] = metric_cls
        return metric_cls

    @classmethod
    def get(cls, name):
        if name not in cls._metrics:
            avail = ", ".join(cls._metrics.keys())
            raise ValueError(f"Unknown metric: '{name}'. Available: {avail}")
        return cls._metrics[name]

    @classmethod
    def list_all(cls): return sorted(cls._metrics.keys())
