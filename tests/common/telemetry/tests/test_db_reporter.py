"""
Tests for DBReporter (Database Reporter).

This module focuses on testing the DBReporter implementation:
- Verifies local file output format and content
- Tests bulk metrics handling
- Validates JSON output structure
- Tests multiple report scenarios
"""

import json
import os
import tempfile
import time
from unittest.mock import Mock

import pytest

# Import the telemetry framework
from common.telemetry import (
    GaugeMetric, HistogramMetric
)

pytestmark = [
    pytest.mark.topology('any'),
    pytest.mark.disable_loganalyzer
]


class TestDBReporter:
    """Test suite for database reporter file output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_request = Mock()
        self.mock_request.node.name = "test_db_reporter"
        self.mock_request.node.fspath.strpath = "/test/path/test_example.py"
        self.mock_request.node.callspec.params = {}
        self.mock_tbinfo = {"conf-name": "vlab-testbed-01", "duts": ["dut-01"]}

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_db_reporter_file_creation(self):
        """Test that DBReporter creates output file correctly."""
        # Create DB reporter
        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(
            output_dir=self.temp_dir,
            request=self.mock_request,
            tbinfo=self.mock_tbinfo
        )

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
        output_files = db_reporter.get_output_files()
        assert len(output_files) == 1

        # Verify file content
        with open(output_files[0], 'r') as f:
            content = json.load(f)

        # Verify metadata
        assert content["metadata"]["reporter_type"] == "db"
        assert content["metadata"]["measurement_count"] == 2

        # Verify measurements
        measurements = content["measurements"]
        assert len(measurements) == 2

        # Verify first record
        record1 = measurements[0]
        assert record1["metric_name"] == "test.db.metric"
        assert record1["value"] == 75.5
        assert record1["metric_type"] == "gauge"
        assert record1["description"] == "Test DB metric"
        assert record1["unit"] == "percent"
        assert record1["labels"]["device.id"] == "dut-01"
        assert record1["labels"]["test.iteration"] == "1"
        assert record1["labels"]["test.testcase"] == "test_db_reporter"
        assert "timestamp" in record1

        # Verify second record
        record2 = measurements[1]
        assert record2["value"] == 82.3
        assert record2["labels"]["test.iteration"] == "2"

    def test_db_reporter_output_directory_handling(self):
        """Test DB reporter output directory creation and file management."""
        from common.telemetry.reporters.db_reporter import DBReporter

        # Test with non-existent directory
        non_existent_dir = os.path.join(self.temp_dir, "new_subdir")
        db_reporter = DBReporter(
            output_dir=non_existent_dir,
            request=self.mock_request,
            tbinfo=self.mock_tbinfo
        )

        # Directory should be created automatically
        assert os.path.exists(non_existent_dir)

        # Test file operations
        metric = GaugeMetric("test.dir.metric", "Test dir metric", "count", db_reporter)
        metric.record(100)
        db_reporter.report()

        # Verify file was created in the specified directory
        output_files = db_reporter.get_output_files()
        assert len(output_files) == 1
        assert output_files[0].startswith(non_existent_dir)

    def test_db_reporter_file_prefix_customization(self):
        """Test DB reporter with custom file prefix."""
        from common.telemetry.reporters.db_reporter import DBReporter

        custom_prefix = "custom_metrics"
        db_reporter = DBReporter(
            output_dir=self.temp_dir,
            file_prefix=custom_prefix,
            request=self.mock_request,
            tbinfo=self.mock_tbinfo
        )

        metric = GaugeMetric("test.prefix.metric", "Test prefix metric", "count", db_reporter)
        metric.record(100)
        db_reporter.report()

        # Verify file uses custom prefix
        output_files = os.listdir(self.temp_dir)
        custom_files = [f for f in output_files if f.startswith(custom_prefix)]
        assert len(custom_files) == 1
        assert custom_files[0].startswith(f"{custom_prefix}_")

    def test_db_reporter_multiple_reports(self):
        """Test that DB reporter creates separate files for multiple report() calls."""
        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(
            output_dir=self.temp_dir,
            request=self.mock_request,
            tbinfo=self.mock_tbinfo
        )

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
        output_files = db_reporter.get_output_files()
        assert len(output_files) == 2

        # Verify file contents
        total_records = 0
        all_values = []
        for output_file in output_files:
            with open(output_file, 'r') as f:
                content = json.load(f)
                measurements = content["measurements"]
                total_records += len(measurements)
                for record in measurements:
                    all_values.append(record["value"])

        assert total_records == 3  # 2 from first report, 1 from second report
        assert sorted(all_values) == [100, 200, 300]

    def test_db_reporter_file_format(self):
        """Test the exact format of DB reporter output files."""
        from common.telemetry.reporters.db_reporter import DBReporter
        db_reporter = DBReporter(
            output_dir=self.temp_dir,
            request=self.mock_request,
            tbinfo=self.mock_tbinfo
        )

        # Test all metric types
        gauge_metric = GaugeMetric("test.gauge", "Test gauge", "percent", db_reporter)
        histogram_metric = HistogramMetric("test.histogram", "Test histogram", "ms",
                                           db_reporter, buckets=[0.5, 1.0, 2.0])

        # Record one value for each type
        gauge_metric.record(42.5, {"type": "gauge_test"})
        histogram_metric.record_bucket_counts([1.23], {"type": "histogram_test"})

        db_reporter.report()

        # Read and verify the output format
        output_files = db_reporter.get_output_files()
        assert len(output_files) == 1

        with open(output_files[0], 'r') as f:
            content = json.load(f)

        measurements = content["measurements"]
        assert len(measurements) == 3

        # Verify each record has required fields
        for record in measurements:
            required_fields = [
                "metric_name", "metric_type", "value", "unit",
                "description", "labels", "timestamp", "timestamp_iso"
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


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
