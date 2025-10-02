#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ============================
# CONFIGURA TU INFRA AQUÍ
# ============================
OFS = {
    "host": "10.0.10.5",
    "bridge": "OFS",
    "uplinks": ["ens6", "ens7", "ens8"],
    "user": "ubuntu",
}

WORKERS = [
    {"name": "worker1", "host": "10.0.10.2", "bridge": "ovs_host2", "uplink": "ens4", "user": "ubuntu"},
    {"name": "worker2", "host": "10.0.10.3", "bridge": "ovs_host3", "uplink": "ens4", "user": "ubuntu"},
    {"name": "worker3", "host": "10.0.10.4", "bridge": "ovs_host4", "uplink": "ens4", "user": "ubuntu"},
]

# Rutas de scripts en hosts remotos
INIT_OFS = "./init_ofs.sh"
INIT_WORKER = "./init_worker.sh"
VM_CREATE = "./vm_create_multi.sh"   # versión multi-NIC

# VNC inicial por worker (contador por host)
VNC_START = 5901

# Estado persistente (local al orquestador)
STATE_PATH = os.path.expanduser("~/.orchestrator/vlans.json")

# VLAN válidas 802.1Q (0 y 4095 reservadas por estándar)
VLAN_MIN, VLAN_MAX = 1, 4094
# ============================


# --------- Utilitarios de estado persistente ---------
def load_state():
    if not os.path.exists(STATE_PATH):
        return {"used_vlans": [], "slices": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"used_vlans": [], "slices": {}}
    data.setdefault("used_vlans", [])
    data.setdefault("slices", {})
    return data


def save_state(state):
    Path(STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def allocate_vlans_for_edges(edges, node_ids, state_used_vlans):
    """
    Asigna 1 VLAN por edge, en orden determinista, evitando repetidos
    con respecto a state_used_vlans (persistente).
    Retorna:
      edge_vlan_map: { (min(a,b),max(a,b)) : vlan }
      new_used: set con todas las VLAN usadas tras asignación
    """
    # Orden determinista por (from,to)
    edges_sorted = sorted(
        (e for e in edges if e["from"] in node_ids and e["to"] in node_ids and e["from"] != e["to"]),
        key=lambda e: (min(e["from"], e["to"]), max(e["from"], e["to"]))
    )
    used = set(state_used_vlans)
    edge_vlan_map = {}

    # Generador secuencial 1..4094, saltando usadas
    def next_vlan():
        for v in range(VLAN_MIN, VLAN_MAX + 1):
            if v not in used:
                yield v

    gen = next_vlan()
    for e in edges_sorted:
        a, b = e["from"], e["to"]
        key = (min(a, b), max(a, b))
        # Asignación automática (ignora cualquier 'vlan' en JSON si llegase)
        try:
            vlan = next(gen)
        except StopIteration:
            raise RuntimeError("No quedan VLANs disponibles (superaste 4094 enlaces activos).")
        edge_vlan_map[key] = vlan
        used.add(vlan)

    return edge_vlan_map, used


# --------- SSH helpers ---------
def run_ssh(user, host, cmd, dry=False):
    printable = f'ssh -t {user}@{host} "{cmd}"'
    print("[SSH]", printable)
    if dry:
        return
    subprocess.check_call(["ssh", "-t", f"{user}@{host}", cmd])


# --------- Infra inicial ---------
def init_infra(dry=False):
    # OFS
    ofs_cmd = f'"{INIT_OFS}" {OFS["bridge"]} ' + " ".join(OFS["uplinks"])
    run_ssh(OFS["user"], OFS["host"], ofs_cmd, dry=dry)

    # Workers
    for wk in WORKERS:
        wk_cmd = f'sudo "{INIT_WORKER}" {wk["bridge"]} {wk["uplink"]}'
        run_ssh(wk["user"], wk["host"], wk_cmd, dry=dry)


# --------- Parse y planificación ---------
def parse_topology(topo, state):
    nodes = topo["nodes"]
    edges = topo["edges"]
    node_ids = {n["id"] for n in nodes}

    # 1 VLAN por edge (automática, persistente)
    edge_vlan_map, new_used = allocate_vlans_for_edges(edges, node_ids, state["used_vlans"])

    # VLANs por VM (cada edge que toca a la VM le añade una NIC/VLAN)
    vm_vlans = defaultdict(set)
    for e in edges:
        a, b = e["from"], e["to"]
        if a in node_ids and b in node_ids and a != b:
            key = (min(a, b), max(a, b))
            vlan = edge_vlan_map[key]
            vm_vlans[a].add(vlan)
            vm_vlans[b].add(vlan)

    nodes_sorted = sorted(nodes, key=lambda n: n["id"])
    return nodes_sorted, vm_vlans, edge_vlan_map, new_used


def compute_vnc_counters_from_state(state):
    """
    Devuelve un dict host->next_vnc_port considerando lo ya usado en slices previos.
    """
    vnc_counters = {wk["host"]: VNC_START for wk in WORKERS}
    for slice_id, meta in state.get("slices", {}).items():
        for vm in meta.get("vms", []):
            host = vm.get("worker_host")
            vnc = vm.get("vnc_port")
            if host and isinstance(vnc, int):
                vnc_counters[host] = max(vnc_counters.get(host, VNC_START), vnc + 1)
    return vnc_counters


def plan(nodes_sorted, vm_vlans, vnc_counters, slice_id):
    actions = []
    w = 0
    for n in nodes_sorted:
        wk = WORKERS[w % len(WORKERS)]
        vm_name = f"vm{n['id']}-{slice_id[-6:]}"  # ahora sí existe slice_id
        vlans = sorted(vm_vlans.get(n["id"], []))

        vnc_port = vnc_counters[wk["host"]]
        vnc_counters[wk["host"]] = vnc_port + 1

        actions.append({
            "node_id": n["id"],
            "vm_name": vm_name,
            "worker": wk,
            "vlans": vlans,
            "vnc_port": vnc_port
        })
        w += 1
    return actions


# --------- Despliegue ---------
def deploy(actions, dry=False):
    for a in actions:
        wk = a["worker"]
        vlans = a["vlans"]
        vlan_args = " ".join(str(v) for v in vlans) if vlans else ""
        cmd = f'sudo "{VM_CREATE}" {a["vm_name"]} {wk["bridge"]} {a["vnc_port"]} {vlan_args}'.strip()
        run_ssh(wk["user"], wk["host"], cmd, dry=dry)


# --------- Gestión de slices ---------
def default_slice_id_from_path(json_path):
    base = os.path.basename(json_path)
    base = re.sub(r"\.json$", "", base, flags=re.I)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{base}-{ts}"


def record_slice(state, slice_id, edge_vlan_map, actions):
    # Guardar VLANs y VMs creadas para liberar después
    vlans = sorted(set(edge_vlan_map.values()))
    vms = []
    for a in actions:
        vms.append({
            "name": a["vm_name"],
            "worker_host": a["worker"]["host"],
            "worker_name": a["worker"]["name"],
            "bridge": a["worker"]["bridge"],
            "vnc_port": a["vnc_port"],
            "vlans": a["vlans"],
        })
    state["slices"][slice_id] = {
        "vlans": vlans,
        "vms": vms,
        "created_at": datetime.now().isoformat()
    }
    # Actualiza used_vlans global
    used = set(state["used_vlans"])
    used.update(vlans)
    state["used_vlans"] = sorted(list(used))


def release_slice(state, slice_id):
    """
    Elimina registro del slice y libera sus VLANs del pool persistente.
    No apaga VMs ni borra puertos OVS (eso sería otro comando; aquí solo liberamos pool).
    """
    meta = state["slices"].get(slice_id)
    if not meta:
        print(f"[WARN] Slice '{slice_id}' no encontrado en estado. Nada que liberar.")
        return False

    slice_vlans = set(meta.get("vlans", []))
    # Quita VLANs del global used_vlans solo si no las usa otro slice
    in_use_by_others = set()
    for sid, m in state["slices"].items():
        if sid == slice_id:
            continue
        in_use_by_others.update(m.get("vlans", []))

    new_used = [v for v in state["used_vlans"] if v not in slice_vlans or v in in_use_by_others]
    state["used_vlans"] = sorted(new_used)

    # Borra slice
    del state["slices"][slice_id]
    return True


# ============================
#           MAIN
# ============================
def main():
    ap = argparse.ArgumentParser(
        description="Orquestador: VLAN por enlace (1..4094) con pool persistente y multi-NIC (vm_create_multi.sh)."
    )
    ap.add_argument("--json", help="Ruta al JSON exportado (sin coords). Requerido para deploy.")
    ap.add_argument("--slice-id", help="Identificador del slice. Si no se indica, se autogenera.")
    ap.add_argument("--no-init", action="store_true", help="No ejecutar init_ofs/init_worker (solo VMs).")
    ap.add_argument("--dry-run", action="store_true", help="No ejecuta SSH, solo imprime el plan/comandos.")
    ap.add_argument("--release-slice", help="Libera el pool de VLANs para el slice indicado (no borra VMs).")
    args = ap.parse_args()

    state = load_state()

    # Sólo liberar VLANs de un slice y salir
    if args.release_slice:
        ok = release_slice(state, args.release_slice)
        if ok:
            save_state(state)
            print(f"[OK] VLANs liberadas para slice '{args.release_slice}'.")
        return

    if not args.json:
        ap.error("--json es requerido para desplegar (o usa --release-slice).")

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)
    topo = data.get("topology", data)

    # Parse y asignación de VLAN por edge con estado persistente
    nodes_sorted, vm_vlans, edge_vlan_map, new_used = parse_topology(topo, state)

    # VNC por worker considerando lo ya usado en slices previos
    vnc_counters = compute_vnc_counters_from_state(state)

    # Planificación (round-robin simple entre workers)
    slice_id = args.slice_id or default_slice_id_from_path(args.json)
    actions = plan(nodes_sorted, vm_vlans, vnc_counters, slice_id)


    # Mostrar plan
    print("\n[INFO] VLAN por enlace:")
    for (a, b), vlan in sorted(edge_vlan_map.items()):
        print(f"  {a} -- {b}  vlan={vlan}")

    print("\n[INFO] VLANs por VM:")
    for n in nodes_sorted:
        vl = sorted(vm_vlans.get(n["id"], []))
        print(f"  vm{n['id']}: {vl}")

    print("\n[PLAN]")
    for a in actions:
        wk = a["worker"]
        print(f"  {a['vm_name']} -> {wk['name']}({wk['host']}) bridge={wk['bridge']} vlans={a['vlans']} vnc={a['vnc_port']}")

    # Si todo OK, despliegue
    if not args.no_init:
        print("\n[STEP] init infra…")
        init_infra(dry=args.dry_run)

    print("[STEP] deploy VMs…")
    deploy(actions, dry=args.dry_run)

    # Registrar slice
    slice_id = args.slice_id or default_slice_id_from_path(args.json)
    record_slice(state, slice_id, edge_vlan_map, actions)
    save_state(state)
    print(f"[DONE] OK — slice_id='{slice_id}' guardado en {STATE_PATH}")


if __name__ == "__main__":
    main()
