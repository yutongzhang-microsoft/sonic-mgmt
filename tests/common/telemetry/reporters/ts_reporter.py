"""
TimeSeries (TS) Reporter for real-time monitoring via OTLP.

This reporter sends metrics directly to OpenTelemetry collectors using
the OTLP protocol for real-time monitoring, dashboards, and alerting.
"""

import logging
import os
from typing import Dict, Optional, List, Tuple
from ..base import Reporter
from ..constants import (
    REPORTER_TYPE_TS, METRIC_TYPE_GAUGE, METRIC_TYPE_COUNTER, METRIC_TYPE_HISTOGRAM,
    ENV_SONIC_MGMT_TS_REPORT_ENDPOINT
)

# OTLP exporter imports (optional - graceful degradation if not available)
try:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics.export import (
        MetricsData, ResourceMetrics, ScopeMetrics, Metric,
        Gauge, Sum, Histogram, AggregationTemporality
    )
    from opentelemetry.sdk.metrics._internal.point import (
        NumberDataPoint, HistogramDataPoint
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk._internal.scope import InstrumentationScope
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False
    logging.warning("OTLP exporter not available, TSReporter will operate in mock mode")


class TSReporter(Reporter):
    """
    TimeSeries reporter for real-time monitoring via OTLP.

    Sends metrics directly to OpenTelemetry collectors using the OTLP protocol
    without requiring the full OpenTelemetry SDK setup.
    """

    def __init__(self, endpoint: Optional[str] = None, headers: Optional[Dict[str, str]] = None,
                 resource_attributes: Optional[Dict[str, str]] = None, request=None, tbinfo=None):
        """
        Initialize TS reporter with OTLP exporter.

        Args:
            endpoint: OTLP collector endpoint (default: from SONIC_MGMT_TS_REPORT_ENDPOINT env var)
            headers: Additional headers for OTLP requests
            resource_attributes: Additional resource attributes for metrics
            request: pytest request object for test context
            tbinfo: testbed info fixture data
        """
        super().__init__(REPORTER_TYPE_TS, request, tbinfo)

        # Configuration
        self.endpoint = endpoint or os.environ.get(ENV_SONIC_MGMT_TS_REPORT_ENDPOINT, 'http://localhost:4317')
        self.headers = headers or {}
        self.resource_attributes = resource_attributes or {}
        self.mock_exporter = None  # For testing compatibility
        self._setup_exporter()

    def _setup_exporter(self):
        """
        Set up OTLP metric exporter.
        """
        if not OTLP_AVAILABLE:
            self.exporter = None
            return

        try:
            self.exporter = OTLPMetricExporter(
                endpoint=self.endpoint,
                headers=self.headers
            )
            logging.info(f"TSReporter: OTLP exporter initialized for endpoint {self.endpoint}")
        except Exception as e:
            logging.error(f"TSReporter: Failed to initialize OTLP exporter: {e}")
            self.exporter = None

    def set_mock_exporter(self, mock_exporter_func):
        """
        Set a mock exporter function for testing.

        Args:
            mock_exporter_func: Function that takes MetricsData as parameter.
                              Set to None to clear mock exporter.
        """
        self.mock_exporter = mock_exporter_func
        logging.info(f"TSReporter: Mock exporter {'set' if mock_exporter_func else 'cleared'}")

    def _report(self, timestamp: float):
        """
        Report all collected metrics via OTLP.

        Args:
            timestamp: Timestamp for this reporting batch (automatically in nanoseconds)
        """
        logging.info(f"TSReporter: Reporting {len(self.recorded_metrics)} measurements")

        if not OTLP_AVAILABLE:
            self._report_mock(timestamp)
            return

        # Create MetricsData using SDK objects
        metrics_data = self._create_metrics_data(timestamp)
        if metrics_data:
            if self.mock_exporter:
                # Use mock exporter for testing - but adapt ResourceMetrics for compatibility
                self._export_metrics_mock(metrics_data)
            else:
                self._export_metrics(metrics_data)

    def _report_mock(self, timestamp: float):
        """
        Mock reporting when OTLP is not available.

        Args:
            timestamp: Timestamp for this reporting batch
        """
        for record in self.recorded_metrics:
            logging.info(f"MOCK TSReporter: {record.metric.name}={record.value} "
                         f"labels={record.labels} timestamp={timestamp}")

    def _create_metrics_data(self, timestamp: float) -> Optional[MetricsData]:
        """
        Create MetricsData using SDK objects from current measurements.

        Args:
            timestamp: Timestamp for all measurements in this batch

        Returns:
            MetricsData object or None if creation fails
        """
        if not OTLP_AVAILABLE:
            return None

        # Create SDK Resource
        resource = self._create_resource()

        # Group measurements by metric for efficient batching
        metric_groups = {}
        for record in self.recorded_metrics:
            key = (record.metric.name, record.metric.metric_type)
            if key not in metric_groups:
                metric_groups[key] = {
                    'metric': record.metric,
                    'measurements': []
                }
            metric_groups[key]['measurements'].append((record.value, record.labels))

        # Create SDK metrics
        sdk_metrics = []
        for (metric_name, metric_type), group in metric_groups.items():
            sdk_metric = self._create_sdk_metric(group['metric'], group['measurements'], timestamp)
            if sdk_metric:
                sdk_metrics.append(sdk_metric)

        if len(sdk_metrics) == 0:
            return None

        # Create ResourceMetrics with ScopeMetrics
        scope = InstrumentationScope(
            name="sonic-test-telemetry",
            version="1.0.0"
        )

        scope_metrics = ScopeMetrics(
            scope=scope,
            metrics=sdk_metrics,
            schema_url=""
        )

        resource_metrics = ResourceMetrics(
            resource=resource,
            scope_metrics=[scope_metrics],
            schema_url=""
        )

        return MetricsData(resource_metrics=[resource_metrics])

    def _create_resource(self) -> Resource:
        """
        Create SDK Resource with attributes.
        """
        # Merge test context with resource attributes
        all_attrs = {
            "service.name": "sonic-test-telemetry",
            "service.version": "1.0.0",
            **self.test_context,
            **self.resource_attributes
        }

        return Resource.create(all_attrs)

    def _create_sdk_metric(self, metric, measurements: List[Tuple[float, Dict[str, str]]],
                           timestamp: float) -> Optional[Metric]:
        """
        Create SDK Metric from measurements.

        Args:
            metric: Metric instance from telemetry framework
            measurements: List of (value, labels) tuples
            timestamp: Timestamp for all measurements

        Returns:
            SDK Metric or None if conversion fails
        """
        timestamp_ns = int(timestamp)

        if metric.metric_type == METRIC_TYPE_GAUGE:
            data_points = []
            for value, labels in measurements:
                data_point = NumberDataPoint(
                    attributes=labels,
                    start_time_unix_nano=timestamp_ns,
                    time_unix_nano=timestamp_ns,
                    value=float(value)
                )
                data_points.append(data_point)

            gauge_data = Gauge(data_points=data_points)
            return Metric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                data=gauge_data
            )

        elif metric.metric_type == METRIC_TYPE_COUNTER:
            data_points = []
            for value, labels in measurements:
                data_point = NumberDataPoint(
                    attributes=labels,
                    start_time_unix_nano=timestamp_ns,
                    time_unix_nano=timestamp_ns,
                    value=float(value)
                )
                data_points.append(data_point)

            sum_data = Sum(
                data_points=data_points,
                aggregation_temporality=AggregationTemporality.CUMULATIVE,
                is_monotonic=True
            )
            return Metric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                data=sum_data
            )

        elif metric.metric_type == METRIC_TYPE_HISTOGRAM:
            data_points = []
            for value, labels in measurements:
                # Simple histogram with single bucket for now
                data_point = HistogramDataPoint(
                    attributes=labels,
                    start_time_unix_nano=timestamp_ns,
                    time_unix_nano=timestamp_ns,
                    count=1,
                    sum=float(value),
                    bucket_counts=[1],  # Single bucket
                    explicit_bounds=[]  # No explicit bounds
                )
                data_points.append(data_point)

            histogram_data = Histogram(
                data_points=data_points,
                aggregation_temporality=AggregationTemporality.CUMULATIVE
            )
            return Metric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                data=histogram_data
            )

        else:
            return None

    def _export_metrics(self, metrics_data: MetricsData):
        """
        Export MetricsData using the configured OTLP exporter.

        Args:
            metrics_data: MetricsData object to export
        """
        if self.exporter:
            result = self.exporter.export(metrics_data)
            if result.name == 'SUCCESS':
                logging.info("TSReporter: Successfully exported to OTLP endpoint")
            else:
                logging.warning(f"TSReporter: Export failed with result: {result}")
        else:
            logging.warning("TSReporter: No exporter available")

    def _export_metrics_mock(self, metrics_data: MetricsData):
        """
        Export MetricsData using mock exporter for testing.

        Args:
            metrics_data: MetricsData object to export
        """
        if self.mock_exporter and metrics_data.resource_metrics:
            # Extract the first ResourceMetrics for compatibility with test expectations
            resource_metrics = metrics_data.resource_metrics[0]
            self.mock_exporter(resource_metrics)
            logging.info("TSReporter: Successfully exported via mock exporter")
        else:
            logging.warning("TSReporter: No mock exporter available")
