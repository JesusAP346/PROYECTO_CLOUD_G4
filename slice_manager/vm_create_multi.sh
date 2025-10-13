#!/bin/bash
# Uso:
#   sudo ./vm_create_multi.sh [--image <alias|ruta>] <vmName> <ovsBridge> <vncPort> <vlan1> [<vlan2> ...]
# alias soportados: cirros (default), ubuntu
set -euo pipefail

# --------- Flags opcionales ----------
IMAGE_ALIAS_OR_PATH="cirros"
if [[ "${1:-}" == "--image" ]]; then
  [[ $# -ge 2 ]] || { echo "[ERROR] Falta valor para --image"; exit 1; }
  IMAGE_ALIAS_OR_PATH="$2"
  shift 2
elif [[ "${1:-}" == --image=* ]]; then
  IMAGE_ALIAS_OR_PATH="${1#--image=}"
  shift 1
fi

# --------- Posicionales ----------
vmName=$1
ovs=$2
vncPort=$3
shift 3
vlans=("$@")

# --------- Imágenes en el mismo directorio ---------
# Usa la misma que te funcionó en tu prueba manual:
UBUNTU_IMG_DEFAULT="focal-server-cloudimg-amd64.img"
CIRROS_IMG_DEFAULT="cirros-0.5.1-x86_64-disk.img"

# Resolver alias o ruta a archivo real
resolve_image() {
  local val="$1"
  case "$val" in
    cirros)  echo "$CIRROS_IMG_DEFAULT" ;;
    ubuntu)  echo "$UBUNTU_IMG_DEFAULT" ;;
    *)
      if [[ -f "$val" ]]; then
        echo "$val"
      else
        echo "[ERROR] Imagen no encontrada: '$val'. Usa alias 'cirros' o 'ubuntu', o pasa una ruta válida." >&2
        exit 1
      fi
      ;;
  esac
}

IMG="$(resolve_image "$IMAGE_ALIAS_OR_PATH")"
displayVNC=$((vncPort-5900))

if [[ ! -f $IMG ]]; then
  echo "[ERROR] Imagen $IMG no encontrada en $(pwd)"
  exit 1
fi

# --- Red user-mode opcional (como tu comando que funcionó) ---
# Si exportas USE_USERNET=1 y la imagen es ubuntu, usamos NAT user-mode y NO creamos TAP/OVS/VLANs.
USE_USERNET="${USE_USERNET:-0}"

# --- Reordenar: si existe VLAN 300, que sea eth0 (solo cuando usamos TAP/OVS) ---
INTERNET_VLAN=300
has_inet=false
for v in "${vlans[@]}"; do [[ "$v" == "$INTERNET_VLAN" ]] && has_inet=true; done
if [[ "$USE_USERNET" != "1" ]]; then
  if $has_inet; then
    reordered=("$INTERNET_VLAN")
    for v in "${vlans[@]}"; do [[ "$v" != "$INTERNET_VLAN" ]] && reordered+=("$v"); done
    vlans=("${reordered[@]}")
  fi
fi

# Directorio de logs (mapeos por VM)
LOGDIR="/var/log/vm-orchestrator"
MAPFILE="$LOGDIR/${vmName}.map"
if ! mkdir -p "$LOGDIR" 2>/dev/null; then
  LOGDIR="/tmp/vm-orchestrator"
  mkdir -p "$LOGDIR"
  MAPFILE="$LOGDIR/${vmName}.map"
fi

# --------- Detectar formato de imagen ---------
detect_img_format() {
  if command -v qemu-img >/dev/null 2>&1; then
    qemu-img info --output=json "$1" 2>/dev/null \
      | sed -n 's/.*"format": *"\([^"]*\)".*/\1/p'
  fi
}
FMT="$(detect_img_format "$IMG")"
if [[ -z "${FMT:-}" ]]; then
  case "$IMAGE_ALIAS_OR_PATH" in
    ubuntu) FMT="qcow2" ;;
    cirros) FMT="qcow2" ;;  # pon "raw" si tu cirros es RAW
    *)      FMT="qcow2" ;;
  esac
fi

# --------- Opciones base (igual a lo que te funcionó) ---------
MEM_OPTS=(-m 2048)           # 2G RAM
MACHINE_OPTS=(-machine q35)  # q35
BOOT_OPTS=(-boot order=c)    # desde disco
DISPLAY_OPTS=(-display none) # sin GTK; usamos VNC

# --------- Construcción de red ----------
NETARGS=()
{
  echo "# VM: $vmName  (VNC :$displayVNC -> puerto $vncPort)"
  echo "# Imagen: $IMG (format=$FMT)"
  echo "# Interfaces:"
} | tee "$MAPFILE" >/dev/null

USERNET_ARGS=()
if [[ "$USE_USERNET" == "1" && "$IMAGE_ALIAS_OR_PATH" == "ubuntu" ]]; then
  # Modo NAT user-mode (sin TAP/OVS/VLAN)
  USERNET_ARGS=(-netdev user,id=net0 -device virtio-net-pci,netdev=net0)
  echo "  eth0  user-mode (NAT)  (sin TAP/OVS)" | tee -a "$MAPFILE" >/dev/null
else
  # TAPs + OVS + VLANs (no usamos 'bus' ni 'addr'; QEMU autoplaza en q35)
  for idx in "${!vlans[@]}"; do
    vlan=${vlans[$idx]}
    shortName=$(echo "$vmName" | sed 's/[^a-zA-Z0-9]//g' | cut -c1-8)
    tapName="tap-${shortName}-${idx}"
    tapName="${tapName:0:15}"

    ip link show "$tapName" &>/dev/null || sudo ip tuntap add dev "$tapName" mode tap
    sudo ip link set dev "$tapName" up
    sudo ovs-vsctl --may-exist add-port "$ovs" "$tapName" tag="$vlan"

    hash=$(echo -n "${vmName}-${idx}" | sha256sum | cut -c1-10)
    b2=${hash:0:2}; b3=${hash:2:2}; b4=${hash:4:2}; b5=${hash:6:2}; b6=${hash:8:2}
    mac=$(printf '02:%s:%s:%s:%s:%s' "$b2" "$b3" "$b4" "$b5" "$b6")

    NETARGS+=(-netdev tap,id=net${idx},ifname=${tapName},script=no,downscript=no)
    NETARGS+=(-device virtio-net-pci,netdev=net${idx},mac=${mac})

    echo "  eth${idx}  vlan=${vlan}  tap=${tapName}  mac=${mac}" | tee -a "$MAPFILE" >/dev/null
  done
fi

echo "# Log guardado en: $MAPFILE"
echo "[INFO] Lanzando $vmName con $((${#vlans[@]})) NICs (o user-mode), VNC :$displayVNC ..."

# --------- Lanzamiento QEMU ---------
sudo qemu-system-x86_64 \
  -enable-kvm \
  -cpu host \
  "${MEM_OPTS[@]}" \
  "${MACHINE_OPTS[@]}" \
  "${BOOT_OPTS[@]}" \
  -vnc 0.0.0.0:"$displayVNC" \
  "${DISPLAY_OPTS[@]}" \
  -serial telnet:0.0.0.0:$((vncPort+1000)),server,nowait \
  -daemonize \
  -snapshot \
  "${USERNET_ARGS[@]}" \
  "${NETARGS[@]}" \
  -drive file="$IMG",if=virtio,format="$FMT",cache=none,aio=threads,discard=unmap

echo "[OK] VM $vmName lanzada. Revisa $MAPFILE para el mapeo de interfaces."
if $has_inet && [[ "$USE_USERNET" != "1" ]]; then
  echo "# Recuerda: dentro de la VM puedes pedir DHCP en eth0 (VLAN 300) con:"
  echo "#   sudo /sbin/cirros-dhcpc up eth0"
fi
