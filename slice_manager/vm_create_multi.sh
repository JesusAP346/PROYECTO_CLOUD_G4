#!/bin/bash
# Uso: sudo ./vm_create_multi.sh <vmName> <ovsBridge> <vncPort> <vlan1> [<vlan2> ...]

set -euo pipefail

vmName=$1
ovs=$2
vncPort=$3
shift 3
vlans=("$@")

IMG=cirros-0.5.1-x86_64-disk.img
displayVNC=$((vncPort-5900))

if [[ ! -f $IMG ]]; then
  echo "[ERROR] Imagen $IMG no encontrada en $(pwd)"
  exit 1
fi

# Directorio de logs (mapeos por VM)
LOGDIR="/var/log/vm-orchestrator"
MAPFILE="$LOGDIR/${vmName}.map"
if ! mkdir -p "$LOGDIR" 2>/dev/null; then
  LOGDIR="/tmp/vm-orchestrator"
  mkdir -p "$LOGDIR"
  MAPFILE="$LOGDIR/${vmName}.map"
fi

# Construir parámetros de red
NETARGS=()
echo "# VM: $vmName  (VNC :$displayVNC -> puerto $vncPort)" | tee "$MAPFILE" >/dev/null
echo "# ethX ↔ VLAN ↔ TAP ↔ MAC" | tee -a "$MAPFILE" >/dev/null

# Para orden estable dentro de la VM, asignamos cada NIC a una addr del bus PCI (3,4,5,...)
# Nota: e1000 en pci.0 es suficiente para cirros; si usas virtio-net, cambia 'e1000' por 'virtio-net-pci'
for idx in "${!vlans[@]}"; do
  vlan=${vlans[$idx]}

  # Nombre TAP seguro: ≤ 15 chars
  shortName=$(echo "$vmName" | cut -c1-8)
  tapName="tap-${shortName}-${vlan}"

  # (Re)crear TAP idempotente
  ip link show "$tapName" &>/dev/null || sudo ip tuntap add dev "$tapName" mode tap
  sudo ip link set dev "$tapName" up

  # MAC pseudo-aleatoria estable por vmName+vlan (para trazabilidad)
  # (si prefieres completamente aleatoria, usa el bloque od/urandom)
  hash=$(echo -n "${vmName}-${vlan}" | sha256sum | cut -c1-10)
  # Tomamos 5 bytes del hash:
  b2=${hash:0:2}; b3=${hash:2:2}; b4=${hash:4:2}; b5=${hash:6:2}; b6=${hash:8:2}
  mac=$(printf '02:%s:%s:%s:%s:%s' "$b2" "$b3" "$b4" "$b5" "$b6")

  # Añadir puerto al OVS con VLAN (idempotente)
  sudo ovs-vsctl --may-exist add-port "$ovs" "$tapName" tag="$vlan"

  # QEMU: netdev y device con orden estable en el bus
  NETARGS+=(-netdev tap,id=net${idx},ifname=${tapName},script=no,downscript=no)
  # Posición PCI: arrancamos en 0x3 y sumamos idx (evita colisiones con otros devices)
  pci_addr=$(printf "0x%x" $((0x3 + idx)))
  NETARGS+=(-device e1000,netdev=net${idx},mac=${mac},bus=pci.0,addr=${pci_addr})

  # Registrar mapeo esperado
  echo "eth${idx}  vlan=${vlan}  tap=${tapName}  mac=${mac}" | tee -a "$MAPFILE" >/dev/null
done

echo "# Log guardado en: $MAPFILE"
echo "[INFO] Lanzando $vmName con $((${#vlans[@]})) NICs, VNC :$displayVNC ..."

sudo qemu-system-x86_64 \
  -enable-kvm \
  -name "$vmName" \
  -vnc 0.0.0.0:"$displayVNC" \
  -daemonize \
  -snapshot \
  "${NETARGS[@]}" \
  "$IMG"

echo "[OK] VM $vmName lanzada. Revisa $MAPFILE para el mapeo ethX↔VLAN."
