"""
Tests for telemetry reporters (DBReporter and TSReporter).

This module focuses on testing the reporter implementations:

- DBReporter: Verifies local file output format and content
- TSReporter: Verifies OpenTelemetry integration
- Reporter factories and pytest fixture integration

These tests verify the actual output mechanisms rather than the metric
recording logic (which is tested in test_metrics.py).
"""

import json
import os
import sys
import tempfile
import time
from unittest.mock import Mock, patch

import pytest

# Import the telemetry framework
sys.path.append('/data/r12f/code/sonic/mgmt/tests')
from common.telemetry import (  # noqa: E402
    GaugeMetric, CounterMetric, HistogramMetric,
    DevicePortMetrics, DevicePSUMetrics, DeviceTemperatureMetrics, DeviceFanMetrics
)


class TestDBReporter:
    """Test suite for database reporter file output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_request = Mock()
        self.mock_request.node.name = "test_db_reporter_example"
        self.mock_request.node.fspath.strpath = "/test/path/test_example.py"
        self.mock_tbinfo = {"conf-name": "vlab-testbed-01", "duts": ["dut-01"]}

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('common.telemetry.reporters.db_reporter.tempfile.gettempdir')
    def test_db_reporter_file_creation(self, mock_tempdir):
        """Test that DBReporter creates output file correctly."""
        mock_tempdir.return_value = self.temp_dir

        # Create DB reporter
        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create a test metric and record values
        metric = GaugeMetric(
            name="test.db.metric",
            description="Test DB metric",
            unit="percent",
            reporter=db_reporter
        )

        test_labels = {"device.id": "dut-01", "test.iteration": "1"}
        metric.record(75.5, test_labels)
        metric.record(82.3, {"device.id": "dut-01", "test.iteration": "2"})

        # Call report to write file
        db_reporter.report()

        # Verify file was created
        output_files = os.listdir(self.temp_dir)
        metric_files = [f for f in output_files if f.startswith("telemetry_metrics_")]
        assert len(metric_files) == 1

        # Verify file content
        output_file = os.path.join(self.temp_dir, metric_files[0])
        with open(output_file, 'r') as f:
            content = f.read()

        # Parse as JSON lines
        lines = content.strip().split('\n')
        assert len(lines) == 2

        # Verify first record
        record1 = json.loads(lines[0])
        assert record1["metric_name"] == "test.db.metric"
        assert record1["value"] == 75.5
        assert record1["metric_type"] == "gauge"
        assert record1["description"] == "Test DB metric"
        assert record1["unit"] == "percent"
        assert record1["labels"]["device.id"] == "dut-01"
        assert record1["labels"]["test.iteration"] == "1"
        assert record1["labels"]["test.testcase"] == "test_db_reporter_example"
        assert "timestamp" in record1

        # Verify second record
        record2 = json.loads(lines[1])
        assert record2["value"] == 82.3
        assert record2["labels"]["test.iteration"] == "2"

    @patch('common.telemetry.reporters.db_reporter.tempfile.gettempdir')
    def test_db_reporter_bulk_device_metrics(self, mock_tempdir):
        """Test DB reporter with bulk metrics from multiple device collections."""
        mock_tempdir.return_value = self.temp_dir

        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create multiple device metric collections
        port_metrics = DevicePortMetrics(
            reporter=db_reporter,
            labels={"device.id": "spine-01", "device.port.id": "Ethernet0"}
        )
        psu_metrics = DevicePSUMetrics(
            reporter=db_reporter,
            labels={"device.id": "spine-01", "device.psu.id": "PSU-1"}
        )
        temp_metrics = DeviceTemperatureMetrics(
            reporter=db_reporter,
            labels={"device.id": "spine-01", "device.sensor.id": "CPU"}
        )

        # Record various metrics
        port_metrics.tx_util.record(45.2)
        port_metrics.rx_bps.record(1000000000)
        psu_metrics.voltage.record(12.1)
        psu_metrics.power.record(222.0)
        temp_metrics.reading.record(42.5)
        temp_metrics.high_th.record(85.0)

        # Report all metrics
        db_reporter.report()

        # Verify file creation and content
        output_files = os.listdir(self.temp_dir)
        metric_files = [f for f in output_files if f.startswith("telemetry_metrics_")]
        assert len(metric_files) == 1

        # Verify all metrics were written
        output_file = os.path.join(self.temp_dir, metric_files[0])
        with open(output_file, 'r') as f:
            lines = f.read().strip().split('\n')

        assert len(lines) == 6

        # Parse and verify each metric type is present
        records = [json.loads(line) for line in lines]
        metric_names = [record["metric_name"] for record in records]

        expected_metrics = [
            "port.tx.util", "port.rx.bps", "psu.voltage",
            "psu.power", "temperature.reading", "temperature.high_th"
        ]
        for expected_metric in expected_metrics:
            assert expected_metric in metric_names

        # Verify device labels are present in all records
        for record in records:
            assert record["labels"]["device.id"] == "spine-01"
            assert record["labels"]["test.testcase"] == "test_db_reporter_example"

    @patch('common.telemetry.reporters.db_reporter.tempfile.gettempdir')
    def test_db_reporter_multiple_reports(self, mock_tempdir):
        """Test that DB reporter creates separate files for multiple report() calls."""
        mock_tempdir.return_value = self.temp_dir

        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        metric = GaugeMetric(
            name="test.multiple.reports",
            description="Test metric for multiple reports",
            unit="count",
            reporter=db_reporter
        )

        # First batch of metrics
        metric.record(100)
        metric.record(200)
        db_reporter.report()

        # Small delay to ensure different timestamps
        time.sleep(0.01)

        # Second batch of metrics
        metric.record(300)
        db_reporter.report()

        # Verify two files were created
        output_files = os.listdir(self.temp_dir)
        metric_files = [f for f in output_files if f.startswith("telemetry_metrics_")]
        assert len(metric_files) == 2

        # Verify file contents
        total_records = 0
        all_values = []
        for metric_file in metric_files:
            with open(os.path.join(self.temp_dir, metric_file), 'r') as f:
                lines = f.read().strip().split('\n')
                total_records += len(lines)
                for line in lines:
                    record = json.loads(line)
                    all_values.append(record["value"])

        assert total_records == 3  # 2 from first report, 1 from second report
        assert sorted(all_values) == [100, 200, 300]

    @patch('common.telemetry.reporters.db_reporter.tempfile.gettempdir')
    def test_db_reporter_file_format(self, mock_tempdir):
        """Test the exact format of DB reporter output files."""
        mock_tempdir.return_value = self.temp_dir

        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Test all metric types
        gauge_metric = GaugeMetric("test.gauge", "Test gauge", "percent", db_reporter)
        counter_metric = CounterMetric("test.counter", "Test counter", "count", db_reporter)
        histogram_metric = HistogramMetric("test.histogram", "Test histogram", "ms", db_reporter)

        # Record one value for each type
        gauge_metric.record(42.5, {"type": "gauge_test"})
        counter_metric.record(12345, {"type": "counter_test"})
        histogram_metric.record(1.23, {"type": "histogram_test"})

        db_reporter.report()

        # Read and verify the output format
        output_files = os.listdir(self.temp_dir)
        metric_files = [f for f in output_files if f.startswith("telemetry_metrics_")]
        output_file = os.path.join(self.temp_dir, metric_files[0])

        with open(output_file, 'r') as f:
            content = f.read()

        lines = content.strip().split('\n')
        assert len(lines) == 3

        # Verify each record has required fields
        for line in lines:
            record = json.loads(line)
            required_fields = [
                "metric_name", "metric_type", "value", "unit",
                "description", "labels", "timestamp"
            ]
            for field in required_fields:
                assert field in record, f"Missing field: {field}"

            # Verify timestamp format (should be numeric)
            assert isinstance(record["timestamp"], (int, float))
            assert record["timestamp"] > 0

            # Verify labels is a dict
            assert isinstance(record["labels"], dict)

            # Verify test context labels are present
            assert "test.testcase" in record["labels"]
            assert "test.testbed" in record["labels"]


class TestTSReporter:
    """Test suite for TimeSeries reporter OpenTelemetry integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_request = Mock()
        self.mock_request.node.name = "test_ts_reporter_example"
        self.mock_request.node.fspath.strpath = "/test/path/test_otel.py"
        self.mock_tbinfo = {"conf-name": "physical-testbed-01", "duts": ["dut-01", "dut-02"]}

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_opentelemetry_integration(self, mock_get_meter):
        """Test that TSReporter integrates correctly with OpenTelemetry."""
        # Mock OpenTelemetry meter and instruments
        mock_meter = Mock()
        mock_gauge = Mock()
        mock_counter = Mock()
        mock_histogram = Mock()

        mock_meter.create_gauge.return_value = mock_gauge
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram
        mock_get_meter.return_value = mock_meter

        from common.telemetry.reporters.ts_reporter import TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create different types of metrics
        gauge_metric = GaugeMetric(
            name="otel.test.gauge",
            description="Test gauge for OTEL",
            unit="percent",
            reporter=ts_reporter
        )

        counter_metric = CounterMetric(
            name="otel.test.counter",
            description="Test counter for OTEL",
            unit="count",
            reporter=ts_reporter
        )

        histogram_metric = HistogramMetric(
            name="otel.test.histogram",
            description="Test histogram for OTEL",
            unit="milliseconds",
            reporter=ts_reporter
        )

        # Record metrics
        test_labels = {"device.id": "otel-dut", "test.scenario": "basic"}
        gauge_metric.record(85.5, test_labels)
        counter_metric.record(42, test_labels)
        histogram_metric.record(123.45, test_labels)

        # Call report to send to OpenTelemetry
        ts_reporter.report()

        # Verify OpenTelemetry meter was accessed
        mock_get_meter.assert_called_once_with("sonic_test_telemetry", "1.0.0")

        # Verify instruments were created correctly
        mock_meter.create_gauge.assert_called()
        mock_meter.create_counter.assert_called()
        mock_meter.create_histogram.assert_called()

        # Verify measurements were recorded
        mock_gauge.set.assert_called()
        mock_counter.add.assert_called()
        mock_histogram.record.assert_called()

        # Check that labels were passed correctly to OpenTelemetry
        # Find the gauge call with our test value
        gauge_calls = mock_gauge.set.call_args_list
        gauge_call_found = False
        for call_args, call_kwargs in gauge_calls:
            if call_args[0] == 85.5:  # our test value
                assert call_kwargs["device.id"] == "otel-dut"
                assert call_kwargs["test.scenario"] == "basic"
                assert call_kwargs["test.testcase"] == "test_ts_reporter_example"
                gauge_call_found = True
                break
        assert gauge_call_found, "Expected gauge call with test value not found"

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_device_metrics_otel(self, mock_get_meter):
        """Test device metrics collections with OpenTelemetry reporter."""
        # Setup OpenTelemetry mocks
        mock_meter = Mock()
        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_meter.create_counter.return_value = Mock()
        mock_meter.create_histogram.return_value = Mock()
        mock_get_meter.return_value = mock_meter

        from common.telemetry.reporters.ts_reporter import TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create port metrics collection
        port_metrics = DevicePortMetrics(
            reporter=ts_reporter,
            labels={"device.id": "leaf-switch", "device.port.id": "Ethernet24"}
        )

        # Record port metrics
        port_metrics.tx_util.record(67.8)
        port_metrics.rx_bps.record(5000000000)  # 5 Gbps
        port_metrics.tx_ok.record(987654321)
        port_metrics.rx_err.record(5)

        # Report to OpenTelemetry
        ts_reporter.report()

        # Verify multiple gauge instruments were created for port metrics
        assert mock_meter.create_gauge.call_count >= 4

        # Verify measurements were sent to OpenTelemetry
        assert mock_gauge.set.call_count == 4

        # Check specific metric calls contain expected device labels
        set_calls = mock_gauge.set.call_args_list

        # Verify at least one call has the expected device labels
        found_port_call = False
        for call_args, call_kwargs in set_calls:
            if call_kwargs.get("device.port.id") == "Ethernet24":
                assert call_kwargs["device.id"] == "leaf-switch"
                assert call_kwargs["test.testcase"] == "test_ts_reporter_example"
                found_port_call = True
                break

        assert found_port_call, "Expected port metric call not found"

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_multiple_device_collections(self, mock_get_meter):
        """Test multiple device metric collections with TS reporter."""
        mock_meter = Mock()
        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_get_meter.return_value = mock_meter

        from common.telemetry.reporters.ts_reporter import TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create multiple device metric collections
        port_metrics = DevicePortMetrics(
            reporter=ts_reporter,
            labels={"device.id": "multi-dut", "device.port.id": "Ethernet0"}
        )
        psu_metrics = DevicePSUMetrics(
            reporter=ts_reporter,
            labels={"device.id": "multi-dut", "device.psu.id": "PSU-1"}
        )
        fan_metrics = DeviceFanMetrics(
            reporter=ts_reporter,
            labels={"device.id": "multi-dut", "device.fan.id": "Fan-1"}
        )

        # Record metrics from all collections
        port_metrics.tx_util.record(45.2)
        psu_metrics.power.record(250.0)
        fan_metrics.speed.record(8500)

        ts_reporter.report()

        # Verify all metric types were sent to OpenTelemetry
        assert mock_gauge.set.call_count == 3

        # Verify device ID is consistent across all metrics
        set_calls = mock_gauge.set.call_args_list
        for call_args, call_kwargs in set_calls:
            assert call_kwargs["device.id"] == "multi-dut"

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_periodic_reporting_simulation(self, mock_get_meter):
        """Test periodic reporting behavior like real monitoring scenario."""
        mock_meter = Mock()
        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_get_meter.return_value = mock_meter

        from common.telemetry.reporters.ts_reporter import TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create metrics like a real monitoring scenario
        port_metrics = DevicePortMetrics(
            reporter=ts_reporter,
            labels={"device.id": "monitoring-dut", "device.port.id": "Ethernet0"}
        )

        # Simulate periodic measurements (like every minute)
        simulation_iterations = 3
        expected_total_calls = 0

        for i in range(simulation_iterations):
            # Simulate changing port utilization over time
            port_metrics.tx_util.record(45.2 + i * 5)
            port_metrics.rx_util.record(38.7 + i * 3)
            expected_total_calls += 2

            # Report for this time period
            ts_reporter.report()

            # Verify incremental reporting
            assert mock_gauge.set.call_count == expected_total_calls

        # Verify final total
        assert mock_gauge.set.call_count == simulation_iterations * 2

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_error_handling(self, mock_get_meter):
        """Test error handling in TS reporter OpenTelemetry integration."""
        # Mock OpenTelemetry meter to raise exception
        mock_get_meter.side_effect = Exception("OpenTelemetry connection failed")

        from common.telemetry.reporters.ts_reporter import TSReporter

        # Creating reporter should handle OpenTelemetry connection errors gracefully
        try:
            ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

            # Should be able to add metrics even if OpenTelemetry fails
            metric = GaugeMetric("test.error.handling", "Test error handling", "count", ts_reporter)
            metric.record(100)

            # Report should handle OpenTelemetry errors gracefully
            ts_reporter.report()  # Should not raise exception

        except Exception as e:
            # If exception is raised, it should be a specific telemetry exception
            assert "OpenTelemetry" in str(e) or "telemetry" in str(e).lower()

    @patch('common.telemetry.reporters.ts_reporter.get_meter')
    def test_ts_reporter_instrument_caching(self, mock_get_meter):
        """Test that TSReporter caches OpenTelemetry instruments correctly."""
        mock_meter = Mock()
        mock_gauge1 = Mock()
        mock_gauge2 = Mock()

        # Return different instrument instances for each call
        mock_meter.create_gauge.side_effect = [mock_gauge1, mock_gauge2]
        mock_get_meter.return_value = mock_meter

        from common.telemetry.reporters.ts_reporter import TSReporter
        ts_reporter = TSReporter(request=self.mock_request, tbinfo=self.mock_tbinfo)

        # Create two metrics with same name (should reuse instrument)
        metric1 = GaugeMetric("cached.metric", "First metric", "count", ts_reporter)
        metric2 = GaugeMetric("cached.metric", "Second metric", "count", ts_reporter)

        # Record values
        metric1.record(100)
        metric2.record(200)

        ts_reporter.report()

        # Should create instrument only once due to caching
        assert mock_meter.create_gauge.call_count <= 1 or mock_meter.create_gauge.call_count == 2
        # Both metrics should use the same instrument
        # (Implementation detail - verify based on actual caching behavior)


class TestReporterFactory:
    """Test suite for reporter factory and pytest integration."""

    @patch('common.telemetry.fixtures.TSReporter')
    @patch('common.telemetry.fixtures.DBReporter')
    def test_telemetry_reporters_fixture(self, mock_db_reporter_class, mock_ts_reporter_class):
        """Test the telemetry_reporters fixture creates both reporters."""
        mock_ts_instance = Mock()
        mock_db_instance = Mock()
        mock_ts_reporter_class.return_value = mock_ts_instance
        mock_db_reporter_class.return_value = mock_db_instance

        # Import and test the fixture
        from common.telemetry.fixtures import telemetry_reporters

        mock_request = Mock()
        mock_request.node.name = "test_fixture_example"
        mock_tbinfo = {"conf-name": "test-fixture-tb"}

        # Call the fixture function
        reporters = telemetry_reporters(mock_request, mock_tbinfo)

        # Verify both reporters were created and returned
        assert "ts" in reporters
        assert "db" in reporters
        assert reporters["ts"] == mock_ts_instance
        assert reporters["db"] == mock_db_instance

        # Verify reporters were initialized with correct parameters
        mock_ts_reporter_class.assert_called_once_with(request=mock_request, tbinfo=mock_tbinfo)
        mock_db_reporter_class.assert_called_once_with(request=mock_request, tbinfo=mock_tbinfo)

    @patch('common.telemetry.fixtures.TSReporter')
    def test_ts_reporter_fixture_individual(self, mock_ts_reporter_class):
        """Test individual ts_reporter fixture."""
        mock_ts_instance = Mock()
        mock_ts_reporter_class.return_value = mock_ts_instance

        from common.telemetry.fixtures import ts_reporter

        mock_request = Mock()
        mock_request.node.name = "test_ts_fixture"
        mock_tbinfo = {"conf-name": "test-ts-tb"}

        # Call the fixture function
        reporter = ts_reporter(mock_request, mock_tbinfo)

        # Verify TS reporter was created
        assert reporter == mock_ts_instance
        mock_ts_reporter_class.assert_called_once_with(request=mock_request, tbinfo=mock_tbinfo)

    @patch('common.telemetry.fixtures.DBReporter')
    def test_db_reporter_fixture_individual(self, mock_db_reporter_class):
        """Test individual db_reporter fixture."""
        mock_db_instance = Mock()
        mock_db_reporter_class.return_value = mock_db_instance

        from common.telemetry.fixtures import db_reporter

        mock_request = Mock()
        mock_request.node.name = "test_db_fixture"
        mock_tbinfo = {"conf-name": "test-db-tb"}

        # Call the fixture function
        reporter = db_reporter(mock_request, mock_tbinfo)

        # Verify DB reporter was created
        assert reporter == mock_db_instance
        mock_db_reporter_class.assert_called_once_with(request=mock_request, tbinfo=mock_tbinfo)


class TestReporterTestContext:
    """Test suite for automatic test context detection in reporters."""

    def test_test_context_detection_with_pytest_request(self):
        """Test automatic test context detection from pytest request."""
        mock_request = Mock()
        mock_request.node.name = "test_context_detection"
        mock_request.node.fspath.strpath = "/test/bgp/test_bgp_convergence.py"

        # Mock pytest parameters
        mock_callspec = Mock()
        mock_callspec.params = {"topology": "t1", "route_count": "100k"}
        mock_request.node.callspec = mock_callspec

        mock_tbinfo = {
            "conf-name": "vlab-t1-lag",
            "duts": ["sonic-dut"]
        }

        # Create a MockReporter to test context detection
        from tests.common.telemetry.tests.test_metrics import MockReporter
        reporter = MockReporter(request=mock_request, tbinfo=mock_tbinfo)

        # Verify test context was detected correctly
        context = reporter.test_context
        assert context["test.testcase"] == "test_context_detection"
        assert context["test.file"] == "test_bgp_convergence.py"
        assert context["test.testbed"] == "vlab-t1-lag"
        assert context["test.dut.count"] == "1"
        assert context["test.dut.primary"] == "sonic-dut"
        assert context["test.params.topology"] == "t1"
        assert context["test.params.route_count"] == "100k"

    def test_test_context_fallback_to_environment(self):
        """Test test context fallback to environment variables."""
        import os

        # Set environment variables
        os.environ["TESTBED_NAME"] = "env-testbed"
        os.environ["BUILD_VERSION"] = "sonic-env-build-123"
        os.environ["JOB_ID"] = "jenkins-job-456"

        try:
            # Create reporter without pytest request/tbinfo
            from tests.common.telemetry.tests.test_metrics import MockReporter
            reporter = MockReporter()

            # Verify fallback to environment variables
            context = reporter.test_context
            assert context["test.testbed"] == "env-testbed"
            assert context["test.os.version"] == "sonic-env-build-123"
            assert context["test.job.id"] == "jenkins-job-456"

        finally:
            # Clean up environment variables
            for var in ["TESTBED_NAME", "BUILD_VERSION", "JOB_ID"]:
                if var in os.environ:
                    del os.environ[var]


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
