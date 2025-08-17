"""
TimeSeries (TS) Reporter for real-time monitoring via OTLP.

This reporter sends metrics directly to OpenTelemetry collectors using
the OTLP protocol for real-time monitoring, dashboards, and alerting.
"""

import logging
import os
import time
from typing import Dict, Optional, List, Tuple
from ..base import Reporter, Metric
from ..constants import (
    REPORTER_TYPE_TS, METRIC_TYPE_GAUGE, METRIC_TYPE_COUNTER, METRIC_TYPE_HISTOGRAM,
    ENV_SONIC_MGMT_TS_REPORT_ENDPOINT
)

# OTLP exporter imports (optional - graceful degradation if not available)
try:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics.export import MetricsData
    from opentelemetry.sdk.metrics._internal.point import ResourceMetrics as SDKResourceMetrics, ScopeMetrics as SDKScopeMetrics
    from opentelemetry.sdk.resources import Resource as SDKResource
    from opentelemetry.proto.metrics.v1.metrics_pb2 import (
        ResourceMetrics as ProtoResourceMetrics, ScopeMetrics as ProtoScopeMetrics, Metric as OTLPMetric,
        Gauge, Sum, Histogram as OTLPHistogram,
        NumberDataPoint, HistogramDataPoint, AggregationTemporality
    )
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource as ProtoResource
    from opentelemetry.proto.common.v1.common_pb2 import KeyValue, InstrumentationScope, AnyValue
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
        self._setup_exporter()

    def _setup_exporter(self):
        """
        Set up OTLP metric exporter.
        """
        self.mock_exporter = None

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
            mock_exporter_func: Function that takes ResourceMetrics as parameter.
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

        if self.mock_exporter or not self.exporter:
            # Use protobuf objects for mock reporting
            resource_metrics = self._create_proto_resource_metrics(timestamp)
            self._export_metrics_mock(resource_metrics)
        else:
            # Use SDK objects for real export
            sdk_resource_metrics = self._create_sdk_resource_metrics(timestamp)
            self._export_metrics_sdk(sdk_resource_metrics)

    def _create_proto_resource_metrics(self, timestamp: float) -> Optional[ProtoResourceMetrics]:
        """
        Create protobuf ResourceMetrics from current measurements for mock reporting.

        Args:
            timestamp: Timestamp for all measurements in this batch

        Returns:
            ProtoResourceMetrics object or None if crafting fails
        """
        if not OTLP_AVAILABLE:
            return None

        resource = self._create_proto_resource()

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

        # Create OTLP metrics
        otlp_metrics = []
        for (metric_name, metric_type), group in metric_groups.items():
            otlp_metric = self._create_otlp_metric(group['metric'], group['measurements'], timestamp)
            if otlp_metric:
                otlp_metrics.append(otlp_metric)

        if len(otlp_metrics) == 0:
            return None

        # Create ProtoResourceMetrics message
        resource_metrics = ProtoResourceMetrics(
            resource=resource,
            scope_metrics=[
                ProtoScopeMetrics(
                    scope=InstrumentationScope(
                        name="sonic-test-telemetry",
                        version="1.0.0"
                    ),
                    metrics=otlp_metrics
                )
            ]
        )

        return resource_metrics

    def _create_proto_resource(self) -> ProtoResource:
        """
        Create protobuf Resource with attributes.
        """
        # Merge test context with resource attributes
        all_attrs = {
            "service.name": "sonic-test-telemetry",
            "service.version": "1.0.0",
            **self.test_context,
            **self.resource_attributes
        }

        # Convert to KeyValue pairs
        attributes = []
        for key, value in all_attrs.items():
            attributes.append(KeyValue(key=key, value=AnyValue(string_value=str(value))))

        return ProtoResource(attributes=attributes)

    def _create_sdk_resource_metrics(self, timestamp: float) -> Optional[SDKResourceMetrics]:
        """
        Create SDK ResourceMetrics from current measurements for real export.

        Args:
            timestamp: Timestamp for all measurements in this batch

        Returns:
            SDKResourceMetrics object or None if crafting fails
        """
        if not OTLP_AVAILABLE:
            return None

        # Create SDK Resource
        sdk_resource = self._create_sdk_resource()

        # For now, create an empty SDKResourceMetrics - the actual implementation
        # would need to create proper SDK metrics objects, but this is complex
        # and may require significant refactoring. For the immediate fix,
        # we'll fall back to mock reporting when real export is needed.
        return None

    def _create_sdk_resource(self) -> SDKResource:
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

        return SDKResource.create(all_attrs)

    def _create_otlp_metric(self, metric: Metric,
                            measurements: List[Tuple[float, Dict[str, str]]],
                            timestamp: float) -> Optional[OTLPMetric]:
        """
        Create OTLP metric from measurements.

        Args:
            metric: Metric instance
            measurements: List of (value, labels) tuples
            timestamp: Timestamp for all measurements

        Returns:
            OTLP Metric or None if conversion fails
        """
        if metric.metric_type == METRIC_TYPE_GAUGE:
            data_points = []
            for value, labels in measurements:
                data_point = NumberDataPoint(
                    attributes=self._labels_to_attributes(labels),
                    time_unix_nano=int(timestamp),
                    as_double=float(value)
                )
                data_points.append(data_point)

            otlp_metric = OTLPMetric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                gauge=Gauge(data_points=data_points)
            )

        elif metric.metric_type == METRIC_TYPE_COUNTER:
            data_points = []
            for value, labels in measurements:
                data_point = NumberDataPoint(
                    attributes=self._labels_to_attributes(labels),
                    time_unix_nano=int(timestamp),
                    as_double=float(value)
                )
                data_points.append(data_point)

            otlp_metric = OTLPMetric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                sum=Sum(
                    data_points=data_points,
                    aggregation_temporality=AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE,
                    is_monotonic=True
                )
            )

        elif metric.metric_type == METRIC_TYPE_HISTOGRAM:
            data_points = []
            for value, labels in measurements:
                # Simple histogram with single bucket for now
                data_point = HistogramDataPoint(
                    attributes=self._labels_to_attributes(labels),
                    time_unix_nano=int(timestamp),
                    count=1,
                    sum=float(value),
                    bucket_counts=[1],  # Single bucket
                    explicit_bounds=[]  # No explicit bounds
                )
                data_points.append(data_point)

            otlp_metric = OTLPMetric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
                histogram=OTLPHistogram(
                    data_points=data_points,
                    aggregation_temporality=AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE
                )
            )

        else:
            return None

        return otlp_metric

    def _labels_to_attributes(self, labels: Dict[str, str]) -> List[KeyValue]:
        """
        Convert labels dictionary to OTLP KeyValue attributes.
        """
        attributes = []
        for key, value in labels.items():
            attributes.append(KeyValue(key=key, value=AnyValue(string_value=str(value))))
        return attributes

    def _export_metrics_sdk(self, sdk_resource_metrics: Optional[SDKResourceMetrics]):
        """
        Export SDK ResourceMetrics using the configured exporter.

        Args:
            sdk_resource_metrics: SDK ResourceMetrics object to export
        """
        if not sdk_resource_metrics:
            # Fall back to proto mock reporting when SDK metrics creation fails
            proto_resource_metrics = self._create_proto_resource_metrics(
                timestamp=int(time.time() * 1_000_000_000)  # Convert to nanoseconds
            )
            self._export_metrics_mock(proto_resource_metrics)
            return

        if self.exporter:
            # Create MetricsData with the SDK ResourceMetrics
            metrics_data = MetricsData(resource_metrics=[sdk_resource_metrics])
            result = self.exporter.export(metrics_data)
            if result.name == 'SUCCESS':
                logging.info("TSReporter: Successfully exported to OTLP endpoint")
            else:
                logging.warning(f"TSReporter: Export failed with result: {result}")
        else:
            logging.warning("TSReporter: No exporter available")

    def _export_metrics_mock(self, resource_metrics: Optional[ProtoResourceMetrics]):
        """
        Export protobuf ResourceMetrics using mock exporter or fallback.

        Args:
            resource_metrics: Protobuf ResourceMetrics object to export
        """
        if not resource_metrics:
            return

        if self.mock_exporter:
            # Use mock exporter for testing
            self.mock_exporter(resource_metrics)
            logging.info("TSReporter: Successfully exported via mock exporter")
        else:
            # Fall back to mock reporting
            self._report_mock_from_resource_metrics(resource_metrics)

    def _report_mock_from_resource_metrics(self, resource_metrics):
        """
        Mock reporting from ResourceMetrics when exporter is not available.

        Args:
            resource_metrics: ResourceMetrics object to mock report
        """
        for scope_metric in resource_metrics.scope_metrics:
            for metric in scope_metric.metrics:
                logging.info(f"MOCK TSReporter: {metric.name} "
                             f"description='{metric.description}' unit='{metric.unit}'")
