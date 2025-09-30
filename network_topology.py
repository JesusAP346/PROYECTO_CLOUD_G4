import tkinter as tk
from tkinter import ttk
import math
import random

class NetworkTopologyBuilder:
    def __init__(self, root):
        self.root = root
        self.root.title("Constructor de Topologías de Red")
        self.root.geometry("1200x800")
        
        # Estados
        self.nodes = []
        self.edges = []
        self.selected_node = None
        self.connect_mode = False
        self.connect_from = None
        self.dragging_node = None
        
        # Configuración
        self.topology = "tree"
        self.node_count = 5
        self.tree_levels = 3
        self.tree_branching = 2
        
        self.setup_ui()
        
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel de control izquierdo
        control_frame = ttk.Frame(main_frame, width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_frame.pack_propagate(False)
        
        # Canvas de visualización
        self.canvas_frame = ttk.Frame(main_frame)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Configuración de topología
        config_group = ttk.LabelFrame(control_frame, text="Configuración", padding=10)
        config_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(config_group, text="Topología:").pack(anchor=tk.W)
        self.topology_var = tk.StringVar(value="tree")
        topology_combo = ttk.Combobox(config_group, textvariable=self.topology_var, 
                                    values=["point-to-point", "star", "ring", "tree", "bus", "mesh"])
        topology_combo.pack(fill=tk.X, pady=(0, 10))
        topology_combo.bind('<<ComboboxSelected>>', self.on_topology_change)
        
        # Configuración específica para árbol
        self.tree_frame = ttk.Frame(config_group)
        self.tree_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.tree_frame, text="Niveles:").pack(anchor=tk.W)
        self.levels_var = tk.IntVar(value=3)
        levels_scale = ttk.Scale(self.tree_frame, from_=2, to=5, variable=self.levels_var, 
                               orient=tk.HORIZONTAL, command=self.on_levels_change)
        levels_scale.pack(fill=tk.X)
        self.levels_label = ttk.Label(self.tree_frame, text="Niveles: 3")
        self.levels_label.pack(anchor=tk.W)
        
        ttk.Label(self.tree_frame, text="Ramificación:").pack(anchor=tk.W)
        self.branching_var = tk.IntVar(value=2)
        branching_scale = ttk.Scale(self.tree_frame, from_=2, to=4, variable=self.branching_var,
                                  orient=tk.HORIZONTAL, command=self.on_branching_change)
        branching_scale.pack(fill=tk.X)
        self.branching_label = ttk.Label(self.tree_frame, text="Ramificación: 2")
        self.branching_label.pack(anchor=tk.W)
        
        # Para otras topologías
        self.other_frame = ttk.Frame(config_group)
        ttk.Label(self.other_frame, text="Número de VMs:").pack(anchor=tk.W)
        self.count_var = tk.IntVar(value=5)
        count_scale = ttk.Scale(self.other_frame, from_=3, to=8, variable=self.count_var,
                              orient=tk.HORIZONTAL, command=self.on_count_change)
        count_scale.pack(fill=tk.X)
        self.count_label = ttk.Label(self.other_frame, text="VMs: 5")
        self.count_label.pack(anchor=tk.W)
        
        ttk.Button(config_group, text="Generar Topología", 
                  command=self.generate_topology).pack(fill=tk.X)
        
        # Acciones
        actions_group = ttk.LabelFrame(control_frame, text="Acciones", padding=10)
        actions_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(actions_group, text="Agregar VM", 
                  command=self.add_node).pack(fill=tk.X, pady=(0, 5))
        
        self.connect_btn = ttk.Button(actions_group, text="Conectar VMs", 
                                     command=self.toggle_connect_mode)
        self.connect_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.delete_btn = ttk.Button(actions_group, text="Eliminar VM seleccionada", 
                                    command=self.delete_selected_node, state=tk.DISABLED)
        self.delete_btn.pack(fill=tk.X)
        
        # Eventos del canvas
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        self.update_ui()
        
    def on_topology_change(self, event):
        self.topology = self.topology_var.get()
        self.update_ui()
        
    def on_levels_change(self, value):
        self.tree_levels = int(float(value))
        self.levels_label.config(text=f"Niveles: {self.tree_levels}")
        
    def on_branching_change(self, value):
        self.tree_branching = int(float(value))
        self.branching_label.config(text=f"Ramificación: {self.tree_branching}")
        
    def on_count_change(self, value):
        self.node_count = int(float(value))
        self.count_label.config(text=f"VMs: {self.node_count}")
        
    def update_ui(self):
        if self.topology == "tree":
            self.tree_frame.pack(fill=tk.X, pady=(0, 10))
            self.other_frame.pack_forget()
        else:
            self.tree_frame.pack_forget()
            self.other_frame.pack(fill=tk.X, pady=(0, 10))
            
    def generate_topology(self):
        new_nodes = []
        new_edges = []
        center_x = 400
        center_y = 300
        radius = 150
        
        node_id = max([node['id'] for node in self.nodes], default=0) + 1
        
        if self.topology == "point-to-point":
            new_nodes = [
                {'id': node_id, 'x': center_x - 100, 'y': center_y, 'label': f'VM-{node_id}'},
                {'id': node_id + 1, 'x': center_x + 100, 'y': center_y, 'label': f'VM-{node_id + 1}'}
            ]
            new_edges = [{'from': node_id, 'to': node_id + 1}]
            
        elif self.topology == "star":
            central_id = node_id
            new_nodes = [{'id': central_id, 'x': center_x, 'y': center_y, 'label': f'VM-{central_id}'}]
            for i in range(self.node_count - 1):
                angle = (i * 2 * math.pi) / (self.node_count - 1)
                new_id = node_id + i + 1
                new_nodes.append({
                    'id': new_id,
                    'x': center_x + radius * math.cos(angle),
                    'y': center_y + radius * math.sin(angle),
                    'label': f'VM-{new_id}'
                })
                new_edges.append({'from': central_id, 'to': new_id})
                
        # Implementar otras topologías similarmente...
        
        self.nodes.extend(new_nodes)
        self.edges.extend(new_edges)
        self.selected_node = None
        self.connect_mode = False
        self.connect_from = None
        self.draw_topology()
        
    def add_node(self):
        new_id = max([node['id'] for node in self.nodes], default=0) + 1
        new_node = {
            'id': new_id,
            'x': 400 + (random.random() - 0.5) * 200,
            'y': 300 + (random.random() - 0.5) * 200,
            'label': f'VM-{new_id}'
        }
        self.nodes.append(new_node)
        self.draw_topology()
        
    def toggle_connect_mode(self):
        self.connect_mode = not self.connect_mode
        self.connect_from = None
        if self.connect_mode:
            self.connect_btn.config(text="Cancelar Conexión")
        else:
            self.connect_btn.config(text="Conectar VMs")
            
    def delete_selected_node(self):
        if self.selected_node:
            self.nodes = [node for node in self.nodes if node['id'] != self.selected_node]
            self.edges = [edge for edge in self.edges 
                         if edge['from'] != self.selected_node and edge['to'] != self.selected_node]
            self.selected_node = None
            self.draw_topology()
            
    def on_canvas_click(self, event):
        # Lógica para seleccionar nodos y conectar
        clicked_node = self.get_node_at_position(event.x, event.y)
        
        if clicked_node:
            if self.connect_mode:
                if self.connect_from is None:
                    self.connect_from = clicked_node['id']
                else:
                    # Crear conexión
                    new_edge = {'from': self.connect_from, 'to': clicked_node['id']}
                    if not self.edge_exists(new_edge):
                        self.edges.append(new_edge)
                    self.connect_from = None
                    self.connect_mode = False
                    self.connect_btn.config(text="Conectar VMs")
            else:
                self.selected_node = clicked_node['id']
                self.delete_btn.config(state=tk.NORMAL)
            self.draw_topology()
        else:
            self.selected_node = None
            self.delete_btn.config(state=tk.DISABLED)
            self.draw_topology()
            
    def on_canvas_drag(self, event):
        if self.dragging_node:
            node = next((n for n in self.nodes if n['id'] == self.dragging_node), None)
            if node:
                node['x'] = event.x
                node['y'] = event.y
                self.draw_topology()
                
    def on_canvas_release(self, event):
        self.dragging_node = None
        
    def get_node_at_position(self, x, y):
        for node in self.nodes:
            distance = math.sqrt((node['x'] - x)**2 + (node['y'] - y)**2)
            if distance <= 30:  # Radio del nodo
                return node
        return None
        
    def edge_exists(self, new_edge):
        return any((edge['from'] == new_edge['from'] and edge['to'] == new_edge['to']) or
                  (edge['from'] == new_edge['to'] and edge['to'] == new_edge['from'])
                  for edge in self.edges)
        
    def draw_topology(self):
        self.canvas.delete("all")
        
        # Dibujar conexiones
        for edge in self.edges:
            from_node = next((n for n in self.nodes if n['id'] == edge['from']), None)
            to_node = next((n for n in self.nodes if n['id'] == edge['to']), None)
            if from_node and to_node:
                self.canvas.create_line(from_node['x'], from_node['y'], 
                                      to_node['x'], to_node['y'], 
                                      width=2, fill="gray")
                                      
                # Punto medio para eliminar conexión
                mid_x = (from_node['x'] + to_node['x']) / 2
                mid_y = (from_node['y'] + to_node['y']) / 2
                self.canvas.create_oval(mid_x-8, mid_y-8, mid_x+8, mid_y+8, 
                                      fill="red", outline="", tags=f"delete_edge_{edge['from']}_{edge['to']}")
        
        # Dibujar nodos
        for node in self.nodes:
            color = "blue"
            if node['id'] == self.selected_node:
                color = "red"
            elif node['id'] == self.connect_from:
                color = "green"
                
            self.canvas.create_oval(node['x']-30, node['y']-30, node['x']+30, node['y']+30,
                                  fill=color, outline="white", width=3,
                                  tags=f"node_{node['id']}")
                                  
            self.canvas.create_text(node['x'], node['y'], text="VM", 
                                  fill="white", font=("Arial", 10, "bold"))
            self.canvas.create_text(node['x'], node['y']+50, text=node['label'],
                                  fill="black", font=("Arial", 10, "bold"))

if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkTopologyBuilder(root)
    root.mainloop()