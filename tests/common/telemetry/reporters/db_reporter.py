"""
Database (DB) Reporter for historical analysis and trend tracking.

This reporter writes metrics to local files that can be uploaded to
OLTP databases for historical analysis, reporting, and trend tracking.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, List
from ..base import Reporter
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

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        logging.info(f"DBReporter initialized: output_dir={self.output_dir}, "
                     f"file_prefix={self.file_prefix}")

    def _report(self, timestamp: float):
        """
        Write all collected metrics to local files.

        Args:
            timestamp: Timestamp for this reporting batch
        """
        logging.info(f"DBReporter: Writing {len(self.recorded_metrics)} measurements to file")

        # Generate filename with timestamp
        timestamp_dt = datetime.fromtimestamp(timestamp)
        timestamp_str = timestamp_dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.file_prefix}_{timestamp_str}.json"
        filepath = os.path.join(self.output_dir, filename)

        # Prepare data structure
        report_data = {
            "metadata": {
                "reporter_type": self.reporter_type,
                "timestamp": timestamp_dt.isoformat(),
                "test_context": self.test_context,
                "measurement_count": len(self.recorded_metrics)
            },
            "measurements": []
        }

        # Convert measurements to JSON-serializable format
        for record in self.recorded_metrics:
            measurement = {
                "metric_name": record.metric.name,
                "metric_type": record.metric.metric_type,
                "description": record.metric.description,
                "unit": record.metric.unit,
                "value": record.data,
                "labels": record.labels,
                "timestamp": timestamp,
                "timestamp_iso": timestamp_dt.isoformat()
            }
            report_data["measurements"].append(measurement)

        # Write to file
        try:
            with open(filepath, 'w') as f:
                json.dump(report_data, f, indent=2, sort_keys=True)

            logging.info(f"DBReporter: Successfully wrote {len(self.recorded_metrics)} "
                         f"measurements to {filepath}")

        except Exception as e:
            logging.error(f"DBReporter: Failed to write measurements to {filepath}: {e}")
            raise

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
