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

// Variables para zoom y pan - SIN LÍMITES
let scale = 1;
let translateX = 0;
let translateY = 0;
let isPanning = false;
let startPanX, startPanY;

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
    svg: document.getElementById('network-svg'),
    exportBtn: document.getElementById('export-btn'),
    clearBtn: document.getElementById('clear-btn'), // Nuevo: botón limpiar
    svgContainer: document.querySelector('.svg-container')
};

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar íconos de Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // Configurar SVG para área infinita
    setupInfiniteCanvas();
    
    // Cargar estado inicial del servidor
    loadTopologyState();
    
    // Configurar event listeners
    setupEventListeners();
    
    // Aplicar transformación inicial
    applyZoom();
});

// NUEVA FUNCIÓN: Configurar canvas infinito
function setupInfiniteCanvas() {
    // Hacer el SVG extremadamente grande para simular área infinita
    elements.svg.setAttribute('width', '10000');
    elements.svg.setAttribute('height', '10000');
    elements.svg.setAttribute('viewBox', '0 0 10000 10000');
    
    // Estilo para permitir área infinita
    elements.svg.style.minWidth = '100%';
    elements.svg.style.minHeight = '100%';
    elements.svg.style.overflow = 'visible';
}

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
    
    // Botón de exportación
    if (elements.exportBtn) {
        elements.exportBtn.addEventListener('click', exportTopology);
    }
    
    // NUEVO: Botón de limpiar todo
    if (elements.clearBtn) {
        elements.clearBtn.addEventListener('click', clearAll);
    }
    
    // Controles de zoom
    document.getElementById('zoom-in').addEventListener('click', zoomIn);
    document.getElementById('zoom-out').addEventListener('click', zoomOut);
    document.getElementById('zoom-reset').addEventListener('click', resetZoom);
    
    // Zoom con rueda del mouse - MEJORADO
    elements.svgContainer.addEventListener('wheel', handleWheel, { passive: false });
    
    // Pan (arrastrar) - MEJORADO
    elements.svgContainer.addEventListener('mousedown', startPan);
    document.addEventListener('mousemove', doPan);
    document.addEventListener('mouseup', stopPan);
    
    // Eventos del SVG
    elements.svg.addEventListener('click', handleSvgClick);
    elements.svg.addEventListener('mousedown', handleMouseDown);
    elements.svg.addEventListener('mousemove', handleMouseMove);
    elements.svg.addEventListener('mouseup', handleMouseUp);
    elements.svg.addEventListener('mouseleave', handleMouseUp);
}

// NUEVA FUNCIÓN: Limpiar toda la topología
async function clearAll() {
    if (state.nodes.length === 0) {
        showNotification('No hay nada que limpiar', 'info');
        return;
    }
    
    if (!confirm('¿Estás seguro de que quieres eliminar toda la topología? Esta acción no se puede deshacer.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/topology/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            state.selectedNode = null;
            state.connectMode = false;
            state.connectFrom = null;
            
            // Resetear UI
            elements.deleteNodeBtn.classList.add('hidden');
            elements.connectModeIndicator.classList.add('hidden');
            elements.connectBtn.textContent = 'Conectar VMs';
            elements.connectBtn.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
            elements.connectBtn.classList.add('bg-purple-600', 'hover:bg-purple-700');
            
            // Resetear vista
            scale = 1;
            translateX = 0;
            translateY = 0;
            
            drawTopology();
            applyZoom();
            
            showNotification('Topología limpiada exitosamente', 'success');
        }
    } catch (error) {
        console.error('Error clearing topology:', error);
        showNotification('Error al limpiar la topología', 'error');
    }
}

// Funciones de zoom y pan - MEJORADAS para área infinita
function zoomIn() {
    scale *= 1.2;
    applyZoom();
}

function zoomOut() {
    scale /= 1.2;
    applyZoom();
}

function resetZoom() {
    scale = 1.2; // Un poco de zoom por defecto para mejor visibilidad
    translateX = -4000 * scale + (elements.svgContainer.clientWidth / 2);
    translateY = -4000 * scale + (elements.svgContainer.clientHeight / 2);
    applyZoom();
}

function applyZoom() {
    // Aplicar transformación al grupo interno en lugar del SVG completo
    let svgGroup = elements.svg.querySelector('#svg-content-group');
    if (!svgGroup) {
        // Crear grupo si no existe
        svgGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        svgGroup.id = 'svg-content-group';
        
        // Mover todo el contenido existente al grupo
        while (elements.svg.firstChild) {
            svgGroup.appendChild(elements.svg.firstChild);
        }
        elements.svg.appendChild(svgGroup);
    }
    
    svgGroup.setAttribute('transform', `translate(${translateX}, ${translateY}) scale(${scale})`);
    document.getElementById('zoom-reset').textContent = `${Math.round(scale * 100)}%`;
}

function handleWheel(event) {
    event.preventDefault();
    
    const rect = elements.svgContainer.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    const delta = -Math.sign(event.deltaY);
    const zoomFactor = 1.1;
    
    // Calcular nueva escala
    const newScale = delta > 0 ? scale * zoomFactor : scale / zoomFactor;
    
    // Calcular desplazamiento para mantener el punto del mouse fijo
    translateX -= (mouseX - translateX) * (newScale/scale - 1);
    translateY -= (mouseY - translateY) * (newScale/scale - 1);
    
    scale = newScale;
    applyZoom();
}

function startPan(event) {
    // Solo iniciar pan si no se está haciendo clic en un nodo y no estamos en modo conexión
    if (!event.target.classList.contains('node') && !state.connectMode) {
        isPanning = true;
        startPanX = event.clientX - translateX;
        startPanY = event.clientY - translateY;
        elements.svgContainer.style.cursor = 'grabbing';
        event.preventDefault();
    }
}

function doPan(event) {
    if (!isPanning) return;
    
    translateX = event.clientX - startPanX;
    translateY = event.clientY - startPanY;
    applyZoom();
}

function stopPan() {
    isPanning = false;
    elements.svgContainer.style.cursor = 'grab';
}

// Exportar SIN coords desde el backend
async function exportTopology() {
  try {
    const res = await fetch('/api/topology/export', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    a.href = URL.createObjectURL(blob);
    a.download = `topologia-deploy-${ts}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);

    showNotification('Topología exportada (deploy) desde backend', 'success');
  } catch (e) {
    console.error('Error exportando:', e);
    showNotification('Error al exportar la topología', 'error');
  }
}


// FUNCIÓN MEJORADA: Mostrar notificaciones
function showNotification(message, type = 'info') {
    // Crear notificación temporal
    const notification = document.createElement('div');
    
    let bgColor = 'bg-blue-500';
    let icon = 'info';
    
    switch(type) {
        case 'success':
            bgColor = 'bg-green-500';
            icon = 'check-circle';
            break;
        case 'error':
            bgColor = 'bg-red-500';
            icon = 'alert-circle';
            break;
        case 'warning':
            bgColor = 'bg-yellow-500';
            icon = 'alert-triangle';
            break;
        default:
            bgColor = 'bg-blue-500';
            icon = 'info';
    }
    
    notification.className = `fixed top-4 right-4 ${bgColor} text-white px-4 py-2 rounded-lg shadow-lg z-50 notification`;
    notification.innerHTML = `
        <div class="flex items-center gap-2">
            <i data-lucide="${icon}" class="w-5 h-5"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Re-inicializar íconos
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // Remover después de 3 segundos
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
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

  // 1) Fijar AZ del slice
  const placement = getSelectedAZSingle();
  try {
    await fetch('/api/placement/az', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(placement)
    });
  } catch (e) {
    console.warn('No se pudo guardar placement AZ, continúo con automático:', e);
  }

  // (opcional) si implementaste el paso inline:
  // config.placement = placement;

  // 2) Generar topología
  try {
    const response = await fetch('/api/topology/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: topologyType, config })
    });

    const data = await response.json();
    if (data.success) {
      state.nodes = data.topology.nodes;
      state.edges = data.topology.edges;
      drawTopology();
      setTimeout(() => perfectCenterTopology(), 50);
      showNotification(`Topología ${topologyType} generada`, 'success');
    }
  } catch (error) {
    console.error('Error generating topology:', error);
    showNotification('Error al generar la topología', 'error');
  }
}


function perfectCenterTopology() {
    if (state.nodes.length === 0) return;
    
    // Calcular el área ocupada por todos los nodos
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    state.nodes.forEach(node => {
        minX = Math.min(minX, node.x - 40); // Incluir radio del nodo
        maxX = Math.max(maxX, node.x + 40);
        minY = Math.min(minY, node.y - 40);
        maxY = Math.max(maxY, node.y + 40);
    });
    
    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;
    const contentCenterX = (minX + maxX) / 2;
    const contentCenterY = (minY + maxY) / 2;
    
    // Obtener dimensiones del contenedor visible
    const container = elements.svgContainer;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    
    // Calcular escala para que la topología ocupe ~70% del área visible
    const targetScaleX = (containerWidth * 0.7) / contentWidth;
    const targetScaleY = (containerHeight * 0.7) / contentHeight;
    const targetScale = Math.min(targetScaleX, targetScaleY, 2.5); // Limitar zoom máximo
    
    // Calcular traslación para centrar perfectamente
    const targetTranslateX = (containerWidth / 2) - (contentCenterX * targetScale);
    const targetTranslateY = (containerHeight / 2) - (contentCenterY * targetScale);
    
    // Aplicar suavemente la nueva vista
    scale = targetScale;
    translateX = targetTranslateX;
    translateY = targetTranslateY;
    
    applyZoom();
}

// NUEVA FUNCIÓN: Ajustar la vista para que quepa toda la topología
function fitViewToTopology() {
    if (state.nodes.length === 0) return;
    
    // Calcular el bounding box de todos los nodos
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    state.nodes.forEach(node => {
        minX = Math.min(minX, node.x);
        maxX = Math.max(maxX, node.x);
        minY = Math.min(minY, node.y);
        maxY = Math.max(maxY, node.y);
    });
    
    // Agregar margen
    const margin = 200;
    minX -= margin;
    maxX += margin;
    minY -= margin;
    maxY += margin;
    
    const width = maxX - minX;
    const height = maxY - minY;
    
    // Obtener dimensiones del contenedor
    const containerWidth = elements.svgContainer.clientWidth;
    const containerHeight = elements.svgContainer.clientHeight;
    
    // Calcular escala para que quepa en el contenedor
    const scaleX = containerWidth / width;
    const scaleY = containerHeight / height;
    const newScale = Math.min(scaleX, scaleY, 2); // Limitar zoom máximo a 2x
    
    // Calcular traslación para centrar
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    
    translateX = containerWidth / 2 - centerX * newScale;
    translateY = containerHeight / 2 - centerY * newScale;
    scale = newScale;
    
    applyZoom();
}

async function addRandomNode() {
    // Usar coordenadas cerca del centro pero con variación mínima
    const x = 5000 + (Math.random() - 0.5) * 200;
    const y = 5000 + (Math.random() - 0.5) * 200;
    
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
            
            // Centrar si hay pocos nodos
            if (state.nodes.length <= 3) {
                setTimeout(perfectCenterTopology, 50);
            }
            
            showNotification('VM agregada exitosamente', 'success');
        }
    } catch (error) {
        console.error('Error adding node:', error);
        showNotification('Error al agregar la VM', 'error');
    }
}

function centerViewOnTopology() {
    // Calcular el centro aproximado de los nodos
    if (state.nodes.length > 0) {
        const avgX = state.nodes.reduce((sum, node) => sum + node.x, 0) / state.nodes.length;
        const avgY = state.nodes.reduce((sum, node) => sum + node.y, 0) / state.nodes.length;
        
        // Ajustar la vista para centrar en el promedio
        // Esto es aproximado, podrías hacer un cálculo más preciso del bounding box
        translateX = -avgX * scale + (elements.svgContainer.clientWidth / 2);
        translateY = -avgY * scale + (elements.svgContainer.clientHeight / 2);
        applyZoom();
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
        showNotification('Modo conexión activado. Selecciona la VM de origen.', 'info');
    } else {
        elements.connectBtn.textContent = 'Conectar VMs';
        elements.connectBtn.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
        elements.connectBtn.classList.add('bg-purple-600', 'hover:bg-purple-700');
        elements.connectModeIndicator.classList.add('hidden');
        showNotification('Modo conexión desactivado', 'info');
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
            showNotification('VM eliminada exitosamente', 'success');
        }
    } catch (error) {
        console.error('Error deleting node:', error);
        showNotification('Error al eliminar la VM', 'error');
    }
}

function handleSvgClick(event) {
    if (event.target.classList.contains('node')) {
        const nodeId = parseInt(event.target.dataset.nodeId);
        handleNodeClick(nodeId, event);
    } else if (event.target.classList.contains('edge-delete')) {
        const fromId = parseInt(event.target.dataset.from);
        const toId = parseInt(event.target.dataset.to);
        deleteEdge(fromId, toId);
    }
}

function handleNodeClick(nodeId, event) {
    event.stopPropagation();
    
    if (state.connectMode) {
        if (state.connectFrom === null) {
            state.connectFrom = nodeId;
            updateConnectStep();
            drawTopology();
            showNotification(`VM ${nodeId} seleccionada como origen. Ahora selecciona la VM destino.`, 'info');
        } else if (state.connectFrom !== nodeId) {
            connectNodes(state.connectFrom, nodeId);
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
            showNotification(`Conexión establecida entre VM-${fromId} y VM-${toId}`, 'success');
        } else {
            showNotification('No se pudo establecer la conexión. Las VMs ya pueden estar conectadas.', 'warning');
        }
    } catch (error) {
        console.error('Error connecting nodes:', error);
        showNotification('Error al conectar las VMs', 'error');
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
            showNotification(`Conexión eliminada entre VM-${fromId} y VM-${toId}`, 'success');
        }
    } catch (error) {
        console.error('Error deleting edge:', error);
        showNotification('Error al eliminar la conexión', 'error');
    }
}

function handleMouseDown(event) {
    if (!event.target.classList.contains('node') || state.connectMode) return;
    
    const nodeId = parseInt(event.target.dataset.nodeId);
    const node = state.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    // Obtener las coordenadas del mouse ajustadas por el zoom y pan
    const rect = elements.svg.getBoundingClientRect();
    const point = elements.svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const svgPoint = point.matrixTransform(elements.svg.getScreenCTM().inverse());
    
    const mouseX = svgPoint.x;
    const mouseY = svgPoint.y;
    
    state.draggingNode = nodeId;
    state.dragOffset = {
        x: mouseX - node.x,
        y: mouseY - node.y
    };
    
    // Prevenir que se active el pan cuando se arrastra un nodo
    event.stopPropagation();
}

function handleMouseMove(event) {
    if (!state.draggingNode) return;
    
    // Obtener las coordenadas del mouse en el sistema de coordenadas del SVG
    const rect = elements.svg.getBoundingClientRect();
    const point = elements.svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const svgPoint = point.matrixTransform(elements.svg.getScreenCTM().inverse());
    
    const mouseX = svgPoint.x;
    const mouseY = svgPoint.y;
    
    const newX = mouseX - state.dragOffset.x;
    const newY = mouseY - state.dragOffset.y;
    
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
    
    // Crear grupo para todo el contenido
    const svgGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    svgGroup.id = 'svg-content-group';
    svgGroup.setAttribute('transform', `translate(${translateX}, ${translateY}) scale(${scale})`);
    
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
            svgGroup.appendChild(line);
            
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
            svgGroup.appendChild(deleteCircle);
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
        circle.style.cursor = 'pointer';
        svgGroup.appendChild(circle);
        
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
        svgGroup.appendChild(foreignObject);
        
        // Etiqueta del nodo
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', node.x);
        text.setAttribute('y', node.y + 50);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'text-xs font-semibold fill-gray-700 select-none');
        text.textContent = node.label;
        svgGroup.appendChild(text);
    });
    
    // Agregar grupo al SVG
    elements.svg.appendChild(svgGroup);
    
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
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
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
function getSelectedAZSingle() {
  const checked = document.querySelector('input[name="slice-az"]:checked');
  const val = (checked && checked.value) || "";
  // "" => automático -> az: null
  return { az: val === "" ? null : val };
}


// Inicializar UI
updateUI();