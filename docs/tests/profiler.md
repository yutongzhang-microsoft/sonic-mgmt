# Azure Profiler Device-Level Performance Analysis

1. [1. Overview](#1-overview)
2. [2. Architecture Overview](#2-architecture-overview)
3. [3. Azure Profiler Container Design](#3-azure-profiler-container-design)
   1. [3.1. Why use a container](#31-why-use-a-container)
   2. [3.2. Container responsibilities](#32-container-responsibilities)
4. [4. Usage](#4-usage)
5. [5. Observing and Analyzing Profiling Data](#5-observing-and-analyzing-profiling-data)
   1. [5.1. Data collection and aggregation](#51-data-collection-and-aggregation)
   2. [5.2. Visualization](#52-visualization)
   3. [5.3. Querying via Kusto](#53-querying-via-kusto)

## 1. Overview
To better understand device-level performance behavior, such as how messages are processed across different threads or services, and where performance hotspots or bottlenecks occur, we aim to build a profiling dashboard that visualizes CPU execution paths in a perf flame graph–like format.

Traditional perf-based profiling often depends on language- or runtime-specific support, which may not be available in all environments. To address this limitation, we require an alternative approach that does not rely on application-level instrumentation.

After evaluation, we adopt [Azure Profiler](https://eng.ms/docs/products/azure-profiler/home/azure-profiler) as the profiling solution. Azure Profiler provides insights into what’s running on machines during both normal execution and abnormal or trigger-based scenarios. It is a distributed sampling profiler designed for low-impact profiling in production environments, using a statistical approach to analyze service behavior.

The centralized backend service aggregates profiling data on a daily basis, provides built-in performance insights, publishes data to Kusto, and supports direct integration for further analysis and visualization.


## 2. Architecture Overview
The profiling solution consists of the following components:

+ Target machine / device \
The physical or virtual machine where performance analysis is required.

+ Azure Profiler container \
A dedicated docker container running Azure Profiler, responsible for collecting CPU samples from the host system.

+ Azure Profiler backend \
A centralized service that aggregates, processes, and stores profiling data.

+ Visualization & analysis layer
Profiling data can be queried from Kusto and visualized in flame graph–like views to identify hotspots and bottlenecks.

<!-- 
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
+ eBPF Profiler
   + Performs kernel-level CPU sampling
   + Emits profiling data via OTLP
+ OpenTelemetry Collector
  + Receives profiling data from eBPF agent
  + Applies optional processing (filtering, batching)
  + Forwards profiles to Pyroscope
+ Pyroscope
  + Stores profiling data
  + Provides flame graph visualization
  + Enables interactive performance analysis

The framework follows OpenTelemetry profiling semantic conventions and uses OTLP as the transport protocol. This allows future integration with additional OTEL-compatible backends and tooling.
-->

## 3. Azure Profiler Container Design
To ensure isolation, portability, and ease of deployment, Azure Profiler is executed inside a dedicated docker container.

### 3.1 Why use a container
+ Avoids polluting the host system with additional dependencies.
+ Provides a consistent runtime environment across different machines.
+ Simplifies deployment and lifecycle management.

### 3.2 Container responsibilities
The Azure Profiler container is responsible for:
+ Installing required system dependencies.
+ Running the Azure Profiler binary.
+ Collecting CPU execution samples from the host.
+ Uploading profiling data to the Azure Profiler backend.

## 4. Usage

## 5. Observing and Analyzing Profiling Data
### 5.1 Data collection and aggregation
+ Azure Profiler continuously samples CPU execution stacks during runtime.
+ Samples are uploaded to the centralized backend service.
+ Profiling data is aggregated per machine, per role, and per day.

### 5.2 Visualization
+ Profiling results can be visualized as flame graph–like CPU execution paths.
+ Hot functions, services, or threads appear as wider blocks, indicating higher CPU consumption.
+ This helps identify:
  + Performance hotspots
  + CPU-intensive services or threads
  + Unexpected execution paths

### 5.3 Querying via Kusto
+ Profiling data is published to Kusto.


<!-- ### 1. Install necessary packages
```buildoutcfg
sudo vim /etc/apt/sources.list
deb http://archive.debian.org/debian buster main
deb http://archive.debian.org/debian-security buster/updates main
 

export https_proxy=http://10.201.148.40:8080
export http_proxy=http://10.201.148.40:8080

sudo -E apt-get update
sudo -E apt-get install libcurl4-gnutls-dev
 
sudo -E apt-get install libxml2
```

### 2. Run commands
```buildoutcfg
sudo -E ./AzureProfiler /GroupName:SonicTest /Role:TestRole /IntervalMinutes:0
```

Check logs: sudo grep AzureProfiler /var/log/syslog

```buildoutcfg
2026 Feb  3 07:45:55.518498 str3-8102-01 WARNING AzureProfiler: WARNING: inotify_add_watch() failed with (2, No such file or directory), not watching fuse events
2026 Feb  3 07:45:59.710414 str3-8102-01 NOTICE AzureProfiler: Profiling...
2026 Feb  3 07:46:07.781492 str3-8102-01 ERR AzureProfiler: Unable to enter namespace!
2026 Feb  3 07:46:07.781572 str3-8102-01 ERR AzureProfiler: Unable to revert namespace!
2026 Feb  3 07:46:09.520814 str3-8102-01 ERR AzureProfiler: Unable to enter namespace!
2026 Feb  3 07:46:09.520917 str3-8102-01 ERR AzureProfiler: Unable to revert namespace!
2026 Feb  3 07:46:22.573555 str3-8102-01 ERR AzureProfiler: CSwitch Lost
2026 Feb  3 07:46:22.632570 str3-8102-01 ERR AzureProfiler: message repeated 143 times: [ CSwitch Lost]
2026 Feb  3 07:46:22.633798 str3-8102-01 WARNING AzureProfiler: WARNING: Stopping early due to errors
2026 Feb  3 07:46:22.634807 str3-8102-01 NOTICE AzureProfiler: Done, 78 MB peak
2026 Feb  3 07:46:23.314797 str3-8102-01 WARNING AzureProfiler: Couldn't find BuildId note: /usr/local/lib/python3.11/dist-packages/google/_upb/_message.abi3.so (mnt:[4026531841]), err=0
2026 Feb  3 07:46:23.315753 str3-8102-01 WARNING AzureProfiler: Couldn't find BuildId note: /usr/bin/containerd-shim-runc-v2 (mnt:[4026531841]), err=0
2026 Feb  3 07:46:23.316828 str3-8102-01 WARNING AzureProfiler: Couldn't open: /usr/sbin/lldpcli (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.316879 str3-8102-01 WARNING AzureProfiler: Couldn't map: /usr/sbin/lldpcli (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.316905 str3-8102-01 WARNING AzureProfiler: Couldn't find BuildId note: /usr/sbin/lldpcli (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.316935 str3-8102-01 WARNING AzureProfiler: Couldn't open: /usr/lib/x86_64-linux-gnu/liblldpctl.so.4.9.1 (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.316983 str3-8102-01 WARNING AzureProfiler: Couldn't map: /usr/lib/x86_64-linux-gnu/liblldpctl.so.4.9.1 (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.317011 str3-8102-01 WARNING AzureProfiler: Couldn't find BuildId note: /usr/lib/x86_64-linux-gnu/liblldpctl.so.4.9.1 (mnt:[4026531841]), err=2
2026 Feb  3 07:46:23.341488 str3-8102-01 WARNING AzureProfiler: Couldn't find BuildId note: /usr/local/lib/python3.11/dist-packages/google/_upb/_message.abi3.so (mnt:[4026532659]), err=2
2026 Feb  3 07:46:24.310178 str3-8102-01 NOTICE AzureProfiler: Uploaded Blob: 2E3F7591A9FEDFB5735D7A733884B645.bin
2026 Feb  3 07:46:24.316768 str3-8102-01 NOTICE AzureProfiler: Child process 562488 exited, status=0
```

### 3. Check Flamegraph
Use kusto query and check the field ViewerUrl
```buildoutcfg
cluster('azureprofilerfollower.westus2.kusto.windows.net').database('azureprofiler').Identifiers 
| where Topic contains "SonicTest"
```
-->