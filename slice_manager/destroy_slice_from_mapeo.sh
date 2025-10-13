#!/usr/bin/env bash
# Destruye en los WORKERS sólo lo que corresponde a un slice,
# usando como fuente el output de:
#   ./mapeo_vms.sh --slice-id <ID>
#
# Para cada VM:
#   - Mata QEMU por VNC display (vnc_port - 5900), luego por -name y por TAPs (fallback).
#   - Borra los TAPs exactos listados por mapeo_vms.sh.
#   - Elimina puertos OVS con esos TAPs en el bridge indicado.
#
# Uso:
#   ./destroy_slice_from_mapeo.sh <ID_DEL_SLICE>
#
# Requisitos: ssh sin password (o con ssh-agent) al usuario de los workers.
# Variables opcionales:
#   SSH_USER (default: ubuntu)

set -euo pipefail

SLICE_ID="${1:-}"
if [[ -z "$SLICE_ID" ]]; then
  echo "Uso: $0 <ID_DEL_SLICE>" >&2
  exit 1
fi

SSH_USER="${SSH_USER:-ubuntu}"

# Validar presencia de mapeo_vms.sh en el directorio actual
if [[ ! -x "/home/ubuntu/mapeo_vms.sh" ]]; then
  echo "No encuentro ./mapeo_vms.sh ejecutable en el directorio actual." >&2
  exit 1
fi

# Ejecuta mapeo y parsea en TSV:
# host \t vm_name \t bridge \t vnc_port \t tap1,tap2,...
MAP_OUT="$(/home/ubuntu/mapeo_vms.sh --slice-id "$SLICE_ID" || true)"
if [[ -z "$MAP_OUT" ]]; then
  echo "mapeo_vms.sh no devolvió datos para el slice '$SLICE_ID'." >&2
  exit 1
fi

TSV="$(
  awk '
    BEGIN { vm=""; host=""; br=""; vnc=""; taps="" }
    # Cabecera de VM, ejemplo:
    #  VM: vm1-XXXX   host: 10.0.10.X   bridge: ovs_hostX   VNC: 5901   PUBLIC: 5901
    /^ VM:/ {
      # si había una VM anterior, imprímela
      if (vm != "" && host != "" && br != "" && vnc != "") {
        print host "\t" vm "\t" br "\t" vnc "\t" taps;
      }
      vm=""; host=""; br=""; vnc=""; taps="";
      if (match($0, /^ VM: ([^[:space:]]+)[[:space:]]+host: ([0-9.]+)[[:space:]]+bridge: ([^[:space:]]+)[[:space:]]+VNC: ([0-9]+)/, m)) {
        vm=m[1]; host=m[2]; br=m[3]; vnc=m[4];
      }
      next;
    }
    # Líneas de tabla con TAP (evita encabezados ----):
    /tap-/ && $0 !~ /^  ----/ {
      if (match($0, /(tap-[[:alnum:]-]+)/, t)) {
        if (taps == "") taps = t[1]; else taps = taps "," t[1];
      }
      next;
    }
    END {
      if (vm != "" && host != "" && br != "" && vnc != "") {
        print host "\t" vm "\t" br "\t" vnc "\t" taps;
      }
    }
  ' <<<"$MAP_OUT"
)"

if [[ -z "$TSV" ]]; then
  echo "No se pudieron parsear VMs/TAPs desde mapeo_vms.sh para '$SLICE_ID'." >&2
  echo "Salida vista:"
  echo "$MAP_OUT"
  exit 1
fi

# Hosts únicos
mapfile -t HOSTS < <(printf '%s\n' "$TSV" | awk -F'\t' '{print $1}' | sort -u)

echo "========== DESTRUCCIÓN SELECTIVA (fuente: mapeo_vms.sh) slice: $SLICE_ID =========="
for host in "${HOSTS[@]}"; do
  # Filtra filas de este host
  VMS_FOR_HOST="$(printf '%s\n' "$TSV" | awk -F'\t' -v h="$host" '$1==h {print $0}')"
  [[ -n "$VMS_FOR_HOST" ]] || continue
  echo "[*] Worker: $host"

  # Codifica el bloque TSV para pasarlo de forma segura al remoto
  B64="$(printf '%s' "$VMS_FOR_HOST" | base64 -w0)"

  # Pasamos la variable al remoto en la MISMA invocación ssh:
  ssh -T "${SSH_USER}@${host}" "B64_FROM_HEAD='$B64' bash -s" <<'EOS'
set -euo pipefail

process_vm() {
  local vm="$1" br="$2" vnc="$3" taps_csv="$4"
  local short="${vm//-/}"
  local disp=$(( vnc - 5900 )); if (( disp < 0 )); then disp=0; fi

  echo "  - VM: $vm (bridge=$br, vnc=$vnc -> :$disp)"

  # 1) Matar QEMU por VNC (más fiable en este entorno)
  local killed=0
  local pids_by_vnc
  # pgrep -fla => "PID CMD..."
  pids_by_vnc="$(pgrep -fla qemu-system-x86_64 | awk -v d=":$disp" '
    {
      # línea completa: PID <espacio> CMD...
      pid=$1
      $1=""; cmd=$0
      if (cmd ~ ("-vnc[[:space:]]+0.0.0.0:" d+0) || cmd ~ ("-vnc[[:space:]]+:" d+0)) {
        print pid
      }
    }' | sort -u | xargs -r echo)"
  if [[ -n "$pids_by_vnc" ]]; then
    echo "    · matando QEMU por VNC (:$disp) PIDs: $pids_by_vnc"
    for pid in $pids_by_vnc; do
      sudo kill -9 "$pid" 2>/dev/null || true
    done
    killed=1
  fi

  # 2) Si no hubo match por VNC, intenta por -name
  if [[ "$killed" -eq 0 ]]; then
    local pids_by_name
    pids_by_name="$(pgrep -f "qemu-system-x86_64.*-name[ =]${vm}" || true)"
    if [[ -n "$pids_by_name" ]]; then
      echo "    · matando QEMU por -name (PIDs: $pids_by_name)"
      sudo pkill -9 -f "qemu-system-x86_64.*-name[ =]${vm}" || true
      killed=1
    fi
  fi

  # 3) Si aún no, intenta por TAPs presentes en cmdline
  if [[ "$killed" -eq 0 && -n "${taps_csv:-}" ]]; then
    # Construye regex tipo "tap-aaa|tap-bbb" escapando caracteres especiales
    local regex
    regex="$(printf '%s' "$taps_csv" | sed -e 's/[].[^$*+?{}()|/\\]/\\&/g' -e 's/,/|/g')"
    local pids_by_tap
    pids_by_tap="$(pgrep -fla qemu-system-x86_64 | awk -v r="$regex" '
      {
        pid=$1; $1=""; cmd=$0
        if (cmd ~ r) print pid
      }' | sort -u | xargs -r echo)"
    if [[ -n "$pids_by_tap" ]]; then
      echo "    · matando QEMU por TAPs (PIDs: $pids_by_tap)"
      for pid in $pids_by_tap; do
        sudo kill -9 "$pid" 2>/dev/null || true
      done
      killed=1
    else
      echo "    · no se encontró QEMU por VNC/-name/TAP (ya podría estar muerto)"
    fi
  fi

  # 4) Borrar TAPs exactos listados por mapeo_vms.sh
  local cnt=0
  if [[ -n "${taps_csv:-}" ]]; then
    IFS=',' read -r -a TAPS <<<"$taps_csv"
    for t in "${TAPS[@]}"; do
      [[ -n "$t" ]] || continue
      if ip link show "$t" >/dev/null 2>&1; then
        echo "    · borrando TAP $t"
        sudo ip link del "$t" || true
        cnt=$((cnt+1))
      fi
    done
  fi
  [[ $cnt -gt 0 ]] || echo "    · no había TAPs para $vm"

  # 5) Limpiar puertos OVS en el bridge indicado
  if sudo ovs-vsctl br-exists "$br" 2>/dev/null; then
    local pcnt=0
    if [[ -n "${taps_csv:-}" ]]; then
      IFS=',' read -r -a TAPS <<<"$taps_csv"
      for p in "${TAPS[@]}"; do
        [[ -n "$p" ]] || continue
        if sudo ovs-vsctl list-ports "$br" | grep -qx "$p"; then
          echo "    · eliminando puerto OVS $p"
          sudo ovs-vsctl --if-exists del-port "$br" "$p" || true
          pcnt=$((pcnt+1))
        fi
      done
    fi
    [[ $pcnt -gt 0 ]] || echo "    · no había puertos OVS para $vm"
  else
    echo "    · el bridge '$br' no existe"
  fi
}

# === Recibe TSV por base64 desde el headnode ===
TSV_DECODED="$(printf '%s' "$B64_FROM_HEAD" | base64 -d)"

# Recorre filas: host \t vm \t bridge \t vnc \t taps_csv
while IFS=$'	' read -r _host vm br vnc taps; do
  [[ -n "${vm:-}" && -n "${br:-}" && -n "${vnc:-}" ]] || continue
  process_vm "$vm" "$br" "$vnc" "${taps:-}"
done <<<"$TSV_DECODED"

exit 0
EOS

done

echo "✅ Destrucción selectiva en workers completada (QEMU/TAPs/OVS)."
echo "Ahora libera el slice en el headnode:"
echo "  python3 /home/ubuntu/deploy_topology.py --release-slice '$SLICE_ID'"
