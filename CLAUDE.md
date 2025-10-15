# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TELECLOUD is a cloud-based network topology orchestration platform that enables users to design, deploy, and manage virtual machine topologies across multiple availability zones. The system consists of:

1. **FastAPI Application** (`main_fastapi.py`) - REST API with JWT authentication and MongoDB persistence
2. **Deployment Orchestrator** (`slice_manager/deploy_topology.py`) - Automated VM deployment using QEMU/OVS
3. **Web Interface** - Interactive topology editor with drag-and-drop (templates/index.html, static/script.js)
4. **Network Management** - VLAN-based isolation with OpenFlow Switch coordination

**Key Architectural Pattern:** This system uses a "template → slice" lifecycle where users create and edit topologies as templates, then deploy them as immutable slices (deployed instances).

## Environment Setup

### Python Version
**CRITICAL**: This project requires Python 3.12. Setup:

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate (Linux/Mac)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup (MongoDB)
The project uses MongoDB 7.0 for state management (users, templates, slices):

```bash
# Install MongoDB 7.0 (Ubuntu)
sudo apt install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify
mongosh telecloud_db --eval "db.stats()"
```

## Running the Application

### Development Mode

```bash
# Start FastAPI server
python main_fastapi.py
# Access at http://127.0.0.1:8000 (or http://0.0.0.0:8000 in production)
```

### Production Mode (Head Node Deployment)

```bash
# Deploy to Head Node with systemd service
./deploy_headnode.sh

# Service management
sudo systemctl status telecloud
sudo systemctl restart telecloud
sudo journalctl -u telecloud -f
```

### Create Admin User

```bash
# Create admin account (username: admin, password: admin123)
python create_admin_mongo.py

# Create custom user with specific role
python create_user_mongo.py
```

### Deploy Topologies

```bash
# Deploy a topology from JSON template
python slice_manager/deploy_topology.py --json templates/my_template.json

# Deploy without reinitializing infrastructure
python slice_manager/deploy_topology.py --json templates/my_template.json --no-init

# Dry run (preview without execution)
python slice_manager/deploy_topology.py --json templates/my_template.json --dry-run

# Deploy to specific slice ID
python slice_manager/deploy_topology.py --json templates/my_template.json --slice-id my-slice-001

# Release VLANs for a slice (does not destroy VMs)
python slice_manager/deploy_topology.py --release-slice my-slice-001
```

## Architecture

### Multi-Zone Infrastructure

The system manages three worker nodes plus one OpenFlow Switch (OFS):

- **OFS**: 10.0.10.5 - Centralized switch coordinating inter-VM connectivity
- **Worker1** (linux-AZ-1): 10.0.10.2 - Isolated availability zone
- **Worker2** (linux-AZ-2): 10.0.10.3 - Shared availability zone
- **Worker3** (linux-AZ-2): 10.0.10.4 - Shared availability zone

**Head Node**: 10.0.10.1 - Runs FastAPI, MongoDB, and orchestrates deployments via SSH (has passwordless SSH keys to all workers)

### Availability Zone Routing

When deploying a topology with `availability_zone` in the JSON template:

- `"linux-AZ-1"`: VMs deploy only to worker1
- `"linux-AZ-2"`: VMs round-robin between worker2 and worker3
- `null` or `""` (auto): VMs round-robin across all workers

### VLAN Allocation Strategy

- **1 VLAN per edge** (link between VMs), not per VM
- VLANs are assigned sequentially (1-4094) and persisted in `~/.orchestrator/vlans.json`
- Multi-NIC VMs: Each VM gets one NIC per VLAN it participates in
- VLANs are reused after releasing a slice
- **Internet Access**: VMs with `internet_access: true` automatically get VLAN 300 (reserved)
- **Reserved VLANs**: VLAN 300 is reserved for internet connectivity

### User Roles and Permissions

| Role | Max Slices | Available Zones |
|------|-----------|-----------------|
| **general** | 3 | linux-AZ-1 only |
| **vip** | 10 | Automatic, linux-AZ-1, linux-AZ-2 |
| **admin** | 999 (unlimited) | Automatic, linux-AZ-1, linux-AZ-2 |

### Template JSON Structure

```json
{
  "metadata": {
    "name": "example_topology",
    "created_at": "2025-10-11T02:26:00.000000",
    "availability_zone": "linux-AZ-1"
  },
  "topology": {
    "nodes": [
      {
        "id": 1,
        "x": 5000,
        "y": 5000,
        "label": "VM-1",
        "flavor": {"vcpus": 2, "ram": 4, "disk": 40},
        "image": "ubuntu",
        "internet_access": false
      }
    ],
    "edges": [
      {"from": 1, "to": 2}
    ]
  }
}
```

**Flavor Constraints:**
- vCPUs: 1-4 (integer)
- RAM: 0.5-4 GB (multiples of 0.5)
- Disk: 1-10 GB (float allowed)

**Supported Images:**
- `ubuntu` - Ubuntu VM
- `cirros` - Lightweight test VM (default)

## Key Files

### Main Application
- `main_fastapi.py` - FastAPI application with JWT auth, MongoDB integration, and API endpoints
- `auth_jwt.py` - JWT authentication system (SECRET_KEY, token generation, role-based access)
- `auth_mongo.py` - Flask-Login authentication (legacy, for app_mongo.py)
- `app_mongo.py` - Flask version with session-based auth (legacy)
- `network_topology.py` - Tkinter desktop GUI (legacy, not actively used)

### Database
- `database/mongo_config.py` - MongoDB connection configuration
- `create_admin_mongo.py` - Script to create admin user
- `create_user_mongo.py` - Script to create users with custom roles

### Deployment Orchestration
- `slice_manager/deploy_topology.py` - Main orchestrator for VM deployment with VLAN management
- `slice_manager/init_ofs.sh` - Initialize OpenFlow Switch
- `slice_manager/init_worker.sh` - Initialize worker OVS bridges
- `slice_manager/vm_create_multi.sh` - Create multi-NIC QEMU VMs
- `slice_manager/eliminar_tap.sh` - Remove TAP interfaces
- `slice_manager/internet_conectivity.sh` - Configure internet access (VLAN 300)

### Frontend
- `templates/index.html` - Topology editor (main canvas interface)
- `templates/login.html` - Login page
- `templates/register.html` - User registration page
- `templates/dashboard.html` - User dashboard (templates and slices)
- `templates/viewer.html` - Read-only slice viewer
- `templates/admin.html` - Admin panel (all users, templates, slices)
- `static/script.js` - Frontend topology visualization and interaction logic
- `static/styles.css` - UI styling

### Documentation
- `Documentacion/API_DOCUMENTATION.md` - Complete REST API reference with JWT examples
- `DEPLOYMENT_GUIDE.md` - Full production deployment guide for Head Node
- `Documentacion/README_MONGODB.md` - MongoDB setup and operations
- `Documentacion/README_FASTAPI.md` - FastAPI development notes

### Example Templates
- `ejemplos_plantillas/` - Sample topology templates for testing

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info
- `GET /api/auth/available-azs` - Get available AZs for user role

### Topology Management
- `POST /api/topology/generate` - Generate predefined topology (tree, star, ring, mesh, bus, point-to-point)
- `POST /api/topology/sync` - Sync frontend topology with backend state
- `POST /api/topology/save` - Save topology as template (creates JSON file + MongoDB entry)
- `POST /api/topology/clear` - Clear current topology
- `GET /api/topology/state` - Get current topology state
- `POST /api/topology/load` - Load topology from uploaded JSON file
- `GET /api/topology/export-json` - Export current topology as JSON
- `POST /api/placement/az` - Set availability zone for new nodes

### Node Management
- `POST /api/nodes` - Add individual VM node
- `DELETE /api/nodes/<id>` - Delete VM node
- `PUT /api/nodes/<id>/move` - Move node position (UI only)
- `PUT /api/nodes/<id>/flavor` - Update VM flavor, image, internet_access

### Edge Management
- `POST /api/edges` - Connect two VMs
- `POST /api/edges/delete` - Delete connection

### Templates (Pre-deployment)
- `GET /api/templates` - Get user's templates
- `PUT /api/templates/<id>` - Update template
- `DELETE /api/templates/<id>` - Delete template
- `POST /api/templates/<id>/deploy` - Deploy template as slice (template is deleted, slice is created)

### Slices (Deployed Topologies)
- `GET /api/slices` - Get user's slices
- `DELETE /api/slices/<slice_id>` - Delete slice (executes eliminar_slice.sh to destroy VMs)

### Admin Endpoints (admin role only)
- `GET /api/admin/users` - Get all users
- `GET /api/admin/templates` - Get all templates (all users)
- `GET /api/admin/slices` - Get all slices (all users)
- `DELETE /api/admin/templates/<id>` - Delete any template
- `DELETE /api/admin/slices/<slice_id>` - Delete any slice

**All endpoints except `/api/auth/register` and `/api/auth/login` require JWT token in Authorization header:**
```
Authorization: Bearer <your-jwt-token>
```

## Important Implementation Details

### State Management

**Backend (FastAPI):**
- `topology` global object in `main_fastapi.py` maintains in-memory topology state (nodes, edges)
- State is synchronized between frontend and backend via `/api/topology/sync`
- Templates are persisted in MongoDB (`templates` collection)
- Slices are persisted in MongoDB (`slices` collection)

**Orchestrator:**
- State persisted in `~/.orchestrator/vlans.json` on Head Node
- Contains `used_vlans` (global pool) and `slices` (deployed instances with VMs and VLANs)

### VNC Port Assignment
VNC ports start at 5901 per worker and increment for each VM. The orchestrator tracks used ports across all slices to avoid conflicts.

### Template → Slice Lifecycle

1. **Creation**: User creates topology in editor
2. **Save as Template**: `POST /api/topology/save` creates:
   - JSON file in `templates/` directory on Head Node
   - MongoDB document in `templates` collection with `json_filename` reference
3. **Deploy**: `POST /api/templates/<id>/deploy`:
   - Executes `python3 /home/ubuntu/deploy_topology.py --json <filepath> --slice-id <slice_id>`
   - Creates VMs on workers via SSH
   - Creates MongoDB document in `slices` collection
   - **Deletes template** from MongoDB (lifecycle transition)
4. **Delete Slice**: `DELETE /api/slices/<slice_id>`:
   - Executes `/home/ubuntu/eliminar_slice.sh <slice_id>`
   - Destroys VMs and frees VLANs
   - Removes slice from MongoDB

### SSH and Networking

- Head Node has **passwordless SSH keys** to all workers (worker1, worker2, worker3, OFS)
- Workers require passwords for SSH between each other
- Deployment commands use `subprocess.run()` with SSH to execute scripts on remote workers
- Internet access uses VLAN 300 and requires `internet_conectivity.sh` configuration

### Topology Generation

The `NetworkTopology.generate_topology()` method supports:
- **point-to-point**: 2 VMs directly connected
- **star**: Central hub with peripheral VMs
- **tree**: Hierarchical structure with configurable levels and branching factor
- **ring**: VMs in circular topology
- **bus**: Linear topology with sequential connections
- **mesh**: Fully connected topology (all VMs connected to all others)

## Development Notes

- Coordinates (x, y) in JSON are for UI visualization only, not used in deployment
- The deployment script uses SSH to execute remote commands on workers and OFS
- VLAN range is 1-4094 (802.1Q standard, excluding reserved 0 and 4095)
- VNC access to VMs: `vnc://<worker-host>:<vnc-port>` (ports 5901+)
- FastAPI must run with `host="0.0.0.0"` for production access (not `127.0.0.1`)
- JWT tokens expire after 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24`)
- MongoDB database name: `telecloud_db`
- Collections: `users`, `templates`, `slices`

## Common Development Tasks

### Adding a New Topology Type

1. Edit `main_fastapi.py` → `NetworkTopology.generate_topology()` method
2. Add new `elif topology_type == "new_type":` branch
3. Generate `new_nodes` and `new_edges` lists
4. Update frontend `static/script.js` to add UI controls for new type

### Modifying User Permissions

1. Edit `auth_jwt.py` → `get_available_zones()` or `get_max_slices()`
2. Modify role-based logic for `general`, `vip`, or `admin`
3. Restart FastAPI service: `sudo systemctl restart telecloud`

### Debugging Deployment Issues

1. Check orchestrator logs: `sudo journalctl -u telecloud -f`
2. Check MongoDB slice records: `mongosh telecloud_db --eval "db.slices.find().pretty()"`
3. Check VLAN state: `cat ~/.orchestrator/vlans.json`
4. Test SSH connectivity: `ssh ubuntu@10.0.10.2` (should not prompt for password)
5. Check OVS bridges: `ssh ubuntu@10.0.10.2 "sudo ovs-vsctl show"`

### Testing API Endpoints

Use FastAPI's interactive docs: `http://127.0.0.1:8000/docs` (Swagger UI)

Or with curl:
```bash
# Login
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Get templates (with token)
curl -X GET http://127.0.0.1:8000/api/templates \
  -H "Authorization: Bearer <your-token>"
```

## Production Deployment

See `DEPLOYMENT_GUIDE.md` for complete Head Node deployment instructions including:
- MongoDB installation and configuration
- FastAPI systemd service setup
- Gateway port forwarding configuration (port 8080 → Head Node:8000)
- SSL/TLS setup (if needed)
- Backup and recovery procedures
