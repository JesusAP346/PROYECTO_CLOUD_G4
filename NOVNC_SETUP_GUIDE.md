# Guía de Instalación noVNC + Websockify

## 📋 Descripción

Esta guía te ayudará a instalar y configurar **noVNC** (cliente VNC basado en HTML5) en el servidor Head Node para permitir acceso VNC desde el navegador.

## 🎯 Objetivo

Permitir que los usuarios accedan a las VMs desplegadas haciendo click derecho en un nodo → "Abrir Terminal VNC" → Se abre nueva pestaña con terminal VNC sin necesidad de RealVNC.

---

## 📦 Paso 1: Instalar Dependencias

Conéctate al Head Node y ejecuta:

```bash
ssh ubuntu@10.20.12.158 -p 5801

# Actualizar repositorios
sudo apt update

# Instalar dependencias
sudo apt install -y git python3 python3-pip python3-numpy net-tools

# Instalar websockify (proxy WebSocket para VNC)
sudo pip3 install websockify
```

---

## 📥 Paso 2: Descargar e Instalar noVNC

```bash
# Ir al directorio web (puede variar según tu setup)
cd /var/www

# Clonar noVNC desde el repositorio oficial
sudo git clone https://github.com/novnc/noVNC.git

# Cambiar permisos
sudo chown -R ubuntu:ubuntu noVNC
cd noVNC

# Crear enlace simbólico para vnc.html
sudo ln -s vnc.html index.html
```

**Verificar instalación:**
```bash
ls -la /var/www/noVNC/vnc.html
# Debe mostrar el archivo vnc.html
```

---

## 🔧 Paso 3: Configurar Websockify como Servicio Systemd

Websockify actúa como proxy entre WebSocket (navegador) y TCP (VNC servers). Vamos a configurarlo como servicio para que arranque automáticamente.

### 3.1 Crear archivo de servicio

```bash
sudo nano /etc/systemd/system/websockify.service
```

**Contenido del archivo:**

```ini
[Unit]
Description=Websockify VNC Proxy for noVNC
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/var/www/noVNC
ExecStart=/usr/local/bin/websockify --web /var/www/noVNC 6080 --target-config=/etc/websockify/targets.conf
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Explicación:**
- `--web /var/www/noVNC`: Sirve archivos HTML/JS de noVNC
- `6080`: Puerto donde escucha websockify (HTTP + WebSocket)
- `--target-config`: Archivo con mapeo de puertos VNC

---

### 3.2 Crear archivo de configuración de targets (Generación Automática)

**IMPORTANTE:** Los puertos VNC públicos se generan dinámicamente cuando despliegas slices. No son estáticos. Por eso, vamos a generar un archivo `targets.conf` que cubra TODOS los puertos posibles en el rango VNC.

```bash
sudo mkdir -p /etc/websockify

# Generar configuración para TODOS los puertos VNC posibles (5900-6100)
# Esto cubre cualquier puerto que genere dinámicamente mapeo_vms.sh
for port in {5900..6100}; do
    echo "$port: localhost:$port"
done | sudo tee /etc/websockify/targets.conf > /dev/null

# Verificar que se generó correctamente
wc -l /etc/websockify/targets.conf
# Debe mostrar ~200 líneas
```

**¿Por qué localhost?**
- `mapeo_vms.sh` ya crea túneles SSH que mapean los puertos de workers (ej: 10.0.10.3:5901) a puertos locales del Head Node (ej: localhost:5904)
- Websockify solo necesita redirigir WebSocket → `localhost:PUERTO`
- El token en la URL es simplemente el número de puerto (ej: 5904)

**Formato del archivo generado:**
```
5900: localhost:5900
5901: localhost:5901
5902: localhost:5902
...
6100: localhost:6100
```

---

### 3.3 Habilitar e iniciar el servicio

```bash
# Recargar systemd
sudo systemctl daemon-reload

# Habilitar para arranque automático
sudo systemctl enable websockify

# Iniciar servicio
sudo systemctl start websockify

# Verificar estado
sudo systemctl status websockify
```

**Salida esperada:**
```
● websockify.service - Websockify VNC Proxy for noVNC
   Loaded: loaded (/etc/systemd/system/websockify.service; enabled)
   Active: active (running) since...
```

**Ver logs:**
```bash
sudo journalctl -u websockify -f
```

---

## 🔥 Paso 4: Configurar Firewall (si está activo)

```bash
# Verificar si UFW está activo
sudo ufw status

# Si está activo, permitir puerto 6080
sudo ufw allow 6080/tcp
sudo ufw reload
```

---

## 🧪 Paso 5: Pruebas de Conectividad

### 5.1 Verificar que websockify está escuchando

```bash
sudo netstat -tulnp | grep 6080
```

**Salida esperada:**
```
tcp        0      0 0.0.0.0:6080            0.0.0.0:*               LISTEN      12345/python3
```

### 5.2 Probar desde el navegador local

**Opción 1: Probar con VM específica**

Desde tu navegador Windows, abre:
```
http://10.20.12.158:6080/vnc.html?host=10.20.12.158&port=5904&autoconnect=true
```

Reemplaza `5904` por el puerto público de una VM que esté corriendo.

**Opción 2: Probar sin autoconnect (manual)**
```
http://10.20.12.158:6080/vnc.html
```

Luego en la interfaz de noVNC:
- **Host:** `10.20.12.158`
- **Port:** `5904` (o el puerto de tu VM)
- Click en **Connect**

---

## 🐛 Troubleshooting

### Problema 1: Websockify no inicia

**Solución:**
```bash
# Ver logs detallados
sudo journalctl -u websockify -n 50

# Verificar que websockify está instalado
which websockify

# Reinstalar si es necesario
sudo pip3 install --upgrade websockify
```

---

### Problema 2: Error "Connection refused" en noVNC

**Causa:** El puerto VNC de destino no está mapeado correctamente.

**Solución:**
```bash
# Verificar que los SSH tunnels estén activos
ps aux | grep "ssh.*5904"

# Si no están, ejecutar mapeo_vms.sh (que ya maneja esto)
cd ~
./mapeo_vms.sh --slice-id pruebaporfa-20251014-163437
```

---

### Problema 3: noVNC se conecta pero pantalla negra

**Causa:** La VM no tiene servidor VNC corriendo o la VM aún no ha iniciado.

**Solución:**
```bash
# Verificar que la VM está corriendo
ssh ubuntu@10.0.10.2  # Worker donde está la VM
sudo virsh list --all

# Ver si el puerto VNC está abierto
sudo netstat -tulnp | grep 5901
```

---

### Problema 4: Error "Failed to connect to server"

**Causa:** Websockify no puede alcanzar el backend VNC.

**Solución:**
```bash
# Probar conectividad manualmente desde Head Node
telnet 10.0.10.2 5901

# Si falla, verificar:
# 1. Que la VM esté corriendo en el worker
# 2. Que el puerto VNC esté configurado correctamente
# 3. Que no haya firewall bloqueando
```

---

## 📝 Paso 6: Configuración Alternativa (Sin Token Config)

Si prefieres una configuración más simple sin archivo de targets, puedes usar websockify en modo directo:

```bash
sudo nano /etc/systemd/system/websockify.service
```

**Cambiar `ExecStart` a:**
```ini
ExecStart=/usr/local/bin/websockify --web /var/www/noVNC 6080 localhost:5900
```

Esto redirige todo el tráfico de websockify al puerto 5900 local (útil si tienes un solo servidor VNC o usas un proxy adicional).

**Para tu caso (múltiples VMs)**, es mejor usar el modo con `--target-config` como se mostró arriba.

---

## 🎉 Paso 7: Integración con FastAPI (Ya está hecho)

La integración con FastAPI ya está completa:

1. ✅ **API Endpoint:** `/api/slices/{slice_id}/vnc-info`
   - Devuelve puertos VNC públicos de las VMs del slice

2. ✅ **Frontend (viewer.html):**
   - Click derecho en nodo → "Abrir Terminal VNC"
   - Abre nueva pestaña con URL de noVNC

---

## 🔄 ¿Necesito actualizar targets.conf?

**No.** El archivo `targets.conf` cubre TODO el rango de puertos (5900-6100), por lo que funciona con cualquier despliegue dinámico. No necesitas regenerarlo cada vez que despliegues o elimines slices.

- `mapeo_vms.sh` crea los túneles SSH dinámicamente
- Websockify ya tiene configurado el mapeo para todos los puertos posibles
- La aplicación llama a `/api/slices/{slice_id}/vnc-info` que consulta `mapeo_vms.sh` para obtener el puerto correcto en tiempo real

---

## 📊 Verificación Final

**Checklist:**

- [ ] Websockify instalado: `websockify --version`
- [ ] noVNC clonado en `/var/www/noVNC`
- [ ] Servicio websockify corriendo: `sudo systemctl status websockify`
- [ ] Puerto 6080 escuchando: `netstat -tulnp | grep 6080`
- [ ] URL de prueba funciona: `http://10.20.12.158:6080/vnc.html`
- [ ] Click derecho en nodo → "Abrir Terminal VNC" → Se abre nueva pestaña
- [ ] La terminal VNC se conecta correctamente a la VM

---

## 📚 Recursos

- [noVNC GitHub](https://github.com/novnc/noVNC)
- [Websockify Documentation](https://github.com/novnc/websockify)
- [VNC RFB Protocol](https://github.com/rfbproto/rfbproto/blob/master/rfbproto.rst)

---

## 🚀 Siguientes Pasos

1. Subir `main_fastapi.py` actualizado al servidor
2. Subir `viewer.html` actualizado al servidor
3. Instalar noVNC siguiendo esta guía
4. Reiniciar servicio telecloud: `sudo systemctl restart telecloud`
5. Probar haciendo click derecho en un nodo desplegado

---

**¡Listo!** Ahora tendrás acceso VNC desde el navegador sin necesidad de RealVNC. 🎉
