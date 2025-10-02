#!/bin/bash
set -euo pipefail

# Listar todas las interfaces tipo tap
for tap in $(ip -o link show type tun | awk -F': ' '{print $2}'); do
    echo "Eliminando $tap ..."
    sudo ip link delete "$tap"
done

echo "✅ Todas las interfaces TAP eliminadas."
