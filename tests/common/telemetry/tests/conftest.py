import pytest

from .common_utils import MockReporter


@pytest.fixture
def mock_reporter(request, tbinfo, duthosts):
    """Provide a fresh mock reporter for each test."""
    return MockReporter(request=request, tbinfo=tbinfo, duthosts=duthosts)
