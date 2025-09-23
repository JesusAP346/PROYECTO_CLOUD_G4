#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
menu.py
Base de menús (texto) para un orquestador tipo Cloud con 3 roles:
- Común
- VIP
- Administrador
Proyecto: PUCP Private Open Cloud Orchestrator
El objetivo es servir como "esqueleto" para implementar luego
las funciones reales. Por ahora, TODO imprime "aún no implementado".
"""
from __future__ import annotations
import os
import sys
import subprocess
import platform
from typing import Optional, List, Dict
from graphviz import Graph
import json

# ---------------------- Utilidades básicas ----------------------
def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')

def pause(msg: str = "\nPresiona Enter para continuar...") -> None:
    input(msg)

def read_int(prompt: str, min_v: Optional[int] = None, max_v: Optional[int] = None) -> int:
    while True:
        try:
            val = int(input(prompt))
            if (min_v is not None and val < min_v) or (max_v is not None and val > max_v):
                raise ValueError()
            return val
        except ValueError:
            rango = ""
            if min_v is not None and max_v is not None:
                rango = f" entre {min_v} y {max_v}"
            elif min_v is not None:
                rango = f" (mínimo {min_v})"
            elif max_v is not None:
                rango = f" (máximo {max_v})"
            print(f"❌ Ingresa un número válido{rango}.")

def read_str(prompt: str, allow_empty: bool = False) -> str:
    while True:
        s = input(prompt).strip()
        if s or allow_empty:
            return s
        print("❌ El campo no puede estar vacío.")

def not_impl(feature: str) -> None:
    print(f"\n⚠️  {feature}: aún no implementado.")
    pause()

# ------------------------ Modelos simples ------------------------
class Role:
    COMUN = "comun"
    VIP = "vip"
    ADMIN = "administrador"

# Límites de recursos por rol (solo texto de referencia)
RESOURCE_LIMITS = {
    Role.COMUN: {"ram_gb": 4, "disk_gb": 40, "az": ["az-1"]},
    Role.VIP:   {"ram_gb": 16, "disk_gb": 200, "az": ["az-1", "az-2"]},
    Role.ADMIN: {"ram_gb": 64, "disk_gb": 1000, "az": ["az-1", "az-2", "az-3"]},
}

# Plantillas disponibles (bloques combinables)
TEMPLATES = [
    "Punto a Punto",
    "Estrella",
    "Anillo",
    "Árbol",
    "Bus",
    "Malla",
    "Libre (vacía)",
    "Mixta (combinada)",
]

# Simuladores de almacenamiento en memoria (solo para mostrar texto)
_FAKE_TOPOLOGIES: List[Dict] = []  # cada elemento: {"id": int, "nombre": str, "propietario": str, "plantillas": [str]}

def _next_topology_id() -> int:
    return (max([t["id"] for t in _FAKE_TOPOLOGIES], default=0) + 1)

# -------------------- Autenticación (solo texto) --------------------
def login_flow() -> Dict:
    """
    "Login" simplificado: se elige rol y usuario. No valida contraseñas.
    Regresa un dict con {"username": str, "role": str}
    """
    clear_screen()
    print("=" * 60)
    print("🌐  PUCP Private Open Cloud Orchestrator  🌐".center(60))
    print("     (Demo de menús por rol)".center(60))
    print("=" * 60)
    print("\nAntes de continuar, selecciona tu rol:")
    print("  1) Usuario común")
    print("  2) Usuario VIP")
    print("  3) Administrador")
    opt = read_int("\nElige 1/2/3: ", 1, 3)
    role = {1: Role.COMUN, 2: Role.VIP, 3: Role.ADMIN}[opt]
    username = read_str("\nNombre de usuario: ")
    print(f"\n✅ Sesión iniciada como '{username}' con rol '{role}'.")
    pause()
    return {"username": username, "role": role}

# ------------------- ASCII ART VISUALIZATION -------------------
def ascii_block(title: str, art_lines: List[str]) -> str:
    """Devuelve un bloque con título y arte ASCII."""
    width = max(len(title), *(len(l) for l in art_lines)) + 4
    top = "┌" + "─" * (width - 2) + "┐"
    bottom = "└" + "─" * (width - 2) + "┘"
    center_title = f" {title} ".center(width - 2, " ")
    body = [f"│{center_title}│"]
    body.append("├" + "─" * (width - 2) + "┤")
    for l in art_lines:
        body.append("│ " + l.ljust(width - 3) + "│")
    return "\n".join([top] + body + [bottom])

def graphviz_preview_for(template: str, g: Graph, base: str = "") -> dict:
    """Añade un subgrafo a g según la plantilla seleccionada y devuelve todos los nodos."""
    prefix = base + template[:3]  # prefijo corto para nodos
    nodes = {}
    
    if template == "Punto a Punto":
        g.node(prefix+"A", "A")
        g.node(prefix+"B", "B")
        g.edge(prefix+"A", prefix+"B")
        nodes = {"A": prefix+"A", "B": prefix+"B"}
    
    elif template == "Estrella":
        g.node(prefix+"C", "C")
        nodes = {"C": prefix+"C"}
        for node in ["A", "B", "D", "E"]:
            g.node(prefix+node, node)
            g.edge(prefix+"C", prefix+node)
            nodes[node] = prefix+node
    
    elif template == "Anillo":
        node_list = [prefix+"A", prefix+"B", prefix+"C", prefix+"D"]
        for node in node_list:
            g.node(node, node[-1])
            nodes[node[-1]] = node
        for i in range(len(node_list)):
            g.edge(node_list[i], node_list[(i+1) % len(node_list)])
    
    elif template == "Árbol":
        g.node(prefix+"R", "R")
        nodes = {"R": prefix+"R"}
        for node in ["A", "B", "C", "D"]:
            g.node(prefix+node, node)
            nodes[node] = prefix+node
        g.edge(prefix+"R", prefix+"A")
        g.edge(prefix+"R", prefix+"B")
        g.edge(prefix+"B", prefix+"C")
        g.edge(prefix+"B", prefix+"D")
    
    elif template == "Bus":
        bus_nodes = [prefix+"A", prefix+"B", prefix+"C", prefix+"D"]
        for n in bus_nodes:
            g.node(n, n[-1])
            nodes[n[-1]] = n
        # Conectar en serie (bus)
        for i in range(len(bus_nodes)-1):
            g.edge(bus_nodes[i], bus_nodes[i+1])
    
    elif template == "Malla":
        node_list = [prefix+"A", prefix+"B", prefix+"C", prefix+"D"]
        for n in node_list:
            g.node(n, n[-1])
            nodes[n[-1]] = n
        # Conectar todos con todos
        for i in range(len(node_list)):
            for j in range(i+1, len(node_list)):
                g.edge(node_list[i], node_list[j])
    
    elif template == "Libre (vacía)":
        g.node(prefix+"X", "X", shape="plaintext")
        nodes = {"X": prefix+"X"}
    
    elif template == "Mixta (combinada)":
        g.node(prefix+"M", "Mixta", shape="plaintext")
        nodes = {"M": prefix+"M"}
    
    return nodes
def render_topology_graph(name: str, templates: list[str], union_label: str = "HUB", conexiones_personalizadas: List[Dict] = None) -> str:
    """Genera un archivo PNG con la topología combinada usando Graphviz."""
    try:
        g = Graph(name, format="png", engine='neato')
        g.attr(overlap="false")
        g.attr(splines="true")
        g.attr(rankdir="LR")
        g.attr(nodesep="0.5")
        g.attr(ranksep="1.0")

        if not templates:
            g.node("empty", "(sin bloques)", shape="plaintext")
        elif len(templates) == 1:
            graphviz_preview_for(templates[0], g)
        else:
            # Almacenar información de todos los nodos
            todos_los_nodos = {}
            
            for i, tpl in enumerate(templates, 1):
                prefix = f"{tpl[:3]}_{i}_"
                nodes = graphviz_preview_for(tpl, g, base=prefix)
                todos_los_nodos[tpl] = {"prefix": prefix, "nodes": nodes}
            
            # Manejar conexiones personalizadas o automáticas
            if conexiones_personalizadas:
                # Conexiones personalizadas
                for conexion in conexiones_personalizadas:
                    tpl_origen = conexion["bloque_origen"]
                    tpl_destino = conexion["bloque_destino"]
                    nodo_origen = conexion["nodo_origen"]
                    nodo_destino = conexion["nodo_destino"]
                    
                    # Encontrar los nodos reales
                    nodo_real_origen = todos_los_nodos[tpl_origen]["nodes"].get(nodo_origen)
                    nodo_real_destino = todos_los_nodos[tpl_destino]["nodes"].get(nodo_destino)
                    
                    if nodo_real_origen and nodo_real_destino:
                        g.edge(nodo_real_origen, nodo_real_destino, color="red", style="bold")
            else:
                # Conexión automática (comportamiento original)
                selected_nodes = []
                for i, tpl in enumerate(templates, 1):
                    prefix = f"{tpl[:3]}_{i}_"
                    nodes = graphviz_preview_for(tpl, g, base=prefix)
                    
                    if union_label in nodes:
                        selected_nodes.append(nodes[union_label])
                        g.node(nodes[union_label], f"{union_label}_{i}", shape="circle")
                
                if len(selected_nodes) > 1:
                    for i in range(len(selected_nodes) - 1):
                        g.edge(selected_nodes[i], selected_nodes[i + 1], color="blue")

        output_file = g.render(filename=f"topologia_{name}", cleanup=True, format="png")
        print(f"📊 Topología renderizada en: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ Error al renderizar la topología: {e}")
        return ""

def ascii_preview_for(template: str) -> str:
    """Arte ASCII simple por plantilla."""
    if template == "Punto a Punto":
        return ascii_block("Punto a Punto", ["A ---- B"])
    if template == "Estrella":
        return ascii_block("Estrella", [
            "    B",
            "    |",
            "D --C-- E",
            "    |",
            "    A"
        ])
    if template == "Anillo":
        return ascii_block("Anillo", [
            "A ---- B",
            "|      |",
            "D ---- C"
        ])
    if template == "Árbol":
        return ascii_block("Árbol", [
            "   R",
            "  / \\",
            " A   B",
            "    / \\",
            "   C   D"
        ])
    if template == "Bus":
        return ascii_block("Bus", [
            "A   B   C   D",
            "|   |   |   |",
            "──────────────"
        ])
    if template == "Malla":
        return ascii_block("Malla (4 nodos)", [
            "A ─── B",
            "│ ╲ ╱ │",
            "│ ╱ ╲ │",
            "D ─── C"
        ])
    if template == "Libre (vacía)":
        return ascii_block("Libre", ["(sin enlaces predefinidos)"])
    if template == "Mixta (combinada)":
        return ascii_block("Mixta", ["(combina varios patrones)"])
    return ascii_block(template, ["(vista no disponible)"])

def ascii_preview_summary(selected: List[str]) -> None:
    """Muestra vista previa concatenando bloques de cada plantilla seleccionada."""
    if not selected:
        print("\n[Vista previa ASCII] No hay bloques seleccionados.")
        return
    print("\n[Vista previa ASCII] Bloques activos:")
    for tpl in selected:
        print()
        print(ascii_preview_for(tpl))

def open_image(filename: str) -> None:
    """Intenta abrir la imagen con el visor predeterminado del sistema"""
    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.call(("open", filename))
        elif platform.system() == "Windows":  # Windows
            os.startfile(filename)
        else:  # Linux
            subprocess.call(("xdg-open", filename))
        print(f"✅ Imagen abierta: {filename}")
    except Exception as e:
        print(f"❌ No se pudo abrir la imagen: {e}")

# -------------------- Menús comunes / submenús --------------------
def show_templates_menu(selected: Optional[List[str]] = None) -> List[str]:
    """
    Submenú para seleccionar и mezclar plantillas como bloques.
    Se pueden elegir múltiples. Muestra feedback inmediato y vista ASCII.
    """
    if selected is None:
        selected = []
    while True:
        clear_screen()
        print("=" * 60)
        print("🧩  Biblioteca de plantillas / bloques  🧩".center(60))
        print("=" * 60)
        for i, name in enumerate(TEMPLATES, 1):
            mark = "✓" if name in selected else " "
            print(f"[{i}] [{mark}] {name}")
        print("\n[0] Listo (volver)")
        if selected:
            print("\nSeleccionadas:", ", ".join(selected))
            ascii_preview_summary(selected)
        choice = read_int("\nSelecciona una plantilla para añadir/quitar: ", 0, len(TEMPLATES))
        if choice == 0:
            return selected
        tpl = TEMPLATES[choice - 1]
        if tpl in selected:
            selected.remove(tpl)
            print(f"\n➖ Quitado: {tpl}")
        else:
            selected.append(tpl)
            print(f"\n➕ Añadido: {tpl}")
        # Mostrar breve vista del bloque añadido/quitado
        print()
        print(ascii_preview_for(tpl))
        pause("\n(Enter para continuar...)")

def export_topology_json(topo: Dict, filename: str = "topologia_export.json") -> None:
    """
    Exporta la topología simulada a un archivo JSON compatible con vis-network.
    Conecta específicamente los nodos del tipo especificado por el usuario.
    """
    # Mapeo de abreviaturas para cada tipo de topología
    abreviatura_topologia = {
        "Punto a Punto": "Punto",
        "Estrella": "Est",
        "Anillo": "Ani",
        "Árbol": "Árb",
        "Bus": "Bus",
        "Malla": "Mal",
        "Libre (vacía)": "Lib",
        "Mixta (combinada)": "Mix"
    }
    
    def plantilla_a_grafo(plantilla, base="", union_label="A"):
        nodes, edges = [], []
        # Usar abreviatura en lugar del prefijo genérico
        abreviatura = abreviatura_topologia.get(plantilla, plantilla[:3])
        prefix = f"{abreviatura}_{base}" if base else abreviatura
        connection_node = None
        
        if plantilla == "Punto a Punto":
            nodes += [f"{prefix}A", f"{prefix}B"]
            edges.append({"from": f"{prefix}A", "to": f"{prefix}B"})
            if union_label in ["A", "B"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}A"
                
        elif plantilla == "Estrella":
            nodes.append(f"{prefix}C")
            for node in ["A", "B", "D", "E"]:
                nodes.append(f"{prefix}{node}")
                edges.append({"from": f"{prefix}C", "to": f"{prefix}{node}"})
            if union_label in ["A", "B", "C", "D", "E"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}C"
                
        elif plantilla == "Anillo":
            nodes += [f"{prefix}A", f"{prefix}B", f"{prefix}C", f"{prefix}D"]
            edges += [
                {"from": f"{prefix}A", "to": f"{prefix}B"},
                {"from": f"{prefix}B", "to": f"{prefix}C"},
                {"from": f"{prefix}C", "to": f"{prefix}D"},
                {"from": f"{prefix}D", "to": f"{prefix}A"},
            ]
            if union_label in ["A", "B", "C", "D"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}A"
                
        elif plantilla == "Árbol":
            nodes += [f"{prefix}R", f"{prefix}A", f"{prefix}B", f"{prefix}C", f"{prefix}D"]
            edges += [
                {"from": f"{prefix}R", "to": f"{prefix}A"},
                {"from": f"{prefix}R", "to": f"{prefix}B"},
                {"from": f"{prefix}B", "to": f"{prefix}C"},
                {"from": f"{prefix}B", "to": f"{prefix}D"},
            ]
            if union_label in ["R", "A", "B", "C", "D"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}R"
                
        elif plantilla == "Bus":
            nodes += [f"{prefix}A", f"{prefix}B", f"{prefix}C", f"{prefix}D"]
            for i in range(len(nodes)-1):
                edges.append({"from": nodes[i], "to": nodes[i+1]})
            if union_label in ["A", "B", "C", "D"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}A"
                
        elif plantilla == "Malla":
            nodes += [f"{prefix}A", f"{prefix}B", f"{prefix}C", f"{prefix}D"]
            for i in range(len(nodes)):
                for j in range(i+1, len(nodes)):
                    edges.append({"from": nodes[i], "to": nodes[j]})
            if union_label in ["A", "B", "C", "D"]:
                connection_node = f"{prefix}{union_label}"
            else:
                connection_node = f"{prefix}A"
                
        elif plantilla == "Libre (vacía)":
            nodes.append(f"{prefix}X")
            connection_node = f"{prefix}X"
            
        elif plantilla == "Mixta (combinada)":
            nodes.append(f"{prefix}M")
            connection_node = f"{prefix}M"
            
        return nodes, edges, connection_node

    all_nodes, all_edges = [], []
    connection_nodes = []
    union_label = topo.get("union_label", "HUB")
    conexiones_personalizadas = topo.get("conexiones_personalizadas", [])
    
    if topo["plantillas"]:
        todos_los_nodos_info = {}
        
        for i, tpl in enumerate(topo["plantillas"], 1):
            base_prefix = f"{i}_"
            nodes, edges, connection_node = plantilla_a_grafo(tpl, base=base_prefix, union_label=union_label)
            all_nodes += nodes
            all_edges += edges
            connection_nodes.append(connection_node)
            todos_los_nodos_info[tpl] = {"prefix": base_prefix, "nodes": nodes, "abreviatura": abreviatura_topologia.get(tpl, tpl[:3])}
        
        if conexiones_personalizadas:
            for conexion in conexiones_personalizadas:
                tpl_origen = conexion["bloque_origen"]
                tpl_destino = conexion["bloque_destino"]
                nodo_origen = conexion["nodo_origen"]
                nodo_destino = conexion["nodo_destino"]
                
                # Encontrar los nodos reales con las abreviaturas correctas
                abrev_origen = todos_los_nodos_info[tpl_origen]["abreviatura"]
                abrev_destino = todos_los_nodos_info[tpl_destino]["abreviatura"]
                prefijo_origen = todos_los_nodos_info[tpl_origen]["prefix"]
                prefijo_destino = todos_los_nodos_info[tpl_destino]["prefix"]
                
                nodo_real_origen = f"{abrev_origen}_{prefijo_origen}{nodo_origen}"
                nodo_real_destino = f"{abrev_destino}_{prefijo_destino}{nodo_destino}"
                
                all_edges.append({"from": nodo_real_origen, "to": nodo_real_destino})
        else:
            if len(connection_nodes) > 1:
                for i in range(len(connection_nodes) - 1):
                    all_edges.append({"from": connection_nodes[i], "to": connection_nodes[i + 1]})
    else:
        all_nodes.append("empty")

    unique_nodes = []
    seen = set()
    for node in all_nodes:
        if node not in seen:
            seen.add(node)
            unique_nodes.append(node)
    
    nodes_json = [{"id": n, "label": n} for n in unique_nodes]
    edges_json = [{"from": e["from"], "to": e["to"]} for e in all_edges]

    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes_json, "edges": edges_json}, f, indent=2)
    print(f"🌐 Topología exportada a {filename}")

def create_topology_flow(user: Dict) -> None:
    """
    Flujo de creación de topología con selección de plantillas y
    configuración de conexiones personalizadas.
    """
    clear_screen()
    print("=== Crear topología ===")
    nombre = read_str("Nombre de la topología: ")
    bloques = show_templates_menu()
    
    conexiones_personalizadas = []
    union_label = "HUB"
    
    if not bloques:
        print("⚠️  No se seleccionaron plantillas. Se creará vacía.")
    else:
        print("📦 Bloques seleccionados:", ", ".join(bloques))
        ascii_preview_summary(bloques)
        
        # Si hay más de un bloque, permitir conexiones personalizadas
        if len(bloques) >= 2:
            print("\n🔗 Configuración de conexiones entre bloques:")
            print("1) Usar conexión automática (nodo central)")
            print("2) Configurar conexiones personalizadas")
            opcion = read_int("Elige opción (1/2): ", 1, 2)
            
            if opcion == 1:
                u = read_str("Elige el NODO DE UNIÓN para combinar bloques (por defecto 'HUB'): ", allow_empty=True)
                if u:
                    union_label = u
            else:
                # Configurar conexiones personalizadas
                conexiones_personalizadas = configurar_conexiones_personalizadas(bloques)
                union_label = "PERSONALIZADO"

    limits = RESOURCE_LIMITS[user["role"]]
    print("== Capacidades disponibles según tu rol ==")
    print(f"- RAM hasta:   {limits['ram_gb']} GB")
    print(f"- Disco hasta: {limits['disk_gb']} GB")
    print(f"- Zonas:       {', '.join(limits['az'])}")
    _ = read_str("Configura RAM (GB) [solo texto, ej. 2/4/8]: ")
    _ = read_str("Configura Disco (GB) [solo texto]: ")
    _ = read_str(f"Elige zona de disponibilidad {limits['az']} [solo texto]: ")

    # Guardado simulado
    topo_id = _next_topology_id()
    _FAKE_TOPOLOGIES.append({
        "id": topo_id,
        "nombre": nombre,
        "propietario": user["username"],
        "plantillas": bloques[:],
        "union_label": union_label,
        "conexiones_personalizadas": conexiones_personalizadas  # NUEVO
    })
    print(f"✅ Topología '{nombre}' (ID {topo_id}) registrada (simulada).")
    export_topology_json(_FAKE_TOPOLOGIES[-1])

    # 🚀 Render con Graphviz
    output_file = render_topology_graph(nombre, bloques, union_label, conexiones_personalizadas)
    if output_file:
        abrir = read_str("¿Deseas abrir la imagen de la topología? (s/n): ").lower()
        if abrir == 's':
            open_image(output_file)

    pause()

def configurar_conexiones_personalizadas(bloques: List[str]) -> List[Dict]:
    """Permite al usuario configurar conexiones específicas entre nodos de diferentes bloques."""
    conexiones = []
    
    print("\n🎯 Configuración de conexiones personalizadas")
    print("Puedes conectar cualquier nodo de un bloque con cualquier nodo de otro bloque.")
    
    # Validar que hay al menos dos bloques para conectar
    if len(bloques) < 2:
        print("❌ Se necesitan al menos dos bloques para configurar conexiones personalizadas.")
        return conexiones
    
    for i in range(len(bloques) - 1):
        for j in range(i + 1, len(bloques)):
            print(f"\n--- Conexiones entre {bloques[i]} y {bloques[j]} ---")
            while True:
                # Mostrar nodos disponibles en el primer bloque
                print(f"Nodos disponibles en {bloques[i]}:")
                nodos_bloque1 = obtener_nodos_disponibles(bloques[i])
                for idx, nodo in enumerate(nodos_bloque1, 1):
                    print(f"  {idx}) {nodo}")
                
                nodo1_idx = read_int(f"Selecciona nodo de {bloques[i]} (1-{len(nodos_bloque1)}): ", 1, len(nodos_bloque1))
                nodo1 = nodos_bloque1[nodo1_idx - 1]
                
                # Mostrar nodos disponibles en el segundo bloque
                print(f"Nodos disponibles en {bloques[j]}:")
                nodos_bloque2 = obtener_nodos_disponibles(bloques[j])
                for idx, nodo in enumerate(nodos_bloque2, 1):
                    print(f"  {idx}) {nodo}")
                
                nodo2_idx = read_int(f"Selecciona nodo de {bloques[j]} (1-{len(nodos_bloque2)}): ", 1, len(nodos_bloque2))
                nodo2 = nodos_bloque2[nodo2_idx - 1]
                
                # Añadir conexión
                conexiones.append({
                    "bloque_origen": bloques[i],
                    "nodo_origen": nodo1,
                    "bloque_destino": bloques[j],
                    "nodo_destino": nodo2
                })
                
                print(f"✅ Conexión añadida: {nodo1} ({bloques[i]}) ↔ {nodo2} ({bloques[j]})")
                
                # Preguntar si quiere añadir más conexiones entre estos mismos bloques
                mas_conexiones = read_str("¿Añadir otra conexión entre estos bloques? (s/n): ").lower()
                if mas_conexiones != 's':
                    break  # ✅ Solo rompe el while, no el for j

    return conexiones


def obtener_nodos_disponibles(plantilla: str) -> List[str]:
    """Devuelve los nodos disponibles para una plantilla dada."""
    if plantilla == "Punto a Punto":
        return ["A", "B"]
    elif plantilla == "Estrella":
        return ["A", "B", "C", "D", "E"]
    elif plantilla == "Anillo":
        return ["A", "B", "C", "D"]
    elif plantilla == "Árbol":
        return ["A", "B", "C", "D", "R"]
    elif plantilla == "Bus":
        return ["A", "B", "C", "D"]
    elif plantilla == "Malla":
        return ["A", "B", "C", "D"]
    elif plantilla == "Libre (vacía)":
        return ["X"]
    elif plantilla == "Mixta (combinada)":
        return ["M"]
    return []
# ------------------- COMBINACIÓN DE BLOQUES (ASCII) -------------------
def combined_ascii(selected: List[str], union_label: str = "HUB") -> str:
    """
    Dibuja una vista combinada muy simple de los bloques seleccionados
    alrededor de un nodo de unión (union_label).
    No busca ser exacto; es una guía visual rápida.
    """
    if not selected:
        return ascii_block("Combinada", ["(sin bloques)"])
    # Plantillas que se conectarán al nodo central
    arms = []
    for tpl in selected:
        if tpl == "Punto a Punto":
            arms.append(f"{union_label} ── A──B")
        elif tpl == "Estrella":
            arms.append(f"{union_label} ── (Estrella)")
        elif tpl == "Anillo":
            arms.append(f"{union_label} ── (Anillo A-B-C-D)")
        elif tpl == "Árbol":
            arms.append(f"{union_label} ── (Árbol R-A/B/C)")
        elif tpl == "Bus":
            arms.append(f"{union_label} ── (Bus A|B|C|D)")
        elif tpl == "Malla":
            arms.append(f"{union_label} ── (Malla A-B-C-D)")
        elif tpl == "Libre (vacía)":
            arms.append(f"{union_label} ── (Libre)")
        elif tpl == "Mixta (combinada)":
            arms.append(f"{union_label} ── (Mixta)")
        else:
            arms.append(f"{union_label} ── ({tpl})")
    # Empaquetar con un bloque ASCII
    return ascii_block(f"Topología Combinada (Nodo unión: {union_label})", arms[:8])

def list_topologies(user: Dict, scope_all: bool = False) -> None:
    clear_screen()
    print("=== Listado de topologías ===\n")
    data = _FAKE_TOPOLOGIES if scope_all else [t for t in _FAKE_TOPOLOGIES if t["propietario"] == user["username"]]
    if not data:
        print("No hay topologías registradas para mostrar.")
    else:
        for t in data:
            print(f"- ID: {t['id']} | Nombre: {t['nombre']} | Dueño: {t['propietario']} | Bloques: {', '.join(t['plantillas']) or '(vacía)'}")
    pause()

def view_topology_detail(user: Dict, scope_all: bool = False) -> None:
    list_topologies(user, scope_all=scope_all)
    topo_id = read_int("\nIngresa el ID de la topología a ver (0 para volver): ", 0)
    if topo_id == 0:
        return
    t = next((x for x in _FAKE_TOPOLOGIES if x["id"] == topo_id), None)
    if not t or (not scope_all and t["propietario"] != user["username"]):
        print("❌ Topología no encontrada o sin permisos.")
    else:
        clear_screen()
        print("=== Detalle de la topología ===\n")
        print(f"ID: {t['id']}")
        print(f"Nombre: {t['nombre']}")
        print(f"Propietario: {t['propietario']}")
        print(f"Plantillas/blq.: {', '.join(t['plantillas']) or '(vacía)'}")
        
        # Mostrar vista ASCII de la topología
        print("\n--- Vista ASCII de la topología ---")
        ascii_preview_summary(t['plantillas'])
        
        # 🚀 Render gráfico con Graphviz
        output_file = render_topology_graph(
            t["nombre"],
            t["plantillas"],
            t.get("union_label", "HUB")
        )
        if output_file:
            # Preguntar si desea abrir la imagen
            abrir = read_str("¿Deseas abrir la imagen de la topología? (s/n): ").lower()
            if abrir == 's':
                open_image(output_file)
    pause()

def update_topology(user: Dict) -> None:
    list_topologies(user, scope_all=False)
    topo_id = read_int("\nIngresa el ID a editar (0 para volver): ", 0)
    if topo_id == 0:
        return
    t = next((x for x in _FAKE_TOPOLOGIES if x["id"] == topo_id and x["propietario"] == user["username"]), None)
    if not t:
        print("❌ Topología no encontrada o sin permisos.")
        pause()
        return
    clear_screen()
    print("=== Editar topología ===\n")
    print(f"Actual: {t['nombre']} | Bloques: {', '.join(t['plantillas']) or '(vacía)'}")
    print("\n1) Renombrar")
    print("2) Modificar bloques (plantillas)")
    print("3) Cambiar recursos (solo texto)")
    print("0) Volver")
    op = read_int("\nElige opción: ", 0, 3)
    if op == 1:
        nuevo = read_str("Nuevo nombre: ")
        t["nombre"] = nuevo
        print("✅ Nombre actualizado.")
        output_file = render_topology_graph(
            t["nombre"],
            t["plantillas"],
            t.get("union_label", "HUB")
        )
        if output_file:
            # Preguntar si desea abrir la imagen
            abrir = read_str("¿Deseas abrir la imagen de la topología? (s/n): ").lower()
            if abrir == 's':
                open_image(output_file)
    elif op == 2:
        t["plantillas"] = show_templates_menu(t["plantillas"][:])
        print("✅ Bloques actualizados.")
        output_file = render_topology_graph(t["nombre"], t["plantillas"], t.get("union_label", "HUB"))
        if output_file:
            # Preguntar si desea abrir la imagen
            abrir = read_str("¿Deseas abrir la imagen de la topología? (s/n): ").lower()
            if abrir == 's':
                open_image(output_file)
    elif op == 3:
        not_impl("Actualización de recursos")
    pause()

def delete_topology(user: Dict, scope_all: bool = False) -> None:
    list_topologies(user, scope_all=scope_all)
    topo_id = read_int("\nIngresa el ID a borrar (0 para volver): ", 0)
    if topo_id == 0:
        return
    idx = next((i for i, x in enumerate(_FAKE_TOPOLOGIES)
                if x["id"] == topo_id and (scope_all or x["propietario"] == user['username'])), None)
    if idx is None:
        print("❌ Topología no encontrada o sin permisos.")
    else:
        conf = read_str("Escribe CONFIRMAR para borrar: ")
        if conf == "CONFIRMAR":
            _FAKE_TOPOLOGIES.pop(idx)
            print("✅ Topología eliminada (simulada).")
        else:
            print("🚫 Operación cancelada.")
    pause()

def duplicate_topology(user: Dict) -> None:
    list_topologies(user, scope_all=False)
    topo_id = read_int("\nID a duplicar (0 para volver): ", 0)
    if topo_id == 0:
        return
    t = next((x for x in _FAKE_TOPOLOGIES if x["id"] == topo_id and x["propietario"] == user["username"]), None)
    if not t:
        print("❌ Topología no encontrada o sin permisos.")
        pause()
        return
    new_id = _next_topology_id()
    copia = {**t, "id": new_id, "nombre": t["nombre"] + " (copia)"}
    _FAKE_TOPOLOGIES.append(copia)
    print(f"✅ Topología duplicada con ID {new_id}.")
    pause()

def export_topology(user: Dict) -> None:
    # Exporta la última topología del usuario (puedes mejorar la selección)
    user_topos = [t for t in _FAKE_TOPOLOGIES if t["propietario"] == user["username"]]
    if not user_topos:
        print("❌ No tienes topologías para exportar.")
    else:
        topo = user_topos[-1]
        export_topology_json(topo)
    pause()

def import_topology(user: Dict) -> None:
    not_impl("Importar topología desde JSON/YAML")

def audit_logs(user: Dict) -> None:
    not_impl("Auditoría / logs (actividad, cambios, despliegues)")

def manage_users(user: Dict) -> None:
    not_impl("Gestión de usuarios (crear, listar, quitar, roles)")

def manage_templates(user: Dict) -> None:
    not_impl("Gestión de plantillas (alta/baja/edición)")

def monitor_all_topologies(user: Dict) -> None:
    not_impl("Monitoreo de topologías de todos los usuarios (estado, métricas)")

def show_resource_limits(user: Dict) -> None:
    clear_screen()
    print("=== Límites de recursos por tu rol ===\n")
    limits = RESOURCE_LIMITS[user["role"]]
    print(f"Rol: {user['role']}")
    print(f"- RAM máx:   {limits['ram_gb']} GB")
    print(f"- Disco máx: {limits['disk_gb']} GB")
    print(f"- Zonas:     {', '.join(limits['az'])}")
    pause()

# -------------------------- Menús por rol --------------------------
def menu_comun(user: Dict) -> None:
    while True:
        clear_screen()
        print("=" * 60)
        print(f"👤 Menú (Usuario común) — {user['username']}".center(60))
        print("=" * 60)
        print("1) Ver mis topologías")
        print("2) Ver detalle de una topología")
        print("3) Crear topología (con plantillas/bloques)")
        print("4) Editar topología propia (CRUD)")
        print("5) Borrar topología propia")
        print("6) Exportar topología")
        print("7) Importar topología")
        print("8) Ver límites de recursos (rol)")
        print("0) Cerrar sesión")
        op = read_int("\nElige opción: ", 0, 9)
        if   op == 1: list_topologies(user, scope_all=False)
        elif op == 2: view_topology_detail(user, scope_all=False)
        elif op == 3: create_topology_flow(user)
        elif op == 4: update_topology(user)
        elif op == 5: delete_topology(user, scope_all=False)
        elif op == 6: export_topology(user)
        elif op == 7: import_topology(user)
        elif op == 8: show_resource_limits(user)
        elif op == 0: break

def menu_vip(user: Dict) -> None:
    while True:
        clear_screen()
        print("=" * 60)
        print(f"💎 Menú (Usuario VIP) — {user['username']}".center(60))
        print("=" * 60)
        print("1) Ver mis topologías")
        print("2) Ver detalle de una topología")
        print("3) Crear topología (plantillas/bloques)")
        print("4) Editar topología propia (CRUD)")
        print("5) Borrar topología propia")
        print("6) Exportar topología")
        print("7) Importar topología")
        print("8) Ver límites de recursos (rol)")
        print("0) Cerrar sesión")
        op = read_int("\nElige opción: ", 0, 9)
        if   op == 1: list_topologies(user, scope_all=False)
        elif op == 2: view_topology_detail(user, scope_all=False)
        elif op == 3: create_topology_flow(user)
        elif op == 4: update_topology(user)
        elif op == 5: delete_topology(user, scope_all=False)
        elif op == 6: export_topology(user)
        elif op == 7: import_topology(user)
        elif op == 8: show_resource_limits(user)
        elif op == 0: break

def menu_admin(user: Dict) -> None:
    while True:
        clear_screen()
        print("=" * 60)
        print(f"🛡️  Menú (Administrador) — {user['username']}".center(60))
        print("=" * 60)
        print("1) Ver todas las topologías")
        print("2) Ver detalle de una topología (todas)")
        print("3) Crear topología (como admin)")
        print("4) Editar topología propia (CRUD)")
        print("5) Borrar CUALQUIER topología")
        print("6) Monitoreo (todas las topologías)")
        print("7) Gestión de usuarios")
        print("8) Gestión de plantillas")
        print("9) Exportar topología")
        print("10) Importar topología")
        print("11) Ver límites de recursos (rol)")
        print("0) Cerrar sesión")
        op = read_int("\nElige opción: ", 0, 12)
        if   op == 1: list_topologies(user, scope_all=True)
        elif op == 2: view_topology_detail(user, scope_all=True)
        elif op == 3: create_topology_flow(user)
        elif op == 4: update_topology(user)
        elif op == 5: delete_topology(user, scope_all=True)
        elif op == 6: monitor_all_topologies(user)
        elif op == 7: manage_users(user)
        elif op == 8: manage_templates(user)
        elif op == 9: export_topology(user)
        elif op == 10: import_topology(user)
        elif op == 11: show_resource_limits(user)
        elif op == 0: break

# ------------------------------ Main ------------------------------
def main() -> None:
    while True:
        user = login_flow()
        role = user["role"]
        if role == Role.COMUN:
            menu_comun(user)
        elif role == Role.VIP:
            menu_vip(user)
        elif role == Role.ADMIN:
            menu_admin(user)
        # Al salir de un menú, se "cierra sesión" y se vuelve al login
        clear_screen()
        print("🔒 Sesión cerrada.")
        again = read_str("¿Iniciar sesión con otro usuario? (s/n): ").lower()
        if again != "s":
            break
    print("\n👋 ¡Gracias por usar PUCP Private Open Cloud Orchestrator (menú demo)!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo...")