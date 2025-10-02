#!/bin/bash
set -euo pipefail

BR=ovs_host2

echo "Puertos en $BR con error y que parecen TAPs huérfanos:"
sudo ovs-vsctl list-ports "$BR" \
| grep -E '^tap-' \
| while read -r port; do
    if ! ip link show "$port" &>/dev/null; then
        echo " - $port (eliminar)"
    fi
done

read -rp "¿Eliminar los puertos listados? [y/N]: " ok
[[ "${ok,,}" == "y" ]] || { echo "Abortado."; exit 0; }

sudo ovs-vsctl list-ports "$BR" \
| grep -E '^tap-' \
| while read -r port; do
    if ! ip link show "$port" &>/dev/null; then
        echo "Eliminando puerto huérfano: $port"
        sudo ovs-vsctl del-port "$BR" "$port"
    fi
done

echo "✅ Limpieza terminada."
