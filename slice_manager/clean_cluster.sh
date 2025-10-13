#!/bin/bash
# ==========================================================
# Limpieza NO-INTERACTIVA del entorno Linux Cluster (worker)
# - Mata procesos QEMU activos
# - Elimina TODAS las interfaces TAP (tun/tap)
# - Borra puertos TAP huérfanos en el bridge OVS indicado
# Uso: sudo ./clean_cluster.sh [BRIDGE]
# Si no se indica, BRIDGE=ovs_host2
# ==========================================================
set -euo pipefail

BR="${1:-${BR:-ovs_host2}}"

echo "========== LIMPIEZA DE ENTORNO LINUX CLUSTER =========="
echo "Bridge OVS objetivo: $BR"

# -------------------------------
# 1) Finalizar procesos QEMU
# -------------------------------
echo ""
echo ">>> Matando procesos QEMU (si existen)..."
if pgrep -f qemu-system-x86_64 >/dev/null 2>&1; then
  # -9 por si quedaron zombis/defunct
  sudo pkill -9 -f qemu-system-x86_64 || true
  echo "✅ QEMU eliminado."
else
  echo "ℹ️ No hay procesos QEMU en ejecución."
fi

# -------------------------------
# 2) Eliminar interfaces TAP
# -------------------------------
echo ""
echo ">>> Eliminando interfaces TAP (tap-*)..."
# ip reporta TAP/TUN como 'type tun'
mapfile -t TAP_LIST < <(ip -o link show type tun | awk -F': ' '{print $2}' || true)
if (( ${#TAP_LIST[@]} > 0 )); then
  for tap in "${TAP_LIST[@]}"; do
    echo " - borrando $tap"
    sudo ip link delete "$tap" || true
  done
  echo "✅ TAPs eliminadas."
else
  echo "ℹ️ No se encontraron interfaces TAP."
fi

# -------------------------------
# 3) Eliminar puertos TAP huérfanos en OVS
# -------------------------------
echo ""
echo ">>> Buscando y eliminando puertos TAP huérfanos en el bridge: $BR"
if sudo ovs-vsctl br-exists "$BR" 2>/dev/null; then
  mapfile -t CANDIDATES < <(sudo ovs-vsctl list-ports "$BR" | grep -E '^tap-' || true)
  if (( ${#CANDIDATES[@]} > 0 )); then
    for port in "${CANDIDATES[@]}"; do
      if ! ip link show "$port" &>/dev/null; then
        echo " - eliminando puerto huérfano: $port"
        sudo ovs-vsctl --if-exists del-port "$BR" "$port" || true
      fi
    done
    echo "✅ Puertos huérfanos limpiados."
  else
    echo "ℹ️ No hay puertos tap-* en $BR."
  fi
else
  echo "⚠️ El bridge $BR no existe; se omite limpieza de OVS."
fi

echo ""
echo "✅ LIMPIEZA COMPLETA DEL CLUSTER FINALIZADA."
