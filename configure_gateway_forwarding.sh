#!/bin/bash
# Script de Configuración de Port Forwarding en Gateway
# Gateway: 10.20.12.158 → Head Node: 10.0.10.1:8000

set -e  # Detener si hay errores

echo "════════════════════════════════════════════════════════════════"
echo "  🌐 TELECLOUD - Configuración de Port Forwarding en Gateway"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
GATEWAY_IP="10.20.12.158"
HEADNODE_IP="10.0.10.1"
HEADNODE_PORT="8000"
EXTERNAL_PORT="8080"

echo -e "${YELLOW}[1/4]${NC} Verificando permisos de superusuario..."
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}✗ Este script debe ejecutarse como root${NC}"
    echo -e "${YELLOW}Ejecuta:${NC} sudo bash configure_gateway_forwarding.sh"
    exit 1
fi
echo -e "${GREEN}✓${NC} Permisos correctos"

# ====================================================================
# PASO 1: Habilitar IP Forwarding
# ====================================================================
echo ""
echo -e "${YELLOW}[2/4]${NC} Habilitando IP forwarding en el kernel..."

# Habilitar temporalmente
sysctl -w net.ipv4.ip_forward=1 > /dev/null

# Habilitar permanentemente
if grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo -e "${GREEN}✓${NC} IP forwarding ya estaba habilitado permanentemente"
else
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    echo -e "${GREEN}✓${NC} IP forwarding habilitado permanentemente"
fi

# ====================================================================
# PASO 2: Configurar reglas iptables
# ====================================================================
echo ""
echo -e "${YELLOW}[3/4]${NC} Configurando reglas de iptables..."

# Limpiar reglas anteriores si existen (búsqueda específica)
echo "  • Limpiando reglas previas de TELECLOUD..."
iptables -t nat -D PREROUTING -p tcp --dport $EXTERNAL_PORT -j DNAT --to-destination $HEADNODE_IP:$HEADNODE_PORT 2>/dev/null || true
iptables -t nat -D POSTROUTING -p tcp -d $HEADNODE_IP --dport $HEADNODE_PORT -j MASQUERADE 2>/dev/null || true
iptables -D FORWARD -p tcp -d $HEADNODE_IP --dport $HEADNODE_PORT -j ACCEPT 2>/dev/null || true

# Agregar nuevas reglas
echo "  • Agregando regla PREROUTING (DNAT)..."
iptables -t nat -A PREROUTING -p tcp --dport $EXTERNAL_PORT -j DNAT --to-destination $HEADNODE_IP:$HEADNODE_PORT

echo "  • Agregando regla POSTROUTING (MASQUERADE)..."
iptables -t nat -A POSTROUTING -p tcp -d $HEADNODE_IP --dport $HEADNODE_PORT -j MASQUERADE

echo "  • Agregando regla FORWARD..."
iptables -A FORWARD -p tcp -d $HEADNODE_IP --dport $HEADNODE_PORT -j ACCEPT

echo -e "${GREEN}✓${NC} Reglas iptables configuradas"

# ====================================================================
# PASO 3: Persistir reglas iptables
# ====================================================================
echo ""
echo -e "${YELLOW}[4/4]${NC} Persistiendo reglas iptables..."

# Instalar iptables-persistent si no está instalado
if ! dpkg -l | grep -q iptables-persistent; then
    echo -e "${YELLOW}⚠${NC} Instalando iptables-persistent..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y iptables-persistent > /dev/null 2>&1
    echo -e "${GREEN}✓${NC} iptables-persistent instalado"
fi

# Guardar reglas actuales
netfilter-persistent save
echo -e "${GREEN}✓${NC} Reglas guardadas persistentemente"

# ====================================================================
# VERIFICACIÓN
# ====================================================================
echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}  ✓ CONFIGURACIÓN DE PORT FORWARDING COMPLETADA${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Configuración aplicada:"
echo "  • Puerto externo:     $EXTERNAL_PORT"
echo "  • Destino:            $HEADNODE_IP:$HEADNODE_PORT"
echo "  • IP Forwarding:      Habilitado"
echo "  • Persistencia:       Configurada"
echo ""
echo "📝 Verificar reglas:"
echo "  • Ver NAT:            sudo iptables -t nat -L -n -v"
echo "  • Ver FORWARD:        sudo iptables -L FORWARD -n -v"
echo "  • IP forward status:  cat /proc/sys/net/ipv4/ip_forward"
echo ""
echo "🌐 Acceso para usuarios:"
echo "  • URL:                http://$GATEWAY_IP:$EXTERNAL_PORT"
echo "  • Credenciales:       admin / admin123"
echo ""
echo "🔧 Comandos útiles:"
echo "  • Probar conexión:    curl -I http://$GATEWAY_IP:$EXTERNAL_PORT/login"
echo "  • Ver logs gateway:   sudo journalctl -f"
echo "  • Limpiar reglas:     sudo iptables -t nat -F && sudo iptables -F FORWARD"
echo "════════════════════════════════════════════════════════════════"
