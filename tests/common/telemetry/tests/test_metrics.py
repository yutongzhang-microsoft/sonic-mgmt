"""
Tests for telemetry metrics classes using mock reporters.

This module focuses on testing the metric classes themselves and metric collections
using mock reporters to verify correct value recording, label passing, and
metric type identification.

Each metric collection test follows the pattern:
1. Initialize collection with mock reporter
2. Record values for each metric attribute
3. Validate recorded metrics match expected JSON baseline
"""

import pytest

# Import the telemetry framework
from common.telemetry import (
    GaugeMetric, CounterMetric, HistogramMetric
)

# Import test utilities
from .common_utils import MockReporter


class TestIndividualMetricTypes:
    """Test suite for individual metric types (GaugeMetric, CounterMetric, HistogramMetric)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_reporter = MockReporter()

    def test_gauge_metric_basic_recording(self):
        """Test that GaugeMetric records values correctly."""
        metric = GaugeMetric(
            name="test.metric.gauge",
            description="Test gauge metric",
            unit="percent",
            reporter=self.mock_reporter
        )

        # Record a value
        metric.record(75.5)

        # Verify it was recorded correctly
        assert len(self.mock_reporter.recorded_metrics) == 1
        record = self.mock_reporter.recorded_metrics[0]
        assert record.metric.name == "test.metric.gauge"
        assert record.value == 75.5
        assert record.metric.metric_type == "gauge"
        assert record.metric.description == "Test gauge metric"
        assert record.metric.unit == "percent"

    def test_counter_metric_basic_recording(self):
        """Test that CounterMetric records values correctly."""
        metric = CounterMetric(
            name="packets.transmitted",
            description="Total packets transmitted",
            unit="packets",
            reporter=self.mock_reporter
        )

        # Record values (counters are cumulative)
        metric.record(1000)
        metric.record(1500)
        metric.record(2100)

        # Verify all values were recorded
        assert len(self.mock_reporter.recorded_metrics) == 3
        values = [r.value for r in self.mock_reporter.recorded_metrics]
        assert values == [1000, 1500, 2100]

        # Verify metric type
        for record in self.mock_reporter.recorded_metrics:
            assert record.metric.metric_type == "counter"

    def test_histogram_metric_basic_recording(self):
        """Test that HistogramMetric records values correctly."""
        metric = HistogramMetric(
            name="response.time",
            description="API response time distribution",
            unit="milliseconds",
            reporter=self.mock_reporter
        )

        # Record a distribution of response times
        response_times = [1.2, 3.4, 2.1, 5.6, 1.8]
        for time in response_times:
            metric.record(time)

        # Verify all values were recorded
        assert len(self.mock_reporter.recorded_metrics) == len(response_times)
        recorded_values = [r.value for r in self.mock_reporter.recorded_metrics]
        assert recorded_values == response_times

        # Verify metric type
        for record in self.mock_reporter.recorded_metrics:
            assert record.metric.metric_type == "histogram"


class TestLabelMerging:
    """Test suite for label merging and precedence."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_reporter = MockReporter()
        # Set up test context in mock reporter
        self.mock_reporter.test_context = {
            "test.testbed": "vlab-01",
            "test.testcase": "test_label_merging",
            "test.file": "test_metrics.py",
            "test.os.version": "sonic-build-123"
        }

    def test_label_precedence_and_merging(self):
        """Test that labels are merged correctly with proper precedence."""

        # Create metric with common labels
        common_labels = {"device.id": "dut-01", "device.port.id": "Ethernet0"}
        metric = GaugeMetric(
            name="port.tx.util",
            description="Port TX utilization",
            unit="percent",
            reporter=self.mock_reporter,
            common_labels=common_labels
        )

        # Record with additional labels, including override
        additional_labels = {
            "test.params.duration": "30s",
            "test.testbed": "override-testbed",  # This should override test context
            "device.id": "override-device"  # This should override common labels
        }
        metric.record(85.5, additional_labels)

        # Verify label merging and precedence
        assert len(self.mock_reporter.recorded_metrics) == 1
        labels = self.mock_reporter.recorded_metrics[0].labels

        # Test context labels (should be preserved unless overridden)
        assert labels["test.testcase"] == "test_label_merging"
        assert labels["test.file"] == "test_metrics.py"
        assert labels["test.os.version"] == "sonic-build-123"

        # Common labels (should be preserved unless overridden)
        assert labels["device.port.id"] == "Ethernet0"  # Not overridden

        # Additional labels should override test context and common labels
        assert labels["test.testbed"] == "override-testbed"  # Overrides test context
        assert labels["device.id"] == "override-device"    # Overrides common labels
        assert labels["test.params.duration"] == "30s"     # New additional label


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
