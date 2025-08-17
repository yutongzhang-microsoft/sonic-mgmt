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
                 buckets: List[float], common_labels: Optional[Dict[str, str]] = None):
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
        super().__init__(METRIC_TYPE_HISTOGRAM, name, description, unit, reporter, common_labels)
        self.buckets = buckets

    def record(self, values: List[float], additional_labels: Optional[Dict[str, str]] = None):
        """
        Record a list of measurements for this histogram metric.

        Args:
            values: List of measured values for histogram distribution
            additional_labels: Additional labels for this specific measurement
        """
        if len(values) != len(self.buckets) + 1:
            raise ValueError("Number of values must match number of histogram buckets")

        self.reporter.add_record(self, values, additional_labels)
