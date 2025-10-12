# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cloud-based network topology builder and deployment system that allows users to design virtual machine topologies (tree, star, ring, mesh, bus, point-to-point) and deploy them across multiple availability zones. The project consists of:

1. **Flask Web Application** (`app.py`) - Interactive web UI for topology design
2. **Deployment Orchestrator** (`slice_manager/deploy_topology.py`) - Automated VM deployment using QEMU/OVS across worker nodes
3. **Network Management** - VLAN-based isolation with OpenFlow Switch (OFS) coordination

## Environment Setup

### Python Version
**IMPORTANT**: This project requires Python 3.12. Use the following setup:

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Database Setup (PostgreSQL 16)
The project uses PostgreSQL for state management:

```bash
# Validate PostgreSQL installation
psql --version

# Connect as postgres user
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'password';

# Create SSH tunnel from local machine (if needed)
ssh -N -L 5433:127.0.0.1:5432 -p 5801 ubuntu@IP
```

## Running the Application

### Web Interface (Development)
```bash
python app.py
# Access at http://127.0.0.1:5000
```

The web interface provides:
- Interactive topology design with drag-and-drop
- Predefined topology generation (tree, star, ring, etc.)
- VM flavor configuration (vCPUs, RAM, disk)
- Availability zone selection
- Template save/load functionality
- SVG/PNG export

### Topology Deployment
```bash
# Deploy a topology from JSON template
python slice_manager/deploy_topology.py --json <template.json> [--slice-id <id>]

# Deploy without reinitializing infrastructure
python slice_manager/deploy_topology.py --json <template.json> --no-init

# Dry run (preview without execution)
python slice_manager/deploy_topology.py --json <template.json> --dry-run

# Release VLANs for a slice
python slice_manager/deploy_topology.py --release-slice <slice-id>
```

## Architecture

### Multi-Zone Infrastructure
The system manages three worker nodes plus one OpenFlow Switch (OFS):

- **OFS**: 10.0.10.5 - Centralized switch coordinating inter-VM connectivity
- **Worker1** (linux-AZ-1): 10.0.10.2 - Isolated availability zone
- **Worker2** (linux-AZ-2): 10.0.10.3 - Shared availability zone
- **Worker3** (linux-AZ-2): 10.0.10.4 - Shared availability zone

### VLAN Allocation Strategy
- **1 VLAN per edge** (link between VMs), not per VM
- VLANs are assigned sequentially (1-4094) and persisted in `~/.orchestrator/vlans.json`
- Multi-NIC VMs: Each VM gets one NIC per VLAN it participates in
- VLANs are reused after releasing a slice

### Availability Zone Routing
When deploying a topology with `availability_zone` in the JSON template:
- `"linux-AZ-1"`: VMs deploy only to worker1
- `"linux-AZ-2"`: VMs round-robin between worker2 and worker3
- `null` or absent: VMs round-robin across all workers

### Template JSON Structure
```json
{
  "metadata": {
    "name": "example_topology",
    "created_at": "2025-10-11T02:26:00.000000",
    "format": "full"
  },
  "flavor_defaults": {
    "vcpus": 2,
    "ram": 4,
    "disk": 40
  },
  "availability_zone": "linux-AZ-1",
  "topology": {
    "nodes": [
      {
        "id": 1,
        "x": 5000,
        "y": 5000,
        "label": "VM-1",
        "flavor": {"vcpus": 2, "ram": 4, "disk": 40},
        "az": "linux-AZ-1"
      }
    ],
    "edges": [
      {"from": 1, "to": 2}
    ]
  }
}
```

## Key Files

- `app.py` - Main Flask application with NetworkTopology class
- `slice_manager/deploy_topology.py` - Orchestrator for VM deployment with VLAN management
- `slice_manager/init_ofs.sh` - Initialize OpenFlow Switch
- `slice_manager/init_worker.sh` - Initialize worker OVS bridges
- `slice_manager/vm_create_multi.sh` - Create multi-NIC QEMU VMs
- `templates/index.html` - Web UI (with embedded JavaScript)
- `static/script.js` - Frontend topology visualization logic
- `ejemplos_plantillas/` - Sample topology templates

## Important Implementation Details

### Flask API Endpoints
- `POST /api/topology/generate` - Generate predefined topology
- `POST /api/topology/save` - Save topology as JSON template
- `POST /api/topology/load` - Load topology from JSON file
- `POST /api/topology/clear` - Clear current topology
- `POST /api/nodes` - Add individual VM node
- `DELETE /api/nodes/<id>` - Delete VM node
- `PUT /api/nodes/<id>/flavor` - Update VM flavor configuration
- `POST /api/edges` - Connect two VMs
- `POST /api/edges/delete` - Delete connection
- `POST /api/placement/az` - Set availability zone for new nodes

### State Management
The orchestrator maintains persistent state in `~/.orchestrator/vlans.json`:
- `used_vlans`: Global list of allocated VLANs
- `slices`: Dictionary of deployed slices with VM details, VLANs, and VNC ports

### VNC Port Assignment
VNC ports start at 5901 per worker and increment for each VM. The orchestrator tracks used ports across all slices to avoid conflicts.

## Development Notes

- The web app maintains topology state in-memory (server-side Flask object)
- Coordinates (x, y) in JSON are for UI visualization only, not used in deployment
- The deployment script uses SSH to execute remote commands on workers and OFS
- VLAN range is 1-4094 (802.1Q standard, excluding reserved 0 and 4095)
- The Tkinter application (`network_topology.py`) is a legacy desktop version, not actively used
