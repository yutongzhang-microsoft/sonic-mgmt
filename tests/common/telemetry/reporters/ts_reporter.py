"""
TimeSeries (TS) Reporter for real-time monitoring via OTLP.

This reporter sends metrics directly to OpenTelemetry collectors using
the OTLP protocol for real-time monitoring, dashboards, and alerting.
"""

import logging
import os
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from ..base import Reporter, Metric
from ..constants import REPORTER_TYPE_TS, METRIC_TYPE_GAUGE, METRIC_TYPE_COUNTER, METRIC_TYPE_HISTOGRAM

# OTLP exporter imports (optional - graceful degradation if not available)
try:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.proto.metrics.v1.metrics_pb2 import (
        ResourceMetrics, ScopeMetrics, Metric as OTLPMetric,
        Gauge, Sum, Histogram as OTLPHistogram,
        NumberDataPoint, HistogramDataPoint
    )
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.common.v1.common_pb2 import KeyValue, InstrumentationScope
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
            endpoint: OTLP collector endpoint (default: from OTEL_EXPORTER_OTLP_ENDPOINT env var)
            headers: Additional headers for OTLP requests
            resource_attributes: Additional resource attributes for metrics
            request: pytest request object for test context
            tbinfo: testbed info fixture data
        """
        super().__init__(REPORTER_TYPE_TS, request, tbinfo)

        # Configuration
        self.endpoint = endpoint or os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')
        self.headers = headers or {}
        self.resource_attributes = resource_attributes or {}

        # Measurement buffer
        self.measurements: List[Tuple[Metric, float, Dict[str, str], float]] = []

        # Initialize exporter if available
        if OTLP_AVAILABLE:
            self._setup_exporter()
        else:
            self.exporter = None

    def _setup_exporter(self):
        """
        Set up OTLP metric exporter.
        """
        try:
            self.exporter = OTLPMetricExporter(
                endpoint=self.endpoint,
                headers=self.headers
            )
            logging.info(f"TSReporter: OTLP exporter initialized for endpoint {self.endpoint}")
        except Exception as e:
            logging.error(f"TSReporter: Failed to initialize OTLP exporter: {e}")
            self.exporter = None

    def add_metric(self, metric: Metric, value: float, additional_labels: Optional[Dict[str, str]] = None):
        """
        Add a metric measurement to the reporter buffer.

        Args:
            metric: Metric instance
            value: Measured value
            additional_labels: Additional labels for this measurement
        """
        # Merge all labels: test context + metric labels + additional labels
        final_labels = {**self.test_context}
        final_labels.update(metric.labels)
        if additional_labels:
            final_labels.update(additional_labels)

        timestamp = time.time_ns()  # Use nanoseconds for OTLP
        self.measurements.append((metric, value, final_labels, timestamp))

        # Log for debugging
        logging.debug(f"TSReporter: Added {metric.name}={value} labels={final_labels}")

    def report(self):
        """
        Report all collected metrics via OTLP and clear buffer.
        """
        if not self.measurements:
            logging.debug("TSReporter: No measurements to report")
            return

        logging.info(f"TSReporter: Reporting {len(self.measurements)} measurements")

        if OTLP_AVAILABLE and self.exporter:
            self._report_to_otlp()
        else:
            self._report_mock()

        # Clear measurements after reporting
        self.measurements.clear()

    def _report_to_otlp(self):
        """
        Send measurements to OTLP endpoint.
        """
        try:
            # Create resource
            resource = self._create_resource()

            # Group measurements by metric for efficient batching
            metric_groups = {}
            for metric, value, labels, timestamp in self.measurements:
                key = (metric.name, metric.metric_type)
                if key not in metric_groups:
                    metric_groups[key] = {
                        'metric': metric,
                        'measurements': []
                    }
                metric_groups[key]['measurements'].append((value, labels, timestamp))

            # Create OTLP metrics
            otlp_metrics = []
            for (metric_name, metric_type), group in metric_groups.items():
                otlp_metric = self._create_otlp_metric(group['metric'], group['measurements'])
                if otlp_metric:
                    otlp_metrics.append(otlp_metric)

            if otlp_metrics:
                # Create ResourceMetrics message
                resource_metrics = ResourceMetrics(
                    resource=resource,
                    scope_metrics=[
                        ScopeMetrics(
                            scope=InstrumentationScope(
                                name="sonic-test-telemetry",
                                version="1.0.0"
                            ),
                            metrics=otlp_metrics
                        )
                    ]
                )

                # Export to OTLP
                result = self.exporter.export([resource_metrics])
                if result.name == 'SUCCESS':
                    logging.info(f"TSReporter: Successfully exported {len(otlp_metrics)} metrics")
                else:
                    logging.error(f"TSReporter: Export failed with result: {result}")

        except Exception as e:
            logging.error(f"TSReporter: Failed to export metrics: {e}")

    def _create_resource(self) -> Resource:
        """
        Create OTLP Resource with attributes.
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
            attributes.append(KeyValue(key=key, value=KeyValue.Value(string_value=str(value))))

        return Resource(attributes=attributes)

    def _create_otlp_metric(self, metric: Metric,
                            measurements: List[Tuple[float, Dict[str, str], int]]) -> Optional[OTLPMetric]:
        """
        Create OTLP metric from measurements.

        Args:
            metric: Metric instance
            measurements: List of (value, labels, timestamp) tuples

        Returns:
            OTLP Metric or None if conversion fails
        """
        try:
            otlp_metric = OTLPMetric(
                name=metric.name,
                description=metric.description,
                unit=metric.unit
            )

            if metric.metric_type == METRIC_TYPE_GAUGE:
                data_points = []
                for value, labels, timestamp in measurements:
                    data_point = NumberDataPoint(
                        attributes=self._labels_to_attributes(labels),
                        time_unix_nano=timestamp,
                        value=NumberDataPoint.Value(as_double=float(value))
                    )
                    data_points.append(data_point)

                otlp_metric.gauge = Gauge(data_points=data_points)

            elif metric.metric_type == METRIC_TYPE_COUNTER:
                data_points = []
                for value, labels, timestamp in measurements:
                    data_point = NumberDataPoint(
                        attributes=self._labels_to_attributes(labels),
                        time_unix_nano=timestamp,
                        value=NumberDataPoint.Value(as_double=float(value))
                    )
                    data_points.append(data_point)

                otlp_metric.sum = Sum(
                    data_points=data_points,
                    aggregation_temporality=Sum.AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE,
                    is_monotonic=True
                )

            elif metric.metric_type == METRIC_TYPE_HISTOGRAM:
                data_points = []
                for value, labels, timestamp in measurements:
                    # Simple histogram with single bucket for now
                    data_point = HistogramDataPoint(
                        attributes=self._labels_to_attributes(labels),
                        time_unix_nano=timestamp,
                        count=1,
                        sum=float(value),
                        bucket_counts=[1],  # Single bucket
                        explicit_bounds=[]  # No explicit bounds
                    )
                    data_points.append(data_point)

                otlp_metric.histogram = OTLPHistogram(
                    data_points=data_points,
                    aggregation_temporality=OTLPHistogram.AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE
                )

            return otlp_metric

        except Exception as e:
            logging.error(f"TSReporter: Failed to create OTLP metric for {metric.name}: {e}")
            return None

    def _labels_to_attributes(self, labels: Dict[str, str]) -> List[KeyValue]:
        """
        Convert labels dictionary to OTLP KeyValue attributes.
        """
        attributes = []
        for key, value in labels.items():
            attributes.append(KeyValue(key=key, value=KeyValue.Value(string_value=str(value))))
        return attributes

    def _report_mock(self):
        """
        Mock reporting when OTLP exporter is not available.
        """
        for metric, value, labels, timestamp in self.measurements:
            timestamp_iso = datetime.fromtimestamp(timestamp / 1e9).isoformat()
            logging.info(f"MOCK TSReporter: {metric.name}={value} "
                         f"type={metric.metric_type} unit={metric.unit} "
                         f"labels={labels} timestamp={timestamp_iso}")

    def get_measurement_count(self) -> int:
        """
        Get the number of pending measurements.

        Returns:
            Count of measurements in buffer
        """
        return len(self.measurements)

    def get_endpoint_info(self) -> Dict[str, str]:
        """
        Get OTLP endpoint configuration information.

        Returns:
            Dictionary with endpoint configuration
        """
        return {
            'endpoint': self.endpoint,
            'exporter_available': str(OTLP_AVAILABLE),
            'exporter_initialized': str(self.exporter is not None)
        }
