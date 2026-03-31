# Multi-VRF Testbed Setup

## Table of Contents
* [Overview](#overview)
* [Approach](#approach)
* [Enabling Multi-VRF Mode](#enabling-multi-vrf-mode)
  * [Step 1: Update testbed.yaml](#step-1-update-testbedyaml)
  * [Step 2: Set max_fp_num to 127](#step-2-set-max_fp_num-to-127)
  * [Step 3: Redeploy topology](#step-3-redeploy-topology)
  * [Manual topology convergence (without TestbedProcessing.py)](#manual-topology-convergence-without-testbedprocessingpy)
* [Test Library Changes](#test-library-changes)
* [Known Limitations](#known-limitations)


## Overview
In a standard testbed (see [VsSetup](README.testbed.VsSetup.md) for general testbed setup),
each BGP neighbor device maps to its own dedicated neighbor container (e.g. cEOS, cSONiC).
For large topologies, this requires a large number of containers, placing significant memory
and CPU demands on the host server.

Multi-VRF mode converges a large number of peer switches into the fewest possible number of
neighbor containers, reducing the overall resource constraints required to run large numbers
of peers.

The SONiC DUT is entirely unaware of this consolidation — its BGP configuration and
dataplane behavior are unchanged.

## Approach

Neighbor containers (e.g. cEOS, cSONiC) may be converged into a smaller number of host
containers. The SONiC-facing configuration of each BGP peer is separated in routing and
bridging via the use of VRFs. The PTF-facing configuration of each BGP peer is separated
within each VRF via VLAN tagging, enabling the use of a single backplane interface on each
host container. Each VRF includes a number of interfaces either facing the SONiC DUT or the
backplane. Changes are kept as transparent to the SONiC DUT as possible.

The diagrams below illustrate the difference between standard and Multi-VRF testbed layouts:

**Standard testbed (one container per BGP peer):**
```
        ┌──────────────────────────────┐
        │          SONiC DUT           │
        │  Port0   Port1   Port2  Port3│
        └────┬───────┬───────┬──────┬──┘
             │       │       │      │
         ┌───┴─┐  ┌──┴──┐ ┌──┴──┐ ┌─┴───┐
         │nbr-0│  │nbr-1│ │nbr-2│ │nbr-3│
         └──┬──┘  └──┬──┘ └──┬──┘ └───┬─┘
            │        │       │        │
        ┌───┴────────┴───────┴────────┴────┐
        │           PTF Container          │
        └──────────────────────────────────┘
```

**Multi-VRF testbed (multiple BGP peers per container, separated by VRF):**
```
        ┌──────────────────────────────┐
        │          SONiC DUT           │
        │  Port0   Port1   Port2  Port3│
        └────┬───────┬───────┬──────┬──┘
             │       │       │      │
        ┌────┴───────┴───────┴──────┴─┐
        │       Host Container        │
        │  ┌─────────┐  ┌─────────┐   │
        │  │  VRF-0  │  │  VRF-1  │.. │
        │  │ (nbr-0) │  │ (nbr-1) │   │
        │  └────┬────┘  └────┬────┘   │
        │       └─────┬──────┘        │
        │    backplane (VLAN-tagged)  │
        └─────────────┬───────────────┘
                      │ VLAN 2000, 2001, ...
        ┌─────────────┴────────────────┐
        │         PTF Container        │
        └──────────────────────────────┘
```

At the time of testbed setup, the ansible topology file for the testbed is modified to
include new metadata specific to multi-vrf configuration, and the VMs list is trimmed to
only include those containers which will host multiple BGP peerings, separated by VRF.
The new metadata includes mappings between host containers and VRFs, backplane VLAN
mappings, and BGP session parameters.

VLAN tag 2000 is used as the starting value for all VLANs between the test infrastructure
PTF container interfaces and neighbor container interfaces.

The IP and IPv6 addresses used to connect the neighbor container and the PTF container
are generated to make backplane connections clearer, more unique, and easier to implement.
In general, backplane L3 addresses used by the neighbor container end in even numbers, and
those used by the PTF container end in odd numbers. All addresses generated for use in
backplane connections start with the value 100 (0x64) in the least-significant octet or
hextet (depending on the address family). The address changes are mapped and stored in the
new multi-vrf metadata in the ansible topology file.

Multiple BGP features, such as local-as and next-hop-peer, are used in order to aid in
the resolution of routes. This is necessary to keep the SONiC DUT as multi-vrf-agnostic as
possible.

## Enabling Multi-VRF Mode

The overall workflow for enabling Multi-VRF mode is:
1. Mark the testbed as `use_converged_peers: true` in `testbed.yaml`.
2. Run `TestbedProcessing.py`, which reads this flag and automatically invokes
   `ceos_topo_converger.py` to rewrite the ansible topology file — merging peer VMs into
   fewer host containers and injecting multi-VRF metadata.
3. Ansible tasks and test libraries read the updated topology to set up VRFs, VLAN-tagged
   backplane links, and adjusted BGP sessions.
4. Run `redeploy-topo` to apply the new topology.

### Step 1: Update testbed.yaml
Add `use_converged_peers: true` to the testbed entry in `sonic-mgmt/ansible/testbed.yaml`:
```yaml
- conf-name: {conf-name}
  group-name: {group-name}
  topo: {topo}
  ...
  use_converged_peers: true
```
`TestbedProcessing.py` reads this flag and invokes `ceos_topo_converger.converge_testbed()`
to rewrite the topology file in-place, merging peer entries and injecting `convergence_data`
metadata before any ansible tasks run.

### Step 2: Set max_fp_num to 127
`max_fp_num` controls the maximum number of interfaces available per neighbor container.
Each neighbor container needs enough forwarding-plane ports to host all BGP sessions across
its VRFs. For full-scale topologies the maximum value, **127**, must be used.

You can pass this as an extra variable to the `redeploy-topo` command in Step 3.

### Step 3: Redeploy topology
```bash
# First-time setup:
./testbed-cli.sh remove-topo <testbed-name> password.txt
./testbed-cli.sh add-topo <testbed-name> password.txt -e max_fp_num=127
./testbed-cli.sh deploy-mg <testbed-name> <inventory> password.txt

# Updating an existing testbed:
./testbed-cli.sh redeploy-topo <testbed-name> password.txt -e max_fp_num=127
```

### Manual topology convergence (without TestbedProcessing.py)

If `TestbedProcessing.py` is not used in your workflow, or you need to rewrite the topology
file independently (e.g. for debugging or inspection), you can call the converger directly:
```bash
# Run from sonic-mgmt/ansible/
python3 -c "
from ceos_topo_converger import converge_testbed
converge_testbed('vars/topo_<your-topo>.yml', 'vars/topo_<your-topo>.yml')
# Same input and output path overwrites the topo file in-place.
# A different output path can be provided as the second argument.
"
```

## Test Library Changes

Test libraries were updated to be aware of the new underlying structure of neighbor
containers, VRFs, and BGP adjacencies. The key changes are:

- **`ansible/ceos_topo_converger.py`** (new): Rewrites the ansible topology YAML in-place,
  merging peer VM entries into fewer host containers and injecting `convergence_data`
  metadata (VRF mappings, backplane VLAN assignments, interface index mappings, and PTF
  backplane addresses).

- **`ansible/TestbedProcessing.py`**: Extended to read `use_converged_peers` from
  `testbed.yaml` and automatically invoke `ceos_topo_converger` before any ansible
  processing runs.

- **`ansible/library/topo_facts.py`** and **`ansible/library/testbed_vm_info.py`**:
  Updated to resolve logical VRF neighbor names from `convergence_data` instead of
  iterating directly over `topology.VMs`.

- **`tests/conftest.py` — `nbrhosts` fixture**: Extended with per-VRF metadata. Callers
  continue to see one entry per logical BGP neighbor (VRF). Multi-VRF-specific data is
  available via `nbrhosts[host]['multi_vrf_data']` when needed (e.g. to deduplicate
  operations on the same physical container).

- **`tests/bgp/bgp_helpers.py`** and **`tests/bgp/conftest.py`**: Updated to pass the
  correct VRF context when querying BGP routes and sessions, and to avoid config session
  race conditions on shared physical containers.


## Known Limitations
- Neighbor containers (e.g. cEOS) do not allow for the creation of interfaces with
interface-IDs greater than 127, when interfaces are laid out unidimensionally.
- The use of multiple VRFs has not been tested in conjunction with asynchronous ansible
tasks.
