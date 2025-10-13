#!/bin/bash
# Purga total: limpia workers y libera TODOS los slices del registro local.
# Uso: ./purge_all_slices.sh
set -euo pipefail

USER_SSH="${USER_SSH:-ubuntu}"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# Mapea cada worker a su bridge OVS
workers=( "10.0.10.2:ovs_host2" "10.0.10.3:ovs_host3" "10.0.10.4:ovs_host4" )

echo "=== 1/2: Limpieza remota en workers ==="
for w in "${workers[@]}"; do
  IFS=: read -r host br <<< "$w"
  echo ">> ${USER_SSH}@${host} (bridge=${br})"
  ssh $SSH_OPTS "${USER_SSH}@${host}" "sudo ./clean_cluster.sh '${br}'" || echo "WARN: fallo en $host"
done

echo
echo "=== 2/2: Liberando slices del registro local ==="
REG="$HOME/.orchestrator/vlans.json"
if [[ -s "$REG" ]]; then
  # Extrae IDs de slices con Python (sin depender de jq)
  mapfile -t SLICES < <(python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.orchestrator/vlans.json")
try:
    with open(p) as f:
        data = json.load(f)
    for sid in (data.get("slices") or {}).keys():
        print(sid)
except Exception:
    pass
PY
)
  if ((${#SLICES[@]})); then
    for sid in "${SLICES[@]}"; do
      echo "[release] $sid"
      python3 deploy_topology.py --release-slice "$sid" || echo "WARN: no se pudo liberar $sid"
    done
  else
    echo "No hay slices en el registro."
  fi
else
  echo "Registro $REG no existe o está vacío. Nada que liberar."
fi

echo
echo "✅ Purga completa."
