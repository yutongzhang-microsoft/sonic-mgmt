"""
Common utilities for telemetry testing.

This module contains shared mock classes and fixtures for testing telemetry
metrics collections and reporters.
"""

import json
import os

from common.telemetry.base import Reporter


class MockReporter(Reporter):
    """Mock reporter that logs all metrics for testing."""

    def __init__(self, request=None, tbinfo=None):
        super().__init__("mock", request, tbinfo)
        self.report_called = False

    def _report(self, timestamp: float):
        """Mark that report was called."""
        self.report_called = True


def validate_recorded_metrics(mock_reporter: MockReporter, collection_name: str):
    """
    Common validation function to compare mock reporter results with expected records from JSON baseline.

    If SONIC_MGMT_GENERATE_BASELINE=1, generates new baseline files from actual recorded data.

    Args:
        mock_reporter: The mock reporter that recorded metrics
        collection_name: Name of the collection to load baseline data for
    """
    # Convert recorded metrics to comparable format
    actual_records = []
    for record in mock_reporter.recorded_metrics:
        actual_records.append({
            "metric_name": record.metric.name,
            "value": record.value,
            "labels": {k: v for k, v in record.labels.items()
                       if not k.startswith("test.")}  # Filter out test context labels
        })

    # Sort by metric name for consistent comparison
    actual_records.sort(key=lambda x: x["metric_name"])

    baseline_dir = os.path.join(os.path.dirname(__file__), 'baselines')
    baseline_file = os.path.join(baseline_dir, f'{collection_name}.json')

    # Check if we should generate baseline
    if os.environ.get("SONIC_MGMT_GENERATE_BASELINE") == "1":
        # Ensure baseline directory exists
        os.makedirs(baseline_dir, exist_ok=True)

        # Write actual records as new baseline
        with open(baseline_file, 'w') as f:
            json.dump(actual_records, f, indent=2)

        print(f"Generated baseline file: {baseline_file}")
        return

    # Load expected records from JSON baseline for validation
    with open(baseline_file, 'r') as f:
        expected_records = json.load(f)

    # Verify correct number of metrics recorded
    assert len(mock_reporter.recorded_metrics) == len(expected_records), \
        f"Expected {len(expected_records)} recorded metrics, got {len(mock_reporter.recorded_metrics)}"

    # Sort expected records by metric name for consistent comparison
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
