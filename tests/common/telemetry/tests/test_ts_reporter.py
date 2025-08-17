"""
Tests for TSReporter (TimeSeries Reporter).

This module focuses on testing the TSReporter implementation:
- Verifies OTLP metric crafting and exporting
- Tests mock exporter functionality
- Validates ResourceMetrics structure
- Tests device metrics integration
"""

import pytest
from unittest.mock import Mock

# Import the telemetry framework
from common.telemetry import (
    GaugeMetric, HistogramMetric,
    DevicePortMetrics
)

pytestmark = [
    pytest.mark.topology('any'),
    pytest.mark.disable_loganalyzer
]


class TestTSReporter:
    """Test suite for TimeSeries reporter OTLP integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_request = Mock()
        self.mock_request.node.name = "test_ts_reporter"
        self.mock_request.node.fspath.strpath = "/test/path/test_otel.py"
        self.mock_request.node.callspec.params = {}
        self.mock_tbinfo = {"conf-name": "physical-testbed-01", "duts": ["dut-01", "dut-02"]}

    def test_set_clear_mock_exporter(self):
        """Test setting and clearing mock exporter."""
        from common.telemetry.reporters.ts_reporter import TSReporter

        mock_exporter_func, _ = self._create_mock_export_func()

        # Create TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Initially no mock exporter
        assert ts_reporter.mock_exporter is None

        # Set mock exporter
        ts_reporter.set_mock_exporter(mock_exporter_func)
        assert ts_reporter.mock_exporter is not None
        assert ts_reporter.mock_exporter == mock_exporter_func

        # Clear mock exporter
        ts_reporter.set_mock_exporter(None)
        assert ts_reporter.mock_exporter is None

    def test_no_measurements(self):
        """Test TSReporter behavior when no measurements are recorded."""
        # Create TSReporter with mock exporter
        ts_reporter, exported_metrics = self._create_ts_reporter_with_mock_exporter()

        # Call report with no measurements
        ts_reporter.report()

        # Verify no export was called
        assert len(exported_metrics) == 0

    def test_mock_exporter_gauge_metric(self):
        """Test TSReporter with mock exporter for GaugeMetric."""
        # Create TSReporter with mock exporter
        ts_reporter, exported_metrics = self._create_ts_reporter_with_mock_exporter()

        # Create gauge metric
        gauge_metric = GaugeMetric(
            name="test.cpu.usage",
            description="CPU usage percentage",
            unit="percent",
            reporter=ts_reporter
        )

        # Record gauge metric
        test_labels = {"device.id": "test-dut", "test.scenario": "gauge"}
        gauge_metric.record(85.5, test_labels)

        # Call report to trigger mock exporter
        ts_reporter.report()

        # Verify mock exporter was called
        assert len(exported_metrics) == 1, f"Expected 1 export call, got {len(exported_metrics)}"

        # Verify the exported MetricsData structure
        metrics_data = exported_metrics[0]
        resource_metrics = metrics_data.resource_metrics[0]
        self._validate_otlp_resource_structure(resource_metrics)
        scope_metric = self._validate_otlp_scope_structure(resource_metrics, expected_metrics_count=1)

        # Check metrics - should have 1 gauge metric
        otlp_metric = scope_metric.metrics[0]
        assert otlp_metric.name == "test.cpu.usage"
        assert otlp_metric.description == "CPU usage percentage"
        assert otlp_metric.unit == "percent"
        assert hasattr(otlp_metric.data, 'data_points')

        # Verify measurements were cleared
        assert ts_reporter.recorded_metrics_count() == 0

    def test_mock_exporter_histogram_metric(self):
        """Test TSReporter with mock exporter for HistogramMetric."""
        # Create TSReporter with mock exporter
        ts_reporter, exported_metrics = self._create_ts_reporter_with_mock_exporter()

        # Create histogram metric
        histogram_metric = HistogramMetric(
            name="test.response.time",
            description="API response time",
            unit="milliseconds",
            buckets=[0, 100, 200],
            reporter=ts_reporter
        )

        # Record histogram metric with a list of values
        test_labels = {"device.id": "test-dut", "test.scenario": "histogram"}
        histogram_metric.record([10, 20, 30, 40], test_labels)

        # Call report to trigger mock exporter
        ts_reporter.report()

        # Verify mock exporter was called
        assert len(exported_metrics) == 1, f"Expected 1 export call, got {len(exported_metrics)}"

        # Verify the exported MetricsData structure
        metrics_data = exported_metrics[0]
        resource_metrics = metrics_data.resource_metrics[0]
        self._validate_otlp_resource_structure(resource_metrics)
        scope_metric = self._validate_otlp_scope_structure(resource_metrics, expected_metrics_count=1)

        # Check metrics - should have 1 histogram metric
        otlp_metric = scope_metric.metrics[0]
        assert otlp_metric.name == "test.response.time"
        assert otlp_metric.description == "API response time"
        assert otlp_metric.unit == "milliseconds"
        assert hasattr(otlp_metric.data, 'data_points')

        # Verify measurements were cleared
        assert ts_reporter.recorded_metrics_count() == 0

    def test_metric_grouping(self):
        """Test that TSReporter correctly groups metrics by name and type."""
        # Create TSReporter with mock exporter
        ts_reporter, exported_metrics = self._create_ts_reporter_with_mock_exporter()

        # Create multiple measurements for the same metric
        metric = GaugeMetric("test.grouped.metric", "Test grouping", "count", ts_reporter)
        metric.record(100, {"instance": "1"})
        metric.record(200, {"instance": "2"})
        metric.record(300, {"instance": "3"})

        ts_reporter.report()

        # Verify grouping - should have 1 OTLP metric with 3 data points
        metrics_data = exported_metrics[0]
        resource_metrics = metrics_data.resource_metrics[0]
        scope_metric = self._validate_otlp_scope_structure(resource_metrics, expected_metrics_count=1)

        otlp_metric = scope_metric.metrics[0]
        assert otlp_metric.name == "test.grouped.metric"
        assert len(otlp_metric.data.data_points) == 3

        # Verify all data points are present
        values = [dp.value for dp in otlp_metric.data.data_points]
        assert sorted(values) == [100.0, 200.0, 300.0]

    def test_periodic_reporting_simulation(self):
        """Test periodic reporting behavior like real monitoring scenario."""
        # Create TSReporter with mock exporter
        ts_reporter, exported_metrics = self._create_ts_reporter_with_mock_exporter()

        # Create metrics like a real monitoring scenario
        port_metrics = DevicePortMetrics(
            reporter=ts_reporter,
            labels={"device.id": "monitoring-dut", "device.port.id": "Ethernet0"}
        )

        # Simulate periodic measurements (like every minute)
        simulation_iterations = 3

        for i in range(simulation_iterations):
            # Simulate changing port utilization over time
            port_metrics.tx_util.record(45.2 + i * 5)
            port_metrics.rx_util.record(38.7 + i * 3)

            # Report for this time period
            ts_reporter.report()

            # Verify incremental reporting
            assert len(exported_metrics) == i + 1

        # Verify final total
        assert len(exported_metrics) == simulation_iterations

    def test_without_mock_exporter(self):
        """Test TSReporter without mock exporter (should fall back to mock reporting)."""
        from common.telemetry.reporters.ts_reporter import TSReporter

        # Create TSReporter without mock exporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create metric
        metric = GaugeMetric(
            name="test.fallback.metric",
            description="Test fallback metric",
            unit="percent",
            reporter=ts_reporter
        )

        # Record measurement
        metric.record(45.0, {"device.id": "fallback-dut"})

        # Report metrics - should fall back to mock reporting (no exception)
        ts_reporter.report()

        # Verify measurements were cleared
        assert ts_reporter.recorded_metrics_count() == 0

    def _create_mock_export_func(self):
        """
        Create a mock exporter function for testing TSReporter.

        Returns:
            tuple: (mock_exporter_func, exported_metrics_list)
                - mock_exporter_func: Function to pass to TSReporter.set_mock_exporter()
                - exported_metrics_list: List that captures all exported MetricsData
        """
        exported_metrics = []

        def mock_exporter_func(metrics_data):
            """
            Mock exporter that captures MetricsData for verification.

            Args:
                metrics_data: MetricsData object from OTLP SDK
            """
            exported_metrics.append(metrics_data)

            # Validate basic structure
            assert hasattr(metrics_data, 'resource_metrics'), "MetricsData missing resource_metrics"
            assert len(metrics_data.resource_metrics) > 0, "MetricsData should have resource_metrics"

            # Log captured metrics for debugging
            for resource_metrics in metrics_data.resource_metrics:
                assert hasattr(resource_metrics, 'resource'), "ResourceMetrics missing resource"
                assert hasattr(resource_metrics, 'scope_metrics'), "ResourceMetrics missing scope_metrics"
                assert len(resource_metrics.scope_metrics) > 0, "ResourceMetrics should have scope_metrics"

        return mock_exporter_func, exported_metrics

    def _create_ts_reporter_with_mock_exporter(self, resource_attributes=None):
        """
        Create TSReporter with mock exporter for testing.

        Args:
            resource_attributes: Optional custom resource attributes

        Returns:
            tuple: (ts_reporter, exported_metrics)
        """
        from common.telemetry.reporters.ts_reporter import TSReporter

        # Create mock exporter
        mock_exporter_func, exported_metrics = self._create_mock_export_func()

        # Create TSReporter with optional resource attributes
        if resource_attributes:
            ts_reporter = TSReporter(
                resource_attributes=resource_attributes,
                request=self.mock_request,
                tbinfo=self.mock_tbinfo
            )
        else:
            ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        ts_reporter.set_mock_exporter(mock_exporter_func)

        return ts_reporter, exported_metrics

    def _validate_otlp_resource_structure(self, resource_metrics, expected_custom_attrs=None):
        """
        Validate OTLP ResourceMetrics structure and resource attributes.

        Args:
            resource_metrics: ResourceMetrics object from OTLP SDK
            expected_custom_attrs: Optional dict of expected custom resource attributes
        """
        # Check resource attributes
        assert resource_metrics.resource is not None
        resource_attrs = resource_metrics.resource.attributes

        # Verify standard service attributes
        assert "service.name" in resource_attrs
        assert resource_attrs["service.name"] == "sonic-test-telemetry"

        # Verify test context attributes
        assert resource_attrs["test.testcase"] == "test_ts_reporter"
        assert resource_attrs["test.testbed"] == "physical-testbed-01"

        # Verify custom resource attributes if provided
        if expected_custom_attrs:
            for key, expected_value in expected_custom_attrs.items():
                assert resource_attrs[key] == expected_value

    def _validate_otlp_scope_structure(self, resource_metrics, expected_metrics_count=1):
        """
        Validate OTLP ScopeMetrics structure.

        Args:
            resource_metrics: ResourceMetrics object from OTLP
            expected_metrics_count: Expected number of metrics in scope

        Returns:
            scope_metric: The validated ScopeMetric object
        """
        # Check scope metrics
        assert len(resource_metrics.scope_metrics) == 1
        scope_metric = resource_metrics.scope_metrics[0]
        assert scope_metric.scope.name == "sonic-test-telemetry"
        assert scope_metric.scope.version == "1.0.0"
        assert len(scope_metric.metrics) == expected_metrics_count

        return scope_metric


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
