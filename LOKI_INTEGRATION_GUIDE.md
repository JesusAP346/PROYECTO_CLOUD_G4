# Guía de Integración Loki + FastAPI

## ✅ Cambios Realizados en `main_fastapi.py`

Se ha modificado el archivo local `main_fastapi.py` para incluir logging estructurado en formato JSON compatible con Loki:

### 1. **Infraestructura de Logging** (Líneas 14-95)
- ✅ Clase `JSONFormatter` para formatear logs en JSON
- ✅ Logger configurado con dos handlers:
  - **File handler**: Escribe JSON a `/var/log/telecloud/app.log` (rotating, 10MB, 5 backups)
  - **Console handler**: Texto legible para desarrollo
- ✅ Campos personalizados: `user`, `action`, `ip`, `slice_id`, `user_id`, `role`, `duration`

### 2. **Middleware HTTP** (Líneas 110-153)
- ✅ Registra todas las peticiones HTTP con:
  - Método, path, IP del cliente
  - Status code de respuesta
  - Duración de la petición en segundos

### 3. **Logging de Autenticación**
- ✅ `/api/auth/register`: Intentos, éxitos y fallos de registro
- ✅ `/api/auth/login`: Intentos, éxitos y fallos de login con IP

### 4. **Logging de Templates**
- ✅ Creación de templates
- ✅ Actualización de templates
- ✅ Eliminación de templates

### 5. **Logging de Despliegues**
- ✅ Inicio de despliegue con detalles (user, slice_id, vm_count, az)
- ✅ Bloqueos por límite de slices
- ✅ Éxito/fallo de despliegue con duración
- ✅ Errores durante el proceso

### 6. **Logging de Slices**
- ✅ Inicio de eliminación de slice
- ✅ Éxito/fallo de eliminación con duración
- ✅ Errores durante el proceso

---

## 📤 **Paso 1: Subir el Archivo Modificado al Servidor**

Desde tu máquina Windows, ejecuta en PowerShell o CMD:

```bash
# Conectarte al servidor Head Node
ssh ubuntu@10.20.12.158 -p 5801

# Luego desde otra terminal en Windows, sube el archivo
scp -P 5801 "C:\Users\Adrian Lopez\Desktop\Cloud_versionfinal\PROYECTO_CLOUD_G4\main_fastapi.py" ubuntu@10.20.12.158:/home/ubuntu/PROYECTO_CLOUD_G4/main_fastapi.py
```

O si prefieres hacerlo desde el servidor directamente:

```bash
# Hacer backup del archivo actual
ssh ubuntu@10.20.12.158 -p 5801
cd /home/ubuntu/PROYECTO_CLOUD_G4
cp main_fastapi.py main_fastapi.py.backup

# Crear el directorio de logs
sudo mkdir -p /var/log/telecloud
sudo chown ubuntu:ubuntu /var/log/telecloud
sudo chmod 755 /var/log/telecloud

# Luego sube el archivo desde Windows usando WinSCP, FileZilla o scp
```

---

## 🔧 **Paso 2: Reiniciar el Servicio FastAPI**

Una vez subido el archivo al servidor:

```bash
# Opción 1: Si usas systemd
sudo systemctl restart fastapi

# Opción 2: Si está corriendo manualmente
# Mata el proceso actual
pkill -f "python.*main_fastapi"

# Inicia nuevamente
cd /home/ubuntu/PROYECTO_CLOUD_G4
nohup python3 main_fastapi.py > /var/log/telecloud/fastapi.out 2>&1 &
```

---

## 🔍 **Paso 3: Verificar que los Logs se Están Generando**

```bash
# Ver los logs en tiempo real
tail -f /var/log/telecloud/app.log

# Ver un log de ejemplo (debería ser JSON)
head -n 5 /var/log/telecloud/app.log | jq .

# Hacer una petición de prueba
curl http://localhost:8000/api/auth/me -H "Authorization: Bearer <token>"
```

**Ejemplo de salida esperada (JSON):**
```json
{
  "timestamp": "2025-10-14T15:30:45.123456Z",
  "level": "INFO",
  "logger": "telecloud",
  "message": "HTTP Request: GET /api/auth/me",
  "module": "main_fastapi",
  "function": "log_requests",
  "line": 124,
  "action": "http_request",
  "ip": "10.20.12.158",
  "method": "GET",
  "path": "/api/auth/me"
}
```

---

## 📊 **Paso 4: Configurar Promtail para Recoger los Logs de FastAPI**

Edita el archivo de configuración de Promtail en el **Head Node (server1)**:

```bash
sudo nano /etc/promtail/promtail-config.yaml
```

**Agrega este nuevo job al final del archivo:**

```yaml
  # FastAPI Application Logs (JSON)
  - job_name: telecloud
    static_configs:
      - targets:
          - localhost
        labels:
          job: telecloud
          host: server1
          __path__: /var/log/telecloud/app.log

    pipeline_stages:
      # Parse JSON automáticamente
      - json:
          expressions:
            timestamp: timestamp
            level: level
            logger: logger
            message: message
            action: action
            user: user
            user_id: user_id
            ip: ip
            slice_id: slice_id
            role: role
            duration: duration_seconds
            error: error
            vm_count: vm_count
            az: az
            template_id: template_id

      # Convertir timestamp a formato Loki
      - timestamp:
          source: timestamp
          format: RFC3339Nano

      # Asignar labels dinámicos
      - labels:
          level:
          action:
          user:
```

**Reinicia Promtail:**

```bash
sudo systemctl restart promtail
sudo systemctl status promtail
```

**Verifica que está funcionando:**

```bash
# Ver logs de Promtail
sudo journalctl -u promtail -f

# Hacer una petición a FastAPI y verificar en Loki
curl http://localhost:8000/api/auth/me -H "Authorization: Bearer <token>"

# Verificar en Loki que llegaron los logs (espera 5-10 segundos)
curl -s 'http://localhost:3100/loki/api/v1/query?query={job="telecloud"}' | jq .
```

---

## 🎨 **Paso 5: Queries de Grafana para Monitorear tu Aplicación**

Ahora puedes usar estas queries en Grafana → Explore → Loki:

### 📊 **Queries Básicas**

```logql
# Todos los logs de FastAPI
{job="telecloud"}

# Logs de autenticación
{job="telecloud", action=~"auth_.*"}

# Logs de despliegues
{job="telecloud", action=~"deployment_.*"}

# Solo errores
{job="telecloud", level="ERROR"}

# Logs de un usuario específico
{job="telecloud", user="admin"}
```

### 🔐 **Monitoreo de Autenticación**

```logql
# Login exitosos en las últimas 24 horas
count_over_time({job="telecloud", action="auth_login_success"}[24h])

# Login fallidos (intentos de intrusión)
{job="telecloud", action="auth_login_failed"}

# Registros de nuevos usuarios
{job="telecloud", action="auth_register_success"}

# Intentos de login por IP
sum by (ip) (count_over_time({job="telecloud", action=~"auth_login_.*"}[1h]))
```

### 🚀 **Monitoreo de Despliegues**

```logql
# Despliegues exitosos
{job="telecloud", action="deployment_success"}

# Despliegues fallidos con detalles de error
{job="telecloud", action="deployment_failed"} | json

# Duración promedio de despliegues exitosos
avg(duration_seconds) by (slice_id) from {job="telecloud", action="deployment_success"}

# Despliegues por usuario
sum by (user) (count_over_time({job="telecloud", action="deployment_start"}[24h]))

# Despliegues por AZ
sum by (az) (count_over_time({job="telecloud", action="deployment_success"}[24h]))
```

### 📦 **Monitoreo de Slices**

```logql
# Eliminaciones de slices exitosas
{job="telecloud", action="slice_delete_success"}

# Eliminaciones fallidas
{job="telecloud", action="slice_delete_failed"}

# Tiempo promedio de eliminación
avg(duration_seconds) from {job="telecloud", action="slice_delete_success"}
```

### 🔧 **Monitoreo de Templates**

```logql
# Creación de templates
{job="telecloud", action="template_create"}

# Templates por usuario
sum by (user) (count_over_time({job="telecloud", action="template_create"}[24h]))
```

### ⚡ **Monitoreo de Performance**

```logql
# Requests más lentas (> 1 segundo)
{job="telecloud", action="http_response"} | json | duration > 1

# Requests por endpoint
sum by (path) (count_over_time({job="telecloud", action="http_request"}[5m]))

# Errores HTTP 5xx
{job="telecloud", action="http_response"} | json | status_code >= 500

# Requests por usuario (autenticadas)
sum by (user) (count_over_time({job="telecloud", user!=""}[1h]))
```

---

## 📈 **Paso 6: Crear Dashboard en Grafana**

1. Ve a **Grafana** → http://10.20.12.158:3000
2. Click en **+ (Create)** → **Dashboard**
3. Click en **Add visualization**
4. Selecciona **Loki** como data source
5. Agrega estos paneles:

### Panel 1: **Login Attempts (Last 24h)**
- Query: `count_over_time({job="telecloud", action=~"auth_login_.*"}[24h])`
- Visualization: **Time series**

### Panel 2: **Deployments Status**
- Query:
  ```
  sum by (action) (count_over_time({job="telecloud", action=~"deployment_(success|failed)"}[24h]))
  ```
- Visualization: **Pie chart**

### Panel 3: **Average Deployment Duration**
- Query: `avg(duration_seconds) from {job="telecloud", action="deployment_success"}`
- Visualization: **Stat**

### Panel 4: **Recent Errors**
- Query: `{job="telecloud", level="ERROR"}`
- Visualization: **Logs**

---

## ✅ **Checklist de Verificación**

- [ ] Archivo `main_fastapi.py` subido al servidor
- [ ] Directorio `/var/log/telecloud` creado con permisos correctos
- [ ] Servicio FastAPI reiniciado
- [ ] Logs JSON generándose en `/var/log/telecloud/app.log`
- [ ] Promtail configurado con job `telecloud`
- [ ] Promtail reiniciado y corriendo sin errores
- [ ] Logs de FastAPI apareciendo en Loki (query: `{job="telecloud"}`)
- [ ] Queries de prueba funcionando en Grafana
- [ ] Dashboard creado (opcional)

---

## 🎯 **Campos de Log Disponibles**

Puedes filtrar por estos campos en tus queries:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `timestamp` | Hora del log (UTC) | `2025-10-14T15:30:45.123456Z` |
| `level` | Nivel de log | `INFO`, `WARNING`, `ERROR` |
| `action` | Acción realizada | `auth_login_success`, `deployment_start` |
| `user` | Username del usuario | `admin`, `usuario1` |
| `user_id` | MongoDB ObjectId del usuario | `507f1f77bcf86cd799439011` |
| `ip` | IP del cliente | `10.20.12.158` |
| `slice_id` | ID del slice | `topology-20251014-153045` |
| `role` | Rol del usuario | `admin`, `vip`, `general` |
| `duration` | Duración de la operación (seg) | `45.23` |
| `vm_count` | Número de VMs | `5` |
| `az` | Availability Zone | `linux-AZ-1`, `auto` |
| `template_id` | MongoDB ObjectId del template | `507f1f77bcf86cd799439012` |
| `error` | Mensaje de error | `Template not found` |

---

## 🚨 **Alertas Recomendadas**

Puedes configurar alertas en Grafana para:

1. **Login fallidos repetidos** (posible intrusión)
   ```logql
   count_over_time({job="telecloud", action="auth_login_failed"}[5m]) > 5
   ```

2. **Despliegues fallando frecuentemente**
   ```logql
   count_over_time({job="telecloud", action="deployment_failed"}[1h]) > 3
   ```

3. **Errores críticos**
   ```logql
   count_over_time({job="telecloud", level="ERROR"}[5m]) > 10
   ```

---

## 📞 **Troubleshooting**

### Problema: Los logs no aparecen en Loki

**Solución:**
```bash
# 1. Verificar que FastAPI está generando logs
tail -f /var/log/telecloud/app.log

# 2. Verificar que Promtail está corriendo
sudo systemctl status promtail

# 3. Ver logs de Promtail para errores
sudo journalctl -u promtail -n 50

# 4. Verificar que el archivo tiene permisos correctos
ls -la /var/log/telecloud/app.log

# 5. Verificar conectividad a Loki
curl http://localhost:3100/ready
```

### Problema: Los logs no son JSON válido

**Solución:**
```bash
# Verificar formato del log
tail -n 1 /var/log/telecloud/app.log | jq .

# Si falla, revisar la configuración del logger en main_fastapi.py
```

### Problema: Promtail no puede leer el archivo

**Solución:**
```bash
# Dar permisos de lectura a Promtail
sudo chmod 644 /var/log/telecloud/app.log
sudo chown ubuntu:ubuntu /var/log/telecloud/app.log
```

---

## 🎉 **¡Listo!**

Ahora tienes:
- ✅ Logging estructurado en JSON
- ✅ Monitoreo centralizado con Loki
- ✅ Visibilidad completa de autenticación, deployments y errores
- ✅ Queries para análisis y troubleshooting
- ✅ Base para crear dashboards y alertas

**Siguiente paso:** Crear dashboards personalizados en Grafana para visualizar métricas clave de tu aplicación.
