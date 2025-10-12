// Función para obtener headers con JWT
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.error('❌ NO HAY TOKEN JWT EN LOCALSTORAGE!');
        window.location.href = '/login';
        return {};
    }
    console.log('✅ Token JWT encontrado:', token.substring(0, 20) + '...');
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

// Función para validar flavor antes de enviar al backend
function validateFlavor(flavor) {
    const vcpus = parseInt(flavor.vcpus);
    const ram = parseFloat(flavor.ram);
    const disk = parseFloat(flavor.disk);

    if (isNaN(vcpus) || vcpus < 1 || vcpus > 4) {
        return { valid: false, error: "vCPUs debe ser un número entero entre 1 y 4" };
    }

    if (isNaN(ram) || ram < 0.5 || ram > 4 || (ram * 2) % 1 !== 0) {
        return { valid: false, error: "RAM debe ser entre 0.5 y 4 GB (múltiplos de 0.5)" };
    }

    // Ahora permite decimales para disco
    if (isNaN(disk) || disk < 1 || disk > 10) {
        return { valid: false, error: "Disco debe ser un número entre 1 y 10 GB" };
    }

    return { valid: true };
}

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
    exportSvgBtn: document.getElementById('export-svg-btn'),
    exportPngBtn: document.getElementById('export-png-btn'),
    clearBtn: document.getElementById('clear-btn'),
    svgContainer: document.querySelector('.svg-container'),
    selectedVmPanel: document.getElementById('selected-vm-panel')
};

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    lucide.createIcons();
    setupInfiniteCanvas();
    loadTopologyState();
    setupEventListeners();
    setupAZListeners();
    initializeDefaultAZ();
    applyZoom();
});

// NUEVA FUNCIÓN: Configurar canvas infinito
function setupInfiniteCanvas() {
    elements.svg.setAttribute('width', '10000');
    elements.svg.setAttribute('height', '10000');
    elements.svg.setAttribute('viewBox', '0 0 10000 10000');
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
    elements.clearBtn.addEventListener('click', clearAll);
    
    // Controles de zoom
    document.getElementById('zoom-in').addEventListener('click', zoomIn);
    document.getElementById('zoom-out').addEventListener('click', zoomOut);
    document.getElementById('zoom-reset').addEventListener('click', resetZoom);
    
    // Eventos del mouse
    elements.svgContainer.addEventListener('wheel', handleWheel, { passive: false });
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

// NUEVA FUNCIÓN: Configurar listeners para Availability Zone
function setupAZListeners() {
    const azRadios = document.querySelectorAll('input[name="slice-az"]');
    azRadios.forEach(radio => {
        radio.addEventListener('change', async function() {
            const azValue = this.value;

            try {
                const response = await fetch('/api/placement/az', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ az: azValue === "" ? null : azValue })
                });

                const data = await response.json();
                if (data.success) {
                    showNotification(`Zona de disponibilidad establecida: ${azValue || 'Automático'}`, 'success');
                } else {
                    showNotification('Error al establecer AZ: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('Error setting AZ:', error);
                showNotification('Error al establecer la zona de disponibilidad', 'error');
            }
        });
    });
}

// NUEVA FUNCIÓN: Establecer AZ por defecto al cargar la página
async function initializeDefaultAZ() {
    try {
        // Establecer linux-AZ-1 como zona de disponibilidad por defecto
        await fetch('/api/placement/az', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ az: 'linux-AZ-1' })
        });
        console.log('Zona de disponibilidad por defecto establecida: linux-AZ-1');
    } catch (error) {
        console.error('Error estableciendo AZ por defecto:', error);
    }
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
            headers: getAuthHeaders()
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
            elements.selectedVmConfig.classList.add('hidden');
            
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

// Exportar como SVG
function exportAsSVG() {
    const svgElement = document.getElementById('network-svg');
    const serializer = new XMLSerializer();
    let svgString = serializer.serializeToString(svgElement);
    
    // Añadir declaración XML
    svgString = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + svgString;
    
    // Crear blob y descargar
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'topology.svg';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('SVG exportado exitosamente', 'success');
}

// Exportar como PNG
function exportAsPNG() {
    const svgElement = document.getElementById('network-svg');
    const serializer = new XMLSerializer();
    let svgString = serializer.serializeToString(svgElement);
    
    // Añadir declaración XML
    svgString = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + svgString;
    
    // Crear canvas para convertir SVG a PNG
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(svgBlob);
    
    const img = new Image();
    img.onload = function() {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        
        // Descargar PNG
        const pngUrl = canvas.toDataURL('image/png');
        const a = document.createElement('a');
        a.href = pngUrl;
        a.download = 'topology.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showNotification('PNG exportado exitosamente', 'success');
    };
    
    img.src = url;
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

    // Fijar AZ del slice
    const placement = getSelectedAZSingle();
    try {
        await fetch('/api/placement/az', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(placement)
        });
    } catch (e) {
        console.warn('No se pudo guardar placement AZ:', e);
    }

    // Generar topología
    try {
        const response = await fetch('/api/topology/generate', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ type: topologyType, config })
        });

        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
            setTimeout(() => perfectCenterTopology(), 50);
            showNotification(`Topología ${topologyType} generada`, 'success');
        } else {
            showNotification('Error al generar la topología: ' + data.error, 'error');
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

    // MEJORADO: Calcular escala con límites más razonables
    const targetScaleX = (containerWidth * 0.7) / contentWidth;
    const targetScaleY = (containerHeight * 0.7) / contentHeight;

    // Limitar zoom: mínimo 0.3 (no muy chico), máximo 2.5 (no muy grande)
    const targetScale = Math.min(Math.max(targetScaleX, targetScaleY, 0.3), 2.5);

    // Calcular traslación para centrar perfectamente
    const targetTranslateX = (containerWidth / 2) - (contentCenterX * targetScale);
    const targetTranslateY = (containerHeight / 2) - (contentCenterY * targetScale);

    // Aplicar suavemente la nueva vista
    scale = targetScale;
    translateX = targetTranslateX;
    translateY = targetTranslateY;

    applyZoom();

    console.log(`✅ Topología centrada: scale=${targetScale.toFixed(2)}, nodes=${state.nodes.length}`);
}

async function addRandomNode() {
    let x, y;

    // Si ya hay nodos, calcular el centro y crear cerca de ahí
    if (state.nodes.length > 0) {
        let sumX = 0, sumY = 0;
        state.nodes.forEach(node => {
            sumX += node.x;
            sumY += node.y;
        });
        const centerX = sumX / state.nodes.length;
        const centerY = sumY / state.nodes.length;

        // Crear la nueva VM cerca del centro de los nodos existentes
        x = centerX + (Math.random() - 0.5) * 150;
        y = centerY + (Math.random() - 0.5) * 150;
    } else {
        // Si no hay nodos, crear en el centro del canvas
        x = 5000 + (Math.random() - 0.5) * 100;
        y = 5000 + (Math.random() - 0.5) * 100;
    }

    // Configuración de flavor por defecto
    const defaultFlavor = {
        vcpus: 1,
        ram: 0.5,
        disk: 1
    };

    // Validar el flavor por defecto
    const validation = validateFlavor(defaultFlavor);
    if (!validation.valid) {
        showNotification(validation.error, 'error');
        return;
    }

    try {
        const response = await fetch('/api/nodes', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                x,
                y,
                flavor: defaultFlavor,
                image: 'ubuntu',
                internet_access: false
            })
        });

        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();

            // Centrar SIEMPRE después de agregar un nodo para ajustar la vista
            setTimeout(perfectCenterTopology, 50);

            showNotification('VM agregada exitosamente', 'success');
        } else {
            showNotification('Error al agregar VM: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error adding node:', error);
        showNotification('Error al agregar la VM', 'error');
    }
}

function toggleConnectMode() {
    state.connectMode = !state.connectMode;
    state.connectFrom = null;
    
    if (state.connectMode) {
        elements.connectBtn.textContent = 'Cancelar Conexión';
        elements.connectBtn.classList.remove('bg-purple-600', 'hover:bg-purple-700');
        elements.connectBtn.classList.add('bg-red-600', 'hover:bg-red-700');
        elements.connectModeIndicator.classList.remove('hidden');
        updateConnectStep();
        showNotification('Modo conexión activado. Selecciona la VM de origen.', 'info');
    } else {
        elements.connectBtn.textContent = 'Conectar VMs';
        elements.connectBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
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
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        if (data.success) {
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            state.selectedNode = null;
            elements.selectedVmConfig.classList.add('hidden');
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
    } else {
        // Clic fuera de un nodo - deseleccionar
        state.selectedNode = null;
        elements.selectedVmPanel.classList.add('hidden');
        drawTopology();
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
            toggleConnectMode();
        }
    } else {
        state.selectedNode = nodeId;
        
        // Mostrar configuración de la VM seleccionada
        if (typeof window.showSelectedVMConfig === 'function') {
            window.showSelectedVMConfig(nodeId);
        }
        
        drawTopology();
    }
}

async function connectNodes(fromId, toId) {
    try {
        const response = await fetch('/api/edges', {
            method: 'POST',
            headers: getAuthHeaders(),
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
            headers: getAuthHeaders(),
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
                headers: getAuthHeaders(),
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
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', fromNode.x);
            line.setAttribute('y1', fromNode.y);
            line.setAttribute('x2', toNode.x);
            line.setAttribute('y2', toNode.y);
            line.setAttribute('stroke', '#94a3b8');
            line.setAttribute('stroke-width', '2');
            svgGroup.appendChild(line);
            
            // Punto para eliminar conexión
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
            deleteCircle.addEventListener('mouseenter', () => deleteCircle.setAttribute('opacity', '0.8'));
            deleteCircle.addEventListener('mouseleave', () => deleteCircle.setAttribute('opacity', '0'));
            svgGroup.appendChild(deleteCircle);
        }
    });
    
    // Dibujar nodos
    state.nodes.forEach(node => {
        const isSelected = state.selectedNode === node.id;
        const isConnecting = state.connectFrom === node.id;
        
        let color = '#3b82f6';
        if (isSelected) color = '#ef4444';
        if (isConnecting) color = '#22c55e';
        
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
        
        // Tooltip con información del flavor
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `VM-${node.id}\n${node.flavor.vcpus} vCPU, ${node.flavor.ram}GB RAM, ${node.flavor.disk}GB Disk\nImagen: ${node.image || 'ubuntu'}\nInternet: ${node.internet_access !== false ? 'Sí' : 'No'}`;
        circle.appendChild(title);
        
        svgGroup.appendChild(circle);
        
        // Icono de servidor
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
    
    elements.svg.appendChild(svgGroup);
    elements.nodeCountDisplay.textContent = state.nodes.length;
    elements.edgeCountDisplay.textContent = state.edges.length;
    
    if (state.nodes.length === 0) {
        elements.emptyState.classList.remove('hidden');
    } else {
        elements.emptyState.classList.add('hidden');
    }
    
    lucide.createIcons();
}

async function loadTopologyState() {
    try {
        // Si tenemos template_data desde el servidor (estamos editando), usarlo
        if (typeof templateData !== 'undefined' && templateData !== null) {
            console.log('📝 Cargando topología desde plantilla:', templateName);
            state.nodes = templateData.nodes || [];
            state.edges = templateData.edges || [];

            // Sincronizar con el servidor - cargar la topología en el backend
            await fetch('/api/topology/sync', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    nodes: state.nodes,
                    edges: state.edges
                })
            });

            // Si hay nodos, centrar la topología
            if (state.nodes.length > 0) {
                drawTopology();
                setTimeout(() => perfectCenterTopology(), 200);
            } else {
                drawTopology();
            }

            // Si hay AZ de plantilla, seleccionarlo
            if (typeof templateAZ !== 'undefined' && templateAZ) {
                const radioBtn = document.querySelector(`input[name="slice-az"][value="${templateAZ}"]`);
                if (radioBtn) radioBtn.checked = true;
            }
        } else {
            // Si no hay template_data, es una NUEVA plantilla - limpiar estado
            console.log('✨ Nueva plantilla - limpiando estado');
            const response = await fetch('/api/topology/clear', {
                method: 'POST',
                headers: getAuthHeaders()
            });
            const data = await response.json();
            state.nodes = data.topology.nodes;
            state.edges = data.topology.edges;
            drawTopology();
        }
    } catch (error) {
        console.error('Error loading topology state:', error);
        // Si falla, inicializar vacío
        state.nodes = [];
        state.edges = [];
        drawTopology();
    }
}

function getSelectedAZSingle() {
    const checked = document.querySelector('input[name="slice-az"]:checked');
    const val = (checked && checked.value) || "";
    return { az: val === "" ? null : val };
}

// Inicializar UI
updateUI();