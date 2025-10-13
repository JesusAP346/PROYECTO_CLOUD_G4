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
import math


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

# --- Gateway (NAT público) ---
# Máquina distinta al headnode: aquí es donde se hará el DNAT público -> worker:vnc
GATEWAY = {
    "host": "10.20.12.158",          # IP/host del GATEWAY
    "user": "ubuntu",                # usuario SSH en el GATEWAY
    "ext_if": "ens3",                # interfaz externa en el GATEWAY (llega el tráfico público)
    "map_script": "/home/ubuntu/vnc_gateway_map.sh",   # script en el GATEWAY
}

# Rango de puertos públicos para VNC en el GATEWAY
PUBLIC_VNC_MIN, PUBLIC_VNC_MAX = 5901, 6000

# Rutas de scripts en hosts remotos (workers y OFS)
INIT_OFS = "./init_ofs.sh"
INIT_WORKER = "./init_worker.sh"
VM_CREATE = "./vm_create_multi.sh"   # versión multi-NIC

# VNC inicial por worker (contador por host)
VNC_START = 5901

# Estado persistente (local al orquestador)
STATE_PATH = os.path.expanduser("~/.orchestrator/vlans.json")

# VLAN válidas 802.1Q (0 y 4095 reservadas por estándar)
VLAN_MIN, VLAN_MAX = 1, 4094

# ======== VLANs reservadas ========
INTERNET_VLAN = 300
RESERVED_VLANS = {INTERNET_VLAN}
# ============================


# --------- Utilitarios de estado persistente ---------
def load_state():
    if not os.path.exists(STATE_PATH):
        return {"used_vlans": [], "slices": {}, "public_ports_used": []}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"used_vlans": [], "slices": {}, "public_ports_used": []}
    data.setdefault("used_vlans", [])
    data.setdefault("slices", {})
    data.setdefault("public_ports_used", [])
    return data


def save_state(state):
    Path(STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def next_free_public_port(state):
    used = set(state.get("public_ports_used", []))
    for p in range(PUBLIC_VNC_MIN, PUBLIC_VNC_MAX + 1):
        if p not in used:
            return p
    raise RuntimeError("No hay puertos VNC públicos disponibles.")


def mark_public_port(state, port):
    used = set(state.get("public_ports_used", []))
    used.add(port)
    state["public_ports_used"] = sorted(list(used))


def unmark_public_port(state, port):
    used = set(state.get("public_ports_used", []))
    used.discard(port)
    state["public_ports_used"] = sorted(list(used))


def allocate_vlans_for_edges(edges, node_ids, state_used_vlans):
    """
    Asigna 1 VLAN por edge, en orden determinista, evitando repetidos
    con respecto a state_used_vlans (persistente).
    Retorna:
      edge_vlan_map: { (min(a,b),max(a,b)) : vlan }
      new_used: set con todas las VLAN usadas tras asignación
    """
    edges_sorted = sorted(
        (e for e in edges if e["from"] in node_ids and e["to"] in node_ids and e["from"] != e["to"]),
        key=lambda e: (min(e["from"], e["to"]), max(e["from"], e["to"]))
    )
    used = set(state_used_vlans) | RESERVED_VLANS

    edge_vlan_map = {}

    def next_vlan():
        for v in range(VLAN_MIN, VLAN_MAX + 1):
            if v not in used:
                yield v

    gen = next_vlan()
    for e in edges_sorted:
        a, b = e["from"], e["to"]
        key = (min(a, b), max(a, b))
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


# --------- NAT público en el GATEWAY ---------
def add_dnat(public_port, backend_ip, backend_port, ext_if, dry=False):
    cmd = f'sudo {GATEWAY["map_script"]} add {public_port} {backend_ip} {backend_port} {ext_if}'
    print("[SSH]", f'ssh -t {GATEWAY["user"]}@{GATEWAY["host"]} "{cmd}"')
    if not dry:
        subprocess.check_call(["ssh", "-t", f'{GATEWAY["user"]}@{GATEWAY["host"]}', cmd])


def del_dnat(public_port, backend_ip, backend_port, ext_if, dry=False):
    cmd = f'sudo {GATEWAY["map_script"]} del {public_port} {backend_ip} {backend_port} {ext_if}'
    print("[SSH]", f'ssh -t {GATEWAY["user"]}@{GATEWAY["host"]} "{cmd}"')
    if not dry:
        subprocess.check_call(["ssh", "-t", f'{GATEWAY["user"]}@{GATEWAY["host"]}', cmd])


# --------- Parse y planificación ---------
def parse_topology(topo, state):
    nodes = topo["nodes"]
    edges = topo["edges"]
    node_ids = {n["id"] for n in nodes}

    edge_vlan_map, new_used = allocate_vlans_for_edges(edges, node_ids, state["used_vlans"])

    vm_vlans = defaultdict(set)
    for e in edges:
        a, b = e["from"], e["to"]
        if a in node_ids and b in node_ids and a != b:
            key = (min(a, b), max(a, b))
            vlan = edge_vlan_map[key]
            vm_vlans[a].add(vlan)
            vm_vlans[b].add(vlan)

    # internet_access -> suma VLAN 300
    for n in nodes:
        if n.get("internet_access") is True:
            vm_vlans[n["id"]].add(INTERNET_VLAN)

    nodes_sorted = sorted(nodes, key=lambda n: n["id"])
    return nodes_sorted, vm_vlans, edge_vlan_map, new_used


def compute_vnc_counters_from_state(state):
    vnc_counters = {wk["host"]: VNC_START for wk in WORKERS}
    for slice_id, meta in state.get("slices", {}).items():
        for vm in meta.get("vms", []):
            host = vm.get("worker_host")
            vnc = vm.get("vnc_port")
            if host and isinstance(vnc, int):
                vnc_counters[host] = max(vnc_counters.get(host, VNC_START), vnc + 1)
    return vnc_counters


# ---------- Selección de pool de workers según AZ ----------
def select_workers_for_az(az: str):
    if az is None:
        return WORKERS[:]
    if az == "linux-AZ-1":
        pool = [w for w in WORKERS if w["name"] == "worker1"]
    elif az == "linux-AZ-2":
        pool = [w for w in WORKERS if w["name"] in ("worker2", "worker3")]
    else:
        raise ValueError(f"AZ no soportada: {az}")
    if not pool:
        raise ValueError(f"No hay workers disponibles para AZ={az}")
    return pool

def as_float(val, default):
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)

def as_int(val, default):
    try:
        return int(float(val))  # acepta "1", 1.0, etc.
    except (TypeError, ValueError):
        return int(default)



def plan(nodes_sorted, vm_vlans, vnc_counters, slice_id, worker_pool, state):
    actions = []
    w = 0
    for n in nodes_sorted:
        wk = worker_pool[w % len(worker_pool)]
        vm_name = f"vm{n['id']}-{slice_id[-6:]}"
        vlans = sorted(vm_vlans.get(n["id"], []))
        vnc_port = vnc_counters[wk["host"]]; vnc_counters[wk["host"]] = vnc_port + 1
        public_port = next_free_public_port(state); mark_public_port(state, public_port)
        img = (n.get("image") or "cirros").strip().lower()

        flv = n.get("flavor") or {}

        vcpus   = as_int(flv.get("vcpus", 1), 1)
        ram_gb  = as_float(flv.get("ram", 1), 1.0)           # admite "0.5"
        # disk: si viene decimal (p.ej. "2.2"), lo subimos al entero superior en GiB
        disk_gb = int(math.ceil(as_float(flv.get("disk", 10), 10)))

        actions.append({
            "node_id": n["id"],
            "vm_name": vm_name,
            "worker": wk,
            "vlans": vlans,
            "vnc_port": vnc_port,
            "public_port": public_port,
            "image": img,
            "flavor": {"vcpus": vcpus, "ram_gb": ram_gb, "disk_gb": disk_gb},
        })
        w += 1
    return actions


# --------- Despliegue ---------
def deploy(actions, dry=False):
    for a in actions:
        wk = a["worker"]; vlans = a["vlans"]
        vlan_args = " ".join(str(v) for v in vlans) if vlans else ""
        img_flag = f'--image {a.get("image","cirros")}'
        flv = a.get("flavor", {})
        flv_flags = f'--vcpus {flv.get("vcpus",1)} --ram-gb {flv.get("ram_gb",1)} --disk-gb {flv.get("disk_gb",10)}'
        cmd = f'sudo "{VM_CREATE}" {img_flag} {flv_flags} {a["vm_name"]} {wk["bridge"]} {a["vnc_port"]} {vlan_args}'.strip()
        run_ssh(wk["user"], wk["host"], cmd, dry=dry)
        add_dnat(a["public_port"], wk["host"], a["vnc_port"], GATEWAY["ext_if"], dry=dry)


# --------- Gestión de slices ---------
def default_slice_id_from_path(json_path):
    base = os.path.basename(json_path)
    base = re.sub(r"\.json$", "", base, flags=re.I)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{base}-{ts}"


def record_slice(state, slice_id, edge_vlan_map, actions):
    vlans = sorted(set(edge_vlan_map.values()))
    vms = []
    for a in actions:
        vms.append({
            "name": a["vm_name"],
            "worker_host": a["worker"]["host"],
            "worker_name": a["worker"]["name"],
            "bridge": a["worker"]["bridge"],
            "vnc_port": a["vnc_port"],
            "public_port": a["public_port"],
            "vlans": a["vlans"],
        })
    state["slices"][slice_id] = {
        "vlans": vlans,
        "vms": vms,
        "created_at": datetime.now().isoformat()
    }
    used = set(state["used_vlans"])
    used.update(vlans)
    state["used_vlans"] = sorted(list(used))


def release_slice(state, slice_id):
    """
    Elimina registro del slice y libera sus VLANs y PUERTOS PÚBLICOS del pool.
    Además borra los DNAT en el GATEWAY (no apaga VMs ni borra puertos OVS).
    """
    meta = state["slices"].get(slice_id)
    if not meta:
        print(f"[WARN] Slice '{slice_id}' no encontrado en estado. Nada que liberar.")
        return False

    # 1) Borrar DNATs y liberar puertos públicos
    for vm in meta.get("vms", []):
        pub = vm.get("public_port")
        wk_ip = vm.get("worker_host")
        vnc = vm.get("vnc_port")
        if isinstance(pub, int) and wk_ip and isinstance(vnc, int):
            try:
                del_dnat(pub, wk_ip, vnc, GATEWAY["ext_if"], dry=False)
            except Exception as e:
                print(f"[WARN] No se pudo borrar DNAT {pub}->{wk_ip}:{vnc}: {e}")
            unmark_public_port(state, pub)

    # 2) Liberar VLANs
    slice_vlans = set(meta.get("vlans", []))
    in_use_by_others = set()
    for sid, m in state["slices"].items():
        if sid == slice_id:
            continue
        in_use_by_others.update(m.get("vlans", []))

    new_used = [v for v in state["used_vlans"] if v not in slice_vlans or v in in_use_by_others]
    state["used_vlans"] = sorted(new_used)

    # 3) Borrar slice
    del state["slices"][slice_id]
    return True


# --------- Destrucción selectiva en workers ---------
def destroy_slice_on_workers(state, slice_id, dry=False):
    """
    Para cada VM del slice:
      - mata SOLO el qemu con -name <vm_name>
      - elimina sus TAPs (tap-<vm_name>-* y tap-<vm_name_sin_guiones>-*)
      - borra puertos OVS asociados en el bridge del worker
    """
    meta = state["slices"].get(slice_id)
    if not meta:
        print(f"[WARN] Slice '{slice_id}' no encontrado en estado. Nada que destruir.")
        return False

    for vm in meta.get("vms", []):
        vm_name  = vm["name"]
        wk_host  = vm["worker_host"]
        wk_user  = next((w["user"] for w in WORKERS if w["host"] == wk_host), "ubuntu")
        wk_bridge = vm.get("bridge")

        # Usamos patrones de shell en vez de regex para evitar problemas de quoting.
        remote = f"""bash -lc 'set -euo pipefail
name="{vm_name}"
short="${{name//-/}}"

# 1) Matar solo la VM con -name <vm_name>
sudo pkill -9 -f "qemu-system-x86_64.*-name[ =]{vm_name}" || true

# 2) Borrar TAPs de esa VM (tap-<name>-* y tap-<name_sin_guiones>-*)
if ip -o link show type tun >/dev/null 2>&1; then
  mapfile -t TAPS < <(ip -o link show type tun | awk -F": " '{{print $2}}' || true)
  for t in "${{TAPS[@]:-}}"; do
    if [[ "$t" == "tap-$name-"* || "$t" == "tap-${{short}}-"* ]]; then
      echo " - borrando $t"
      sudo ip link del "$t" || true
    fi
  done
fi

# 3) Borrar puertos tap-* remanentes en el bridge del worker
if sudo ovs-vsctl br-exists {wk_bridge} 2>/dev/null; then
  mapfile -t PORTS < <(sudo ovs-vsctl list-ports {wk_bridge} || true)
  for p in "${{PORTS[@]:-}}"; do
    if [[ "$p" == "tap-$name-"* || "$p" == "tap-${{short}}-"* ]]; then
      echo " - eliminando puerto huérfano: $p"
      sudo ovs-vsctl --if-exists del-port {wk_bridge} "$p" || true
    fi
  done
fi
'"""
        run_ssh(wk_user, wk_host, remote, dry=dry)

    return True

    """
    Para cada VM del slice:
      - mata SOLO el qemu con -name <vm_name>
      - elimina sus TAPs (tap-<vm_name>-* y tap-<vm_name_sin_guiones>-*)
      - borra puertos OVS asociados en el bridge del worker
    """
    meta = state["slices"].get(slice_id)
    if not meta:
        print(f"[WARN] Slice '{slice_id}' no encontrado en estado. Nada que destruir.")
        return False

    for vm in meta.get("vms", []):
        vm_name  = vm["name"]
        wk_host  = vm["worker_host"]
        wk_user  = next((w["user"] for w in WORKERS if w["host"] == wk_host), "ubuntu")
        wk_bridge = vm.get("bridge")

        remote = f"""bash -lc '
set -euo pipefail
name="{vm_name}"
short="${{name//-/}}"

# 1) Matar solo la VM con -name <vm_name>
if pgrep -a -f "qemu-system-x86_64.*-name[ =]{vm_name}" >/dev/null 2>&1; then
  sudo pkill -9 -f "qemu-system-x86_64.*-name[ =]{vm_name}" || true
fi

# 2) Borrar TAPs de esa VM (con y sin guiones)
if ip -o link show type tun >/dev/null 2>&1; then
  for t in $(ip -o link show type tun | awk -F": " '{{print $2}}' | grep -E "(^| )tap-{vm_name}-|(^| )tap-${{short}}-" || true); do
    echo " - borrando $t"
    sudo ip link del "$t" || true
  done
fi

# 3) Borrar puertos tap-* remanentes del mismo patrón en el bridge
if sudo ovs-vsctl br-exists {wk_bridge} 2>/dev/null; then
  for p in $(sudo ovs-vsctl list-ports {wk_bridge} | grep -E "(^| )tap-{vm_name}-|(^| )tap-${{short}}-" || true); do
    echo " - eliminando puerto huérfano: $p"
    sudo ovs-vsctl --if-exists del-port {wk_bridge} "$p" || true
  done
fi
'"""
        run_ssh(wk_user, wk_host, remote, dry=dry)

    return True


def destroy_and_release_slice(state, slice_id, dry=False):
    """
    1) Destruye VMs/TAPs/puertos OVS del slice en workers (selectivo).
    2) Borra DNATs y libera puertos públicos.
    3) Libera VLANs del pool y elimina el slice del estado.
    """
    if not destroy_slice_on_workers(state, slice_id, dry=dry):
        return False
    freed = release_slice(state, slice_id)
    if freed:
        save_state(state)
        print(f"[OK] Slice '{slice_id}' destruido en workers y liberado (DNAT/puertos/VLANs).")
        return True
    return False


# ============================
#           MAIN
# ============================
def main():
    ap = argparse.ArgumentParser(
        description="Orquestador: VLAN por enlace (1..4094) con pool persistente, multi-NIC (vm_create_multi.sh) y mapeo VNC público vía GATEWAY."
    )
    ap.add_argument("--json", help="Ruta al JSON exportado (sin coords). Requerido para deploy.")
    ap.add_argument("--slice-id", help="Identificador del slice. Si no se indica, se autogenera.")
    ap.add_argument("--no-init", action="store_true", help="No ejecutar init_ofs/init_worker (solo VMs).")
    ap.add_argument("--dry-run", action="store_true", help="No ejecuta SSH, solo imprime el plan/comandos.")
    ap.add_argument("--release-slice", help="Libera el pool de VLANs/puertos para el slice indicado (no borra VMs).")
    ap.add_argument("--destroy-slice", action="store_true",
                    help="Además, destruye VMs/TAPs/puertos OVS del slice en los workers (selectivo).")
    args = ap.parse_args()

    state = load_state()

    # ---- Destruir + liberar (todo en uno) ----
    if args.release_slice and args.destroy_slice:
        ok = destroy_and_release_slice(state, args.release_slice, dry=args.dry_run)
        if not ok:
            print(f"[WARN] No se pudo destruir/liberar el slice '{args.release_slice}'.")
        return

    # ---- Solo liberar (comportamiento anterior) ----
    if args.release_slice:
        ok = release_slice(state, args.release_slice)
        if ok:
            save_state(state)
            print(f"[OK] VLANs y puertos públicos liberados para slice '{args.release_slice}'.")
        return

    # ---- Deploy normal ----
    if not args.json:
        ap.error("--json es requerido para desplegar (o usa --release-slice).")

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    topo = data.get("topology", data)

    # Leer availability_zone desde metadata (si existe)
    meta = data.get("metadata") or {}
    placement_az = meta.get("availability_zone")
    if not placement_az or str(placement_az).strip().lower() in ("automatico", "any", ""):
        placement_az = None

    nodes_sorted, vm_vlans, edge_vlan_map, new_used = parse_topology(topo, state)

    vnc_counters = compute_vnc_counters_from_state(state)

    try:
        worker_pool = select_workers_for_az(placement_az)
    except ValueError as e:
        raise SystemExit(f"[ERROR] {e}")

    slice_id = args.slice_id or default_slice_id_from_path(args.json)
    actions = plan(nodes_sorted, vm_vlans, vnc_counters, slice_id, worker_pool, state)

    chosen_az = placement_az if placement_az is not None else "auto"
    pool_names = ", ".join([w["name"] for w in worker_pool])
    print(f"\n[INFO] placement.az = {chosen_az} -> worker_pool = [{pool_names}]")

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
        print(
            f"  {a['vm_name']} -> {wk['name']}({wk['host']}) "
            f"bridge={wk['bridge']} vlans={a['vlans']} "
            f"vnc={a['vnc_port']} public={a['public_port']} image={a['image']}"
        )

    if not args.no_init:
        print("\n[STEP] init infra…")
        init_infra(dry=args.dry_run)

    print("[STEP] deploy VMs…")
    deploy(actions, dry=args.dry_run)

    slice_id = args.slice_id or default_slice_id_from_path(args.json)
    record_slice(state, slice_id, edge_vlan_map, actions)
    save_state(state)
    print(f"[DONE] OK — slice_id='{slice_id}' guardado en {STATE_PATH}")


if __name__ == "__main__":
    main()
