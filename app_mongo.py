from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
import math
import json
from datetime import datetime
import os
import subprocess
from bson import ObjectId

# Importar módulos MongoDB
from auth_mongo import User, login_manager
from database.mongo_config import get_db

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-mongodb-2025')

# Inicializar Flask-Login
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'

# =======================
# NetworkTopology Class
# =======================

class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.topology_count = 0
        self.placement_az = None

    def generate_topology(self, topology_type, config, flavor=None):
        """Genera una topología específica"""
        if flavor is None:
            flavor = {'vcpus': 2, 'ram': 2, 'disk': 20}

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
                {'id': next_id, 'x': base_x - 50, 'y': base_y, 'label': f'VM-{next_id}', 'flavor': flavor.copy(), 'az': self.placement_az},
                {'id': next_id + 1, 'x': base_x + 50, 'y': base_y, 'label': f'VM-{next_id + 1}', 'flavor': flavor.copy(), 'az': self.placement_az}
            ]
            new_edges = [{'from': next_id, 'to': next_id + 1}]

        elif topology_type == "star":
            radius = 80
            central_id = next_id
            new_nodes = [{'id': central_id, 'x': base_x, 'y': base_y, 'label': f'VM-{central_id}', 'flavor': flavor.copy(), 'az': self.placement_az}]
            node_count = config.get('node_count', 5)
            for i in range(node_count - 1):
                angle = (i * 2 * math.pi) / (node_count - 1)
                new_id = next_id + i + 1
                new_nodes.append({'id': new_id, 'x': base_x + radius * math.cos(angle), 'y': base_y + radius * math.sin(angle), 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
                new_edges.append({'from': central_id, 'to': new_id})

        elif topology_type == "ring":
            node_count = config.get('node_count', 5)
            radius = 70
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({'id': new_id, 'x': base_x + radius * math.cos(angle), 'y': base_y + radius * math.sin(angle), 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
                if i < node_count - 1:
                    new_edges.append({'from': new_id, 'to': new_id + 1})
                else:
                    new_edges.append({'from': new_id, 'to': next_id})

        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            root_id = next_id
            new_nodes.append({'id': root_id, 'x': base_x, 'y': base_y, 'label': f'VM-{root_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
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
                        new_nodes.append({'id': current_id, 'x': x, 'y': y, 'label': f'VM-{current_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
                        new_edges.append({'from': parent['id'], 'to': current_id})
                        next_level.append({'id': current_id, 'x': x, 'y': y})
                        current_id += 1
                current_level = next_level

        elif topology_type == "bus":
            node_count = config.get('node_count', 5)
            bus_spacing = 120 / max(1, node_count - 1)
            for i in range(node_count):
                new_id = next_id + i
                new_nodes.append({'id': new_id, 'x': base_x - 60 + bus_spacing * i, 'y': base_y, 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
                if i > 0:
                    new_edges.append({'from': new_id - 1, 'to': new_id})

        elif topology_type == "mesh":
            node_count = config.get('node_count', 5)
            mesh_radius = 60
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({'id': new_id, 'x': base_x + mesh_radius * math.cos(angle), 'y': base_y + mesh_radius * math.sin(angle), 'label': f'VM-{new_id}', 'flavor': flavor.copy(), 'az': self.placement_az})
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    new_edges.append({'from': next_id + i, 'to': next_id + j})

        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        if self.nodes:
            self.next_id = max(node['id'] for node in self.nodes) + 1

    def add_node(self, x, y, flavor=None):
        if flavor is None:
            flavor = {'vcpus': 2, 'ram': 2, 'disk': 20}
        new_node = {'id': self.next_id, 'x': x, 'y': y, 'label': f'VM-{self.next_id}', 'flavor': flavor.copy(), 'az': self.placement_az}
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

    def update_node_flavor(self, node_id, flavor):
        for node in self.nodes:
            if node['id'] == node_id:
                node['flavor'] = flavor.copy()
                break

    def set_placement_az(self, az):
        self.placement_az = az

    def get_state(self):
        return {'nodes': self.nodes, 'edges': self.edges}

    def load_from_template(self, template_data):
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
            az = template_data.get('availability_zone')
            if az:
                self.placement_az = az
            return True
        except Exception as e:
            print(f"Error loading template: {e}")
            return False

topology = NetworkTopology()

# =======================
# Rutas de Autenticación
# =======================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user, error = User.authenticate(username, password)
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            return render_template('login.html', error=error)
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            return render_template('register.html', error='Las contraseñas no coinciden')
        user, error = User.create(username, email, password)
        if user:
            return redirect(url_for('login', success='Cuenta creada exitosamente'))
        else:
            return render_template('register.html', error=error)
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# =======================
# Dashboard
# =======================

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    templates = list(db.templates.find({'user_id': current_user.id}).sort('created_at', -1))
    slices = list(db.slices.find({'user_id': current_user.id}).sort('deployed_at', -1))
    max_slices = current_user.get_max_slices()
    return render_template('dashboard.html', templates=templates, slices=slices, max_slices=max_slices)

@app.route('/editor')
@login_required
def editor():
    # LIMPIAR la topología global al entrar al editor
    topology.nodes = []
    topology.edges = []
    topology.next_id = 1
    topology.topology_count = 0
    topology.placement_az = None

    template_id = request.args.get('template_id')
    if template_id:
        db = get_db()
        template = db.templates.find_one({'_id': ObjectId(template_id), 'user_id': current_user.id})
        if template:
            return render_template('index.html',
                                 template_data=json.dumps(template['topology_json']),
                                 template_id=str(template['_id']),
                                 template_name=template['name'],
                                 template_az=template.get('availability_zone', ''),
                                 available_zones=current_user.get_available_zones())
    # Nueva plantilla vacía
    return render_template('index.html',
                         template_data=None,
                         template_id=None,
                         template_name=None,
                         template_az='',
                         available_zones=current_user.get_available_zones())

# =======================
# API Endpoints
# =======================

@app.route('/api/topology/generate', methods=['POST'])
@login_required
def generate_topology():
    try:
        data = request.json
        topology.generate_topology(data.get('type', 'tree'), data.get('config', {}), data.get('flavor', None))
        return jsonify({'success': True, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/placement/az', methods=['POST'])
@login_required
def set_placement_az():
    try:
        data = request.json
        az = data.get('az')
        if az and az not in current_user.get_available_zones():
            return jsonify({'success': False, 'error': 'No tienes acceso a esa zona'})
        topology.set_placement_az(az)
        return jsonify({'success': True, 'message': f'Zona establecida: {az}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/topology/clear', methods=['POST'])
@login_required
def clear_topology():
    try:
        topology.nodes = []
        topology.edges = []
        topology.next_id = 1
        topology.topology_count = 0
        topology.placement_az = None
        return jsonify({'success': True, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/topology/save', methods=['POST'])
@login_required
def save_topology():
    try:
        data = request.json
        name = data.get('name', 'topology')
        az = data.get('az', '')
        template_id = data.get('template_id')
        topology_json = {'nodes': topology.nodes, 'edges': topology.edges}
        db = get_db()

        if template_id:
            db.templates.update_one({'_id': ObjectId(template_id), 'user_id': current_user.id}, {'$set': {'name': name, 'topology_json': topology_json, 'availability_zone': az, 'updated_at': datetime.now()}})
            message = "Plantilla actualizada"
        else:
            result = db.templates.insert_one({'user_id': current_user.id, 'name': name, 'topology_json': topology_json, 'availability_zone': az, 'created_at': datetime.now(), 'updated_at': datetime.now()})
            template_id = str(result.inserted_id)
            message = "Plantilla guardada"

        return jsonify({'success': True, 'message': message, 'template_id': template_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/topology/load', methods=['POST'])
@login_required
def load_topology():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Invalid file'})
        template_data = json.load(file)
        success = topology.load_from_template(template_data)
        if success:
            return jsonify({'success': True, 'topology': topology.get_state()})
        return jsonify({'success': False, 'error': 'Error processing template'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/nodes', methods=['POST'])
@login_required
def add_node():
    try:
        data = request.json
        new_node = topology.add_node(data.get('x', 400), data.get('y', 300), data.get('flavor', None))
        return jsonify({'success': True, 'node': new_node, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/nodes/<int:node_id>', methods=['DELETE'])
@login_required
def delete_node(node_id):
    try:
        topology.delete_node(node_id)
        return jsonify({'success': True, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/nodes/<int:node_id>/move', methods=['PUT'])
@login_required
def move_node(node_id):
    try:
        data = request.json
        if data.get('x') is not None and data.get('y') is not None:
            topology.move_node(node_id, data['x'], data['y'])
        return jsonify({'success': True, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/nodes/<int:node_id>/flavor', methods=['PUT'])
@login_required
def update_node_flavor(node_id):
    try:
        data = request.json
        flavor = data.get('flavor')
        if flavor:
            topology.update_node_flavor(node_id, flavor)
            return jsonify({'success': True, 'topology': topology.get_state()})
        return jsonify({'success': False, 'error': 'No flavor provided'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/edges', methods=['POST'])
@login_required
def add_edge():
    try:
        data = request.json
        success = topology.connect_nodes(data.get('from'), data.get('to'))
        return jsonify({'success': success, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/edges/delete', methods=['POST'])
@login_required
def delete_edge():
    try:
        data = request.json
        topology.delete_edge(data.get('from'), data.get('to'))
        return jsonify({'success': True, 'topology': topology.get_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/topology/state', methods=['GET'])
@login_required
def get_topology_state():
    return jsonify(topology.get_state())

@app.route('/api/topology/sync', methods=['POST'])
@login_required
def sync_topology():
    """Sincroniza la topología del frontend con el backend"""
    try:
        data = request.json
        topology.nodes = data.get('nodes', [])
        topology.edges = data.get('edges', [])

        # Actualizar next_id basado en los nodos existentes
        if topology.nodes:
            topology.next_id = max(node['id'] for node in topology.nodes) + 1
        else:
            topology.next_id = 1

        return jsonify({'success': True, 'message': 'Topología sincronizada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/templates/<template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    try:
        db = get_db()
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': current_user.id})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/templates/<template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    try:
        data = request.json
        name = data.get('name', 'topology')
        az = data.get('az', '')

        # Obtener el estado actual de la topología
        topology_json = {'nodes': topology.nodes, 'edges': topology.edges}

        db = get_db()
        result = db.templates.update_one(
            {'_id': ObjectId(template_id), 'user_id': current_user.id},
            {'$set': {
                'name': name,
                'topology_json': topology_json,
                'availability_zone': az,
                'updated_at': datetime.now()
            }}
        )

        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'Plantilla no encontrada'})

        return jsonify({'success': True, 'message': 'Plantilla actualizada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/templates/<template_id>/deploy', methods=['POST'])
@login_required
def deploy_template(template_id):
    try:
        db = get_db()
        active_slices = db.slices.count_documents({'user_id': current_user.id, 'status': 'active'})
        if active_slices >= current_user.get_max_slices():
            return jsonify({'success': False, 'error': f'Límite de {current_user.get_max_slices()} slices alcanzado'})

        template = db.templates.find_one({'_id': ObjectId(template_id), 'user_id': current_user.id})
        if not template:
            return jsonify({'success': False, 'error': 'Plantilla no encontrada'})

        slice_id = f"{template['name']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        vm_count = len(template['topology_json'].get('nodes', []))

        db.slices.insert_one({
            'template_id': str(template['_id']),
            'user_id': current_user.id,
            'slice_id': slice_id,
            'name': template['name'],
            'topology_json': template['topology_json'],
            'availability_zone': template.get('availability_zone'),
            'deployed_at': datetime.now(),
            'status': 'active',
            'vm_count': vm_count
        })

        # Eliminar la plantilla después de desplegarla (ya no es plantilla, es un slice)
        db.templates.delete_one({'_id': ObjectId(template_id), 'user_id': current_user.id})

        return jsonify({'success': True, 'slice_id': slice_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slices/<slice_id>', methods=['DELETE'])
@login_required
def delete_slice(slice_id):
    try:
        db = get_db()
        db.slices.delete_one({'slice_id': slice_id, 'user_id': current_user.id})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    os.makedirs('./templates', exist_ok=True)
    app.run(debug=True, port=5000)
