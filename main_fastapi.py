"""
Aplicación principal con FastAPI + JWT para autenticación
Sirve templates con Flask montado en FastAPI
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, WebSocket, WebSocketDisconnect
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
import asyncio

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

# ==========================================
# FUNCIÓN ASYNC PARA DESPLIEGUE EN BACKGROUND
# ==========================================

async def run_deployment_in_background(slice_id: str, json_filepath: str, template_name: str,
                                       template_id: str, user_id: str, username: str,
                                       vm_count: int, az: str, topology_json: dict,
                                       json_filename: str):
    """
    Ejecuta el despliegue en background y escribe eventos de progreso.
    """
    import subprocess
    db = get_db()

    try:
        # Evento 1: Inicio del despliegue
        write_progress(slice_id, 'deployment_start', f'Iniciando despliegue de {vm_count} VMs...', {
            'slice_id': slice_id,
            'vm_count': vm_count,
            'az': az or 'auto'
        })

        await asyncio.sleep(0.5)

        # Evento 2: Validando configuración
        write_progress(slice_id, 'validation', 'Validando configuración y recursos...', {})

        await asyncio.sleep(0.5)

        # Evento 3: Iniciando script de despliegue
        write_progress(slice_id, 'script_start', 'Ejecutando script de despliegue...', {})

        # EJECUTAR SCRIPT DE DESPLIEGUE
        deploy_script = '/home/ubuntu/deploy_topology.py'
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

        # Crear proceso
        process = await asyncio.create_subprocess_exec(
            'python3', deploy_script, '--json', json_filepath, '--slice-id', slice_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        # Reportar progreso mientras corre (simulado basado en VM count)
        # Por cada VM, reportar progreso
        for i in range(1, vm_count + 1):
            await asyncio.sleep(3)  # Esperar ~3 segundos por VM
            write_progress(slice_id, 'vm_deploying', f'Desplegando VM {i}/{vm_count}...', {
                'vm_number': i,
                'vm_total': vm_count,
                'progress': int((i / vm_count) * 100)
            })

        # Esperar a que termine el proceso
        stdout, stderr = await process.communicate()
        deployment_output = stdout.decode()
        deployment_error = stderr.decode()
        returncode = process.returncode

        # Determinar estado
        if returncode == 0:
            deployment_status = 'active'

            # Evento final: Éxito
            write_progress(slice_id, 'deployment_complete', f'Despliegue completado exitosamente ({vm_count} VMs activas)', {
                'slice_id': slice_id,
                'status': 'active',
                'vm_count': vm_count
            })

            logger.info(
                f"Deployment successful: {slice_id} by {username}",
                extra={
                    'action': 'deployment_success',
                    'user': username,
                    'user_id': user_id,
                    'slice_id': slice_id,
                    'vm_count': vm_count,
                    'az': az or 'auto'
                }
            )
        else:
            deployment_status = 'failed'

            # Evento final: Error
            write_progress(slice_id, 'deployment_error', f'Error en el despliegue: {deployment_error[:200]}', {
                'error': deployment_error,
                'output': deployment_output
            })

            logger.error(
                f"Deployment failed: {slice_id} by {username}",
                extra={
                    'action': 'deployment_failed',
                    'user': username,
                    'user_id': user_id,
                    'slice_id': slice_id,
                    'vm_count': vm_count,
                    'error': deployment_error
                }
            )

        # Crear registro de slice con información del despliegue
        slice_doc = {
            'template_id': template_id,
            'user_id': user_id,
            'slice_id': slice_id,
            'name': template_name,
            'topology_json': topology_json,
            'availability_zone': az,
            'json_filename': json_filename,
            'deployed_at': datetime.now(),
            'status': deployment_status,
            'vm_count': vm_count,
            'deployment_output': deployment_output,
            'deployment_error': deployment_error
        }

        db.slices.insert_one(slice_doc)

        # Eliminar la plantilla (ahora es un slice)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': user_id})

    except asyncio.TimeoutError:
        # Timeout
        write_progress(slice_id, 'deployment_error', 'Error: Timeout - El despliegue tardó más de 5 minutos', {
            'error': 'timeout'
        })

        # Guardar slice como failed
        slice_doc = {
            'template_id': template_id,
            'user_id': user_id,
            'slice_id': slice_id,
            'name': template_name,
            'topology_json': topology_json,
            'availability_zone': az,
            'json_filename': json_filename,
            'deployed_at': datetime.now(),
            'status': 'failed',
            'vm_count': vm_count,
            'deployment_error': 'Timeout: El despliegue tardó más de 5 minutos'
        }
        db.slices.insert_one(slice_doc)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': user_id})

    except Exception as e:
        # Error general
        write_progress(slice_id, 'deployment_error', f'Error: {str(e)}', {
            'error': str(e)
        })

        logger.error(
            f"Deployment exception: {str(e)}",
            extra={
                'action': 'deployment_exception',
                'user': username,
                'user_id': user_id,
                'template_id': template_id,
                'error': str(e)
            }
        )

        # Guardar slice como failed
        slice_doc = {
            'template_id': template_id,
            'user_id': user_id,
            'slice_id': slice_id,
            'name': template_name,
            'topology_json': topology_json,
            'availability_zone': az,
            'json_filename': json_filename,
            'deployed_at': datetime.now(),
            'status': 'failed',
            'vm_count': vm_count,
            'deployment_error': str(e)
        }
        db.slices.insert_one(slice_doc)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': user_id})

@app.post("/api/templates/{template_id}/deploy")
async def deploy_template(template_id: str, current_user: dict = Depends(get_current_active_user)):
    """Desplegar plantilla como slice ejecutando deploy_topology.py EN BACKGROUND con progreso en tiempo real"""
    import os

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

        # Limpiar archivo de progreso previo si existe
        progress_file = get_progress_file(slice_id)
        if os.path.exists(progress_file):
            os.remove(progress_file)

        # EJECUTAR DESPLIEGUE EN BACKGROUND
        asyncio.create_task(run_deployment_in_background(
            slice_id=slice_id,
            json_filepath=json_filepath,
            template_name=template['name'],
            template_id=str(template['_id']),
            user_id=str(current_user['_id']),
            username=current_user['username'],
            vm_count=vm_count,
            az=template.get('availability_zone'),
            topology_json=template['topology_json'],
            json_filename=json_filename
        ))

        # Retornar inmediatamente con el slice_id para que el frontend se conecte al WebSocket
        return {
            'success': True,
            'slice_id': slice_id,
            'status': 'deploying',
            'message': 'Despliegue iniciado en background',
            'vm_count': vm_count,
            'websocket_url': f'/ws/deploy/{slice_id}'
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
# FUNCIÓN DE SINCRONIZACIÓN GLOBAL
# ==========================================

def sync_mongodb_with_vlans():
    """
    Sincroniza TODOS los slices de MongoDB con vlans.json (GLOBAL).
    Elimina de MongoDB los slices que fueron purgados manualmente.
    Retorna cantidad de slices eliminados.
    """
    import os
    db = get_db()
    vlans_file = '/home/ubuntu/.orchestrator/vlans.json'
    active_slice_ids = set()

    # 1. Leer vlans.json para obtener slices que existen físicamente
    try:
        if os.path.exists(vlans_file):
            with open(vlans_file, 'r', encoding='utf-8') as f:
                vlans_data = json.load(f)
                active_slice_ids = set(vlans_data.get('slices', {}).keys())
    except Exception as e:
        logger.warning(f"Error reading vlans.json for global sync: {e}")
        return 0  # Si falla, no sincronizar

    # 2. Obtener TODOS los slices de MongoDB (de todos los usuarios)
    all_slices = list(db.slices.find())

    # 3. Eliminar slices fantasma (que están en MongoDB pero NO en vlans.json)
    removed_count = 0
    for slice_doc in all_slices:
        slice_id = slice_doc.get('slice_id')
        if slice_id and slice_id not in active_slice_ids:
            # Slice purgado manualmente - eliminarlo
            db.slices.delete_one({'_id': slice_doc['_id']})
            removed_count += 1

            logger.info(
                f"Global sync: Removed orphan slice {slice_id} (user: {slice_doc.get('user_id', 'unknown')})",
                extra={
                    'action': 'global_slice_sync_cleanup',
                    'slice_id': slice_id,
                    'user_id': slice_doc.get('user_id')
                }
            )

    # Log resumen si hubo limpieza
    if removed_count > 0:
        logger.info(
            f"Global sync completed: removed {removed_count} orphan slices from all users",
            extra={
                'action': 'global_slice_sync_summary',
                'removed_count': removed_count
            }
        )

    return removed_count

# ==========================================
# ENDPOINTS DE SLICES
# ==========================================

@app.get("/api/slices")
async def get_slices(current_user: dict = Depends(get_current_active_user)):
    """Obtener slices del usuario con sincronización GLOBAL automática"""
    # Sincronizar TODOS los slices de TODOS los usuarios
    sync_mongodb_with_vlans()

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
    """Eliminar slice EN BACKGROUND con progreso en tiempo real vía WebSocket"""
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

        slice_name = slice_doc.get('name', slice_id)
        vm_count = slice_doc.get('vm_count', 0)

        # Log inicio de eliminación
        logger.info(
            f"Slice deletion started: {slice_id} by {current_user['username']}",
            extra={
                'action': 'slice_delete_start',
                'user': current_user['username'],
                'user_id': str(current_user['_id']),
                'slice_id': slice_id,
                'vm_count': vm_count
            }
        )

        # Limpiar archivo de progreso previo si existe
        progress_file = get_deletion_progress_file(slice_id)
        if os.path.exists(progress_file):
            os.remove(progress_file)

        # EJECUTAR ELIMINACIÓN EN BACKGROUND
        asyncio.create_task(run_deletion_in_background(
            slice_id=slice_id,
            slice_name=slice_name,
            user_id=str(current_user['_id']),
            username=current_user['username'],
            vm_count=vm_count
        ))

        # Retornar inmediatamente con el slice_id para que el frontend se conecte al WebSocket
        return {
            'success': True,
            'slice_id': slice_id,
            'status': 'deleting',
            'message': 'Eliminación iniciada en background',
            'websocket_url': f'/ws/delete/{slice_id}'
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
# WEBSOCKET PARA PROGRESO DE DESPLIEGUE
# ==========================================

def get_progress_file(slice_id: str) -> str:
    """Retorna ruta del archivo de progreso temporal"""
    return f"/tmp/deploy_progress_{slice_id}.json"

def write_progress(slice_id: str, event_type: str, message: str, data: dict = None):
    """Escribe un evento de progreso al archivo JSON"""
    progress_file = get_progress_file(slice_id)
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "message": message,
        "data": data or {}
    }

    # Leer eventos existentes
    events = []
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except:
            events = []

    # Agregar nuevo evento
    events.append(event)

    # Escribir de vuelta
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2)

@app.websocket("/ws/deploy/{slice_id}")
async def websocket_deploy_progress(websocket: WebSocket, slice_id: str):
    """
    WebSocket que transmite el progreso del despliegue en tiempo real.
    Lee el archivo de progreso y envía eventos al cliente.
    """
    await websocket.accept()

    progress_file = get_progress_file(slice_id)
    last_sent_count = 0

    try:
        while True:
            # Verificar si hay nuevos eventos
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        events = json.load(f)

                    # Enviar solo eventos nuevos
                    new_events = events[last_sent_count:]
                    for event in new_events:
                        await websocket.send_json(event)
                        last_sent_count += 1

                    # Si hay un evento de completado o error, cerrar conexión
                    if new_events:
                        last_event = new_events[-1]
                        if last_event['type'] in ('deployment_complete', 'deployment_error'):
                            # Esperar 2 segundos para que el frontend procese
                            await asyncio.sleep(2)
                            # Limpiar archivo de progreso
                            try:
                                os.remove(progress_file)
                            except:
                                pass
                            break

                except Exception as e:
                    logger.error(f"Error reading progress file: {e}")

            # Esperar 500ms antes de revisar nuevamente
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for slice {slice_id}")
    except Exception as e:
        logger.error(f"WebSocket error for slice {slice_id}: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

# ==========================================
# WEBSOCKET PARA PROGRESO DE ELIMINACIÓN
# ==========================================

def get_deletion_progress_file(slice_id: str) -> str:
    """Retorna ruta del archivo de progreso de eliminación temporal"""
    return f"/tmp/deletion_progress_{slice_id}.json"

def write_deletion_progress(slice_id: str, event_type: str, message: str, data: dict = None):
    """Escribe un evento de progreso de eliminación al archivo JSON"""
    progress_file = get_deletion_progress_file(slice_id)
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "message": message,
        "data": data or {}
    }

    # Leer eventos existentes
    events = []
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except:
            events = []

    # Agregar nuevo evento
    events.append(event)

    # Escribir de vuelta
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2)

async def run_deletion_in_background(slice_id: str, slice_name: str, user_id: str, username: str, vm_count: int):
    """
    Ejecuta la eliminación en background y escribe eventos de progreso REAL.
    Pasos:
      1. destroy_slice_from_mapeo.sh - Destruye VMs/TAPs/OVS
      2. deploy_topology.py --release-slice - Libera VLANs y puertos
    """
    import subprocess
    db = get_db()

    try:
        # Evento 1: Inicio
        write_deletion_progress(slice_id, 'deletion_start', f'Iniciando eliminación de slice "{slice_name}"...', {
            'slice_id': slice_id,
            'vm_count': vm_count
        })

        await asyncio.sleep(0.5)

        # Evento 2: Destruyendo VMs en workers
        write_deletion_progress(slice_id, 'destroying_vms', 'Destruyendo VMs y liberando recursos en workers...', {})

        # PASO 1: Ejecutar destroy_slice_from_mapeo.sh
        destroy_script = '/home/ubuntu/destroy_slice_from_mapeo.sh'
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

        process1 = await asyncio.create_subprocess_exec(
            'bash', destroy_script, slice_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        stdout1, stderr1 = await process1.communicate()
        destroy_output = stdout1.decode()
        destroy_error = stderr1.decode()
        destroy_returncode = process1.returncode

        if destroy_returncode != 0:
            # Error en destroy
            write_deletion_progress(slice_id, 'deletion_error', f'Error al destruir VMs: {destroy_error[:200]}', {
                'error': destroy_error,
                'output': destroy_output
            })

            logger.error(
                f"Deletion failed (destroy): {slice_id} by {username}",
                extra={
                    'action': 'deletion_failed_destroy',
                    'user': username,
                    'user_id': user_id,
                    'slice_id': slice_id,
                    'error': destroy_error
                }
            )

            # Actualizar slice con error
            db.slices.update_one(
                {'slice_id': slice_id, 'user_id': user_id},
                {'$set': {
                    'deletion_attempted_at': datetime.now(),
                    'deletion_error': destroy_error,
                    'deletion_output': destroy_output,
                    'status': 'deletion_failed'
                }}
            )
            return

        await asyncio.sleep(0.5)

        # Evento 3: Liberando recursos
        write_deletion_progress(slice_id, 'releasing_resources', 'Liberando VLANs y puertos públicos...', {})

        # PASO 2: Ejecutar deploy_topology.py --release-slice
        release_script = '/home/ubuntu/deploy_topology.py'

        process2 = await asyncio.create_subprocess_exec(
            'python3', release_script, '--release-slice', slice_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        stdout2, stderr2 = await process2.communicate()
        release_output = stdout2.decode()
        release_error = stderr2.decode()
        release_returncode = process2.returncode

        if release_returncode != 0:
            # Error en release
            write_deletion_progress(slice_id, 'deletion_error', f'Error al liberar recursos: {release_error[:200]}', {
                'error': release_error,
                'output': release_output
            })

            logger.error(
                f"Deletion failed (release): {slice_id} by {username}",
                extra={
                    'action': 'deletion_failed_release',
                    'user': username,
                    'user_id': user_id,
                    'slice_id': slice_id,
                    'error': release_error
                }
            )

            # Actualizar slice con error
            db.slices.update_one(
                {'slice_id': slice_id, 'user_id': user_id},
                {'$set': {
                    'deletion_attempted_at': datetime.now(),
                    'deletion_error': release_error,
                    'deletion_output': release_output,
                    'status': 'deletion_failed'
                }}
            )
            return

        # Evento final: Éxito
        write_deletion_progress(slice_id, 'deletion_complete', f'Slice "{slice_name}" eliminado exitosamente', {
            'slice_id': slice_id
        })

        logger.info(
            f"Deletion successful: {slice_id} by {username}",
            extra={
                'action': 'deletion_success',
                'user': username,
                'user_id': user_id,
                'slice_id': slice_id,
                'vm_count': vm_count
            }
        )

        # Eliminar de MongoDB
        db.slices.delete_one({'slice_id': slice_id, 'user_id': user_id})

    except asyncio.TimeoutError:
        write_deletion_progress(slice_id, 'deletion_error', 'Error: Timeout - La eliminación tardó más de lo esperado', {
            'error': 'timeout'
        })

        db.slices.update_one(
            {'slice_id': slice_id, 'user_id': user_id},
            {'$set': {
                'deletion_attempted_at': datetime.now(),
                'deletion_error': 'Timeout',
                'status': 'deletion_failed'
            }}
        )

    except Exception as e:
        write_deletion_progress(slice_id, 'deletion_error', f'Error: {str(e)}', {
            'error': str(e)
        })

        logger.error(
            f"Deletion exception: {str(e)}",
            extra={
                'action': 'deletion_exception',
                'user': username,
                'user_id': user_id,
                'slice_id': slice_id,
                'error': str(e)
            }
        )

        db.slices.update_one(
            {'slice_id': slice_id, 'user_id': user_id},
            {'$set': {
                'deletion_attempted_at': datetime.now(),
                'deletion_error': str(e),
                'status': 'deletion_failed'
            }}
        )

@app.websocket("/ws/delete/{slice_id}")
async def websocket_deletion_progress(websocket: WebSocket, slice_id: str):
    """
    WebSocket que transmite el progreso de la eliminación en tiempo real.
    Lee el archivo de progreso y envía eventos al cliente.
    """
    await websocket.accept()

    progress_file = get_deletion_progress_file(slice_id)
    last_sent_count = 0

    try:
        while True:
            # Verificar si hay nuevos eventos
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        events = json.load(f)

                    # Enviar solo eventos nuevos
                    new_events = events[last_sent_count:]
                    for event in new_events:
                        await websocket.send_json(event)
                        last_sent_count += 1

                    # Si hay un evento de completado o error, cerrar conexión
                    if new_events:
                        last_event = new_events[-1]
                        if last_event['type'] in ('deletion_complete', 'deletion_error'):
                            # Esperar 2 segundos para que el frontend procese
                            await asyncio.sleep(2)
                            # Limpiar archivo de progreso
                            try:
                                os.remove(progress_file)
                            except:
                                pass
                            break

                except Exception as e:
                    logger.error(f"Error reading deletion progress file: {e}")

            # Esperar 500ms antes de revisar nuevamente
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for deletion {slice_id}")
    except Exception as e:
        logger.error(f"WebSocket error for deletion {slice_id}: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

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
    """Obtener todos los slices de todos los usuarios (solo admin) con sincronización GLOBAL"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere rol de administrador")

    try:
        # Sincronizar TODOS los slices de TODOS los usuarios
        sync_mongodb_with_vlans()

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
