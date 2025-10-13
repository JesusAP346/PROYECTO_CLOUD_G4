#!/usr/bin/env bash
  # Uso: /home/ubuntu/eliminar_slice.sh <SLICE_ID>
  # Script mejorado con logging detallado y verificación de errores

  ID="$1"

  # Validar que se proporcionó un ID
  [ -n "$ID" ] || {
      echo "ERROR: Uso incorrecto"
      echo "Uso: $0 <SLICE_ID>"
      exit 1
  }

  echo "=========================================="
  echo "INICIANDO ELIMINACIÓN DE SLICE: $ID"
  echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=========================================="

  # PASO 1: Ejecutar destroy_slice_from_mapeo.sh
  echo ""
  echo "[PASO 1/2] Ejecutando destroy_slice_from_mapeo.sh..."
  DESTROY_SCRIPT="/home/ubuntu/destroy_slice_from_mapeo.sh"

  # Verificar que el script existe
  if [ ! -f "$DESTROY_SCRIPT" ]; then
      echo "ERROR: No se encontró el script: $DESTROY_SCRIPT"
      exit 1
  fi

  # Verificar que el script tiene permisos de ejecución
  if [ ! -x "$DESTROY_SCRIPT" ]; then
      echo "ERROR: El script no tiene permisos de ejecución: $DESTROY_SCRIPT"
      echo "Solución: chmod +x $DESTROY_SCRIPT"
      exit 1
  fi

  # Ejecutar el script y capturar el código de salida
  echo "Ejecutando: $DESTROY_SCRIPT $ID"
  "$DESTROY_SCRIPT" "$ID"
  DESTROY_EXIT_CODE=$?

  if [ $DESTROY_EXIT_CODE -eq 0 ]; then
      echo "✓ destroy_slice_from_mapeo.sh ejecutado exitosamente (exit code: $DESTROY_EXIT_CODE)"
  else
      echo "✗ ERROR: destroy_slice_from_mapeo.sh falló (exit code: $DESTROY_EXIT_CODE)"
      echo "ABORTANDO: No se continuará con la liberación de recursos"
      exit $DESTROY_EXIT_CODE
  fi

  # PASO 2: Ejecutar deploy_topology.py --release-slice
  echo ""
  echo "[PASO 2/2] Ejecutando deploy_topology.py --release-slice..."
  DEPLOY_SCRIPT="/home/ubuntu/deploy_topology.py"

  # Verificar que el script existe
  if [ ! -f "$DEPLOY_SCRIPT" ]; then
      echo "ERROR: No se encontró el script: $DEPLOY_SCRIPT"
      exit 1
  fi

  # Ejecutar el script y capturar el código de salida
  echo "Ejecutando: python3 $DEPLOY_SCRIPT --release-slice $ID"
  python3 "$DEPLOY_SCRIPT" --release-slice "$ID"
  RELEASE_EXIT_CODE=$?

  if [ $RELEASE_EXIT_CODE -eq 0 ]; then
      echo "✓ deploy_topology.py --release-slice ejecutado exitosamente (exit code: $RELEASE_EXIT_CODE)"
  else
      echo "✗ ERROR: deploy_topology.py --release-slice falló (exit code: $RELEASE_EXIT_CODE)"
      exit $RELEASE_EXIT_CODE
  fi

  # FINALIZACIÓN EXITOSA
  echo ""
  echo "=========================================="
  echo "✓ SLICE $ID ELIMINADO EXITOSAMENTE"
  echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=========================================="
  exit 0
