"""
Example test demonstrating TS (TimeSeries) reporter usage for real-time monitoring.

This example shows how to use the telemetry framework with the TS reporter
to emit metrics for real-time monitoring via OpenTelemetry. The TS reporter
is ideal for continuous monitoring during test execution.
"""

import pytest
from tests.common.telemetry import (
    METRIC_LABEL_DEVICE_ID,
    METRIC_LABEL_DEVICE_PORT_ID
)
from tests.common.telemetry.metrics.device import DevicePortMetrics


pytestmark = [
    pytest.mark.topology('any'),
    pytest.mark.disable_loganalyzer
]


def test_ts_reporter_with_device_port_metrics(ts_reporter):
    """Example test using TS reporter for real-time port monitoring.

    This test demonstrates:
    1. Setting up device and port labels for metric identification
    2. Creating DevicePortMetrics instance with common labels
    3. Recording various port metrics (throughput, utilization, counters)
    4. Reporting metrics to OpenTelemetry for real-time monitoring

    Args:
        ts_reporter: pytest fixture providing TS reporter for real-time monitoring
    """
    # Define device context - this identifies which device/port we're monitoring
    device_labels = {
        METRIC_LABEL_DEVICE_ID: "switch-01",
        METRIC_LABEL_DEVICE_PORT_ID: "Ethernet0"
    }

    # Create port metrics collection with device labels automatically applied
    port_metrics = DevicePortMetrics(reporter=ts_reporter, labels=device_labels)

    # Record throughput metrics (bytes per second)
    port_metrics.rx_bps.record(1000000000)  # 1 Gbps RX
    port_metrics.tx_bps.record(850000000)   # 850 Mbps TX

    # Record utilization metrics (percentage)
    port_metrics.rx_util.record(85.5)  # 85.5% RX utilization
    port_metrics.tx_util.record(72.3)  # 72.3% TX utilization

    # Record packet counters
    port_metrics.rx_ok.record(1500000)  # 1.5M successful RX packets
    port_metrics.tx_ok.record(1200000)  # 1.2M successful TX packets

    # Record error counters (should be low/zero in healthy systems)
    port_metrics.rx_err.record(0)  # No RX errors
    port_metrics.tx_err.record(2)  # 2 TX errors detected

    # Record drop counters
    port_metrics.rx_drop.record(10)  # 10 RX drops
    port_metrics.tx_drop.record(5)   # 5 TX drops

    # Record overrun events (buffer overflow conditions)
    port_metrics.rx_overrun.record(0)  # No RX overruns
    port_metrics.tx_overrun.record(1)  # 1 TX overrun event

    # Report all recorded metrics to OpenTelemetry
    # This sends the metrics to the OTLP endpoint for real-time monitoring
    ts_reporter.report()

    # Verify metrics were collected (optional validation)
    assert ts_reporter.get_recorded_metrics_count() == 0  # Should be 0 after reporting


def test_ts_reporter_multiple_ports(ts_reporter):
    """Example test monitoring multiple ports simultaneously.

    This demonstrates how to efficiently monitor multiple network ports
    using the same metrics definitions but different label sets.

    Args:
        ts_reporter: pytest fixture providing TS reporter for real-time monitoring
    """
    # Monitor multiple ports on the same device
    ports_to_monitor = ["Ethernet0", "Ethernet4", "Ethernet8", "Ethernet12"]
    device_id = "switch-02"

    for port_id in ports_to_monitor:
        # Create labels specific to each port
        port_labels = {
            METRIC_LABEL_DEVICE_ID: device_id,
            METRIC_LABEL_DEVICE_PORT_ID: port_id
        }

        # Create port metrics for this specific port
        port_metrics = DevicePortMetrics(reporter=ts_reporter, labels=port_labels)

        # Simulate different traffic patterns per port
        if port_id == "Ethernet0":
            # High utilization port
            port_metrics.rx_bps.record(9500000000)  # 9.5 Gbps
            port_metrics.tx_bps.record(9200000000)  # 9.2 Gbps
            port_metrics.rx_util.record(95.0)
            port_metrics.tx_util.record(92.0)
        elif port_id == "Ethernet4":
            # Medium utilization port
            port_metrics.rx_bps.record(5000000000)  # 5 Gbps
            port_metrics.tx_bps.record(4800000000)  # 4.8 Gbps
            port_metrics.rx_util.record(50.0)
            port_metrics.tx_util.record(48.0)
        else:
            # Low utilization ports
            port_metrics.rx_bps.record(1000000000)  # 1 Gbps
            port_metrics.tx_bps.record(800000000)   # 800 Mbps
            port_metrics.rx_util.record(10.0)
            port_metrics.tx_util.record(8.0)

        # Record packet counters (simulated)
        port_metrics.rx_ok.record(1000000)
        port_metrics.tx_ok.record(900000)
        port_metrics.rx_err.record(0)
        port_metrics.tx_err.record(0)
        port_metrics.rx_drop.record(0)
        port_metrics.tx_drop.record(0)

    # Report all collected metrics at once
    ts_reporter.report()

    # All metrics should be reported
    assert ts_reporter.get_recorded_metrics_count() == 0


def test_ts_reporter_with_custom_test_labels(ts_reporter):
    """Example showing how to add test-specific labels to metrics.

    This demonstrates adding test parameters and context as labels
    for better metric categorization and analysis.

    Args:
        ts_reporter: pytest fixture providing TS reporter for real-time monitoring
    """
    # Base device labels
    device_labels = {
        METRIC_LABEL_DEVICE_ID: "switch-03",
        METRIC_LABEL_DEVICE_PORT_ID: "Ethernet0"
    }

    # Add test-specific parameters as labels
    test_context_labels = {
        **device_labels,
        "test.params.topology": "t1",
        "test.params.traffic_pattern": "uniform",
        "test.params.frame_size": "1518",
        "test.params.test_duration": "300"
    }

    # Create port metrics with enhanced labeling
    port_metrics = DevicePortMetrics(reporter=ts_reporter, labels=test_context_labels)

    # Record metrics during a specific test scenario
    port_metrics.rx_bps.record(7500000000)  # 7.5 Gbps during test
    port_metrics.tx_bps.record(7500000000)  # 7.5 Gbps during test
    port_metrics.rx_util.record(75.0)       # 75% utilization
    port_metrics.tx_util.record(75.0)       # 75% utilization

    # Record detailed counters for test validation
    port_metrics.rx_ok.record(2500000)  # Expected packet count
    port_metrics.tx_ok.record(2500000)  # Expected packet count
    port_metrics.rx_err.record(0)       # Should be zero for successful test
    port_metrics.tx_err.record(0)       # Should be zero for successful test

    # Report metrics with test context
    ts_reporter.report()

    assert ts_reporter.get_recorded_metrics_count() == 0
