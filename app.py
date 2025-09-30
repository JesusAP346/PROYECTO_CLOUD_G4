from flask import Flask, render_template, jsonify, request
import math
import json

app = Flask(__name__)

class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
    
    def generate_topology(self, topology_type, config):
        """Genera una topología específica basada en el tipo y configuración"""
        self.nodes = []
        self.edges = []
        
        center_x = 400
        center_y = 300
        radius = 150
        
        if topology_type == "point-to-point":
            self.nodes = [
                {'id': 1, 'x': center_x - 100, 'y': center_y, 'label': 'VM-1'},
                {'id': 2, 'x': center_x + 100, 'y': center_y, 'label': 'VM-2'}
            ]
            self.edges = [{'from': 1, 'to': 2}]
            self.next_id = 3
            
        elif topology_type == "star":
            central_id = 1
            self.nodes = [{'id': central_id, 'x': center_x, 'y': center_y, 'label': 'VM-1'}]
            
            for i in range(config.get('node_count', 5) - 1):
                angle = (i * 2 * math.pi) / (config.get('node_count', 5) - 1)
                new_id = i + 2
                self.nodes.append({
                    'id': new_id,
                    'x': center_x + radius * math.cos(angle),
                    'y': center_y + radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
                self.edges.append({'from': central_id, 'to': new_id})
            self.next_id = config.get('node_count', 5) + 1
            
        elif topology_type == "ring":
            node_count = config.get('node_count', 5)
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = i + 1
                self.nodes.append({
                    'id': new_id,
                    'x': center_x + radius * math.cos(angle),
                    'y': center_y + radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
                self.edges.append({
                    'from': new_id,
                    'to': (new_id % node_count) + 1
                })
            self.next_id = node_count + 1
            
        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            
            # Nodo raíz
            root_id = 1
            self.nodes.append({'id': root_id, 'x': center_x, 'y': 80, 'label': 'VM-1'})
            current_level = [{'id': root_id, 'x': center_x, 'y': 80}]
            next_id = 2
            
            for level in range(1, levels):
                next_level = []
                nodes_in_level = len(current_level) * branching
                spacing = 700 / (nodes_in_level + 1)
                y = 80 + level * 140
                
                for parent_idx, parent in enumerate(current_level):
                    for i in range(branching):
                        child_idx = parent_idx * branching + i
                        x = spacing * (child_idx + 1) + 50
                        self.nodes.append({
                            'id': next_id,
                            'x': x,
                            'y': y,
                            'label': f'VM-{next_id}'
                        })
                        self.edges.append({'from': parent['id'], 'to': next_id})
                        next_level.append({'id': next_id, 'x': x, 'y': y})
                        next_id += 1
                
                current_level = next_level
            self.next_id = next_id
            
        elif topology_type == "bus":
            node_count = config.get('node_count', 5)
            bus_spacing = 600 / (node_count + 1)
            
            for i in range(node_count):
                new_id = i + 1
                self.nodes.append({
                    'id': new_id,
                    'x': bus_spacing * (i + 1) + 100,
                    'y': center_y,
                    'label': f'VM-{new_id}'
                })
                if i > 0:
                    self.edges.append({'from': new_id - 1, 'to': new_id})
            self.next_id = node_count + 1
            
        elif topology_type == "mesh":
            node_count = config.get('node_count', 5)
            mesh_radius = 120
            
            # Crear nodos
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                self.nodes.append({
                    'id': i + 1,
                    'x': center_x + mesh_radius * math.cos(angle),
                    'y': center_y + mesh_radius * math.sin(angle),
                    'label': f'VM-{i+1}'
                })
            
            # Crear conexiones de malla completa
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    self.edges.append({'from': i + 1, 'to': j + 1})
            self.next_id = node_count + 1
    
    def add_node(self, x, y):
        """Agrega un nuevo nodo en la posición especificada"""
        new_node = {
            'id': self.next_id,
            'x': x,
            'y': y,
            'label': f'VM-{self.next_id}'
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
        # Verificar si la conexión ya existe
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
    
    def get_state(self):
        """Retorna el estado actual de la topología"""
        return {
            'nodes': self.nodes,
            'edges': self.edges
        }

# Instancia global de la topología
topology = NetworkTopology()

@app.route('/')
def index():
    return render_template('index.html')

# API Endpoints
@app.route('/api/topology/generate', methods=['POST'])
def generate_topology():
    data = request.json
    topology_type = data.get('type', 'tree')
    config = data.get('config', {})
    
    topology.generate_topology(topology_type, config)
    
    return jsonify({
        'success': True,
        'topology': topology.get_state()
    })

@app.route('/api/nodes', methods=['POST'])
def add_node():
    data = request.json
    x = data.get('x', 400)
    y = data.get('y', 300)
    
    new_node = topology.add_node(x, y)
    
    return jsonify({
        'success': True,
        'node': new_node,
        'topology': topology.get_state()
    })

@app.route('/api/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    topology.delete_node(node_id)
    
    return jsonify({
        'success': True,
        'topology': topology.get_state()
    })

@app.route('/api/nodes/<int:node_id>/move', methods=['PUT'])
def move_node(node_id):
    data = request.json
    x = data.get('x')
    y = data.get('y')
    
    if x is not None and y is not None:
        topology.move_node(node_id, x, y)
    
    return jsonify({
        'success': True,
        'topology': topology.get_state()
    })

@app.route('/api/edges', methods=['POST'])
def add_edge():
    data = request.json
    from_id = data.get('from')
    to_id = data.get('to')
    
    success = topology.connect_nodes(from_id, to_id)
    
    return jsonify({
        'success': success,
        'topology': topology.get_state()
    })

@app.route('/api/edges/delete', methods=['POST'])
def delete_edge():
    data = request.json
    from_id = data.get('from')
    to_id = data.get('to')
    
    topology.delete_edge(from_id, to_id)
    
    return jsonify({
        'success': True,
        'topology': topology.get_state()
    })

@app.route('/api/topology/state', methods=['GET'])
def get_topology_state():
    return jsonify(topology.get_state())

if __name__ == '__main__':
    app.run(debug=True)