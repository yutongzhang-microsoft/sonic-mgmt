"""
SONiC Mgmt Test Telemetry Framework

A comprehensive telemetry data collection and reporting framework for SONiC test infrastructure,
designed to emit metrics for real-time monitoring and historical analysis.

The telemetry framework provides dual reporting pipelines optimized for different use cases:

- **TS (TimeSeries)**: Real-time monitoring via OpenTelemetry (every 1 minute)
- **DB (Database)**: Historical analysis via local files → OLTP Database (end of test)

## Quick Start

```python
import pytest
from common.telemetry import *

def test_example_with_telemetry(ts_reporter):
    # Define device context
    device_labels = {METRIC_LABEL_DEVICE_ID: "switch-01"}

    # Record port metrics
    port_labels = {**device_labels, METRIC_LABEL_DEVICE_PORT_ID: "Ethernet0"}
    port_metrics = DevicePortMetrics(reporter=ts_reporter, labels=port_labels)
    port_metrics.tx_util.record(45.2)
    port_metrics.rx_bps.record(1000000000)  # 1Gbps

    # Report to OpenTelemetry
    ts_reporter.report()
```

## Core Components

### Reporters
- `TSReporter`: Real-time monitoring via OpenTelemetry
- `DBReporter`: Historical analysis via local file export

### Metrics
- `GaugeMetric`: Instantaneous values (temperature, utilization)
- `CounterMetric`: Cumulative values (packet counts, errors)
- `HistogramMetric`: Distribution tracking (latencies, sizes)

### Device Metrics Collections
- `DevicePortMetrics`: Network interface statistics
- `DevicePSUMetrics`: Power supply measurements
- `DeviceQueueMetrics`: Buffer utilization
- `DeviceTemperatureMetrics`: Thermal monitoring
- `DeviceFanMetrics`: Cooling system monitoring

### Pytest Integration
- `ts_reporter`: Function-scoped TS reporter fixture
- `db_reporter`: Function-scoped DB reporter fixture
- `ts_reporter_session`: Session-scoped TS reporter fixture
- `db_reporter_session`: Session-scoped DB reporter fixture
"""

# Base classes
from .base import Reporter, Metric, MetricCollection, MetricDefinition

# Metric types
from .metrics import GaugeMetric, CounterMetric, HistogramMetric

# Reporters
from .reporters import TSReporter, DBReporter

# Device metric collections
from .metrics.device import (
    DevicePortMetrics, DevicePSUMetrics, DeviceQueueMetrics,
    DeviceTemperatureMetrics, DeviceFanMetrics
)

# Constants and labels
from .constants import (
    # Common Labels
    METRIC_LABEL_DEVICE_ID, METRIC_LABEL_DEVICE_PORT_ID, METRIC_LABEL_DEVICE_PSU_ID,
    METRIC_LABEL_DEVICE_QUEUE_ID, METRIC_LABEL_DEVICE_SENSOR_ID, METRIC_LABEL_DEVICE_FAN_ID,

    # Port Metrics
    METRIC_NAME_PORT_RX_BPS, METRIC_NAME_PORT_TX_BPS, METRIC_NAME_PORT_RX_UTIL, METRIC_NAME_PORT_TX_UTIL,

    # PSU Metrics
    METRIC_NAME_PSU_VOLTAGE, METRIC_NAME_PSU_CURRENT, METRIC_NAME_PSU_POWER,

    # BGP Metrics
    METRIC_NAME_BGP_CONVERGENCE_TIME_PORT_RESTART,

    # Units
    UNIT_SECONDS, UNIT_BYTES_PER_SECOND, UNIT_PERCENT, UNIT_COUNT
)

# Pytest fixtures (imported for convenience, but should be used via conftest.py)
from .fixtures import ts_reporter, db_reporter, ts_reporter_session, db_reporter_session, telemetry_reporters

# Version information
__version__ = "1.0.0"
__author__ = "SONiC Test Infrastructure Team"

# Public API - define what gets imported with "from common.telemetry import *"
__all__ = [
    # Base classes
    'Reporter', 'Metric', 'MetricCollection', 'MetricDefinition',

    # Metric types
    'GaugeMetric', 'CounterMetric', 'HistogramMetric',

    # Reporters
    'TSReporter', 'DBReporter',

    # Device metrics
    'DevicePortMetrics', 'DevicePSUMetrics', 'DeviceQueueMetrics',
    'DeviceTemperatureMetrics', 'DeviceFanMetrics',

    # Essential constants
    'METRIC_LABEL_DEVICE_ID', 'METRIC_LABEL_DEVICE_PORT_ID', 'METRIC_LABEL_DEVICE_PSU_ID',
    'METRIC_LABEL_DEVICE_QUEUE_ID', 'METRIC_LABEL_DEVICE_SENSOR_ID', 'METRIC_LABEL_DEVICE_FAN_ID',

    # Port metric names
    'METRIC_NAME_PORT_RX_BPS', 'METRIC_NAME_PORT_TX_BPS', 'METRIC_NAME_PORT_RX_UTIL', 'METRIC_NAME_PORT_TX_UTIL',

    # PSU metric names
    'METRIC_NAME_PSU_VOLTAGE', 'METRIC_NAME_PSU_CURRENT', 'METRIC_NAME_PSU_POWER',

    # BGP metric names
    'METRIC_NAME_BGP_CONVERGENCE_TIME_PORT_RESTART',

    # Common units
    'UNIT_SECONDS', 'UNIT_PERCENT', 'UNIT_COUNT', 'UNIT_BYTES_PER_SECOND',

    # Pytest fixtures
    'ts_reporter', 'db_reporter', 'ts_reporter_session', 'db_reporter_session', 'telemetry_reporters'
]
