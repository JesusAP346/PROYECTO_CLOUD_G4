#!/bin/bash
# Script de Despliegue Automático para Head Node (10.0.10.1)
# TELECLOUD - Sistema de Gestión de Topologías

set -e  # Detener si hay errores

echo "════════════════════════════════════════════════════════════════"
echo "  🚀 TELECLOUD - Despliegue en Head Node"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
PROJECT_DIR="$HOME/PROYECTO_CLOUD_G4"
VENV_DIR="$PROJECT_DIR/.venv"

# ====================================================================
# PASO 1: Verificar sistema
# ====================================================================
echo -e "${YELLOW}[1/8]${NC} Verificando sistema..."

# Verificar si estamos en Ubuntu
if [ ! -f /etc/os-release ]; then
    echo -e "${RED}✗ No se puede determinar el sistema operativo${NC}"
    exit 1
fi

source /etc/os-release
echo -e "${GREEN}✓${NC} Sistema: $PRETTY_NAME"

# Verificar Python 3.12
if command -v python3.12 &> /dev/null; then
    PYTHON_VERSION=$(python3.12 --version)
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION instalado"
else
    echo -e "${YELLOW}⚠${NC} Python 3.12 no encontrado. Instalando..."
    sudo apt update
    sudo apt install -y software-properties-common
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y python3.12 python3.12-venv python3.12-dev
    echo -e "${GREEN}✓${NC} Python 3.12 instalado"
fi

# ====================================================================
# PASO 2: Instalar MongoDB
# ====================================================================
echo ""
echo -e "${YELLOW}[2/8]${NC} Verificando MongoDB..."

if systemctl is-active --quiet mongod; then
    echo -e "${GREEN}✓${NC} MongoDB ya está corriendo"
else
    if command -v mongod &> /dev/null; then
        echo -e "${YELLOW}⚠${NC} MongoDB instalado pero no corriendo. Iniciando..."
        sudo systemctl start mongod
        sudo systemctl enable mongod
    else
        echo -e "${YELLOW}⚠${NC} MongoDB no encontrado. Instalando..."

        # Importar clave GPG
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
           sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

        # Agregar repositorio
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
           sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

        # Instalar
        sudo apt update
        sudo apt install -y mongodb-org

        # Iniciar servicio
        sudo systemctl start mongod
        sudo systemctl enable mongod

        echo -e "${GREEN}✓${NC} MongoDB instalado e iniciado"
    fi
fi

# Verificar que MongoDB esté corriendo
sleep 2
if systemctl is-active --quiet mongod; then
    echo -e "${GREEN}✓${NC} MongoDB corriendo correctamente"
else
    echo -e "${RED}✗ MongoDB no pudo iniciar${NC}"
    exit 1
fi

# ====================================================================
# PASO 3: Crear entorno virtual
# ====================================================================
echo ""
echo -e "${YELLOW}[3/8]${NC} Configurando entorno virtual..."

cd "$PROJECT_DIR"

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠${NC} Virtual environment ya existe. Eliminando..."
    rm -rf "$VENV_DIR"
fi

python3.12 -m venv "$VENV_DIR"
echo -e "${GREEN}✓${NC} Virtual environment creado"

# Activar venv
source "$VENV_DIR/bin/activate"

# ====================================================================
# PASO 4: Instalar dependencias
# ====================================================================
echo ""
echo -e "${YELLOW}[4/8]${NC} Instalando dependencias Python..."

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo -e "${GREEN}✓${NC} Dependencias instaladas"

# ====================================================================
# PASO 5: Inicializar base de datos
# ====================================================================
echo ""
echo -e "${YELLOW}[5/8]${NC} Inicializando base de datos MongoDB..."

python database/mongo_config.py

echo -e "${GREEN}✓${NC} Base de datos inicializada"

# ====================================================================
# PASO 6: Crear usuario admin
# ====================================================================
echo ""
echo -e "${YELLOW}[6/8]${NC} Verificando usuario administrador..."

# Verificar si admin ya existe
ADMIN_EXISTS=$(python -c "
from database.mongo_config import get_db
db = get_db()
result = db.users.find_one({'username': 'admin'})
print('exists' if result else 'notfound')
" 2>/dev/null)

if [ "$ADMIN_EXISTS" = "exists" ]; then
    echo -e "${GREEN}✓${NC} Usuario admin ya existe"
else
    echo -e "${YELLOW}⚠${NC} Creando usuario administrador..."
    python create_admin_mongo.py
    echo -e "${GREEN}✓${NC} Usuario admin creado (admin/admin123)"
fi

# ====================================================================
# PASO 7: Configurar servicio systemd
# ====================================================================
echo ""
echo -e "${YELLOW}[7/8]${NC} Configurando servicio systemd..."

# Crear archivo de servicio
sudo tee /etc/systemd/system/telecloud.service > /dev/null <<EOF
[Unit]
Description=TELECLOUD FastAPI Application
After=network.target mongod.service
Requires=mongod.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python main_fastapi.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Recargar systemd
sudo systemctl daemon-reload

# Detener servicio si está corriendo
if systemctl is-active --quiet telecloud; then
    echo -e "${YELLOW}⚠${NC} Deteniendo servicio anterior..."
    sudo systemctl stop telecloud
fi

# Habilitar e iniciar servicio
sudo systemctl enable telecloud
sudo systemctl start telecloud

# Esperar un momento
sleep 3

# Verificar estado
if systemctl is-active --quiet telecloud; then
    echo -e "${GREEN}✓${NC} Servicio TELECLOUD iniciado correctamente"
else
    echo -e "${RED}✗ Error al iniciar el servicio${NC}"
    echo -e "${YELLOW}Ver logs:${NC} sudo journalctl -u telecloud -n 50"
    exit 1
fi

# ====================================================================
# PASO 8: Verificar funcionamiento
# ====================================================================
echo ""
echo -e "${YELLOW}[8/8]${NC} Verificando funcionamiento..."

# Esperar a que la aplicación esté lista
sleep 2

# Probar endpoint
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/login 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓${NC} FastAPI respondiendo correctamente (HTTP $HTTP_STATUS)"
else
    echo -e "${RED}✗ FastAPI no responde correctamente (HTTP $HTTP_STATUS)${NC}"
    echo -e "${YELLOW}Ver logs:${NC} sudo journalctl -u telecloud -n 50"
    exit 1
fi

# ====================================================================
# RESUMEN FINAL
# ====================================================================
echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}  ✓ DESPLIEGUE COMPLETADO EXITOSAMENTE${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Información del sistema:"
echo "  • MongoDB:        $(systemctl is-active mongod)"
echo "  • TELECLOUD:      $(systemctl is-active telecloud)"
echo "  • URL local:      http://localhost:8000"
echo "  • Usuario admin:  admin / admin123"
echo ""
echo "📝 Comandos útiles:"
echo "  • Ver logs:       sudo journalctl -u telecloud -f"
echo "  • Reiniciar:      sudo systemctl restart telecloud"
echo "  • Estado:         sudo systemctl status telecloud"
echo "  • Detener:        sudo systemctl stop telecloud"
echo ""
echo "🔧 Siguiente paso:"
echo "  Configurar port forwarding en el Gateway para acceso externo"
echo "════════════════════════════════════════════════════════════════"
