"""
Histogram metric implementation for the SONiC telemetry framework.

Histogram metrics track the distribution of values over time,
useful for measuring latencies, response times, or request sizes.
"""

from typing import List, Optional, Dict
from ..base import Metric, Reporter
from ..constants import METRIC_TYPE_HISTOGRAM


class HistogramMetric(Metric):
    """
    Histogram metric implementation.

    Histograms track the distribution of measured values, providing
    percentiles, averages, and bucket counts for analysis.
    """

    def __init__(self, name: str, description: str, unit: str, reporter: Reporter,
                 buckets: Optional[List[float]] = None,
                 common_labels: Optional[Dict[str, str]] = None):
        """
        Initialize histogram metric.

        Args:
            name: Metric name in OpenTelemetry format
            description: Human-readable description
            unit: Unit of measurement (e.g., 'seconds', 'milliseconds', 'bytes')
            reporter: Reporter instance to send measurements to
            buckets: Optional bucket boundaries for histogram distribution
            common_labels: Common labels to apply to all measurements of this metric
        """
        super().__init__(name, description, unit, reporter, common_labels)
        self.buckets = buckets or self._default_buckets()

    def _get_metric_type(self) -> str:
        """
        Return metric type identifier.

        Returns:
            Histogram metric type constant
        """
        return METRIC_TYPE_HISTOGRAM

    def _default_buckets(self) -> List[float]:
        """
        Provide default bucket boundaries for histogram.

        Returns:
            List of bucket boundary values
        """
        # Default OpenTelemetry-style buckets
        return [0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5,
                0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
