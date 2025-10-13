#!/bin/bash
# destroy_slice.sh - Destruye un slice específico

if [ $# -ne 1 ]; then
    echo "Uso: $0 <slice-id>"
    echo "Ejemplo: $0 adrian_v2-20251013-004759"
    exit 1
fi

SLICE_ID=$1

echo "=== Destruyendo slice: $SLICE_ID ==="

# 1. Destruir VMs en workers y liberar recursos
echo "Destruyendo VMs y liberando recursos..."
python3 deploy_topology_alex.py --destroy-slice "$SLICE_ID"

if [ $? -eq 0 ]; then
    echo "✅ Slice $SLICE_ID destruido exitosamente"
else
    echo "❌ Error al destruir el slice $SLICE_ID"
    exit 1
fi
