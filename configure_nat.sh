#!/bin/bash
# configure_nat.sh

echo "=== CONFIGURANDO NAT PARA VLAN 300 ==="

# 1. Activar interfaz
echo "1. Activando interfaz gw300..."
sudo ip link set gw300 up
echo "   Estado de gw300:"
ip addr show gw300 | grep state

# 2. Configurar iptables
echo "2. Configurando iptables..."

# Limpiar reglas anteriores
sudo iptables -t nat -F
sudo iptables -F FORWARD

# Agregar reglas NAT
sudo iptables -t nat -A POSTROUTING -s 10.60.7.0/24 -o ens3 -j MASQUERADE

# Agregar reglas FORWARD stateful
sudo iptables -A FORWARD -i gw300 -o ens3 -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A FORWARD -i ens3 -o gw300 -m state --state ESTABLISHED,RELATED -j ACCEPT

# Configurar política por defecto
sudo iptables -P FORWARD DROP

# 3. Verificar configuración
echo "3. Verificando configuración:"
echo "   - Reglas NAT:"
sudo iptables -t nat -L -n
echo "   - Reglas FORWARD:"
sudo iptables -L FORWARD -n -v
echo "   - IP forwarding:"
sysctl net.ipv4.ip_forward

echo "=== CONFIGURACIÓN COMPLETADA ==="