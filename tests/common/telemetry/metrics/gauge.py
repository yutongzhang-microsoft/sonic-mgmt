"""
Gauge metric implementation for the SONiC telemetry framework.

Gauge metrics represent a value that can go up or down over time,
such as temperature, utilization percentages, or current measurements.
"""

from typing import Dict, Optional
from ..base import Metric, Reporter
from ..constants import METRIC_TYPE_GAUGE


class GaugeMetric(Metric):
    """
    Gauge metric implementation.

    Gauges represent instantaneous values that can increase or decrease,
    like temperature readings, utilization percentages, or queue depths.
    """

    def __init__(self, name: str, description: str, unit: str, reporter: Reporter,
                 common_labels: Optional[Dict[str, str]] = None):
        """
        Initialize gauge metric.

        Args:
            name: Metric name in OpenTelemetry format
            description: Human-readable description
            unit: Unit of measurement (e.g., 'celsius', 'percent', 'bytes')
            reporter: Reporter instance to send measurements to
            common_labels: Common labels to apply to all measurements of this metric
        """
        super().__init__(name, description, unit, reporter, common_labels)

    def _get_metric_type(self) -> str:
        """
        Return metric type identifier.

        Returns:
            Gauge metric type constant
        """
        return METRIC_TYPE_GAUGE
