# Guía de Despliegue TELECLOUD en Head Node

Esta guía te ayudará a desplegar el sistema TELECLOUD (FastAPI + MongoDB) en el Head Node para que todo tu equipo pueda acceder sin necesidad de configuración local.

## 📋 Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Arquitectura del Despliegue](#arquitectura-del-despliegue)
3. [Paso 1: Preparar el Proyecto](#paso-1-preparar-el-proyecto)
4. [Paso 2: Subir Proyecto al Head Node](#paso-2-subir-proyecto-al-head-node)
5. [Paso 3: Desplegar en Head Node](#paso-3-desplegar-en-head-node)
6. [Paso 4: Configurar Port Forwarding en Gateway](#paso-4-configurar-port-forwarding-en-gateway)
7. [Paso 5: Verificar Funcionamiento](#paso-5-verificar-funcionamiento)
8. [Acceso para el Equipo](#acceso-para-el-equipo)
9. [Troubleshooting](#troubleshooting)
10. [Comandos Útiles](#comandos-útiles)

---

## Requisitos Previos

### Información de Acceso SSH

**Acceso desde tu máquina local:**

| Componente | Comando SSH | Password |
|------------|-------------|----------|
| Gateway | `ssh ubuntu@10.20.12.158` | ubuntu |
| Head Node | `ssh ubuntu@10.20.12.158 -p 5801` | tallarinesverdes12 |
| Worker 1 | `ssh ubuntu@10.20.12.158 -p 5802` | ubuntu |
| Worker 2 | `ssh ubuntu@10.20.12.158 -p 5803` | ubuntu |
| Worker 3 | `ssh ubuntu@10.20.12.158 -p 5804` | ubuntu |
| OFS | `ssh ubuntu@10.20.12.158 -p 5805` | ubuntu |

Los puertos 5801-5805 son port forwardings configurados en el Gateway que te permiten acceder directamente a cada servidor interno.

**IPs de la red interna (10.0.10.0/24):**

| Componente | IP Interna | Acceso desde Gateway |
|------------|-----------|---------------------|
| Head Node | 10.0.10.1 | `ssh ubuntu@10.0.10.1` |
| Worker 1 | 10.0.10.2 | `ssh ubuntu@10.0.10.2` |
| Worker 2 | 10.0.10.3 | `ssh ubuntu@10.0.10.3` |
| Worker 3 | 10.0.10.4 | `ssh ubuntu@10.0.10.4` |
| OFS | 10.0.10.5 | `ssh ubuntu@10.0.10.5` |

**Particularidad del Head Node:**
- Desde el Head Node puedes hacer SSH a cualquier Worker/OFS sin password (tiene SSH keys configuradas)
- Desde Workers/OFS entre sí, sí piden password

### Software Requerido Localmente
- Cliente SSH (OpenSSH, PuTTY, etc.)
- SCP o herramienta similar para transferencia de archivos
- Navegador web moderno

---

## Arquitectura del Despliegue

```
┌─────────────────────────────────────────────────────────────┐
│  Tu Máquina Local                                           │
│  ssh ubuntu@10.20.12.158 -p 580X                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │   Gateway    │
                    │ 10.20.12.158 │
                    │ Puertos:     │
                    │  22 (Gateway)│
                    │  5801→HN     │
                    │  5802→W1     │
                    │  5803→W2     │
                    │  5804→W3     │
                    │  5805→OFS    │
                    │  8080→HN:8000│
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │     Red Interna (10.0.10.0/24)      │
        └──────────────────┬──────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Head Node   │
                    │  10.0.10.1   │
                    ├──────────────┤
                    │ FastAPI:8000 │
                    │ MongoDB:27017│
                    │ SSH keys → * │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┬───────────┐
          │                │                │           │
     ┌────▼────┐     ┌────▼────┐     ┌────▼────┐  ┌───▼───┐
     │Worker 1 │     │Worker 2 │     │Worker 3 │  │  OFS  │
     │10.0.10.2│     │10.0.10.3│     │10.0.10.4│  │10.0.10│
     └─────────┘     └─────────┘     └─────────┘  └───────┘
```

**Flujo de Acceso Web:**
1. Usuario accede a `http://10.20.12.158:8080` desde su navegador
2. Gateway redirige la petición a `10.0.10.1:8000` (Head Node)
3. FastAPI en Head Node procesa la petición
4. MongoDB en Head Node gestiona la persistencia de datos
5. Head Node orquesta despliegues en Workers (sin password por SSH keys)

---

## Paso 1: Preparar el Proyecto

### 1.1 Verificar Archivos Requeridos

Asegúrate de que tu proyecto local contiene estos archivos:

```bash
PROYECTO_CLOUD_G4/
├── main_fastapi.py           # Aplicación FastAPI principal
├── auth_jwt.py                # Sistema de autenticación JWT
├── requirements.txt           # Dependencias Python
├── database/
│   └── mongo_config.py        # Configuración MongoDB
├── create_admin_mongo.py      # Script para crear usuario admin
├── templates/                 # Plantillas HTML (Jinja2)
│   ├── index.html
│   ├── login.html
│   └── register.html
├── static/                    # Archivos estáticos (CSS, JS, imágenes)
│   ├── script.js
│   └── styles.css
├── slice_manager/             # Orquestador de topologías
├── deploy_headnode.sh         # Script de despliegue automático
└── configure_gateway_forwarding.sh  # Script de port forwarding
```

### 1.2 Verificar que main_fastapi.py esté configurado para producción

Abre `main_fastapi.py` y verifica que la última sección tenga:

```python
if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" permite acceso desde cualquier IP (necesario para producción)
    uvicorn.run("main_fastapi:app", host="0.0.0.0", port=8000, reload=False)
```

✅ **host="0.0.0.0"** es crucial para permitir acceso externo al servicio.

---

## Paso 2: Subir Proyecto al Head Node

### Método A: Subir Directamente al Head Node (Recomendado)

Desde tu **máquina local**, aprovecha el port forwarding del Gateway para subir directamente:

```bash
scp -P 5801 -r PROYECTO_CLOUD_G4/ ubuntu@10.20.12.158:~/
# Password: tallarinesverdes12
```

**Nota:** Usa `-P` (mayúscula) para especificar el puerto en SCP.

### Método B: En Dos Pasos (Gateway → Head Node)

#### 2.1 Subir al Gateway

```bash
scp -r PROYECTO_CLOUD_G4/ ubuntu@10.20.12.158:~/
# Password: ubuntu
```

#### 2.2 Conectar al Gateway

```bash
ssh ubuntu@10.20.12.158
# Password: ubuntu
```

#### 2.3 Copiar del Gateway al Head Node

Desde dentro del Gateway, usando IPs internas:

```bash
scp -r ~/PROYECTO_CLOUD_G4/ ubuntu@10.0.10.1:~/
# Password: tallarinesverdes12
```

### 2.4 Verificar que el proyecto se subió correctamente

Conecta al Head Node directamente desde tu máquina local:

```bash
ssh ubuntu@10.20.12.158 -p 5801
# Password: tallarinesverdes12
```

Una vez dentro del Head Node:
```bash
ls -la ~/PROYECTO_CLOUD_G4
# Deberías ver todos los archivos del proyecto
```

---

## Paso 3: Desplegar en Head Node

### 3.1 Conectar al Head Node

Desde tu **máquina local**:

```bash
ssh ubuntu@10.20.12.158 -p 5801
# Password: tallarinesverdes12
```

### 3.2 Dar permisos de ejecución al script

```bash
cd ~/PROYECTO_CLOUD_G4
chmod +x deploy_headnode.sh
```

### 3.3 Ejecutar el script de despliegue

```bash
./deploy_headnode.sh
```

Este script realizará automáticamente:
- ✅ Verificación del sistema operativo (Ubuntu)
- ✅ Instalación de Python 3.12 (si es necesario)
- ✅ Instalación y configuración de MongoDB 7.0
- ✅ Creación del entorno virtual Python (.venv)
- ✅ Instalación de todas las dependencias (FastAPI, pymongo, etc.)
- ✅ Inicialización de la base de datos MongoDB
- ✅ Creación del usuario admin (admin/admin123)
- ✅ Configuración del servicio systemd para auto-start
- ✅ Inicio del servicio TELECLOUD
- ✅ Verificación de funcionamiento (HTTP 200)

**Tiempo estimado:** 5-10 minutos dependiendo de la velocidad de la conexión.

### 3.4 Verificar que el servicio está corriendo

```bash
sudo systemctl status telecloud
```

Deberías ver:
```
● telecloud.service - TELECLOUD FastAPI Application
   Loaded: loaded (/etc/systemd/system/telecloud.service; enabled)
   Active: active (running) since ...
   Main PID: ...
```

### 3.5 Probar localmente desde Head Node

```bash
curl -I http://localhost:8000/login
```

**Respuesta esperada:**
```
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
...
```

---

## Paso 4: Configurar Port Forwarding en Gateway

### 4.1 Copiar script al Gateway

Desde tu **máquina local**:

```bash
scp configure_gateway_forwarding.sh ubuntu@10.20.12.158:~/
# Password: ubuntu
```

### 4.2 Conectar al Gateway

```bash
ssh ubuntu@10.20.12.158
# Password: ubuntu
```

### 4.3 Ejecutar el script de configuración

```bash
cd ~
chmod +x configure_gateway_forwarding.sh
sudo ./configure_gateway_forwarding.sh
```

Este script configurará automáticamente:
- ✅ Habilita IP forwarding en el kernel (`net.ipv4.ip_forward=1`)
- ✅ Configura reglas iptables NAT para PREROUTING (puerto 8080 → 10.0.10.1:8000)
- ✅ Configura reglas iptables POSTROUTING (MASQUERADE)
- ✅ Configura reglas iptables FORWARD (permitir tráfico)
- ✅ Persiste reglas con iptables-persistent (sobreviven reinicios)

### 4.4 Verificar reglas iptables

```bash
sudo iptables -t nat -L -n -v | grep 8080
```

**Salida esperada:**
```
0     0 DNAT       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            tcp dpt:8080 to:10.0.10.1:8000
```

También verifica la regla de MASQUERADE:

```bash
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.0.10.1
```

---

## Paso 5: Verificar Funcionamiento

### 5.1 Desde el Gateway

Verifica que el Gateway puede alcanzar el Head Node:

```bash
# Desde el Gateway
curl -I http://10.0.10.1:8000/login
```

**Respuesta esperada:** `HTTP/1.1 200 OK`

### 5.2 Desde el Gateway (usando port forwarding local)

```bash
# Desde el Gateway
curl -I http://localhost:8080/login
```

**Respuesta esperada:** `HTTP/1.1 200 OK`

### 5.3 Desde tu máquina local

Abre tu navegador y accede a:

```
http://10.20.12.158:8080
```

Deberías ver la página de login de TELECLOUD con:
- Logo y nombre del proyecto
- Campos de usuario y contraseña
- Botón "Iniciar Sesión"
- Link "Regístrate aquí"

### 5.4 Probar login

Usa las credenciales del administrador:
- **Usuario:** `admin`
- **Password:** `admin123`

Si todo funciona correctamente, deberías:
1. Ser autenticado con JWT
2. Ser redirigido al editor de topologías (index.html)
3. Ver el canvas de diseño con herramientas de topología

---

## Acceso para el Equipo

### Acceso Web Directo (Recomendado)

Cualquier miembro del equipo puede acceder desde su navegador:

```
URL: http://10.20.12.158:8080
```

**Credenciales iniciales:**
- Usuario: `admin`
- Password: `admin123`

### Crear Cuentas Individuales

Cada miembro del equipo debe crear su propia cuenta:

1. Acceder a `http://10.20.12.158:8080`
2. Hacer clic en **"Regístrate aquí"**
3. Completar el formulario:
   - **Nombre de usuario:** único, sin espacios
   - **Email:** correo electrónico válido
   - **Password:** mínimo seguro recomendado
   - **Tipo de cuenta:**
     - **Usuario General:** Máximo 3 slices, solo linux-AZ-1
     - **Usuario VIP:** Máximo 10 slices, todas las AZ disponibles
4. Clic en **"Crear Cuenta"**

### Permisos por Rol

| Rol | Max Slices | Availability Zones Disponibles |
|-----|-----------|-------------------------------|
| **General** | 3 | linux-AZ-1, openstack-AZ-1 (próximamente) |
| **VIP** | 10 | Automático, linux-AZ-1, linux-AZ-2, openstack-AZ-1/2 (próximamente) |
| **Admin** | Ilimitado | Automático, linux-AZ-1, linux-AZ-2, openstack-AZ-1/2 (próximamente) |

### Acceso SSH al Head Node (Solo Administradores)

Si necesitas acceso SSH para administración:

```bash
# Desde tu máquina local al Head Node
ssh ubuntu@10.20.12.158 -p 5801
# Password: tallarinesverdes12
```

Desde el Head Node puedes conectarte a Workers sin password:

```bash
# Desde Head Node a Worker 1 (sin password)
ssh ubuntu@10.0.10.2

# Desde Head Node a Worker 2 (sin password)
ssh ubuntu@10.0.10.3

# Desde Head Node a OFS (sin password)
ssh ubuntu@10.0.10.5
```

---

## Troubleshooting

### Problema 1: No puedo acceder a http://10.20.12.158:8080

**Síntomas:**
- "Connection refused"
- "This site can't be reached"
- Timeout al cargar la página

**Diagnóstico y Soluciones:**

#### Paso 1: Verificar que FastAPI está corriendo

```bash
# Conectar al Head Node
ssh ubuntu@10.20.12.158 -p 5801

# Ver estado del servicio
sudo systemctl status telecloud
```

Si muestra `inactive` o `failed`:
```bash
# Iniciar el servicio
sudo systemctl start telecloud

# Ver logs para identificar errores
sudo journalctl -u telecloud -n 50
```

#### Paso 2: Verificar que FastAPI escucha en 0.0.0.0:8000

```bash
# Desde el Head Node
ss -tulnp | grep 8000
```

**Salida correcta:**
```
tcp   LISTEN  0  128  0.0.0.0:8000  0.0.0.0:*  users:(("python",pid=...))
```

Si muestra `127.0.0.1:8000` en lugar de `0.0.0.0:8000`, main_fastapi.py no está configurado correctamente.

#### Paso 3: Verificar port forwarding en Gateway

```bash
# Conectar al Gateway
ssh ubuntu@10.20.12.158

# Ver reglas de NAT
sudo iptables -t nat -L -n -v | grep 8080
```

Si no aparecen reglas, ejecuta:
```bash
sudo ./configure_gateway_forwarding.sh
```

#### Paso 4: Verificar conectividad Gateway → Head Node

```bash
# Desde el Gateway
curl -I http://10.0.10.1:8000/login
```

Si falla, verifica la red interna y que el Head Node esté activo.

---

### Problema 2: El servicio TELECLOUD no inicia

**Síntomas:**
```bash
sudo systemctl status telecloud
# Output: failed (Result: exit-code)
```

**Soluciones:**

#### Ver logs detallados

```bash
sudo journalctl -u telecloud -n 100 --no-pager
```

Busca errores comunes:
- `ModuleNotFoundError`: Falta instalar dependencias
- `Failed to connect to MongoDB`: MongoDB no está corriendo
- `Address already in use`: Puerto 8000 ocupado por otro proceso
- `Permission denied`: Problema de permisos en archivos

#### Verificar MongoDB

```bash
sudo systemctl status mongod
```

Si no está corriendo:
```bash
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### Verificar entorno virtual y dependencias

```bash
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate
pip list | grep -E "fastapi|pymongo|uvicorn"
```

Si faltan dependencias:
```bash
pip install -r requirements.txt
```

#### Probar ejecución manual para ver errores

```bash
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate
python main_fastapi.py
```

Esto mostrará errores detallados en tiempo real.

---

### Problema 3: MongoDB no está corriendo

**Síntomas:**
- Error: "Failed to connect to MongoDB"
- `systemctl status mongod` muestra `inactive (dead)`

**Soluciones:**

#### Iniciar MongoDB

```bash
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### Ver logs de MongoDB

```bash
sudo journalctl -u mongod -n 50
```

#### Verificar que MongoDB escucha en 27017

```bash
ss -tulnp | grep 27017
```

#### Probar conexión manual

```bash
mongosh
# Debería conectarse sin errores
```

---

### Problema 4: Error de autenticación JWT

**Síntomas:**
- "No se pudo validar las credenciales"
- Login rechazado con credenciales correctas
- Token inválido o expirado

**Soluciones:**

#### Verificar que el usuario admin existe en MongoDB

```bash
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate
python -c "
from database.mongo_config import get_db
db = get_db()
user = db.users.find_one({'username': 'admin'})
if user:
    print(f'✓ Usuario admin encontrado: {user[\"email\"]}')
else:
    print('✗ Usuario admin NO existe')
"
```

#### Recrear usuario admin

```bash
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate
python create_admin_mongo.py
```

#### Verificar SECRET_KEY en auth_jwt.py

Abre `auth_jwt.py` y asegúrate de que `SECRET_KEY` esté definida y sea consistente.

---

### Problema 5: Port forwarding no funciona después de reiniciar Gateway

**Síntomas:**
- Funcionaba antes pero dejó de funcionar
- Después de `reboot` del Gateway no se puede acceder

**Soluciones:**

#### Verificar que iptables-persistent está instalado

```bash
# Desde el Gateway
dpkg -l | grep iptables-persistent
```

Si no está instalado:
```bash
sudo apt install iptables-persistent
```

#### Recargar reglas de iptables

```bash
sudo netfilter-persistent reload
```

#### Verificar que IP forwarding está habilitado

```bash
cat /proc/sys/net/ipv4/ip_forward
# Debe mostrar: 1
```

Si muestra `0`:
```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

#### Re-ejecutar script de configuración

```bash
sudo ./configure_gateway_forwarding.sh
```

---

### Problema 6: No se pueden desplegar topologías a los Workers

**Síntomas:**
- La interfaz web funciona pero los despliegues fallan
- Error: "SSH connection failed" en logs

**Soluciones:**

#### Verificar SSH keys desde Head Node

```bash
# Desde Head Node
ssh ubuntu@10.0.10.2
# NO debe pedir password
```

Si pide password, las SSH keys no están configuradas:

```bash
# Desde Head Node, generar keys si no existen
ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa

# Copiar key a Workers
ssh-copy-id ubuntu@10.0.10.2
ssh-copy-id ubuntu@10.0.10.3
ssh-copy-id ubuntu@10.0.10.4
ssh-copy-id ubuntu@10.0.10.5
```

#### Verificar que Workers están accesibles

```bash
# Desde Head Node
ping -c 3 10.0.10.2
ping -c 3 10.0.10.3
ping -c 3 10.0.10.4
ping -c 3 10.0.10.5
```

---

## Comandos Útiles

### Gestión del Servicio TELECLOUD

```bash
# Ver estado del servicio
sudo systemctl status telecloud

# Iniciar servicio
sudo systemctl start telecloud

# Detener servicio
sudo systemctl stop telecloud

# Reiniciar servicio (después de cambios en código)
sudo systemctl restart telecloud

# Ver logs en tiempo real
sudo journalctl -u telecloud -f

# Ver últimas 100 líneas de logs
sudo journalctl -u telecloud -n 100

# Ver logs desde hoy
sudo journalctl -u telecloud --since today

# Ver logs con errores
sudo journalctl -u telecloud -p err
```

### Gestión de MongoDB

```bash
# Ver estado
sudo systemctl status mongod

# Iniciar MongoDB
sudo systemctl start mongod

# Detener MongoDB
sudo systemctl stop mongod

# Reiniciar MongoDB
sudo systemctl restart mongod

# Conectar a MongoDB shell
mongosh

# Conectar a base de datos específica
mongosh telecloud_db

# Ver bases de datos
mongosh --eval "show dbs"

# Ver usuarios registrados
mongosh telecloud_db --eval "db.users.find().pretty()"

# Contar usuarios
mongosh telecloud_db --eval "db.users.countDocuments()"

# Ver slices desplegados
mongosh telecloud_db --eval "db.slices.find().pretty()"
```

### Verificación de Red

```bash
# Ver todos los puertos escuchando
ss -tulnp

# Ver puertos específicos
ss -tulnp | grep 8000    # FastAPI
ss -tulnp | grep 27017   # MongoDB

# Probar conectividad local (desde Head Node)
curl -I http://localhost:8000/login

# Probar conectividad interna (desde Gateway)
curl -I http://10.0.10.1:8000/login

# Probar port forwarding (desde Gateway)
curl -I http://localhost:8080/login

# Ver reglas de firewall (desde Gateway)
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v

# Ver conexiones activas
sudo netstat -an | grep 8000

# Ver estadísticas de tráfico
sudo iptables -t nat -L -n -v | grep pkts
```

### Gestión del Proyecto

```bash
# Activar entorno virtual
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate

# Desactivar entorno virtual
deactivate

# Ver dependencias instaladas
pip list

# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Verificar versión de Python
python --version

# Ejecutar FastAPI manualmente (para debugging)
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate
python main_fastapi.py

# Ver variables de entorno
env | grep -i python
```

### Debugging Avanzado

```bash
# Ver procesos de Python corriendo
ps aux | grep python

# Matar proceso de FastAPI manualmente
pkill -f main_fastapi.py

# Ver uso de recursos del servicio
systemd-cgtop

# Monitorear uso de CPU/RAM en tiempo real
htop

# Ver espacio en disco
df -h

# Ver uso de memoria
free -h

# Ver información del sistema
uname -a

# Ver tiempo de uptime del sistema
uptime

# Ver carga del sistema
cat /proc/loadavg

# Reiniciar Head Node (usar con PRECAUCIÓN)
sudo reboot
```

### Gestión de Logs

```bash
# Ver tamaño de logs del sistema
sudo journalctl --disk-usage

# Limpiar logs antiguos (dejar últimos 3 días)
sudo journalctl --vacuum-time=3d

# Ver logs del kernel
sudo dmesg | tail -50

# Ver logs de sistema general
sudo tail -f /var/log/syslog
```

---

## Seguridad Adicional (Opcional)

### Cambiar Contraseña del Usuario Admin

```bash
# Conectar al Head Node
ssh ubuntu@10.20.12.158 -p 5801

# Activar entorno virtual
cd ~/PROYECTO_CLOUD_G4
source .venv/bin/activate

# Ejecutar Python interactivo
python
```

```python
from database.mongo_config import get_db
from auth_jwt import get_password_hash

db = get_db()

# Cambiar password del admin
new_password = "nueva-contraseña-segura-123!"
password_hash = get_password_hash(new_password)

result = db.users.update_one(
    {'username': 'admin'},
    {'$set': {'password_hash': password_hash}}
)

if result.modified_count > 0:
    print("✓ Password actualizado exitosamente")
else:
    print("✗ No se pudo actualizar el password")

exit()
```

### Cambiar SECRET_KEY de JWT

Para mayor seguridad en producción:

```bash
# Generar nueva clave secreta
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edita `auth_jwt.py` y reemplaza:

```python
SECRET_KEY = "nueva-clave-generada-aleatoriamente"
```

Luego reinicia el servicio:

```bash
sudo systemctl restart telecloud
```

### Configurar Firewall (ufw)

```bash
# Habilitar firewall
sudo ufw enable

# Permitir SSH
sudo ufw allow 22/tcp

# Permitir puerto de FastAPI (solo desde red interna)
sudo ufw allow from 10.0.10.0/24 to any port 8000

# Ver estado
sudo ufw status verbose
```

---

## Backup y Recuperación

### Hacer Backup de MongoDB

```bash
# Conectar al Head Node
ssh ubuntu@10.20.12.158 -p 5801

# Crear directorio de backups
mkdir -p ~/backups

# Backup completo de la base de datos
mongodump --db telecloud_db --out ~/backups/mongodb_$(date +%Y%m%d_%H%M%S)

# Verificar backup
ls -lh ~/backups/
```

### Restaurar Backup de MongoDB

```bash
# Listar backups disponibles
ls -l ~/backups/

# Restaurar backup específico
mongorestore --db telecloud_db ~/backups/mongodb_20251012_153000/telecloud_db

# Verificar restauración
mongosh telecloud_db --eval "db.users.countDocuments()"
```

### Hacer Backup del Proyecto Completo

```bash
# Desde Head Node
cd ~
tar -czf PROYECTO_CLOUD_G4_backup_$(date +%Y%m%d).tar.gz PROYECTO_CLOUD_G4/

# Ver tamaño del backup
ls -lh PROYECTO_CLOUD_G4_backup_*.tar.gz
```

### Descargar Backup a tu Máquina Local

```bash
# Desde tu máquina local
scp -P 5801 ubuntu@10.20.12.158:~/PROYECTO_CLOUD_G4_backup_*.tar.gz ./
```

### Restaurar Proyecto desde Backup

```bash
# Subir backup al Head Node
scp -P 5801 PROYECTO_CLOUD_G4_backup_20251012.tar.gz ubuntu@10.20.12.158:~/

# Conectar al Head Node
ssh ubuntu@10.20.12.158 -p 5801

# Detener servicio
sudo systemctl stop telecloud

# Hacer backup del proyecto actual (por seguridad)
mv ~/PROYECTO_CLOUD_G4 ~/PROYECTO_CLOUD_G4.old

# Extraer backup
tar -xzf ~/PROYECTO_CLOUD_G4_backup_20251012.tar.gz

# Reiniciar servicio
sudo systemctl start telecloud
```

---

## Monitoreo y Mantenimiento

### Verificar Salud del Sistema

```bash
# Script de verificación rápida
#!/bin/bash
echo "=== Estado del Sistema TELECLOUD ==="
echo ""
echo "FastAPI:"
sudo systemctl is-active telecloud
echo ""
echo "MongoDB:"
sudo systemctl is-active mongod
echo ""
echo "Puerto 8000:"
ss -tulnp | grep 8000 | grep -q LISTEN && echo "Escuchando" || echo "No disponible"
echo ""
echo "Usuarios registrados:"
mongosh telecloud_db --quiet --eval "db.users.countDocuments()"
echo ""
echo "Slices activos:"
mongosh telecloud_db --quiet --eval "db.slices.countDocuments()"
```

### Automatizar Backups (Cron)

```bash
# Editar crontab
crontab -e

# Agregar backup diario a las 2 AM
0 2 * * * mongodump --db telecloud_db --out ~/backups/mongodb_$(date +\%Y\%m\%d) && find ~/backups -type d -mtime +7 -exec rm -rf {} \;
```

---

## Resumen del Flujo de Despliegue

```
┌────────────────────────────────────────────────────────┐
│ 1. Preparar proyecto localmente                       │
│    ✓ Verificar archivos                               │
│    ✓ Configurar main_fastapi.py (host=0.0.0.0)        │
└────────────────┬───────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────┐
│ 2. Subir proyecto al Head Node                        │
│    scp -P 5801 -r PROYECTO_CLOUD_G4/ \                │
│        ubuntu@10.20.12.158:~/                         │
│    Password: tallarinesverdes12                       │
└────────────────┬───────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────┐
│ 3. Ejecutar deploy_headnode.sh en Head Node          │
│    ssh ubuntu@10.20.12.158 -p 5801                    │
│    ./deploy_headnode.sh                               │
│    → Instala MongoDB, Python, dependencias            │
│    → Configura servicio systemd                       │
└────────────────┬───────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────┐
│ 4. Configurar port forwarding en Gateway              │
│    ssh ubuntu@10.20.12.158 (sin -p, es puerto 22)    │
│    sudo ./configure_gateway_forwarding.sh             │
│    → Configura iptables NAT (8080 → 10.0.10.1:8000)  │
└────────────────┬───────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────┐
│ 5. ✅ Sistema listo para uso                           │
│    → http://10.20.12.158:8080                         │
│    → Usuario: admin / admin123                        │
│    → Equipo puede crear cuentas individuales          │
└────────────────────────────────────────────────────────┘
```

---

## Información de Contacto

Para soporte o preguntas sobre el sistema:

1. **Revisar logs:** `sudo journalctl -u telecloud -n 100`
2. **Verificar MongoDB:** `sudo systemctl status mongod`
3. **Verificar conectividad:** `curl -I http://localhost:8000/login`
4. **Consultar esta guía:** Sección de [Troubleshooting](#troubleshooting)

---

**¡Despliegue Completo! 🚀**

Tu sistema TELECLOUD ahora está corriendo en el Head Node (10.0.10.1) y accesible para todo tu equipo a través de:

**http://10.20.12.158:8080**

El sistema está configurado para:
- ✅ Iniciar automáticamente al encender el Head Node
- ✅ Reiniciar automáticamente si falla
- ✅ Persistir datos en MongoDB
- ✅ Registrar logs del sistema
- ✅ Orquestar despliegues en Workers sin password
