"""
Aplicación principal con FastAPI + JWT para autenticación
Sirve templates con Flask montado en FastAPI
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import timedelta
from typing import Optional
from bson import ObjectId
import json
from datetime import datetime

# Imports de autenticación JWT
from auth_jwt import (
    Token, UserLogin, UserCreate, get_current_user, get_current_active_user,
    authenticate_user, create_access_token, create_user,
    get_available_zones, get_max_slices, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Imports de MongoDB
from database.mongo_config import get_db

# Imports de topología (del código existente)
import math

# ==========================================
# INICIALIZACIÓN FASTAPI
# ==========================================

app = FastAPI(title="Cloud Topology Manager API", version="2.0")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==========================================
# CLASE DE TOPOLOGÍA (de app_mongo.py)
# ==========================================

class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.topology_count = 0
        self.placement_az = None

    def _validate_flavor(self, flavor):
        """Valida que el flavor cumpla con los límites"""
        if not flavor:
            return True, ""

        vcpus = flavor.get('vcpus')
        ram = flavor.get('ram')
        disk = flavor.get('disk')

        # Validar vCPUs (1-4 enteros)
        if vcpus is not None:
            try:
                vcpus = int(vcpus)
                if vcpus < 1 or vcpus > 4:
                    return False, "vCPUs debe estar entre 1 y 4"
            except (ValueError, TypeError):
                return False, "vCPUs debe ser un número entero"

        # Validar RAM (0.5-4 GB, múltiplos de 0.5)
        if ram is not None:
            try:
                ram = float(ram)
                if ram < 0.5 or ram > 4 or (ram * 2) % 1 != 0:
                    return False, "RAM debe estar entre 0.5 y 4 GB (múltiplos de 0.5)"
            except (ValueError, TypeError):
                return False, "RAM debe ser un número"

        # Validar Disco (1-10 GB, ahora con decimales)
        if disk is not None:
            try:
                disk = float(disk)
                if disk < 1 or disk > 10:
                    return False, "Disco debe estar entre 1 y 10 GB"
            except (ValueError, TypeError):
                return False, "Disco debe ser un número"

        return True, ""

    def generate_topology(self, topology_type, config, flavor=None):
        if flavor is None:
            flavor = {'vcpus': 1, 'ram': 0.5, 'disk': 1}
        else:
            is_valid, error_msg = self._validate_flavor(flavor)
            if not is_valid:
                raise ValueError(f"Flavor inválido: {error_msg}")

        self.topology_count += 1
        grid_size = 3
        col = (self.topology_count - 1) % grid_size
        row = (self.topology_count - 1) // grid_size
        spacing_x = 250
        spacing_y = 200
        base_x = 200 + col * spacing_x
        base_y = 150 + row * spacing_y

        new_nodes = []
        new_edges = []

        if self.nodes:
            next_id = max([node['id'] for node in self.nodes]) + 1
        else:
            next_id = 1

        if topology_type == "point-to-point":
            new_nodes = [
                {'id': next_id, 'x': base_x - 50, 'y': base_y, 'label': f'VM-{next_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False},
                {'id': next_id + 1, 'x': base_x + 50, 'y': base_y, 'label': f'VM-{next_id + 1}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False}
            ]
            new_edges = [{'from': next_id, 'to': next_id + 1}]

        elif topology_type == "star":
            radius = 80
            central_id = next_id
            new_nodes = [{'id': central_id, 'x': base_x, 'y': base_y, 'label': f'VM-{central_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False}]
            node_count = config.get('node_count', 5)
            for i in range(node_count - 1):
                angle = (i * 2 * math.pi) / (node_count - 1)
                new_id = next_id + i + 1
                new_nodes.append({'id': new_id, 'x': base_x + radius * math.cos(angle), 'y': base_y + radius * math.sin(angle), 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})
                new_edges.append({'from': central_id, 'to': new_id})

        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            root_id = next_id
            new_nodes.append({'id': root_id, 'x': base_x, 'y': base_y, 'label': f'VM-{root_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})
            current_level = [{'id': root_id, 'x': base_x, 'y': base_y}]
            current_id = next_id + 1
            for level in range(1, levels):
                next_level = []
                nodes_in_level = len(current_level) * branching
                spacing = min(200, 300 / max(1, nodes_in_level))
                y = base_y + level * 80
                for parent_idx, parent in enumerate(current_level):
                    for i in range(branching):
                        child_idx = parent_idx * branching + i
                        total_width = (nodes_in_level - 1) * spacing
                        start_x = base_x - total_width / 2
                        x = start_x + child_idx * spacing
                        new_nodes.append({'id': current_id, 'x': x, 'y': y, 'label': f'VM-{current_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})
                        new_edges.append({'from': parent['id'], 'to': current_id})
                        next_level.append({'id': current_id, 'x': x, 'y': y})
                        current_id += 1
                current_level = next_level

        elif topology_type == "ring":
            node_count = config.get('node_count', 5)
            radius = 100
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                x = base_x + radius * math.cos(angle)
                y = base_y + radius * math.sin(angle)
                new_nodes.append({'id': new_id, 'x': x, 'y': y, 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})
                # Conectar con el siguiente nodo
                next_node_id = next_id + ((i + 1) % node_count)
                new_edges.append({'from': new_id, 'to': next_node_id})

        elif topology_type == "bus":
            node_count = config.get('node_count', 5)
            spacing = 80
            for i in range(node_count):
                new_id = next_id + i
                x = base_x + (i - node_count // 2) * spacing
                y = base_y
                new_nodes.append({'id': new_id, 'x': x, 'y': y, 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})
                # Conectar con el siguiente nodo (excepto el último)
                if i < node_count - 1:
                    new_edges.append({'from': new_id, 'to': new_id + 1})

        elif topology_type == "mesh":
            node_count = config.get('node_count', 5)
            radius = 100
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                x = base_x + radius * math.cos(angle)
                y = base_y + radius * math.sin(angle)
                new_nodes.append({'id': new_id, 'x': x, 'y': y, 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'image': 'ubuntu', 'internet_access': False})

            # Conectar todos con todos (malla completa)
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    new_edges.append({'from': next_id + i, 'to': next_id + j})

        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        if self.nodes:
            self.next_id = max(node['id'] for node in self.nodes) + 1

    def add_node(self, x, y, flavor=None, image='ubuntu', internet_access=False):
        if flavor is None:
            flavor = {'vcpus': 1, 'ram': 0.5, 'disk': 1}
        else:
            is_valid, error_msg = self._validate_flavor(flavor)
            if not is_valid:
                raise ValueError(f"Flavor inválido: {error_msg}")

        new_node = {
            'id': self.next_id,
            'x': x,
            'y': y,
            'label': f'VM-{self.next_id}',
            'flavor': flavor.copy(),
            'image': image,
            'internet_access': internet_access
        }
        self.nodes.append(new_node)
        self.next_id += 1
        return new_node

    def delete_node(self, node_id):
        self.nodes = [node for node in self.nodes if node['id'] != node_id]
        self.edges = [edge for edge in self.edges if edge['from'] != node_id and edge['to'] != node_id]

    def connect_nodes(self, from_id, to_id):
        existing = any((edge['from'] == from_id and edge['to'] == to_id) or (edge['from'] == to_id and edge['to'] == from_id) for edge in self.edges)
        if not existing and from_id != to_id:
            self.edges.append({'from': from_id, 'to': to_id})
            return True
        return False

    def delete_edge(self, from_id, to_id):
        self.edges = [edge for edge in self.edges if not (edge['from'] == from_id and edge['to'] == to_id)]

    def move_node(self, node_id, x, y):
        for node in self.nodes:
            if node['id'] == node_id:
                node['x'] = x
                node['y'] = y
                break

    def update_node_flavor(self, node_id, flavor, image=None, internet_access=None):
        is_valid, error_msg = self._validate_flavor(flavor)
        if not is_valid:
            raise ValueError(f"Flavor inválido: {error_msg}")

        for node in self.nodes:
            if node['id'] == node_id:
                node['flavor'] = flavor.copy()
                if image is not None:
                    node['image'] = image
                if internet_access is not None:
                    node['internet_access'] = internet_access
                break

    def set_placement_az(self, az):
        self.placement_az = az

    def get_state(self):
        return {'nodes': self.nodes, 'edges': self.edges}

    def load_from_template(self, template_data):
        """Carga una topología desde datos de plantilla"""
        try:
            self.nodes = []
            self.edges = []

            topology_data = template_data.get('topology', {})
            self.nodes = topology_data.get('nodes', [])
            self.edges = topology_data.get('edges', [])

            if self.nodes:
                self.next_id = max(node['id'] for node in self.nodes) + 1
            else:
                self.next_id = 1

            self.topology_count = 0

            metadata = template_data.get('metadata', {})
            az = metadata.get('availability_zone')
            if az:
                self.placement_az = az

            return True
        except Exception as e:
            print(f"Error loading template: {e}")
            return False

topology = NetworkTopology()

# ==========================================
# ENDPOINTS DE AUTENTICACIÓN
# ==========================================

@app.post("/api/auth/register", response_model=dict)
async def register(user_data: UserCreate):
    """Registro de nuevo usuario"""
    user, error = create_user(user_data)
    if error:
        raise HTTPException(status_code=400, detail=error)

    return {
        "success": True,
        "message": "Usuario creado exitosamente",
        "user": {
            "id": str(user['_id']),
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        }
    }

@app.post("/api/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Login con JWT"""
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user['_id'])}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user['_id']),
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "is_active": user.get('is_active', True)
        }
    }

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """Obtiene información del usuario actual"""
    return {
        "id": str(current_user['_id']),
        "username": current_user['username'],
        "email": current_user['email'],
        "role": current_user['role'],
        "is_active": current_user.get('is_active', True),
        "available_zones": get_available_zones(current_user),
        "max_slices": get_max_slices(current_user)
    }

@app.get("/api/auth/available-azs")
async def get_available_azs(current_user: dict = Depends(get_current_active_user)):
    """Obtiene las zonas de disponibilidad permitidas para el usuario actual"""
    available_azs = get_available_zones(current_user)
    role = current_user.get('role', 'general')

    # Construir lista de AZ según el rol
    all_azs = []

    if role == 'general':
        # Usuario General: solo linux-AZ-1 + openstack-AZ-1 (próximamente)
        all_azs = [
            {"value": "linux-AZ-1", "label": "linux-AZ-1", "enabled": True, "coming_soon": False},
            {"value": "openstack-AZ-1", "label": "openstack-AZ-1 (Próximamente)", "enabled": False, "coming_soon": True}
        ]
    elif role == 'vip':
        # Usuario VIP: automático + todas linux + todas openstack (próximamente)
        all_azs = [
            {"value": "", "label": "Automático", "enabled": True, "coming_soon": False},
            {"value": "linux-AZ-1", "label": "linux-AZ-1", "enabled": True, "coming_soon": False},
            {"value": "linux-AZ-2", "label": "linux-AZ-2", "enabled": True, "coming_soon": False},
            {"value": "openstack-AZ-1", "label": "openstack-AZ-1 (Próximamente)", "enabled": False, "coming_soon": True},
            {"value": "openstack-AZ-2", "label": "openstack-AZ-2 (Próximamente)", "enabled": False, "coming_soon": True}
        ]
    elif role == 'admin':
        # Admin: igual que VIP por ahora (openstack próximamente)
        all_azs = [
            {"value": "", "label": "Automático", "enabled": True, "coming_soon": False},
            {"value": "linux-AZ-1", "label": "linux-AZ-1", "enabled": True, "coming_soon": False},
            {"value": "linux-AZ-2", "label": "linux-AZ-2", "enabled": True, "coming_soon": False},
            {"value": "openstack-AZ-1", "label": "openstack-AZ-1 (Próximamente)", "enabled": False, "coming_soon": True},
            {"value": "openstack-AZ-2", "label": "openstack-AZ-2 (Próximamente)", "enabled": False, "coming_soon": True}
        ]

    return {
        "success": True,
        "role": role,
        "azs": all_azs
    }

# ==========================================
# ENDPOINTS DE TOPOLOGÍA
# ==========================================

@app.post("/api/topology/generate")
async def generate_topology_endpoint(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Generar topología"""
    try:
        topology.generate_topology(data.get('type', 'tree'), data.get('config', {}), data.get('flavor', None))
        return {'success': True, 'topology': topology.get_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/topology/sync")
async def sync_topology(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Sincronizar topología del frontend con backend"""
    try:
        topology.nodes = data.get('nodes', [])
        topology.edges = data.get('edges', [])

        if topology.nodes:
            topology.next_id = max(node['id'] for node in topology.nodes) + 1
        else:
            topology.next_id = 1

        return {'success': True, 'message': 'Topología sincronizada'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/topology/save")
async def save_topology(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Guardar plantilla en MongoDB Y en archivo físico .json"""
    import os
    import re
    try:
        name = data.get('name', 'topology')
        az = data.get('az', '')
        template_id = data.get('template_id')
        topology_json = {'nodes': topology.nodes, 'edges': topology.edges}
        db = get_db()

        # Validar y limpiar nombre
        if not name or name.strip() == "":
            name = 'topology'
        # Limpiar el nombre para que sea válido como archivo
        clean_name = re.sub(r'[^\w\-_.]', '_', name)

        # 1. GUARDAR EN MONGODB
        if template_id:
            db.templates.update_one(
                {'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])},
                {'$set': {'name': name, 'topology_json': topology_json, 'availability_zone': az, 'updated_at': datetime.now()}}
            )
            message = "Plantilla actualizada"
        else:
            result = db.templates.insert_one({
                'user_id': str(current_user['_id']),
                'name': name,
                'topology_json': topology_json,
                'availability_zone': az,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            template_id = str(result.inserted_id)
            message = "Plantilla guardada"

        # 2. GUARDAR ARCHIVO FÍSICO .JSON EN SERVIDOR (como el amigo)
        template_data = {
            'metadata': {
                'name': name,
                'created_at': datetime.now().isoformat(),
                'availability_zone': az
            },
            'topology': topology_json
        }

        filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join('./templates', filename)

        # Crear directorio si no existe
        os.makedirs('./templates', exist_ok=True)

        # Guardar archivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)

        return {
            'success': True,
            'message': message,
            'template_id': template_id,
            'filename': filename,
            'filepath': filepath
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/topology/state")
async def get_topology_state(current_user: dict = Depends(get_current_active_user)):
    """Obtener estado de la topología"""
    return topology.get_state()

@app.post("/api/topology/clear")
async def clear_topology(current_user: dict = Depends(get_current_active_user)):
    """Limpiar topología"""
    topology.nodes = []
    topology.edges = []
    topology.next_id = 1
    topology.topology_count = 0
    topology.placement_az = None
    return {'success': True, 'topology': topology.get_state()}

@app.post("/api/placement/az")
async def set_placement_az(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Establecer zona de disponibilidad para la topología"""
    try:
        az = data.get('az')
        topology.set_placement_az(az)
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/nodes")
async def add_node(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Agregar un nodo a la topología"""
    try:
        x = data.get('x', 0)
        y = data.get('y', 0)
        flavor = data.get('flavor', {'vcpus': 1, 'ram': 0.5, 'disk': 1})
        image = data.get('image', 'ubuntu')
        internet_access = data.get('internet_access', False)
        topology.add_node(x, y, flavor, image, internet_access)
        return {'success': True, 'topology': topology.get_state()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/nodes/{node_id}")
async def delete_node(node_id: int, current_user: dict = Depends(get_current_active_user)):
    """Eliminar un nodo de la topología"""
    try:
        topology.delete_node(node_id)
        return {'success': True, 'topology': topology.get_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/nodes/{node_id}/move")
async def move_node(node_id: int, data: dict, current_user: dict = Depends(get_current_active_user)):
    """Mover un nodo a una nueva posición"""
    try:
        x = data.get('x', 0)
        y = data.get('y', 0)
        topology.move_node(node_id, x, y)
        return {'success': True, 'topology': topology.get_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/nodes/{node_id}/flavor")
async def update_node_flavor(node_id: int, data: dict, current_user: dict = Depends(get_current_active_user)):
    """Actualizar el flavor de un nodo"""
    try:
        flavor = data.get('flavor', {'vcpus': 1, 'ram': 0.5, 'disk': 1})
        image = data.get('image')
        internet_access = data.get('internet_access')
        topology.update_node_flavor(node_id, flavor, image, internet_access)
        return {'success': True, 'topology': topology.get_state()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/edges")
async def add_edge(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Conectar dos nodos"""
    try:
        from_id = data.get('from')
        to_id = data.get('to')
        success = topology.connect_nodes(from_id, to_id)
        return {'success': success, 'topology': topology.get_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/edges/delete")
async def delete_edge_endpoint(data: dict, current_user: dict = Depends(get_current_active_user)):
    """Eliminar una conexión entre dos nodos"""
    try:
        from_id = data.get('from')
        to_id = data.get('to')
        topology.delete_edge(from_id, to_id)
        return {'success': True, 'topology': topology.get_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/topology/export-json")
async def export_topology_json(current_user: dict = Depends(get_current_active_user)):
    """Exporta la topología actual como JSON para descargar"""
    try:
        # Obtener la AZ actual
        current_az = topology.placement_az if topology.placement_az else ""

        template_data = {
            'metadata': {
                'name': 'topology_export',
                'created_at': datetime.now().isoformat(),
                'availability_zone': current_az
            },
            'topology': topology.get_state()
        }

        return {'success': True, 'data': template_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/topology/load")
async def load_topology_from_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_active_user)):
    """Carga una topología desde un archivo JSON"""
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail='Invalid file format. Only JSON files are allowed.')

        contents = await file.read()
        template_data = json.loads(contents)

        success = topology.load_from_template(template_data)

        if success:
            return {
                'success': True,
                'topology': topology.get_state(),
                'availability_zone': topology.placement_az
            }
        else:
            raise HTTPException(status_code=400, detail='Error processing template')
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid JSON format')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS DE TEMPLATES
# ==========================================

@app.get("/api/templates")
async def get_templates(current_user: dict = Depends(get_current_active_user)):
    """Obtener plantillas del usuario"""
    db = get_db()
    templates = list(db.templates.find({'user_id': str(current_user['_id'])}).sort('created_at', -1))

    # Convertir ObjectId a string
    for template in templates:
        template['_id'] = str(template['_id'])

    return {"templates": templates}

@app.put("/api/templates/{template_id}")
async def update_template(template_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """Actualizar plantilla"""
    try:
        name = data.get('name', 'topology')
        az = data.get('az', '')
        topology_json = {'nodes': topology.nodes, 'edges': topology.edges}

        db = get_db()
        result = db.templates.update_one(
            {'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])},
            {'$set': {
                'name': name,
                'topology_json': topology_json,
                'availability_zone': az,
                'updated_at': datetime.now()
            }}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        return {'success': True, 'message': 'Plantilla actualizada'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar plantilla"""
    try:
        db = get_db()
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates/{template_id}/deploy")
async def deploy_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Desplegar plantilla como slice"""
    try:
        db = get_db()
        active_slices = db.slices.count_documents({'user_id': str(current_user['_id']), 'status': 'active'})
        max_slices = get_max_slices(current_user)

        if active_slices >= max_slices:
            raise HTTPException(status_code=400, detail=f'Límite de {max_slices} slices alcanzado')

        template = db.templates.find_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})
        if not template:
            raise HTTPException(status_code=404, detail='Plantilla no encontrada')

        slice_id = f"{template['name']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        vm_count = len(template['topology_json'].get('nodes', []))

        db.slices.insert_one({
            'template_id': str(template['_id']),
            'user_id': str(current_user['_id']),
            'slice_id': slice_id,
            'name': template['name'],
            'topology_json': template['topology_json'],
            'availability_zone': template.get('availability_zone'),
            'deployed_at': datetime.now(),
            'status': 'active',
            'vm_count': vm_count
        })

        # Eliminar la plantilla (ahora es un slice)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})

        return {'success': True, 'slice_id': slice_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS DE SLICES
# ==========================================

@app.get("/api/slices")
async def get_slices(current_user: dict = Depends(get_current_active_user)):
    """Obtener slices del usuario"""
    db = get_db()
    slices = list(db.slices.find({'user_id': str(current_user['_id'])}).sort('deployed_at', -1))

    # Convertir ObjectId a string
    for slice in slices:
        slice['_id'] = str(slice['_id'])

    return {"slices": slices}

@app.delete("/api/slices/{slice_id}")
async def delete_slice(slice_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar slice"""
    try:
        db = get_db()
        db.slices.delete_one({'slice_id': slice_id, 'user_id': str(current_user['_id'])})
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS DE ADMINISTRADOR
# ==========================================

@app.get("/api/admin/users")
async def get_all_users(current_user: dict = Depends(get_current_active_user)):
    """Obtener todos los usuarios (solo admin)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()
        users = list(db.users.find({}, {'password_hash': 0}).sort('created_at', -1))

        # Convertir ObjectId a string
        for user in users:
            user['_id'] = str(user['_id'])

        return {"success": True, "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/templates")
async def get_all_templates(current_user: dict = Depends(get_current_active_user)):
    """Obtener todas las plantillas de todos los usuarios (solo admin)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()
        # Obtener todas las plantillas con info del usuario
        templates = list(db.templates.find().sort('created_at', -1))

        # Enriquecer con info del usuario
        for template in templates:
            template['_id'] = str(template['_id'])
            user = db.users.find_one({'_id': ObjectId(template['user_id'])})
            if user:
                template['username'] = user['username']
                template['user_role'] = user.get('role', 'general')

        return {"success": True, "templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/slices")
async def get_all_slices(current_user: dict = Depends(get_current_active_user)):
    """Obtener todos los slices de todos los usuarios (solo admin)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()
        # Obtener todos los slices con info del usuario
        slices = list(db.slices.find().sort('deployed_at', -1))

        # Enriquecer con info del usuario
        for slice in slices:
            slice['_id'] = str(slice['_id'])
            user = db.users.find_one({'_id': ObjectId(slice['user_id'])})
            if user:
                slice['username'] = user['username']
                slice['user_role'] = user.get('role', 'general')

        return {"success": True, "slices": slices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/templates/{template_id}")
async def admin_delete_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar cualquier plantilla (solo admin)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()
        result = db.templates.delete_one({'_id': ObjectId(template_id)})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        return {'success': True, 'message': 'Plantilla eliminada por administrador'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/slices/{slice_id}")
async def admin_delete_slice(slice_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar cualquier slice (solo admin)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()
        result = db.slices.delete_one({'slice_id': slice_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Slice no encontrado")

        return {'success': True, 'message': 'Slice eliminado por administrador'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS PARA UI (TEMPLATES HTML)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirigir a login"""
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Página de registro"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Página de dashboard - requiere token en cookie o localStorage"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request, template_id: Optional[str] = None):
    """Página del editor"""
    context = {"request": request}

    # Si hay template_id, cargar los datos de la plantilla
    if template_id:
        try:
            db = get_db()
            template = db.templates.find_one({'_id': ObjectId(template_id)})
            if template:
                context['template_data'] = json.dumps(template['topology_json'])
                context['template_id'] = template_id
                context['template_name'] = template['name']
                context['template_az'] = template.get('availability_zone', '')
        except:
            pass

    return templates.TemplateResponse("index.html", context)

@app.get("/viewer", response_class=HTMLResponse)
async def viewer_page(request: Request, slice_id: Optional[str] = None):
    """Página del visor de slices (solo lectura)"""
    context = {"request": request, "view_only": True}

    # Cargar datos del slice
    if slice_id:
        try:
            db = get_db()
            slice_doc = db.slices.find_one({'_id': ObjectId(slice_id)})
            if slice_doc:
                context['slice_data'] = json.dumps(slice_doc['topology_json'])
                context['slice_id'] = slice_id
                context['slice_name'] = slice_doc['name']
                context['slice_az'] = slice_doc.get('availability_zone', '')
        except:
            pass

    return templates.TemplateResponse("viewer.html", context)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Página de administración (solo para admins)"""
    return templates.TemplateResponse("admin.html", {"request": request})

# ==========================================
# EJECUCIÓN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" permite acceso desde cualquier IP (necesario para producción)
    # reload=False en producción para mejor rendimiento
    uvicorn.run("main_fastapi:app", host="0.0.0.0", port=8000, reload=False)
