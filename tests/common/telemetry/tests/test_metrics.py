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

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import pytest

# Import the telemetry framework
sys.path.append('/data/r12f/code/sonic/mgmt/tests')
from common.telemetry import (  # noqa: E402
    DevicePortMetrics, DevicePSUMetrics, DeviceQueueMetrics,
    DeviceTemperatureMetrics, DeviceFanMetrics,
    GaugeMetric, CounterMetric, HistogramMetric
)
from common.telemetry.base import Reporter, Metric  # noqa: E402


@dataclass
class MockMetricRecord:
    """Mock record of a metric measurement for testing."""
    metric: 'Metric'
    value: float
    labels: Dict[str, str]
    timestamp: Optional[float] = None


class MockReporter(Reporter):
    """Mock reporter that logs all metrics for testing."""

    def __init__(self, reporter_type: str = "mock", request=None, tbinfo=None):
        super().__init__(reporter_type, request, tbinfo)
        self.recorded_metrics: List[MockMetricRecord] = []
        self.report_called = False

    def add_metric(self, metric: 'Metric', value: float, additional_labels: Optional[Dict[str, str]] = None):
        """Record the metric call for verification."""
        # Merge all labels (test context + metric labels + additional labels)
        final_labels = {}
        final_labels.update(self.test_context)
        final_labels.update(metric.labels)
        if additional_labels:
            final_labels.update(additional_labels)

        record = MockMetricRecord(
            metric=metric,
            value=value,
            labels=final_labels
        )
        self.recorded_metrics.append(record)

    def report(self):
        """Mark that report was called."""
        self.report_called = True


@pytest.fixture
def mock_reporter():
    """Provide a fresh mock reporter for each test."""
    return MockReporter()


def load_expected_records(collection_name: str) -> List[Dict]:
    """Load expected records from JSON baseline file."""
    baseline_dir = os.path.join(os.path.dirname(__file__), 'baselines')
    baseline_file = os.path.join(baseline_dir, f'{collection_name}.json')

    with open(baseline_file, 'r') as f:
        baseline_data = json.load(f)

    return baseline_data["expected_records"]


def validate_recorded_metrics(mock_reporter: MockReporter, expected_records: List[Dict]):
    """
    Common validation function to compare mock reporter results with expected records from JSON.

    Args:
        mock_reporter: The mock reporter that recorded metrics
        expected_records: List of expected record dictionaries from JSON baseline
    """
    # Verify correct number of metrics recorded
    assert len(mock_reporter.recorded_metrics) == len(expected_records), \
        f"Expected {len(expected_records)} recorded metrics, got {len(mock_reporter.recorded_metrics)}"

    # Convert recorded metrics to comparable format
    actual_records = []
    for record in mock_reporter.recorded_metrics:
        actual_records.append({
            "metric_name": record.metric.name,
            "value": record.value,
            "labels": {k: v for k, v in record.labels.items()
                       if not k.startswith("test.")}  # Filter out test context labels
        })

    # Sort both lists by metric name for consistent comparison
    actual_records.sort(key=lambda x: x["metric_name"])
    expected_records.sort(key=lambda x: x["metric_name"])

    # Validate each expected record was recorded correctly
    for i, expected in enumerate(expected_records):
        actual = actual_records[i]

        assert actual["metric_name"] == expected["metric_name"], \
            f"Metric name mismatch at index {i}: expected {expected['metric_name']}, got {actual['metric_name']}"

        assert actual["value"] == expected["value"], \
            f"Value mismatch for {expected['metric_name']}: expected {expected['value']}, got {actual['value']}"

        assert actual["labels"] == expected["labels"], \
            f"Labels mismatch for {expected['metric_name']}: expected {expected['labels']}, got {actual['labels']}"


def test_device_port_metrics(mock_reporter):
    """Test DevicePortMetrics collection records all metrics correctly."""
    # Load expected records from JSON baseline
    expected_records = load_expected_records("device_port_metrics")

    # Create port metrics collection
    port_metrics = DevicePortMetrics(
        reporter=mock_reporter,
        labels={"device.id": "spine-01", "device.port.id": "Ethernet8"}
    )

    # Record each metric value directly
    port_metrics.tx_util.record(45.2)
    port_metrics.rx_util.record(32.8)
    port_metrics.tx_bps.record(1200000000)
    port_metrics.rx_bps.record(1000000000)
    port_metrics.tx_ok.record(12345678)
    port_metrics.rx_ok.record(10987654)
    port_metrics.tx_err.record(3)
    port_metrics.rx_err.record(5)
    port_metrics.tx_drop.record(12)
    port_metrics.rx_drop.record(8)
    port_metrics.tx_overrun.record(0)
    port_metrics.rx_overrun.record(1)

    # Validate results using common function
    validate_recorded_metrics(mock_reporter, expected_records)


def test_device_psu_metrics(mock_reporter):
    """Test DevicePSUMetrics collection records all metrics correctly."""
    # Load expected records from JSON baseline
    expected_records = load_expected_records("device_psu_metrics")

    # Create PSU metrics collection
    psu_metrics = DevicePSUMetrics(
        reporter=mock_reporter,
        labels={"device.id": "leaf-02", "device.psu.id": "PSU-1"}
    )

    # Record each metric value directly
    psu_metrics.voltage.record(12.1)
    psu_metrics.current.record(18.5)
    psu_metrics.power.record(222.0)
    psu_metrics.status.record(1.0)
    psu_metrics.led.record(1.0)

    # Validate results using common function
    validate_recorded_metrics(mock_reporter, expected_records)


def test_device_queue_metrics(mock_reporter):
    """Test DeviceQueueMetrics collection records all metrics correctly."""
    # Load expected records from JSON baseline
    expected_records = load_expected_records("device_queue_metrics")

    # Create queue metrics collection
    queue_metrics = DeviceQueueMetrics(
        reporter=mock_reporter,
        labels={"device.id": "dut-01", "device.queue.id": "UC0"}
    )

    # Record each metric value directly
    queue_metrics.watermark_bytes.record(1048576)

    # Validate results using common function
    validate_recorded_metrics(mock_reporter, expected_records)


def test_device_temperature_metrics(mock_reporter):
    """Test DeviceTemperatureMetrics collection records all metrics correctly."""
    # Load expected records from JSON baseline
    expected_records = load_expected_records("device_temperature_metrics")

    # Create temperature metrics collection
    temp_metrics = DeviceTemperatureMetrics(
        reporter=mock_reporter,
        labels={"device.id": "spine-01", "device.sensor.id": "CPU"}
    )

    # Record each metric value directly
    temp_metrics.reading.record(42.5)
    temp_metrics.high_th.record(85.0)
    temp_metrics.low_th.record(0.0)
    temp_metrics.crit_high_th.record(95.0)
    temp_metrics.crit_low_th.record(-10.0)
    temp_metrics.warning.record(0.0)

    # Validate results using common function
    validate_recorded_metrics(mock_reporter, expected_records)


def test_device_fan_metrics(mock_reporter):
    """Test DeviceFanMetrics collection records all metrics correctly."""
    # Load expected records from JSON baseline
    expected_records = load_expected_records("device_fan_metrics")

    # Create fan metrics collection
    fan_metrics = DeviceFanMetrics(
        reporter=mock_reporter,
        labels={"device.id": "leaf-01", "device.fan.id": "Fan-1"}
    )

    # Record each metric value directly
    fan_metrics.speed.record(8500.0)
    fan_metrics.status.record(1.0)

    # Validate results using common function
    validate_recorded_metrics(mock_reporter, expected_records)


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
