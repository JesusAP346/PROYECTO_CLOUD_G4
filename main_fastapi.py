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
import logging
import sys
from logging.handlers import RotatingFileHandler
import os

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
# CONFIGURACIÓN DE LOGGING PARA LOKI
# ==========================================

class JSONFormatter(logging.Formatter):
    """Formateador de logs en JSON para Loki"""
    def format(self, record):
        from datetime import timezone
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Agregar información adicional si existe
        if hasattr(record, 'user'):
            log_data['user'] = record.user
        if hasattr(record, 'action'):
            log_data['action'] = record.action
        if hasattr(record, 'ip'):
            log_data['ip'] = record.ip
        if hasattr(record, 'slice_id'):
            log_data['slice_id'] = record.slice_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'role'):
            log_data['role'] = record.role
        if hasattr(record, 'duration'):
            log_data['duration_seconds'] = record.duration

        return json.dumps(log_data)

# Crear logger
logger = logging.getLogger("telecloud")
logger.setLevel(logging.INFO)

# Asegurar que el directorio de logs existe
log_dir = '/var/log/telecloud'
os.makedirs(log_dir, exist_ok=True)

# Handler para archivo (JSON)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'app.log'),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setFormatter(JSONFormatter())
file_handler.setLevel(logging.INFO)

# Handler para consola (texto legible)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
console_handler.setLevel(logging.INFO)

# Agregar handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("TELECLOUD FastAPI application starting", extra={'action': 'app_start'})

# ==========================================
# INICIALIZACIÓN FASTAPI
# ==========================================

app = FastAPI(title="Cloud Topology Manager API", version="2.0")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==========================================
# MIDDLEWARE PARA LOGGING DE REQUESTS
# ==========================================

import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware que registra todas las peticiones HTTP"""
    start_time = time.time()

    # Obtener información del cliente
    client_ip = request.client.host if request.client else "unknown"

    # Log de inicio de request
    logger.info(
        f"HTTP Request: {request.method} {request.url.path}",
        extra={
            'action': 'http_request',
            'ip': client_ip,
            'method': request.method,
            'path': request.url.path
        }
    )

    # Procesar la request
    response = await call_next(request)

    # Calcular duración
    duration = time.time() - start_time

    # Log de respuesta
    logger.info(
        f"HTTP Response: {response.status_code} - {request.method} {request.url.path}",
        extra={
            'action': 'http_response',
            'ip': client_ip,
            'method': request.method,
            'path': request.url.path,
            'status_code': response.status_code,
            'duration': round(duration, 3)
        }
    )

    return response

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
async def register(user_data: UserCreate, request: Request):
    """Registro de nuevo usuario"""
    client_ip = request.client.host if request.client else "unknown"

    # Log intento de registro
    logger.info(
        f"Registration attempt: {user_data.username}",
        extra={
            'action': 'auth_register_attempt',
            'user': user_data.username,
            'email': user_data.email,
            'role': user_data.role,
            'ip': client_ip
        }
    )

    user, error = create_user(user_data)
    if error:
        # Log registro fallido
        logger.warning(
            f"Registration failed: {user_data.username} - {error}",
            extra={
                'action': 'auth_register_failed',
                'user': user_data.username,
                'email': user_data.email,
                'error': error,
                'ip': client_ip
            }
        )
        raise HTTPException(status_code=400, detail=error)

    # Log registro exitoso
    logger.info(
        f"Registration successful: {user['username']} (ID: {str(user['_id'])})",
        extra={
            'action': 'auth_register_success',
            'user': user['username'],
            'user_id': str(user['_id']),
            'role': user['role'],
            'ip': client_ip
        }
    )

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
async def login(user_credentials: UserLogin, request: Request):
    """Login con JWT"""
    client_ip = request.client.host if request.client else "unknown"

    # Log intento de login
    logger.info(
        f"Login attempt: {user_credentials.username}",
        extra={
            'action': 'auth_login_attempt',
            'user': user_credentials.username,
            'ip': client_ip
        }
    )

    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        # Log login fallido
        logger.warning(
            f"Login failed: {user_credentials.username} - Invalid credentials",
            extra={
                'action': 'auth_login_failed',
                'user': user_credentials.username,
                'ip': client_ip,
                'reason': 'invalid_credentials'
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user['_id'])}, expires_delta=access_token_expires
    )

    # Log login exitoso
    logger.info(
        f"Login successful: {user['username']} (ID: {str(user['_id'])})",
        extra={
            'action': 'auth_login_success',
            'user': user['username'],
            'user_id': str(user['_id']),
            'role': user['role'],
            'ip': client_ip
        }
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

        # Generar filename con timestamp único
        filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        templates_dir = '/home/ubuntu/PROYECTO_CLOUD_G4/templates'
        filepath = os.path.join(templates_dir, filename)

        # 1. GUARDAR ARCHIVO FÍSICO .JSON EN SERVIDOR PRIMERO
        template_data = {
            'metadata': {
                'name': name,
                'created_at': datetime.now().isoformat(),
                'availability_zone': az
            },
            'topology': topology_json
        }

        # Crear directorio si no existe
        os.makedirs(templates_dir, exist_ok=True)

        # Guardar archivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)

        # 2. GUARDAR EN MONGODB (con json_filename)
        if template_id:
            db.templates.update_one(
                {'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])},
                {'$set': {
                    'name': name,
                    'topology_json': topology_json,
                    'availability_zone': az,
                    'json_filename': filename,
                    'updated_at': datetime.now()
                }}
            )
            message = "Plantilla actualizada"

            # Log actualización de template
            logger.info(
                f"Template updated: {name} by {current_user['username']}",
                extra={
                    'action': 'template_update',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'template_id': template_id,
                    'template_name': name,
                    'az': az,
                    'node_count': len(topology_json['nodes'])
                }
            )
        else:
            result = db.templates.insert_one({
                'user_id': str(current_user['_id']),
                'name': name,
                'topology_json': topology_json,
                'availability_zone': az,
                'json_filename': filename,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            template_id = str(result.inserted_id)
            message = "Plantilla guardada"

            # Log creación de template
            logger.info(
                f"Template created: {name} by {current_user['username']}",
                extra={
                    'action': 'template_create',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'template_id': template_id,
                    'template_name': name,
                    'az': az,
                    'node_count': len(topology_json['nodes']),
                    'json_filename': filename
                }
            )

        return {
            'success': True,
            'message': message,
            'template_id': template_id,
            'filename': filename,
            'filepath': filepath
        }
    except Exception as e:
        # Log error al guardar template
        logger.error(
            f"Template save error: {str(e)}",
            extra={
                'action': 'template_save_error',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'error': str(e)
            }
        )
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
    import os
    import re
    try:
        name = data.get('name', 'topology')
        az = data.get('az', '')
        topology_json = {'nodes': topology.nodes, 'edges': topology.edges}

        # Limpiar nombre y generar nuevo archivo JSON
        if not name or name.strip() == "":
            name = 'topology'
        clean_name = re.sub(r'[^\w\-_.]', '_', name)
        filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        templates_dir = '/home/ubuntu/PROYECTO_CLOUD_G4/templates'
        filepath = os.path.join(templates_dir, filename)

        # Guardar archivo JSON físico
        template_data = {
            'metadata': {
                'name': name,
                'created_at': datetime.now().isoformat(),
                'availability_zone': az
            },
            'topology': topology_json
        }

        os.makedirs(templates_dir, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)

        # Actualizar MongoDB con el nuevo json_filename
        db = get_db()
        result = db.templates.update_one(
            {'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])},
            {'$set': {
                'name': name,
                'topology_json': topology_json,
                'availability_zone': az,
                'json_filename': filename,
                'updated_at': datetime.now()
            }}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        return {'success': True, 'message': 'Plantilla actualizada', 'filename': filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar plantilla"""
    try:
        db = get_db()

        # Obtener info del template antes de eliminar
        template = db.templates.find_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})

        result = db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})

        if result.deleted_count > 0:
            # Log eliminación exitosa
            logger.info(
                f"Template deleted: {template.get('name', 'unknown')} by {current_user['username']}",
                extra={
                    'action': 'template_delete',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'template_id': template_id,
                    'template_name': template.get('name', 'unknown') if template else 'unknown'
                }
            )

        return {'success': True}
    except Exception as e:
        # Log error al eliminar
        logger.error(
            f"Template delete error: {str(e)}",
            extra={
                'action': 'template_delete_error',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'template_id': template_id,
                'error': str(e)
            }
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates/{template_id}/deploy")
async def deploy_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Desplegar plantilla como slice ejecutando deploy_topology.py"""
    import subprocess
    import os
    deploy_start_time = time.time()

    try:
        db = get_db()
        active_slices = db.slices.count_documents({'user_id': str(current_user['_id']), 'status': 'active'})
        max_slices = get_max_slices(current_user)

        if active_slices >= max_slices:
            logger.warning(
                f"Deployment blocked: slice limit reached for {current_user['username']}",
                extra={
                    'action': 'deployment_blocked',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'reason': 'slice_limit_reached',
                    'current_slices': active_slices,
                    'max_slices': max_slices
                }
            )
            raise HTTPException(status_code=400, detail=f'Límite de {max_slices} slices alcanzado')

        template = db.templates.find_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})
        if not template:
            logger.warning(
                f"Deployment failed: template not found {template_id}",
                extra={
                    'action': 'deployment_template_not_found',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'template_id': template_id
                }
            )
            raise HTTPException(status_code=404, detail='Plantilla no encontrada')

        # Obtener json_filename del template
        json_filename = template.get('json_filename')
        if not json_filename:
            raise HTTPException(status_code=400, detail='Template no tiene archivo JSON asociado')

        slice_id = f"{template['name']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        vm_count = len(template['topology_json'].get('nodes', []))

        # Log inicio de despliegue
        logger.info(
            f"Deployment started: {slice_id} by {current_user['username']}",
            extra={
                'action': 'deployment_start',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'slice_id': slice_id,
                'template_id': template_id,
                'template_name': template['name'],
                'az': template.get('availability_zone', 'auto'),
                'vm_count': vm_count
            }
        )

        # Verificar que el archivo JSON existe
        json_filepath = os.path.join('/home/ubuntu/PROYECTO_CLOUD_G4/templates', json_filename)
        if not os.path.exists(json_filepath):
            raise HTTPException(status_code=404, detail=f'Archivo JSON no encontrado: {json_filename}')

        # EJECUTAR SCRIPT DE DESPLIEGUE (ruta absoluta en Head Node)
        deploy_script = '/home/ubuntu/deploy_topology.py'
        deployment_status = 'deploying'
        deployment_output = ''
        deployment_error = ''

        try:
            # Ejecutar el script de despliegue con PATH completo para SSH
            # IMPORTANTE: Pasar --slice-id para que coincida con MongoDB
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

            result = subprocess.run(
                ['python3', deploy_script, '--json', json_filepath, '--slice-id', slice_id],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos de timeout
                env=env  # Agregar PATH completo
            )

            deployment_output = result.stdout
            deployment_error = result.stderr

            if result.returncode == 0:
                deployment_status = 'active'
            else:
                deployment_status = 'failed'

        except subprocess.TimeoutExpired:
            deployment_status = 'failed'
            deployment_error = 'Timeout: El despliegue tardó más de 5 minutos'
        except Exception as deploy_error:
            deployment_status = 'failed'
            deployment_error = str(deploy_error)

        # Crear registro de slice con información del despliegue
        slice_doc = {
            'template_id': str(template['_id']),
            'user_id': str(current_user['_id']),
            'slice_id': slice_id,
            'name': template['name'],
            'topology_json': template['topology_json'],
            'availability_zone': template.get('availability_zone'),
            'json_filename': json_filename,
            'deployed_at': datetime.now(),
            'status': deployment_status,
            'vm_count': vm_count,
            'deployment_output': deployment_output,
            'deployment_error': deployment_error
        }

        db.slices.insert_one(slice_doc)

        # Eliminar la plantilla (ahora es un slice)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': str(current_user['_id'])})

        # Calcular duración del despliegue
        deploy_duration = time.time() - deploy_start_time

        # Log resultado del despliegue
        if deployment_status == 'active':
            logger.info(
                f"Deployment successful: {slice_id} by {current_user['username']}",
                extra={
                    'action': 'deployment_success',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'slice_id': slice_id,
                    'vm_count': vm_count,
                    'az': template.get('availability_zone', 'auto'),
                    'duration': round(deploy_duration, 2)
                }
            )
        else:
            logger.error(
                f"Deployment failed: {slice_id} by {current_user['username']}",
                extra={
                    'action': 'deployment_failed',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'slice_id': slice_id,
                    'vm_count': vm_count,
                    'error': deployment_error,
                    'duration': round(deploy_duration, 2)
                }
            )

        return {
            'success': deployment_status != 'failed',
            'slice_id': slice_id,
            'status': deployment_status,
            'message': 'Despliegue completado' if deployment_status == 'active' else 'Despliegue falló',
            'output': deployment_output if deployment_output else None,
            'error': deployment_error if deployment_error else None
        }
    except HTTPException:
        raise
    except Exception as e:
        # Log error general del despliegue
        logger.error(
            f"Deployment exception: {str(e)}",
            extra={
                'action': 'deployment_exception',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'template_id': template_id,
                'error': str(e)
            }
        )
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

@app.get("/api/slices/{slice_id}/vnc-info")
async def get_slice_vnc_info(slice_id: str, current_user: dict = Depends(get_current_active_user)):
    """Obtener información VNC de las VMs de un slice ejecutando mapeo_vms.sh"""
    import subprocess
    try:
        # Verificar que el slice pertenece al usuario (seguridad)
        # El parámetro slice_id puede ser el _id de MongoDB o el slice_id real
        db = get_db()

        # Intentar buscar por _id primero (viene del viewer/dashboard)
        try:
            slice_doc = db.slices.find_one({'_id': ObjectId(slice_id), 'user_id': str(current_user['_id'])})
        except:
            # Si falla (no es ObjectId válido), buscar por slice_id
            slice_doc = db.slices.find_one({'slice_id': slice_id, 'user_id': str(current_user['_id'])})

        if not slice_doc:
            raise HTTPException(status_code=404, detail='Slice no encontrado')

        # Extraer el slice_id real del documento (el que usa mapeo_vms.sh)
        real_slice_id = slice_doc.get('slice_id')
        if not real_slice_id:
            raise HTTPException(status_code=500, detail='Slice sin slice_id válido')

        # Ejecutar mapeo_vms.sh con output JSON usando el slice_id REAL
        mapeo_script = '/home/ubuntu/mapeo_vms.sh'

        # Agregar PATH completo para que encuentre SSH
        import os
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

        result = subprocess.run(
            ['python3', mapeo_script, '--json', '--slice-id', real_slice_id],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f'Error ejecutando mapeo_vms.sh: {result.stderr}')

        # Parse JSON output
        vnc_data = json.loads(result.stdout)

        return {
            'success': True,
            'slice_id': vnc_data['slice_id'],
            'vms': vnc_data['results']
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail='Timeout al obtener info VNC')
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f'Error parseando JSON de mapeo_vms.sh: {str(e)}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/slices/{slice_id}")
async def delete_slice(slice_id: str, current_user: dict = Depends(get_current_active_user)):
    """Eliminar slice ejecutando eliminar_slice.sh (destruye VMs y libera recursos)"""
    import subprocess
    import os
    delete_start_time = time.time()

    try:
        db = get_db()

        # Verificar que el slice existe y pertenece al usuario
        slice_doc = db.slices.find_one({'slice_id': slice_id, 'user_id': str(current_user['_id'])})
        if not slice_doc:
            logger.warning(
                f"Slice deletion failed: slice not found {slice_id}",
                extra={
                    'action': 'slice_delete_not_found',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'slice_id': slice_id
                }
            )
            raise HTTPException(status_code=404, detail='Slice no encontrado')

        # Log inicio de eliminación
        logger.info(
            f"Slice deletion started: {slice_id} by {current_user['username']}",
            extra={
                'action': 'slice_delete_start',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'slice_id': slice_id,
                'vm_count': slice_doc.get('vm_count', 0)
            }
        )

        # EJECUTAR SCRIPT DE ELIMINACIÓN (ruta absoluta en Head Node)
        delete_script = '/home/ubuntu/eliminar_slice.sh'
        deletion_output = ''
        deletion_error = ''
        deletion_success = False

        try:
            # Ejecutar el script con PATH completo para SSH
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

            result = subprocess.run(
                ['bash', delete_script, slice_id],
                capture_output=True,
                text=True,
                timeout=180,  # 3 minutos de timeout
                env=env
            )

            deletion_output = result.stdout
            deletion_error = result.stderr

            if result.returncode == 0:
                deletion_success = True
            else:
                deletion_success = False

        except subprocess.TimeoutExpired:
            deletion_error = 'Timeout: La eliminación tardó más de 3 minutos'
            deletion_success = False
        except Exception as delete_error:
            deletion_error = str(delete_error)
            deletion_success = False

        # Si el script falló, registrar el error pero NO eliminar de MongoDB
        if not deletion_success:
            # Construir mensaje de error detallado
            error_detail = f"Error al eliminar slice:\n\n"
            error_detail += f"=== STDOUT ===\n{deletion_output}\n\n"
            error_detail += f"=== STDERR ===\n{deletion_error}\n\n"
            error_detail += f"=== Return Code ===\n{result.returncode}"

            # Log fallo de eliminación
            logger.error(
                f"Slice deletion failed: {slice_id} by {current_user['username']}",
                extra={
                    'action': 'slice_delete_failed',
                    'user': current_user['username'],
                    'user_id': str(current_user['_id']),
                    'slice_id': slice_id,
                    'error': deletion_error,
                    'return_code': result.returncode
                }
            )

            # Actualizar el slice con información del error
            db.slices.update_one(
                {'slice_id': slice_id, 'user_id': str(current_user['_id'])},
                {'$set': {
                    'deletion_attempted_at': datetime.now(),
                    'deletion_error': deletion_error,
                    'deletion_output': deletion_output,
                    'status': 'deletion_failed'
                }}
            )
            raise HTTPException(
                status_code=500,
                detail=error_detail
            )

        # Si exitoso, eliminar de MongoDB
        db.slices.delete_one({'slice_id': slice_id, 'user_id': str(current_user['_id'])})

        # Calcular duración
        delete_duration = time.time() - delete_start_time

        # Log éxito de eliminación
        logger.info(
            f"Slice deletion successful: {slice_id} by {current_user['username']}",
            extra={
                'action': 'slice_delete_success',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'slice_id': slice_id,
                'duration': round(delete_duration, 2)
            }
        )

        return {
            'success': True,
            'message': 'Slice eliminado correctamente (VMs destruidas y recursos liberados)',
            'output': deletion_output if deletion_output else None
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log excepción general
        logger.error(
            f"Slice deletion exception: {str(e)}",
            extra={
                'action': 'slice_delete_exception',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'slice_id': slice_id,
                'error': str(e)
            }
        )
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
    """Eliminar cualquier slice ejecutando eliminar_slice.sh (solo admin)"""
    import subprocess
    import os
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        db = get_db()

        # Verificar que el slice existe (sin restricción de usuario)
        slice_doc = db.slices.find_one({'slice_id': slice_id})
        if not slice_doc:
            raise HTTPException(status_code=404, detail='Slice no encontrado')

        # EJECUTAR SCRIPT DE ELIMINACIÓN (ruta absoluta en Head Node)
        delete_script = '/home/ubuntu/eliminar_slice.sh'
        deletion_output = ''
        deletion_error = ''
        deletion_success = False

        try:
            # Ejecutar el script con PATH completo para SSH
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

            result = subprocess.run(
                ['bash', delete_script, slice_id],
                capture_output=True,
                text=True,
                timeout=180,  # 3 minutos de timeout
                env=env
            )

            deletion_output = result.stdout
            deletion_error = result.stderr

            if result.returncode == 0:
                deletion_success = True
            else:
                deletion_success = False

        except subprocess.TimeoutExpired:
            deletion_error = 'Timeout: La eliminación tardó más de 3 minutos'
            deletion_success = False
        except Exception as delete_error:
            deletion_error = str(delete_error)
            deletion_success = False

        # Si el script falló, registrar el error pero NO eliminar de MongoDB
        if not deletion_success:
            # Construir mensaje de error detallado
            error_detail = f"Error al eliminar slice (Admin):\n\n"
            error_detail += f"=== STDOUT ===\n{deletion_output}\n\n"
            error_detail += f"=== STDERR ===\n{deletion_error}\n\n"
            error_detail += f"=== Return Code ===\n{result.returncode}"

            # Actualizar el slice con información del error
            db.slices.update_one(
                {'slice_id': slice_id},
                {'$set': {
                    'deletion_attempted_at': datetime.now(),
                    'deletion_error': deletion_error,
                    'deletion_output': deletion_output,
                    'status': 'deletion_failed'
                }}
            )
            raise HTTPException(
                status_code=500,
                detail=error_detail
            )

        # Si exitoso, eliminar de MongoDB
        db.slices.delete_one({'slice_id': slice_id})

        return {
            'success': True,
            'message': 'Slice eliminado por administrador (VMs destruidas y recursos liberados)',
            'output': deletion_output if deletion_output else None
        }

    except HTTPException:
        raise
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
