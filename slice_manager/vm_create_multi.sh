#!/bin/bash
# Uso:
#   sudo ./vm_create_multi.sh [--image <alias|ruta>] [--vcpus N] [--ram-gb G] [--disk-gb G] \
#       <vmName> <ovsBridge> <vncPort> <vlan1> [<vlan2> ...]
# alias soportados: cirros (default), ubuntu
set -euo pipefail

# --------- Flags opcionales ----------
IMAGE_ALIAS_OR_PATH="cirros"
VCPUS=1
RAM_GB=1
DISK_GB=10

# Parseo de flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)       [[ $# -ge 2 ]] || { echo "[ERROR] Falta valor para --image"; exit 1; }; IMAGE_ALIAS_OR_PATH="$2"; shift 2 ;;
    --image=*)     IMAGE_ALIAS_OR_PATH="${1#--image=}"; shift 1 ;;
    --vcpus)       [[ $# -ge 2 ]] || { echo "[ERROR] Falta valor para --vcpus"; exit 1; }; VCPUS="$2"; shift 2 ;;
    --vcpus=*)     VCPUS="${1#--vcpus=}"; shift 1 ;;
    --ram-gb)      [[ $# -ge 2 ]] || { echo "[ERROR] Falta valor para --ram-gb"; exit 1; }; RAM_GB="$2"; shift 2 ;;
    --ram-gb=*)    RAM_GB="${1#--ram-gb=}"; shift 1 ;;
    --disk-gb)     [[ $# -ge 2 ]] || { echo "[ERROR] Falta valor para --disk-gb"; exit 1; }; DISK_GB="$2"; shift 2 ;;
    --disk-gb=*)   DISK_GB="${1#--disk-gb=}"; shift 1 ;;
    *) break ;;
  esac
done

# --------- Posicionales ----------
if [[ $# -lt 3 ]]; then
  echo "Uso: sudo $0 [--image ...] [--vcpus N] [--ram-gb G] [--disk-gb G] <vmName> <ovsBridge> <vncPort> <vlan1> [<vlan2> ...]"
  exit 1
fi
vmName=$1
ovs=$2
vncPort=$3
shift 3
vlans=("${@:-}")

# --------- Imágenes por defecto (mismo directorio) ---------
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

# --- Path absoluto de la imagen base (clave para evitar el error del backing file) ---
BASE_IMG_ABS="$(readlink -f "$IMG" 2>/dev/null || python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$IMG")"

# --- Red user-mode opcional ---
USE_USERNET="${USE_USERNET:-0}"

# --- Reordenar VLAN 300 primero (solo TAP/OVS) ---
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

# Directorio de logs
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
    qemu-img info --output=json "$BASE_IMG_ABS" 2>/dev/null \
      | sed -n 's/.*"format": *"\([^"]*\)".*/\1/p'
  fi
}
FMT="$(detect_img_format "$BASE_IMG_ABS")"
if [[ -z "${FMT:-}" ]]; then
  case "$IMAGE_ALIAS_OR_PATH" in
    ubuntu) FMT="qcow2" ;;
    cirros) FMT="qcow2" ;;
    *)      FMT="qcow2" ;;
  esac
fi

# --------- Memoria y CPU desde flavor ----------
RAM_MIB=$(awk -v g="$RAM_GB" 'BEGIN{printf "%d", (g*1024)+0.5}')
MEM_OPTS=(-m "$RAM_MIB")
SMP_OPTS=(-smp "$VCPUS")
MACHINE_OPTS=(-machine q35)
BOOT_OPTS=(-boot order=c)
DISPLAY_OPTS=(-display none)

# --------- Disco por-VM (overlay qcow2 con backing absoluto) ----------
DISKDIR="/var/lib/vm-orchestrator/disks"
sudo mkdir -p "$DISKDIR"
VM_DISK="$DISKDIR/${vmName}.qcow2"

if [[ ! -f "$VM_DISK" ]]; then
  sudo qemu-img create -f qcow2 -F "$FMT" -b "$BASE_IMG_ABS" "$VM_DISK" >/dev/null
fi

# Tamaño virtual base (GiB) y resize si flavor > base
BASE_VSIZE_BYTES=$(qemu-img info --output=json "$BASE_IMG_ABS" 2>/dev/null | sed -n 's/.*"virtual-size": *\([0-9]\+\).*/\1/p')
if [[ -z "${BASE_VSIZE_BYTES:-}" ]]; then
  BASE_VSIZE_GB=10
else
  BASE_VSIZE_GB=$(awk -v b="$BASE_VSIZE_BYTES" 'BEGIN{printf "%d", (b/1024/1024/1024)+0.5}')
fi
if (( DISK_GB > BASE_VSIZE_GB )); then
  sudo qemu-img resize "$VM_DISK" "${DISK_GB}G" >/dev/null
fi

# --------- Construcción de red ----------
NETARGS=()
{
  echo "# VM: $vmName  (VNC :$displayVNC -> puerto $vncPort)"
  echo "# Imagen base: $BASE_IMG_ABS (format=$FMT) -> overlay: $VM_DISK (disk=${DISK_GB}G, base=${BASE_VSIZE_GB}G)"
  echo "# vCPUs=$VCPUS  RAM=${RAM_GB}GiB"
  echo "# Interfaces:"
} | tee "$MAPFILE" >/dev/null

USERNET_ARGS=()
if [[ "$USE_USERNET" == "1" && "$IMAGE_ALIAS_OR_PATH" == "ubuntu" ]]; then
  USERNET_ARGS=(-netdev user,id=net0 -device virtio-net-pci,netdev=net0)
  echo "  eth0  user-mode (NAT)  (sin TAP/OVS)" | tee -a "$MAPFILE" >/dev/null
else
  IS_UBUNTU=0
  [[ "$IMAGE_ALIAS_OR_PATH" == "ubuntu" ]] && IS_UBUNTU=1
  PCI_BASE_SLOT=3

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

    if [[ $IS_UBUNTU -eq 1 ]]; then
      slot=$((PCI_BASE_SLOT + idx))
      slot_hex=$(printf '0x%02x' "$slot")
      NETARGS+=(-device virtio-net-pci,netdev=net${idx},mac=${mac},bus=pcie.0,addr=${slot_hex})
      guest_if="enp0s${slot}"
    else
      NETARGS+=(-device virtio-net-pci,netdev=net${idx},mac=${mac})
      guest_if="eth${idx}"
    fi

    echo "  ${guest_if}  vlan=${vlan}  tap=${tapName}  mac=${mac}" | tee -a "$MAPFILE" >/dev/null
  done
fi

echo "# Log guardado en: $MAPFILE"
echo "[INFO] Lanzando $vmName con $((${#vlans[@]})) NICs (o user-mode), VNC :$displayVNC ..."

# --------- Lanzamiento QEMU ---------
sudo qemu-system-x86_64 \
  -enable-kvm \
  -cpu host \
  "${MEM_OPTS[@]}" \
  "${SMP_OPTS[@]}" \
  "${MACHINE_OPTS[@]}" \
  "${BOOT_OPTS[@]}" \
  -vnc 0.0.0.0:"$displayVNC" \
  "${DISPLAY_OPTS[@]}" \
  -serial telnet:0.0.0.0:$((vncPort+1000)),server,nowait \
  -daemonize \
  -snapshot \
  "${USERNET_ARGS[@]}" \
  "${NETARGS[@]}" \
  -drive file="$VM_DISK",if=virtio,format=qcow2,cache=none,aio=threads,discard=unmap

echo "[OK] VM $vmName lanzada. Revisa $MAPFILE para el mapeo de interfaces."

# Pista DHCP si hay VLAN 300
if $has_inet && [[ "$USE_USERNET" != "1" ]]; then
  if [[ "${IMAGE_ALIAS_OR_PATH}" == "ubuntu" ]]; then
    echo "# Recuerda (Ubuntu): dentro de la VM puedes pedir DHCP en enp0s3 (VLAN 300) con:"
    echo "#   sudo dhclient enp0s3"
  else
    echo "# Recuerda (Cirros): dentro de la VM puedes pedir DHCP en eth0 (VLAN 300) con:"
    echo "#   sudo /sbin/cirros-dhcpc up eth0"
  fi
fi
