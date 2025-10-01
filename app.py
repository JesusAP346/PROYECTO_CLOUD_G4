from flask import Flask, render_template, jsonify, request
import math
import json
from datetime import datetime

app = Flask(__name__)

class NetworkTopology:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.next_id = 1
    
    def generate_topology(self, topology_type, config):
        """Genera una topología específica y la AGREGA a la existente"""
        # Centro del área visible - usar coordenadas más centrales
        center_x = 5000
        center_y = 5000
        # Radio MUY REDUCIDO para máxima compactación
        base_radius = 200
        
        # NO reiniciamos nodes y edges, los mantenemos
        new_nodes = []
        new_edges = []
        
        # Calcular el siguiente ID disponible
        next_id = max([node['id'] for node in self.nodes], default=0) + 1
        
        if topology_type == "point-to-point":
            # Solo 100px de separación
            new_nodes = [
                {'id': next_id, 'x': center_x - 50, 'y': center_y, 'label': f'VM-{next_id}'},
                {'id': next_id + 1, 'x': center_x + 50, 'y': center_y, 'label': f'VM-{next_id + 1}'}
            ]
            new_edges = [{'from': next_id, 'to': next_id + 1}]
            
        elif topology_type == "star":
            central_id = next_id
            new_nodes = [{'id': central_id, 'x': center_x, 'y': center_y, 'label': f'VM-{central_id}'}]
            
            node_count = config.get('node_count', 5)
            # Radio muy pequeño para nodos periféricos
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
            # Radio muy compacto
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
                # Conectar en anillo
                if i < node_count - 1:
                    new_edges.append({'from': new_id, 'to': new_id + 1})
                else:
                    new_edges.append({'from': new_id, 'to': next_id})
                    
        elif topology_type == "tree":
            levels = config.get('tree_levels', 3)
            branching = config.get('tree_branching', 2)
            
            # Nodo raíz en el centro
            root_id = next_id
            new_nodes.append({'id': root_id, 'x': center_x, 'y': center_y, 'label': f'VM-{root_id}'})
            current_level = [{'id': root_id, 'x': center_x, 'y': center_y}]
            current_id = next_id + 1
            
            for level in range(1, levels):
                next_level = []
                nodes_in_level = len(current_level) * branching
                # Espaciado MUY COMPACTO
                level_width = 400  # Ancho fijo muy reducido
                spacing = level_width / max(1, nodes_in_level)
                y = center_y + level * 120  # Espaciado vertical mínimo
                
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
            # Bus muy compacto
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
            # Malla muy compacta
            mesh_radius = base_radius * 0.5
            
            # Crear nodos
            for i in range(node_count):
                angle = (i * 2 * math.pi) / node_count
                new_id = next_id + i
                new_nodes.append({
                    'id': new_id,
                    'x': center_x + mesh_radius * math.cos(angle),
                    'y': center_y + mesh_radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
            
            # Crear conexiones de malla completa
            for i in range(node_count):
                for j in range(i + 1, node_count):
                    new_edges.append({'from': next_id + i, 'to': next_id + j})
        
        # AGREGAR nuevos nodos y edges a los existentes (no reemplazar)
        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        
        # Actualizar next_id para futuras adiciones
        if new_nodes:
            self.next_id = max(node['id'] for node in self.nodes) + 1
    
    def add_node(self, x, y):
        """Agrega un nuevo nodo en la posición especificada"""
        if x is None or y is None:
            x = 5000
            y = 5000
            
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
    
    def get_state(self, include_coords: bool = True):
        clean_nodes = []
        if include_coords:
            # Devolver todo tal cual
            clean_nodes = [
                {'id': n['id'], 'label': n['label'], 'x': n['x'], 'y': n['y']}
                for n in self.nodes
            ]
        else:
            # Solo devolver id y label
            clean_nodes = [
                {'id': n['id'], 'label': n['label']}
                for n in self.nodes
            ]
        return {
            'nodes': clean_nodes,
            'edges': self.edges
        }

# Instancia global de la topología
topology = NetworkTopology()

@app.route('/')
def index():
    return render_template('index.html')

# API Endpoints (mantener igual que antes)
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

@app.route('/api/topology/clear', methods=['POST'])
def clear_topology():
    topology.nodes = []
    topology.edges = []
    topology.next_id = 1
    
    return jsonify({
        'success': True,
        'topology': topology.get_state()
    })

@app.route('/api/nodes', methods=['POST'])
def add_node():
    data = request.json
    x = data.get('x', 5000)
    y = data.get('y', 5000)
    
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

@app.route('/api/topology/export', methods=['GET'])
def export_topology():
    export_format = (request.args.get('format') or '').lower()
    include_coords = (export_format != 'deploy')  # si piden deploy, ocultamos x,y

    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'total_nodes': len(topology.nodes),
            'total_connections': len(topology.edges),
            'sentinel': 'deploy-no-coords'  # <--- marca
        },
        'topology': topology.get_state(include_coords=False)
    }
    return jsonify(export_data)

if __name__ == '__main__':
    app.run(debug=True)