"""
Base classes for the SONiC telemetry framework.

This module contains the abstract base classes and core interfaces
for the telemetry system including Reporter, Metric, and MetricCollection.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from dataclasses import dataclass
import os
import time
from .constants import (
    METRIC_LABEL_TEST_TESTBED, METRIC_LABEL_TEST_OS_VERSION,
    METRIC_LABEL_TEST_TESTCASE, METRIC_LABEL_TEST_FILE,
    METRIC_LABEL_TEST_JOB_ID, METRIC_LABEL_TEST_PARAMS_PREFIX,
    ENV_TESTBED_NAME, ENV_BUILD_VERSION, ENV_JOB_ID
)


@dataclass
class MetricDefinition:
    """
    Definition for a metric in a collection.

    This class provides a clean, type-safe way to define metrics
    with all their attributes in a structured format.
    """
    attribute_name: str
    metric_name: str
    description: str
    unit: str

    def __str__(self) -> str:
        """Return a readable string representation."""
        return f"MetricDefinition({self.attribute_name}: {self.metric_name})"


@dataclass
class MetricRecord:
    """
    Record of a metric measurement.

    This replaces the tuple-based measurement storage with a type-safe
    dataclass that provides better code clarity and maintainability.
    """
    metric: 'Metric'
    value: float
    labels: Dict[str, str]

    def __str__(self) -> str:
        """Return a readable string representation."""
        return f"MetricRecord({self.metric.name}={self.value}, labels={len(self.labels)})"


class Reporter(ABC):
    """
    Abstract base class for telemetry reporters.

    Reporters are responsible for collecting and dispatching metrics
    to their respective backends (OpenTelemetry for TS, files for DB).
    """

    def __init__(self, reporter_type: str, request=None, tbinfo=None):
        """
        Initialize reporter with type identifier.

        Args:
            reporter_type: Type of reporter ('ts' or 'db')
            request: pytest request object for test context
            tbinfo: testbed info fixture data
        """
        self.reporter_type = reporter_type
        self.test_context = self._detect_test_context(request, tbinfo)
        self.metrics: List[MetricRecord] = []

    def _detect_test_context(self, request=None, tbinfo=None) -> Dict[str, str]:
        """
        Automatically detect test context from pytest data and tbinfo fixture.

        Args:
            request: pytest request object for test context
            tbinfo: testbed info fixture data

        Returns:
            Dict containing test metadata labels
        """
        context = {}

        # Get test case name from pytest request
        context[METRIC_LABEL_TEST_TESTCASE] = request.node.name
        context[METRIC_LABEL_TEST_FILE] = os.path.basename(request.node.fspath.strpath)

        # Get test parameters if available
        if hasattr(request.node, 'callspec') and request.node.callspec:
            for param_name, param_value in request.node.callspec.params.items():
                context[f'{METRIC_LABEL_TEST_PARAMS_PREFIX}.{param_name}'] = str(param_value)

        if tbinfo is not None:
            # Get testbed name from tbinfo fixture
            context[METRIC_LABEL_TEST_TESTBED] = tbinfo.get('conf-name', 'unknown') if tbinfo else 'unknown'

        # Fallback to environment variables if pytest data not available
        if not context.get(METRIC_LABEL_TEST_TESTBED):
            context[METRIC_LABEL_TEST_TESTBED] = os.environ.get(ENV_TESTBED_NAME, 'unknown')

        context[METRIC_LABEL_TEST_OS_VERSION] = os.environ.get(ENV_BUILD_VERSION, 'unknown')
        context[METRIC_LABEL_TEST_JOB_ID] = os.environ.get(ENV_JOB_ID, 'unknown')

        return context

    def add_metric(self, metric: 'Metric', value: float, additional_labels: Optional[Dict[str, str]] = None):
        """
        Add a metric measurement to the reporter.

        The reporter will merge test context, metric labels, and additional labels.

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

        record = MetricRecord(metric=metric, value=value, labels=final_labels)
        self.metrics.append(record)

    @property
    def recorded_metrics(self) -> List[MetricRecord]:
        """Get the recorded metrics."""
        return self.metrics

    def recorded_metrics_count(self) -> int:
        """
        Get the number of pending measurements.

        Returns:
            Count of measurements in buffer
        """
        return len(self.metrics)

    def report(self):
        """
        Report all collected metrics to the backend and clear the buffer.

        This method generates the timestamp and calls the subclass-specific _report method.
        """
        if not self.recorded_metrics:
            return

        timestamp = time.time_ns()
        self._report(timestamp)
        self.metrics.clear()

    @abstractmethod
    def _report(self, timestamp: float):
        """
        Implementation-specific reporting logic.

        Args:
            timestamp: Timestamp for this reporting batch
        """
        pass


class Metric(ABC):
    """
    Abstract base class for telemetry metrics.

    Metrics represent measurable quantities following OpenTelemetry conventions.
    """

    def __init__(self, name: str, description: str, unit: str, reporter: Reporter,
                 common_labels: Optional[Dict[str, str]] = None):
        """
        Initialize metric with metadata.

        Args:
            name: Metric name in OpenTelemetry format (lowercase.snake_case.dot_separated)
            description: Human-readable description
            unit: Unit of measurement
            reporter: Reporter instance to send measurements to
            common_labels: Common labels to apply to all measurements of this metric
        """
        self.name = name
        self.description = description
        self.unit = unit
        self.reporter = reporter
        self._common_labels = common_labels or {}
        self.metric_type = self._get_metric_type()

    @property
    def labels(self) -> Dict[str, str]:
        """
        Get the common labels for this metric (read-only).

        Returns:
            Dictionary containing common labels for this metric
        """
        return self._common_labels

    @abstractmethod
    def _get_metric_type(self) -> str:
        """
        Return the type of this metric (gauge, counter, histogram).

        Returns:
            String identifier for metric type
        """
        pass

    def record(self, value: float, additional_labels: Optional[Dict[str, str]] = None):
        """
        Record a measurement for this metric.

        Args:
            value: Measured value
            additional_labels: Additional labels for this specific measurement
        """
        # Let the reporter handle all label merging
        self.reporter.add_metric(self, value, additional_labels)


class MetricCollection:
    """
    Base class for organizing related metrics into collections.

    This provides a convenient way to group metrics that are commonly
    used together (e.g., port metrics, PSU metrics).

    Subclasses should define METRICS_DEFINITIONS as a class attribute
    containing a list of tuples: (attribute_name, metric_name, description, unit)
    """

    # Subclasses should override this with their metric definitions
    METRICS_DEFINITIONS: List[MetricDefinition] = []

    def __init__(self, reporter: Reporter, labels: Optional[Dict[str, str]] = None):
        """
        Initialize metric collection.

        Args:
            reporter: Reporter instance for all metrics in this collection
            labels: Common labels to apply to all metrics in this collection
        """
        self.reporter = reporter
        self.labels = labels or {}
        self._create_metrics()

    def _create_metrics(self):
        """
        Create all metrics using the METRICS_DEFINITIONS class attribute.

        Uses the GaugeMetric class by default. Subclasses can override this method
        if they need to use different metric types.
        """
        # Import here to avoid circular imports
        from .metrics.gauge import GaugeMetric

        for definition in self.METRICS_DEFINITIONS:
            metric = GaugeMetric(
                name=definition.metric_name,
                description=definition.description,
                unit=definition.unit,
                reporter=self.reporter,
                common_labels=self.labels
            )
            setattr(self, definition.attribute_name, metric)
