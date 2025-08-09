"""
Database (DB) Reporter for historical analysis and trend tracking.

This reporter writes metrics to local files that can be uploaded to
OLTP databases for historical analysis, reporting, and trend tracking.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from ..base import Reporter, Metric
from ..constants import REPORTER_TYPE_DB


class DBReporter(Reporter):
    """
    Database reporter for historical analysis.

    Writes metrics to local JSON files that can be processed and uploaded
    to databases for long-term storage, trend analysis, and reporting.
    """

    def __init__(self, output_dir: Optional[str] = None, file_prefix: Optional[str] = None,
                 request=None, tbinfo=None):
        """
        Initialize DB reporter with file output configuration.

        Args:
            output_dir: Directory for output files (default: current directory)
            file_prefix: Prefix for output filenames (default: 'telemetry')
            request: pytest request object for test context
            tbinfo: testbed info fixture data
        """
        super().__init__(REPORTER_TYPE_DB, request, tbinfo)
        self.output_dir = output_dir or os.getcwd()
        self.file_prefix = file_prefix or 'telemetry'
        self.measurements: List[Tuple[Metric, float, Dict[str, str], float]] = []

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        logging.info(f"DBReporter initialized: output_dir={self.output_dir}, "
                     f"file_prefix={self.file_prefix}")

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

        timestamp = time.time()
        self.measurements.append((metric, value, final_labels, timestamp))

        # Log for debugging
        logging.debug(f"DBReporter: Added {metric.name}={value} labels={final_labels}")

    def report(self):
        """
        Write all collected metrics to local files and clear buffer.
        """
        if not self.measurements:
            logging.debug("DBReporter: No measurements to report")
            return

        logging.info(f"DBReporter: Writing {len(self.measurements)} measurements to file")

        # Generate filename with timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.file_prefix}_{timestamp_str}.json"
        filepath = os.path.join(self.output_dir, filename)

        # Prepare data structure
        report_data = {
            "metadata": {
                "reporter_type": self.reporter_type,
                "timestamp": datetime.now().isoformat(),
                "test_context": self.test_context,
                "measurement_count": len(self.measurements)
            },
            "measurements": []
        }

        # Convert measurements to JSON-serializable format
        for metric, value, labels, timestamp in self.measurements:
            measurement = {
                "metric_name": metric.name,
                "metric_type": metric.metric_type,
                "description": metric.description,
                "unit": metric.unit,
                "value": value,
                "labels": labels,
                "timestamp": timestamp,
                "timestamp_iso": datetime.fromtimestamp(timestamp).isoformat()
            }
            report_data["measurements"].append(measurement)

        # Write to file
        try:
            with open(filepath, 'w') as f:
                json.dump(report_data, f, indent=2, sort_keys=True)

            logging.info(f"DBReporter: Successfully wrote {len(self.measurements)} "
                         f"measurements to {filepath}")

            # Clear measurements after successful write
            self.measurements.clear()

        except Exception as e:
            logging.error(f"DBReporter: Failed to write measurements to {filepath}: {e}")
            raise

    def get_measurement_count(self) -> int:
        """
        Get the number of pending measurements.

        Returns:
            Count of measurements in buffer
        """
        return len(self.measurements)

    def get_output_files(self) -> List[str]:
        """
        Get list of output files created by this reporter.

        Returns:
            List of output file paths
        """
        files = []
        for filename in os.listdir(self.output_dir):
            if filename.startswith(self.file_prefix) and filename.endswith('.json'):
                files.append(os.path.join(self.output_dir, filename))
        return sorted(files)

    def clear_output_files(self):
        """
        Remove all output files created by this reporter.

        Use with caution - this permanently deletes telemetry data files.
        """
        files = self.get_output_files()
        for filepath in files:
            try:
                os.remove(filepath)
                logging.info(f"DBReporter: Removed output file {filepath}")
            except Exception as e:
                logging.warning(f"DBReporter: Failed to remove {filepath}: {e}")
