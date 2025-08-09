"""
Pytest fixtures for the SONiC telemetry framework.

This module provides pytest fixtures for easy integration of telemetry
reporters and metrics into test cases.
"""

import os
import tempfile
from typing import Generator
import pytest
from .reporters import TSReporter, DBReporter


@pytest.fixture(scope="function")
def ts_reporter(request, tbinfo) -> Generator[TSReporter, None, None]:
    """
    Pytest fixture providing a TSReporter instance for real-time monitoring.

    This fixture creates a TSReporter configured for test use, with automatic
    cleanup after each test function.

    Args:
        request: pytest request object for test context
        tbinfo: testbed info fixture data

    Yields:
        TSReporter: Configured reporter instance for OpenTelemetry metrics
    """
    # Create TSReporter with test-specific configuration
    reporter = TSReporter(
        endpoint=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'),
        resource_attributes={
            "test.framework": "pytest",
            "test.runner": "sonic-mgmt"
        },
        request=request,
        tbinfo=tbinfo
    )

    try:
        yield reporter
    finally:
        # Ensure any pending metrics are reported before cleanup
        if reporter.get_measurement_count() > 0:
            reporter.report()


@pytest.fixture(scope="function")
def db_reporter(request, tbinfo) -> Generator[DBReporter, None, None]:
    """
    Pytest fixture providing a DBReporter instance for historical analysis.

    This fixture creates a DBReporter with temporary output directory
    that is automatically cleaned up after each test function.

    Args:
        request: pytest request object for test context
        tbinfo: testbed info fixture data

    Yields:
        DBReporter: Configured reporter instance for database export
    """
    # Create temporary directory for test output
    with tempfile.TemporaryDirectory(prefix="telemetry_test_") as temp_dir:
        reporter = DBReporter(
            output_dir=temp_dir,
            file_prefix="test_telemetry",
            request=request,
            tbinfo=tbinfo
        )

        try:
            yield reporter
        finally:
            # Ensure any pending metrics are reported before cleanup
            if reporter.get_measurement_count() > 0:
                reporter.report()


@pytest.fixture(scope="session")
def ts_reporter_session(request, tbinfo) -> Generator[TSReporter, None, None]:
    """
    Session-scoped TSReporter fixture for sharing across multiple tests.

    This fixture creates a single TSReporter instance that persists
    for the entire test session, useful for long-running tests or
    when you want to aggregate metrics across multiple test functions.

    Args:
        request: pytest request object for test context
        tbinfo: testbed info fixture data

    Yields:
        TSReporter: Session-scoped reporter instance
    """
    reporter = TSReporter(
        endpoint=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'),
        resource_attributes={
            "test.framework": "pytest",
            "test.runner": "sonic-mgmt",
            "test.scope": "session"
        },
        request=request,
        tbinfo=tbinfo
    )

    try:
        yield reporter
    finally:
        # Final report of any pending metrics
        if reporter.get_measurement_count() > 0:
            reporter.report()


@pytest.fixture(scope="session")
def db_reporter_session(tmp_path_factory, request, tbinfo) -> Generator[DBReporter, None, None]:
    """
    Session-scoped DBReporter fixture with persistent output directory.

    This fixture creates a DBReporter that writes to a persistent
    directory for the entire test session, allowing collection
    of metrics across multiple test functions.

    Args:
        tmp_path_factory: Pytest's temporary path factory
        request: pytest request object for test context
        tbinfo: testbed info fixture data

    Yields:
        DBReporter: Session-scoped reporter instance
    """
    # Create session-scoped temporary directory
    output_dir = tmp_path_factory.mktemp("telemetry_session")

    reporter = DBReporter(
        output_dir=str(output_dir),
        file_prefix="session_telemetry",
        request=request,
        tbinfo=tbinfo
    )

    try:
        yield reporter
    finally:
        # Final report of any pending metrics
        if reporter.get_measurement_count() > 0:
            reporter.report()


@pytest.fixture(scope="function")
def telemetry_reporters(ts_reporter, db_reporter):
    """
    Convenience fixture providing both TS and DB reporters.

    This fixture returns a tuple of both reporter types for tests
    that need to emit to both real-time monitoring and historical storage.

    Args:
        ts_reporter: Function-scoped TS reporter fixture
        db_reporter: Function-scoped DB reporter fixture

    Returns:
        Tuple[TSReporter, DBReporter]: Both reporter instances
    """
    return ts_reporter, db_reporter


# Pytest configuration hooks for telemetry integration
def pytest_configure(config):
    """
    Configure pytest with telemetry-specific settings.

    This hook is called during pytest configuration to set up
    telemetry-related markers and configuration.
    """
    config.addinivalue_line(
        "markers",
        "telemetry: mark test to use telemetry framework"
    )
    config.addinivalue_line(
        "markers",
        "no_telemetry: mark test to skip telemetry reporting"
    )


def pytest_runtest_setup(item):
    """
    Setup hook called before each test runs.

    This can be used to automatically configure telemetry
    for tests marked with telemetry markers.
    """
    if item.get_closest_marker("no_telemetry"):
        # Skip telemetry setup for marked tests
        return

    # Additional telemetry setup can be added here if needed


def pytest_runtest_teardown(item, nextitem):
    """
    Teardown hook called after each test completes.

    This ensures proper cleanup of telemetry resources
    after each test execution.
    """
    # Additional telemetry cleanup can be added here if needed
    pass
