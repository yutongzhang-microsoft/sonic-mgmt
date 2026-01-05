# SONiC OTEL-based Profiler Framework

1. [1. Overview](#1-overview)
2. [2. Architecture Overview](#2-architecture-overview)
   1. [2.1. OpenTelemetry Compatiable](#21-opentelemetry-compatiable)
3. [3. Data observation ](#3-data-observation)
   1. [3.1. Emitting inbox metrics](#31-emitting-inbox-metrics)
4. [4. Deployment Model](#4-deployment-model)
   1. [4.1. Common Metrics](#41-common-metrics)

## 1. Overview
To better understand device-level performance behavior, such as how messages are processed across different threads or services, and where performance hotspots or bottlenecks occur, we aim to build a profiling dashboard that visualizes CPU execution paths in a perf flame graph–like format. \
Traditional perf-based profiling, however, often depends on language or runtime-specific support, which may not be available in all environments. To address this limitation, we require an alternative approach that does not rely on application-level instrumentation. \
After evaluation, we identified the OpenTelemetry profiling agent [ebpf-profiler](https://github.com/open-telemetry/opentelemetry-ebpf-profiler) as a suitable replacement for perf, providing similar profiling capabilities in a language-agnostic manner. We therefore use this agent to collect device-level profiling data. \
For data collection and visualization, we leverage OpenTelemetry-provided components, including [opentelemetry-collector-contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib) for profile ingestion and processing, and [Pyroscope](https://github.com/grafana/pyroscope) for flame graph visualization.

## 2. Architecture Overview
Diagram:
```buildoutcfg
+------------------+
|   Target Device  |
|                  |
|  eBPF Profiler   |
|  (CPU sampling)  |
+--------+---------+
         |
         | OTLP
         v
+---------------------------+
| OpenTelemetry Collector   |
| (profiles pipeline)       |
+-------------+-------------+
              |
              | HTTP
              v
+------------------+
|   Pyroscope UI   |
| (Flame Graphs)   |
+------------------+
```
Component Details:


## 3. Data observation 

## 4. Deployment Model

