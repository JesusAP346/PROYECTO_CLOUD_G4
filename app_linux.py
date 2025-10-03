from flask import Flask, render_template, jsonify, request
import math
import json
import os
import re
from datetime import datetime

# Si quieres, ajusta folders:
app = Flask(__name__, template_folder='templates', static_folder='static')

# ====== Config para guardado de plantillas ======
SAVE_DIR = "/home/ubuntu/proyecto/PROYECTO_CLOUD_G4/ejemplos_plantillas"  # <-- CAMBIA si quieres otra ruta
os.makedirs(SAVE_DIR, exist_ok=True)

def _slugify(name: str) -> str:
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9\-_. ]+", "", name)  # limpia caracteres raros
    name = re.sub(r"\s+", "-", name)
    return name or "plantilla"


# ====== Lógica de topologías ======
class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.slice_placement = {"az": None}
    
    def generate_topology(self, topology_type, config):
        """Genera una topología específica y la AGREGA a la existente"""
        center_x = 5000
        center_y = 5000
        base_radius = 200
        
        new_nodes = []
        new_edges = []
        
        next_id = max([node['id'] for node in self.nodes], default=0) + 1
        
        if topology_type == "point-to-point":
            new_nodes = [
                {'id': next_id, 'x': center_x - 50, 'y': center_y, 'label': f'VM-{next_id}'},
                {'id': next_id + 1, 'x': center_x + 50, 'y': center_y, 'label': f'VM-{next_id + 1}'}
            ]
            new_edges = [{'from': next_id, 'to': next_id + 1}]
            
        elif topology_type == "star":
            central_id = next_id
            new_nodes = [{'id': central_id, 'x': center_x, 'y': center_y, 'label': f'VM-{central_id}'}]
            
            node_count = config.get('node_count', 5)
            star_radius = base_radius * 0.8
            for i in range(node_count - 1):
                angle = (i * 2 * math.pi) / (node_count - 1)
                new_id = next_id + i + 1
                new_nodes.append({
                    'id': new_id,
                    'x': center_x + star_radius * math.cos(angle),
                    'y': center_y + star_radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
                new_edges.append({'from': central_id, 'to': new_id})
                
        elif topology_type == "ring":
            node_count = config.get('node_count', 5)
            ring_radius = base_radius * 0.6
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': center_x + ring_radius * math.cos(angle),
                    'y': center_y + ring_radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
                if i < node_count - 1:
                    new_edges.append({'from': new_id, 'to': new_id + 1})
                else:
                    new_edges.append({'from': new_id, 'to': next_id})
                    
        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            
            root_id = next_id
            new_nodes.append({'id': root_id, 'x': center_x, 'y': center_y, 'label': f'VM-{root_id}'})
            current_level = [{'id': root_id, 'x': center_x, 'y': center_y}]
            current_id = next_id + 1
            
            for level in range(1, levels):
                next_level = []
                nodes_in_level = len(current_level) * branching
                level_width = 400
                spacing = level_width / max(1, nodes_in_level)
                y = center_y + level * 120
                
                for parent_idx, parent in enumerate(current_level):
                    for i in range(branching):
                        child_idx = parent_idx * branching + i
                        x = center_x - (level_width / 2) + spacing * (child_idx + 0.5)
                        new_nodes.append({
                            'id': current_id,
                            'x': x,
                            'y': y,
                            'label': f'VM-{current_id}'
                        })
                        new_edges.append({'from': parent['id'], 'to': current_id})
                        next_level.append({'id': current_id, 'x': x, 'y': y})
                        current_id += 1
                
                current_level = next_level
                
        elif topology_type == "bus":
            node_count = config.get('node_count', 5)
            bus_width = 300
            bus_spacing = bus_width / (node_count + 1)
            
            for i in range(node_count):
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': center_x - (bus_width / 2) + bus_spacing * (i + 1),
                    'y': center_y,
                    'label': f'VM-{new_id}'
                })
                if i > 0:
                    new_edges.append({'from': new_id - 1, 'to': new_id})
                    
        elif topology_type == "mesh":
            node_count = config.get('node_count', 5)
            mesh_radius = base_radius * 0.5
            
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': center_x + mesh_radius * math.cos(angle),
                    'y': center_y + mesh_radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    new_edges.append({'from': next_id + i, 'to': next_id + j})
        
        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        
        if new_nodes:
            self.next_id = max(node['id'] for node in self.nodes) + 1
    
    def add_node(self, x, y):
        if x is None or y is None:
            x = 5000
            y = 5000
        new_node = {'id': self.next_id, 'x': x, 'y': y, 'label': f'VM-{self.next_id}'}
        self.nodes.append(new_node)
        self.next_id += 1
        return new_node
    
    def delete_node(self, node_id):
        self.nodes = [node for node in self.nodes if node['id'] != node_id]
        self.edges = [edge for edge in self.edges if edge['from'] != node_id and edge['to'] != node_id]
    
    def connect_nodes(self, from_id, to_id):
        existing = any(
            (edge['from'] == from_id and edge['to'] == to_id) or
            (edge['from'] == to_id and edge['to'] == from_id)
            for edge in self.edges
        )
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
    
    def get_state(self, include_coords: bool = True):
        if include_coords:
            clean_nodes = [{'id': n['id'], 'label': n['label'], 'x': n['x'], 'y': n['y']} for n in self.nodes]
        else:
            clean_nodes = [{'id': n['id'], 'label': n['label']} for n in self.nodes]
        return {'nodes': clean_nodes, 'edges': self.edges}


# ====== Instancia global ======
topology = NetworkTopology()


# ====== Rutas ======
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/topology/generate', methods=['POST'])
def generate_topology():
    data = request.json or {}
    topology_type = data.get('type', 'tree')
    config = data.get('config', {})
    topology.generate_topology(topology_type, config)
    return jsonify({'success': True, 'topology': topology.get_state()})


@app.route('/api/topology/clear', methods=['POST'])
def clear_topology():
    topology.nodes = []
    topology.edges = []
    topology.next_id = 1
    return jsonify({'success': True, 'topology': topology.get_state()})


@app.route('/api/nodes', methods=['POST'])
def add_node():
    data = request.json or {}
    x = data.get('x', 5000)
    y = data.get('y', 5000)
    new_node = topology.add_node(x, y)
    return jsonify({'success': True, 'node': new_node, 'topology': topology.get_state()})


@app.route('/api/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    topology.delete_node(node_id)
    return jsonify({'success': True, 'topology': topology.get_state()})


@app.route('/api/nodes/<int:node_id>/move', methods=['PUT'])
def move_node(node_id):
    data = request.json or {}
    x = data.get('x')
    y = data.get('y')
    if x is not None and y is not None:
        topology.move_node(node_id, x, y)
    return jsonify({'success': True, 'topology': topology.get_state()})


@app.route('/api/edges', methods=['POST'])
def add_edge():
    data = request.json or {}
    from_id = data.get('from')
    to_id = data.get('to')
    success = topology.connect_nodes(from_id, to_id)
    return jsonify({'success': success, 'topology': topology.get_state()})


@app.route('/api/edges/delete', methods=['POST'])
def delete_edge():
    data = request.json or {}
    from_id = data.get('from')
    to_id = data.get('to')
    topology.delete_edge(from_id, to_id)
    return jsonify({'success': True, 'topology': topology.get_state()})


@app.route('/api/topology/state', methods=['GET'])
def get_topology_state():
    return jsonify(topology.get_state())


@app.route('/api/topology/export', methods=['GET'])
def export_topology():
    export_format = (request.args.get('format') or '').lower()
    include_coords = (export_format != 'deploy')
    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'total_nodes': len(topology.nodes),
            'total_connections': len(topology.edges),
            'placement': {'az': topology.slice_placement.get('az', None)}
        },
        'topology': topology.get_state(include_coords=include_coords)
    }
    return jsonify(export_data)


@app.route('/api/placement/az', methods=['POST'])
def set_slice_placement():
    data = request.json or {}
    az = data.get('az', None)
    allowed = {None, "linux-AZ-1", "linux-AZ-2", "openstack-AZ-1"}
    if az not in allowed:
        return jsonify({"success": False, "error": "AZ inválida"}), 400
    topology.slice_placement = {"az": az}
    return jsonify({"success": True, "placement": topology.slice_placement})


# ====== NUEVO: Guardar plantilla a archivo ======
@app.route('/api/topology/save', methods=['POST'])
def save_topology():
    payload = request.get_json(force=True) or {}
    # Body opcional: { "name": "mi_plantilla", "format": "deploy" | "full" }
    name = payload.get("name", "plantilla")
    export_format = (payload.get("format") or "full").lower()
    include_coords = (export_format != "deploy")

    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'total_nodes': len(topology.nodes),
            'total_connections': len(topology.edges),
            'placement': {'az': topology.slice_placement.get('az', None)}
        },
        'topology': topology.get_state(include_coords=include_coords)
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"{stamp}_{_slugify(name)}.json"
    fpath = os.path.join(SAVE_DIR, fname)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True, "file": fpath, "filename": fname})


# ====== MAIN ======
if __name__ == '__main__':
    # Para server1: escucha solo en localhost (usa túnel SSH desde tu PC)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
