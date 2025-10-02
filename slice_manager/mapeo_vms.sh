#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, argparse, subprocess, shlex
from pathlib import Path
from datetime import datetime

STATE_PATH = os.path.expanduser("~/.orchestrator/vlans.json")

MAP_PATHS = [
    "/var/log/vm-orchestrator/{name}.map",
    "/tmp/vm-orchestrator/{name}.map",
]

def run_ssh(host, user, cmd, timeout=10):
    try:
        out = subprocess.check_output(
            ["ssh", f"{user}@{host}", cmd],
            stderr=subprocess.STDOUT,
            timeout=timeout
        )
        return out.decode("utf-8", "ignore")
    except subprocess.CalledProcessError as e:
        return f"[SSH-ERR] {e.output.decode('utf-8', 'ignore')}".rstrip()
    except subprocess.TimeoutExpired:
        return "[SSH-ERR] timeout"

def load_state():
    if not os.path.exists(STATE_PATH):
        raise SystemExit(f"[ERR] No existe {STATE_PATH}")
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def pick_slice(state, slice_id):
    slices = state.get("slices", {})
    if not slices:
        raise SystemExit("[ERR] No hay slices registrados aún.")
    if slice_id:
        if slice_id not in slices:
            raise SystemExit(f"[ERR] Slice '{slice_id}' no encontrado.")
        return slice_id, slices[slice_id]
    # elegir el más reciente por created_at
    def parse_dt(x):
        try:
            return datetime.fromisoformat(x.replace("Z",""))
        except Exception:
            return datetime.min
    latest_id = max(slices.keys(), key=lambda sid: parse_dt(slices[sid].get("created_at","")))
    return latest_id, slices[latest_id]

def fetch_map_for_vm(host, user, vm_name):
    for pat in MAP_PATHS:
        rem = pat.format(name=vm_name)
        # cat si existe
        cmd = f"test -f {shlex.quote(rem)} && cat {shlex.quote(rem)} || echo '__MISSING__'"
        out = run_ssh(host, user, cmd)
        if "__MISSING__" not in out and not out.startswith("[SSH-ERR]"):
            return rem, out.strip()
    return None, None

def parse_map_text(txt):
    """
    Espera líneas como:
      eth0  vlan=4  tap=tap-vm1-xxxx-4  mac=02:aa:bb:...
    Devuelve lista de dicts [{eth, vlan, tap, mac}]
    """
    rows = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts or not parts[0].startswith("eth"):
            continue
        entry = {"eth": parts[0], "vlan": "", "tap": "", "mac": ""}
        for p in parts[1:]:
            if p.startswith("vlan="):
                entry["vlan"] = p.split("=",1)[1]
            elif p.startswith("tap="):
                entry["tap"] = p.split("=",1)[1]
            elif p.startswith("mac="):
                entry["mac"] = p.split("=",1)[1]
        rows.append(entry)
    # ordenar por ethX
    def eth_idx(e):
        try:
            return int(e["eth"].replace("eth",""))
        except:
            return 999
    return sorted(rows, key=eth_idx)

def main():
    ap = argparse.ArgumentParser(description="Recolecta y muestra ethX↔VLAN↔TAP↔MAC de VMs de un slice.")
    ap.add_argument("--slice-id", help="ID exacto del slice; si no se indica, toma el más reciente.")
    ap.add_argument("--json", action="store_true", help="Salida en JSON en vez de tabla.")
    ap.add_argument("--user", default="ubuntu", help="Usuario SSH en workers (default: ubuntu)")
    args = ap.parse_args()

    state = load_state()
    sid, meta = pick_slice(state, args.slice_id)

    vms = meta.get("vms", [])
    if not vms:
        raise SystemExit(f"[ERR] Slice '{sid}' no tiene VMs registradas.")

    results = []
    for vm in vms:
        vm_name = vm["name"]
        host = vm["worker_host"]
        bridge = vm.get("bridge","")
        vnc = vm.get("vnc_port","")
        rem_path, txt = fetch_map_for_vm(host, args.user, vm_name)
        if txt is None:
            results.append({
                "vm": vm_name, "host": host, "bridge": bridge, "vnc_port": vnc,
                "map_path": None, "error": "map file not found", "ifaces": []
            })
            continue
        rows = parse_map_text(txt)
        results.append({
            "vm": vm_name, "host": host, "bridge": bridge, "vnc_port": vnc,
            "map_path": rem_path, "error": None, "ifaces": rows
        })

    if args.json:
        print(json.dumps({"slice_id": sid, "results": results}, indent=2))
        return

    # salida bonita en texto
    print(f"\n[SICE] {sid}\n")
    for r in results:
        print(f" VM: {r['vm']}   host: {r['host']}   bridge: {r['bridge']}   VNC: {r['vnc_port']}")
        print(f"  map: {r['map_path'] or 'N/A'}")
        if r["error"]:
            print(f"  ERROR: {r['error']}\n")
            continue
        if not r["ifaces"]:
            print("  (sin entradas en el map)\n")
            continue
        print("  eth   vlan    tap                    mac")
        print("  ----  ------  --------------------   -----------------")
        for row in r["ifaces"]:
            print(f"  {row['eth']:<4}  {row['vlan']:<6}  {row['tap']:<20}   {row['mac']}")
        print()
    print("[OK] listo.")

if __name__ == "__main__":
    main()
