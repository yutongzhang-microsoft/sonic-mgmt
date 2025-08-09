"""
Counter metric implementation for the SONiC telemetry framework.

Counter metrics represent cumulative values that only increase over time,
such as packet counts, error counts, or total bytes transferred.
"""

from typing import Dict, Optional
from ..base import Metric, Reporter
from ..constants import METRIC_TYPE_COUNTER


class CounterMetric(Metric):
    """
    Counter metric implementation.

    Counters represent cumulative values that monotonically increase,
    like packet counts, bytes transferred, or error occurrences.
    """

    def __init__(self, name: str, description: str, unit: str, reporter: Reporter,
                 common_labels: Optional[Dict[str, str]] = None):
        """
        Initialize counter metric.

        Args:
            name: Metric name in OpenTelemetry format
            description: Human-readable description
            unit: Unit of measurement (e.g., 'count', 'bytes', 'packets')
            reporter: Reporter instance to send measurements to
            common_labels: Common labels to apply to all measurements of this metric
        """
        super().__init__(name, description, unit, reporter, common_labels)

    def _get_metric_type(self) -> str:
        """
        Return metric type identifier.

        Returns:
            Counter metric type constant
        """
        return METRIC_TYPE_COUNTER
