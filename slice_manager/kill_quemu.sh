#!/bin/bash

# Listar los procesos de QEMU
echo "Procesos QEMU encontrados:"
pgrep -fa qemu-system-x86_64

# Confirmar antes de matar (puedes quitar esta parte si quieres que sea automático)
read -p "¿Deseas terminar estos procesos? (s/n): " respuesta
if [[ "$respuesta" != "s" ]]; then
    echo "Operación cancelada."
    exit 0
fi

# Matar solo procesos qemu-system-x86_64
for pid in $(pgrep -f qemu-system-x86_64); do
    echo "Matando proceso QEMU PID: $pid"
    kill -9 "$pid"
done

echo "Todos los procesos QEMU fueron eliminados."
