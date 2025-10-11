from flask import Flask, render_template, jsonify, request, send_file
import math
import json
from datetime import datetime
import os
import tempfile

app = Flask(__name__)

class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.topology_count = 0
        self.placement_az = None
    
    def generate_topology(self, topology_type, config, flavor=None):
        """Genera una topología específica y la AGREGA a la existente"""
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
                {
                    'id': next_id, 
                    'x': base_x - 50, 
                    'y': base_y, 
                    'label': f'VM-{next_id}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                },
                {
                    'id': next_id + 1, 
                    'x': base_x + 50, 
                    'y': base_y, 
                    'label': f'VM-{next_id + 1}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                }
            ]
            new_edges = [{'from': next_id, 'to': next_id + 1}]
            
        elif topology_type == "star":
            radius = 80
            central_id = next_id
            new_nodes = [{
                'id': central_id, 
                'x': base_x, 
                'y': base_y, 
                'label': f'VM-{central_id}',
                'flavor': flavor.copy(),
                'az': self.placement_az
            }]
            
            node_count = config.get('node_count', 5)
            for i in range(node_count - 1):
                angle = (i * 2 * math.pi) / (node_count - 1)
                new_id = next_id + i + 1
                new_nodes.append({
                    'id': new_id,
                    'x': base_x + radius * math.cos(angle),
                    'y': base_y + radius * math.sin(angle),
                    'label': f'VM-{new_id}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                })
                new_edges.append({'from': central_id, 'to': new_id})
            
        elif topology_type == "ring":
            node_count = config.get('node_count', 5)
            radius = 70
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': base_x + radius * math.cos(angle),
                    'y': base_y + radius * math.sin(angle),
                    'label': f'VM-{new_id}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                })
                if i < node_count - 1:
                    new_edges.append({'from': new_id, 'to': new_id + 1})
                else:
                    new_edges.append({'from': new_id, 'to': next_id})
                    
        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            
            root_id = next_id
            new_nodes.append({
                'id': root_id, 
                'x': base_x, 
                'y': base_y, 
                'label': f'VM-{root_id}',
                'flavor': flavor.copy(),
                'az': self.placement_az
            })
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
                        
                        new_nodes.append({
                            'id': current_id,
                            'x': x,
                            'y': y,
                            'label': f'VM-{current_id}',
                            'flavor': flavor.copy(),
                            'az': self.placement_az
                        })
                        new_edges.append({'from': parent['id'], 'to': current_id})
                        next_level.append({'id': current_id, 'x': x, 'y': y})
                        current_id += 1
                
                current_level = next_level
                
        elif topology_type == "bus":
            node_count = config.get('node_count', 5)
            bus_spacing = 120 / max(1, node_count - 1)
            
            for i in range(node_count):
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': base_x - 60 + bus_spacing * i,
                    'y': base_y,
                    'label': f'VM-{new_id}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                })
                if i > 0:
                    new_edges.append({'from': new_id - 1, 'to': new_id})
                    
        elif topology_type == "mesh":
            node_count = config.get('node_count', 5)
            mesh_radius = 60
            
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': base_x + mesh_radius * math.cos(angle),
                    'y': base_y + mesh_radius * math.sin(angle),
                    'label': f'VM-{new_id}',
                    'flavor': flavor.copy(),
                    'az': self.placement_az
                })
            
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    new_edges.append({'from': next_id + i, 'to': next_id + j})
        
        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        
        if self.nodes:
            self.next_id = max(node['id'] for node in self.nodes) + 1
    
    def add_node(self, x, y, flavor=None):
        """Agrega un nuevo nodo en la posición especificada con flavor"""
        if flavor is None:
            flavor = {'vcpus': 2, 'ram': 2, 'disk': 20}
        
        new_node = {
            'id': self.next_id,
            'x': x,
            'y': y,
            'label': f'VM-{self.next_id}',
            'flavor': flavor.copy(),
            'az': self.placement_az
        }
        self.nodes.append(new_node)
        self.next_id += 1
        return new_node
    
    def delete_node(self, node_id):
        """Elimina un nodo y todas sus conexiones"""
        self.nodes = [node for node in self.nodes if node['id'] != node_id]
        self.edges = [edge for edge in self.edges 
                     if edge['from'] != node_id and edge['to'] != node_id]
    
    def connect_nodes(self, from_id, to_id):
        """Conecta dos nodos si no existe ya la conexión"""
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
        """Elimina una conexión entre nodos"""
        self.edges = [
            edge for edge in self.edges 
            if not (edge['from'] == from_id and edge['to'] == to_id)
        ]
    
    def move_node(self, node_id, x, y):
        """Mueve un nodo a una nueva posición"""
        for node in self.nodes:
            if node['id'] == node_id:
                node['x'] = x
                node['y'] = y
                break
    
    def update_node_flavor(self, node_id, flavor):
        """Actualiza el flavor de un nodo específico"""
        for node in self.nodes:
            if node['id'] == node_id:
                node['flavor'] = flavor.copy()
                break
    
    def set_placement_az(self, az):
        """Establece la zona de disponibilidad para nuevos nodos"""
        self.placement_az = az
    
    def get_state(self):
        """Retorna el estado actual de la topología"""
        return {
            'nodes': self.nodes,
            'edges': self.edges
        }
    
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
            
            az = template_data.get('availability_zone')
            if az:
                self.placement_az = az
                
            return True
        except Exception as e:
            print(f"Error loading template: {e}")
            return False

# Instancia global de la topología
topology = NetworkTopology()

@app.route('/')
def index():
    return render_template('index.html')

# API Endpoints
@app.route('/api/topology/generate', methods=['POST'])
def generate_topology():
    try:
        data = request.json
        topology_type = data.get('type', 'tree')
        config = data.get('config', {})
        flavor = data.get('flavor', None)
        
        topology.generate_topology(topology_type, config, flavor)
        
        return jsonify({
            'success': True,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/placement/az', methods=['POST'])
def set_placement_az():
    try:
        data = request.json
        az = data.get('az')
        
        topology.set_placement_az(az)
        
        return jsonify({
            'success': True,
            'message': f'Zona de disponibilidad establecida: {az}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/topology/clear', methods=['POST'])
def clear_topology():
    try:
        topology.nodes = []
        topology.edges = []
        topology.next_id = 1
        topology.topology_count = 0
        topology.placement_az = None
        
        return jsonify({
            'success': True,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/topology/save', methods=['POST'])
def save_topology():
    try:
        data = request.json
        name = data.get('name', 'topology')
        format_type = data.get('format', 'full')
        flavor = data.get('flavor', {})
        az = data.get('az', '')
        
        template_data = {
            'metadata': {
                'name': name,
                'created_at': datetime.now().isoformat(),
                'format': format_type
            },
            'flavor_defaults': flavor,
            'availability_zone': az,
            'topology': {
                'nodes': topology.nodes,
                'edges': topology.edges
            }
        }
        
        filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"./templates/{filename}"
        
        os.makedirs('./templates', exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(template_data, f, indent=2)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'file': filepath
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/topology/load', methods=['POST'])
def load_topology():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if file and file.filename.endswith('.json'):
            template_data = json.load(file)
            success = topology.load_from_template(template_data)
            
            if success:
                return jsonify({
                    'success': True,
                    'topology': topology.get_state()
                })
            else:
                return jsonify({'success': False, 'error': 'Error processing template'})
        
        return jsonify({'success': False, 'error': 'Invalid file format'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/nodes', methods=['POST'])
def add_node():
    try:
        data = request.json
        x = data.get('x', 400)
        y = data.get('y', 300)
        flavor = data.get('flavor', None)
        
        new_node = topology.add_node(x, y, flavor)
        
        return jsonify({
            'success': True,
            'node': new_node,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    try:
        topology.delete_node(node_id)
        
        return jsonify({
            'success': True,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/nodes/<int:node_id>/move', methods=['PUT'])
def move_node(node_id):
    try:
        data = request.json
        x = data.get('x')
        y = data.get('y')
        
        if x is not None and y is not None:
            topology.move_node(node_id, x, y)
        
        return jsonify({
            'success': True,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/nodes/<int:node_id>/flavor', methods=['PUT'])
def update_node_flavor(node_id):
    try:
        data = request.json
        flavor = data.get('flavor')
        
        if flavor:
            topology.update_node_flavor(node_id, flavor)
            
            return jsonify({
                'success': True,
                'topology': topology.get_state()
            })
        
        return jsonify({
            'success': False,
            'error': 'No flavor provided'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/edges', methods=['POST'])
def add_edge():
    try:
        data = request.json
        from_id = data.get('from')
        to_id = data.get('to')
        
        success = topology.connect_nodes(from_id, to_id)
        
        return jsonify({
            'success': success,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/edges/delete', methods=['POST'])
def delete_edge():
    try:
        data = request.json
        from_id = data.get('from')
        to_id = data.get('to')
        
        topology.delete_edge(from_id, to_id)
        
        return jsonify({
            'success': True,
            'topology': topology.get_state()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/topology/state', methods=['GET'])
def get_topology_state():
    return jsonify(topology.get_state())

if __name__ == '__main__':
    os.makedirs('./templates', exist_ok=True)
    app.run(debug=True)