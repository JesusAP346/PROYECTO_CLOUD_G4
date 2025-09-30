// Estado de la aplicación
let state = {
    nodes: [],
    edges: [],
    selectedNode: null,
    connectMode: false,
    connectFrom: null,
    draggingNode: null,
    dragOffset: { x: 0, y: 0 }
};

// Elementos del DOM
const elements = {
    topologySelect: document.getElementById('topology-select'),
    treeConfig: document.getElementById('tree-config'),
    otherConfig: document.getElementById('other-config'),
    treeLevels: document.getElementById('tree-levels'),
    treeLevelsValue: document.getElementById('tree-levels-value'),
    treeBranching: document.getElementById('tree-branching'),
    treeBranchingValue: document.getElementById('tree-branching-value'),
    treeTotal: document.getElementById('tree-total'),
    nodeCount: document.getElementById('node-count'),
    nodeCountValue: document.getElementById('node-count-value'),
    generateBtn: document.getElementById('generate-btn'),
    addNodeBtn: document.getElementById('add-node-btn'),
    connectBtn: document.getElementById('connect-btn'),
    deleteNodeBtn: document.getElementById('delete-node-btn'),
    selectedNodeId: document.getElementById('selected-node-id'),
    nodeCountDisplay: document.getElementById('node-count-display'),
    edgeCountDisplay: document.getElementById('edge-count-display'),
    connectModeIndicator: document.getElementById('connect-mode-indicator'),
    connectStep: document.getElementById('connect-step'),
    emptyState: document.getElementById('empty-state'),
    svg: document.getElementById('network-svg')
};

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar íconos de Lucide
    lucide.createIcons();
    
    // Cargar estado inicial del servidor
    loadTopologyState();
    
    // Configurar event listeners
    setupEventListeners();
});

function setupEventListeners() {
    elements.topologySelect.addEventListener('change', updateUI);
    
    elements.treeLevels.addEventListener('input', function() {
        elements.treeLevelsValue.textContent = this.value;
        updateTreeTotal();
    });
    
    elements.treeBranching.addEventListener('input', function() {
        elements.treeBranchingValue.textContent = this.value;
        updateTreeTotal();
    });
    
    elements.nodeCount.addEventListener('input', function() {
        elements.nodeCountValue.textContent = this.value;
    });
    
    elements.generateBtn.addEventListener('click', generateTopology);
    elements.addNodeBtn.addEventListener('click', addRandomNode);
    elements.connectBtn.addEventListener('click', toggleConnectMode);
    elements.deleteNodeBtn.addEventListener('click', deleteSelectedNode);
    
    // Eventos del SVG
    elements.svg.addEventListener('click', handleSvgClick);
    elements.svg.addEventListener('mousedown', handleMouseDown);
    elements.svg.addEventListener('mousemove', handleMouseMove);
    elements.svg.addEventListener('mouseup', handleMouseUp);
    elements.svg.addEventListener('mouseleave', handleMouseUp);
}

function updateUI() {
    const topology = elements.topologySelect.value;
    
    if (topology === 'tree') {
        elements.treeConfig.classList.remove('hidden');
        elements.otherConfig.classList.add('hidden');
    } else if (topology === 'point-to-point') {
        elements.treeConfig.classList.add('hidden');
        elements.otherConfig.classList.add('hidden');
    } else {
        elements.treeConfig.classList.add('hidden');
        elements.otherConfig.classList.remove('hidden');
    }
    
    updateTreeTotal();
}

function updateTreeTotal() {
    const levels = parseInt(elements.treeLevels.value);
    const branching = parseInt(elements.treeBranching.value);
    const total = Math.floor((Math.pow(branching, levels) - 1) / (branching - 1));
    elements.treeTotal.textContent = total;
}

async function generateTopology() {
    const topologyType = elements.topologySelect.value;
    const config = {};
    
    if (topologyType === 'tree') {
        config.tree_levels = parseInt(elements.treeLevels.value);
        config.tree_branching = parseInt(elements.treeBranching.value);
    } else if (topologyType !== 'point-to-point') {
        config.node_count = parseInt(elements.nodeCount.value);
    }
    
    try {
        const response = await fetch('/api/topology/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: topologyType,
                config: config
            })
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
        }
    } catch (error) {
        console.error('Error generating topology:', error);
    }
}

async function addRandomNode() {
    const x = 400 + (Math.random() - 0.5) * 200;
    const y = 300 + (Math.random() - 0.5) * 200;
    
    try {
        const response = await fetch('/api/nodes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ x, y })
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
        }
    } catch (error) {
        console.error('Error adding node:', error);
    }
}

function toggleConnectMode() {
    state.connectMode = !state.connectMode;
    state.connectFrom = null;
    
    if (state.connectMode) {
        elements.connectBtn.textContent = 'Cancelar Conexión';
        elements.connectBtn.classList.remove('bg-purple-600', 'hover:bg-purple-700');
        elements.connectBtn.classList.add('bg-yellow-600', 'hover:bg-yellow-700');
        elements.connectModeIndicator.classList.remove('hidden');
        updateConnectStep();
    } else {
        elements.connectBtn.textContent = 'Conectar VMs';
        elements.connectBtn.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
        elements.connectBtn.classList.add('bg-purple-600', 'hover:bg-purple-700');
        elements.connectModeIndicator.classList.add('hidden');
    }
}

function updateConnectStep() {
    if (state.connectFrom) {
        elements.connectStep.textContent = '2️⃣ Selecciona VM destino';
    } else {
        elements.connectStep.textContent = '1️⃣ Selecciona VM origen';
    }
}

async function deleteSelectedNode() {
    if (!state.selectedNode) return;
    
    try {
        const response = await fetch(`/api/nodes/${state.selectedNode}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            state.selectedNode = null;
            drawTopology();
        }
    } catch (error) {
        console.error('Error deleting node:', error);
    }
}

async function handleSvgClick(event) {
    if (event.target.classList.contains('node')) {
        const nodeId = parseInt(event.target.dataset.nodeId);
        handleNodeClick(nodeId, event);
    } else if (event.target.classList.contains('edge-delete')) {
        const fromId = parseInt(event.target.dataset.from);
        const toId = parseInt(event.target.dataset.to);
        await deleteEdge(fromId, toId);
    }
}

async function handleNodeClick(nodeId, event) {
    event.stopPropagation();
    
    if (state.connectMode) {
        if (state.connectFrom === null) {
            state.connectFrom = nodeId;
            updateConnectStep();
            drawTopology();
        } else if (state.connectFrom !== nodeId) {
            await connectNodes(state.connectFrom, nodeId);
            state.connectFrom = null;
            state.connectMode = false;
            toggleConnectMode(); // Para actualizar UI
        }
    } else {
        state.selectedNode = nodeId;
        elements.deleteNodeBtn.classList.remove('hidden');
        elements.selectedNodeId.textContent = nodeId;
        drawTopology();
    }
}

async function connectNodes(fromId, toId) {
    try {
        const response = await fetch('/api/edges', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ from: fromId, to: toId })
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
        }
    } catch (error) {
        console.error('Error connecting nodes:', error);
    }
}

async function deleteEdge(fromId, toId) {
    try {
        const response = await fetch('/api/edges/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ from: fromId, to: toId })
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
        }
    } catch (error) {
        console.error('Error deleting edge:', error);
    }
}

function handleMouseDown(event) {
    if (!event.target.classList.contains('node') || state.connectMode) return;
    
    const nodeId = parseInt(event.target.dataset.nodeId);
    const node = state.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    const rect = elements.svg.getBoundingClientRect();
    const point = elements.svg.createSVGPoint();
    point.x = event.clientX - rect.left;
    point.y = event.clientY - rect.top;
    
    state.draggingNode = nodeId;
    state.dragOffset = {
        x: point.x - node.x,
        y: point.y - node.y
    };
}

async function handleMouseMove(event) {
    if (!state.draggingNode) return;
    
    const rect = elements.svg.getBoundingClientRect();
    const point = elements.svg.createSVGPoint();
    point.x = event.clientX - rect.left;
    point.y = event.clientY - rect.top;
    
    const newX = point.x - state.dragOffset.x;
    const newY = point.y - state.dragOffset.y;
    
    // Actualizar posición localmente para respuesta inmediata
    const node = state.nodes.find(n => n.id === state.draggingNode);
    if (node) {
        node.x = newX;
        node.y = newY;
        drawTopology();
    }
}

async function handleMouseUp() {
    if (!state.draggingNode) return;
    
    // Sincronizar con el servidor
    const node = state.nodes.find(n => n.id === state.draggingNode);
    if (node) {
        try {
            await fetch(`/api/nodes/${state.draggingNode}/move`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    x: node.x,
                    y: node.y
                })
            });
        } catch (error) {
            console.error('Error moving node:', error);
        }
    }
    
    state.draggingNode = null;
}

function drawTopology() {
    // Limpiar SVG
    elements.svg.innerHTML = '';
    
    // Dibujar conexiones
    state.edges.forEach(edge => {
        const fromNode = state.nodes.find(n => n.id === edge.from);
        const toNode = state.nodes.find(n => n.id === edge.to);
        
        if (fromNode && toNode) {
            // Línea de conexión
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', fromNode.x);
            line.setAttribute('y1', fromNode.y);
            line.setAttribute('x2', toNode.x);
            line.setAttribute('y2', toNode.y);
            line.setAttribute('stroke', '#94a3b8');
            line.setAttribute('stroke-width', '2');
            elements.svg.appendChild(line);
            
            // Punto para eliminar conexión (en el medio)
            const midX = (fromNode.x + toNode.x) / 2;
            const midY = (fromNode.y + toNode.y) / 2;
            
            const deleteCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            deleteCircle.setAttribute('cx', midX);
            deleteCircle.setAttribute('cy', midY);
            deleteCircle.setAttribute('r', '8');
            deleteCircle.setAttribute('fill', '#ef4444');
            deleteCircle.setAttribute('opacity', '0');
            deleteCircle.classList.add('edge-delete');
            deleteCircle.dataset.from = edge.from;
            deleteCircle.dataset.to = edge.to;
            deleteCircle.style.cursor = 'pointer';
            deleteCircle.addEventListener('mouseenter', () => {
                deleteCircle.setAttribute('opacity', '0.8');
            });
            deleteCircle.addEventListener('mouseleave', () => {
                deleteCircle.setAttribute('opacity', '0');
            });
            elements.svg.appendChild(deleteCircle);
        }
    });
    
    // Dibujar nodos
    state.nodes.forEach(node => {
        const isSelected = state.selectedNode === node.id;
        const isConnecting = state.connectFrom === node.id;
        const isDragging = state.draggingNode === node.id;
        
        let color = '#3b82f6'; // blue-500
        if (isSelected) color = '#ef4444'; // red-500
        if (isConnecting) color = '#22c55e'; // green-500
        if (isDragging) color = '#eab308'; // yellow-500
        
        // Círculo del nodo
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', node.x);
        circle.setAttribute('cy', node.y);
        circle.setAttribute('r', '30');
        circle.setAttribute('fill', color);
        circle.setAttribute('stroke', isSelected || isConnecting ? '#ffffff' : 'none');
        circle.setAttribute('stroke-width', '3');
        circle.classList.add('node');
        circle.dataset.nodeId = node.id;
        circle.style.cursor = isDragging ? 'grabbing' : 'grab';
        elements.svg.appendChild(circle);
        
        // Texto de la VM (usando foreignObject para HTML)
        const foreignObject = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
        foreignObject.setAttribute('x', node.x - 15);
        foreignObject.setAttribute('y', node.y - 15);
        foreignObject.setAttribute('width', '30');
        foreignObject.setAttribute('height', '30');
        foreignObject.style.pointerEvents = 'none';
        
        const div = document.createElement('div');
        div.className = 'flex items-center justify-center h-full';
        div.innerHTML = '<i data-lucide="server" class="w-4 h-4 text-white"></i>';
        foreignObject.appendChild(div);
        elements.svg.appendChild(foreignObject);
        
        // Etiqueta del nodo
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', node.x);
        text.setAttribute('y', node.y + 50);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'text-xs font-semibold fill-gray-700 select-none');
        text.textContent = node.label;
        elements.svg.appendChild(text);
    });
    
    // Actualizar estadísticas
    elements.nodeCountDisplay.textContent = state.nodes.length;
    elements.edgeCountDisplay.textContent = state.edges.length;
    
    // Mostrar/ocultar estado vacío
    if (state.nodes.length === 0) {
        elements.emptyState.classList.remove('hidden');
    } else {
        elements.emptyState.classList.add('hidden');
    }
    
    // Actualizar botón de eliminar
    if (state.selectedNode) {
        elements.deleteNodeBtn.classList.remove('hidden');
    } else {
        elements.deleteNodeBtn.classList.add('hidden');
    }
    
    // Re-inicializar íconos de Lucide
    lucide.createIcons();
}

async function loadTopologyState() {
    try {
        const response = await fetch('/api/topology/state');
        const data = await response.json();
        state.nodes = data.nodes;
        state.edges = data.edges;
        drawTopology();
    } catch (error) {
        console.error('Error loading topology state:', error);
    }
}

// Inicializar UI
updateUI();