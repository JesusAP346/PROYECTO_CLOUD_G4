# 🌐 Cloud Topology Manager - FastAPI + JWT

Sistema de gestión de topologías de red con **FastAPI**, **JWT** y **MongoDB**.

---

## ✨ **Características**

- ✅ API REST con FastAPI
- ✅ Autenticación con JWT (JSON Web Tokens)
- ✅ Sistema multi-rol (General, VIP, Admin)
- ✅ MongoDB para persistencia
- ✅ Endpoints REST para comunicación entre servidores
- ✅ Documentación interactiva (Swagger UI)

---

## 📋 **Requisitos**

1. **Python 3.8+**
2. **MongoDB** (base de datos)
3. **Git** (opcional)

---

## 🚀 **Instalación Rápida**

### **1. Instalar MongoDB**

**Windows:**
- Descargar: https://www.mongodb.com/try/download/community
- Instalar → Siguiente → Siguiente → Finish
- MongoDB se ejecuta automáticamente como servicio ✅

Ver guía detallada: [`INSTALACION_MONGODB_WINDOWS.md`](INSTALACION_MONGODB_WINDOWS.md)

---

### **2. Clonar Proyecto**

```bash
git clone <url-repositorio>
cd PROYECTO_CLOUD_G4
```

---

### **3. Crear Entorno Virtual**

```bash
# Crear
python -m venv .venv

# Activar (Windows)
.venv\Scripts\activate

# Activar (Linux/Mac)
source .venv/bin/activate
```

---

### **4. Instalar Dependencias**

```bash
pip install -r requirements.txt
```

**Nuevas dependencias agregadas:**
- `fastapi` - Framework web
- `uvicorn` - Servidor ASGI
- `python-jose[cryptography]` - JWT
- `passlib[bcrypt]` - Encriptación de contraseñas
- `pymongo` - Driver MongoDB

---

### **5. Inicializar MongoDB**

```bash
python database\mongo_config.py
```

**Salida esperada:**
```
✅ Conectado a MongoDB exitosamente
✅ Colección 'users' creada
✅ Colección 'templates' creada
✅ Colección 'slices' creada
```

---

### **6. Crear Usuario Admin**

```bash
python create_admin_mongo.py
```

**Credenciales por defecto:**
- Username: `admin`
- Password: `admin123`
- Rol: admin

---

### **7. Ejecutar Servidor FastAPI**

```bash
python main_fastapi.py
```

**Salida esperada:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

## 🌐 **Acceso a la Aplicación**

| URL | Descripción |
|-----|-------------|
| `http://127.0.0.1:8000` | Aplicación web |
| `http://127.0.0.1:8000/docs` | Documentación API (Swagger) |
| `http://127.0.0.1:8000/redoc` | Documentación alternativa |

---

## 🔐 **Autenticación JWT**

### **Flujo:**

1. **Login** → Obtener token JWT
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {...}
}
```

2. **Usar token en peticiones:**
```bash
curl -X GET http://127.0.0.1:8000/api/templates \
  -H "Authorization: Bearer <tu-token>"
```

---

## 👥 **Roles de Usuario**

| Rol | Límite Slices | Zonas Disponibles |
|-----|--------------|-------------------|
| **general** | 3 | linux-AZ-1 |
| **vip** | 10 | linux-AZ-1, linux-AZ-2 |
| **admin** | ∞ | linux-AZ-1, linux-AZ-2, openstack-AZ-1 |

### **Crear Usuarios:**

```bash
# Usuario interactivo
python create_user_mongo.py

# O usar API
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "usuario1",
    "email": "usuario1@test.com",
    "password": "pass123",
    "role": "general"
  }'
```

---

## 📡 **Endpoints Principales**

### **Autenticación:**
- `POST /api/auth/register` - Registrar usuario
- `POST /api/auth/login` - Login (obtener JWT)
- `GET /api/auth/me` - Info del usuario actual

### **Templates (Plantillas):**
- `GET /api/templates` - Listar plantillas
- `POST /api/topology/save` - Guardar plantilla
- `PUT /api/templates/{id}` - Actualizar plantilla
- `DELETE /api/templates/{id}` - Eliminar plantilla
- `POST /api/templates/{id}/deploy` - Desplegar como slice

### **Slices:**
- `GET /api/slices` - Listar slices
- `DELETE /api/slices/{id}` - Eliminar slice

### **Topología:**
- `POST /api/topology/generate` - Generar topología
- `POST /api/topology/sync` - Sincronizar estado
- `GET /api/topology/state` - Obtener estado
- `POST /api/topology/clear` - Limpiar topología

**📖 Documentación completa:** [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md)

---

## 🔗 **Comunicación entre Servidores**

### **Ejemplo Python:**

```python
import requests

# 1. Obtener token
response = requests.post(
    "http://127.0.0.1:8000/api/auth/login",
    json={"username": "admin", "password": "admin123"}
)
token = response.json()["access_token"]

# 2. Headers con token
headers = {"Authorization": f"Bearer {token}"}

# 3. Hacer peticiones
templates = requests.get(
    "http://127.0.0.1:8000/api/templates",
    headers=headers
).json()

# 4. Desplegar template
deploy = requests.post(
    f"http://127.0.0.1:8000/api/templates/{template_id}/deploy",
    headers=headers
).json()
```

### **Ejemplo JavaScript:**

```javascript
// 1. Login
const loginRes = await fetch('http://127.0.0.1:8000/api/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'admin', password: 'admin123'})
});
const {access_token} = await loginRes.json();

// 2. Usar token
const templatesRes = await fetch('http://127.0.0.1:8000/api/templates', {
  headers: {'Authorization': `Bearer ${access_token}`}
});
const templates = await templatesRes.json();
```

---

## 📁 **Estructura del Proyecto**

```
PROYECTO_CLOUD_G4/
├── main_fastapi.py              # ⭐ App principal FastAPI (USAR ESTE)
├── auth_jwt.py                  # Sistema JWT
├── auth_mongo.py                # Auth Flask (legacy - no usar)
├── app_mongo.py                 # App Flask (legacy - no usar)
├── create_admin_mongo.py        # Script: crear admin
├── create_user_mongo.py         # Script: crear usuarios
├── database/
│   └── mongo_config.py          # Configuración MongoDB
├── templates/                   # Templates HTML
├── static/                      # JavaScript y CSS
├── requirements.txt             # Dependencias
├── API_DOCUMENTATION.md         # 📖 Documentación API
└── INSTALACION_MONGODB_WINDOWS.md
```

---

## 🔧 **Diferencias: Flask vs FastAPI**

| Característica | Flask (app_mongo.py) | FastAPI (main_fastapi.py) |
|----------------|----------------------|---------------------------|
| **Autenticación** | Flask-Login (sesiones) | JWT (tokens) |
| **API REST** | ❌ No | ✅ Sí |
| **Documentación** | ❌ No | ✅ Swagger automático |
| **Async** | ❌ No | ✅ Sí |
| **Comunicación servidor** | ❌ Difícil | ✅ Fácil (REST) |
| **Uso recomendado** | ❌ Legacy | ✅ **USAR ESTE** |

---

## ⚙️ **Configuración**

### **Cambiar clave secreta JWT:**

Editar `auth_jwt.py`:
```python
SECRET_KEY = "tu-clave-super-secreta-aqui"
```

### **Cambiar puerto:**

Editar `main_fastapi.py`:
```python
uvicorn.run("main_fastapi:app", host="127.0.0.1", port=9000)  # Cambiar puerto
```

---

## 🐛 **Solución de Problemas**

### **Error: MongoDB no conecta**
```bash
# Verificar servicio (Windows)
net start MongoDB

# O en Servicios (Win+R → services.msc)
```

### **Error: Puerto ocupado**
Cambiar puerto en `main_fastapi.py` o matar proceso:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

### **Error: Dependencias**
```bash
pip install --upgrade -r requirements.txt
```

---

## ✅ **Checklist para Compañeros**

```
□ Instalar MongoDB
□ git pull
□ Activar entorno virtual (.venv)
□ pip install -r requirements.txt
□ python database\mongo_config.py
□ python create_admin_mongo.py
□ python main_fastapi.py  ← IMPORTANTE: FastAPI, no Flask
□ Abrir http://127.0.0.1:8000/docs
□ Probar login en Swagger UI
```

---

## 📝 **Notas Importantes para el Equipo**

### **⚠️ CAMBIOS IMPORTANTES:**

1. **Ahora usamos FastAPI** (no Flask)
2. **Autenticación con JWT** (no sesiones)
3. **Todos los endpoints requieren token Bearer**
4. **Puerto cambió a 8000** (antes era 5000)
5. **Ejecutar `main_fastapi.py`** (NO `app_mongo.py`)

### **Ventajas del cambio:**

- ✅ Comunicación fácil entre servidores (REST API)
- ✅ Tokens JWT (sin estado, escalable)
- ✅ Documentación automática (Swagger)
- ✅ Async (mejor rendimiento)
- ✅ Compatible con otros servicios

---

## 🚀 **Inicio Rápido (Resumen)**

```bash
# 1. Instalar MongoDB (una vez)
# https://www.mongodb.com/try/download/community

# 2. Setup
python database\mongo_config.py
python create_admin_mongo.py

# 3. Ejecutar
python main_fastapi.py

# 4. Probar
# Navegar a: http://127.0.0.1:8000/docs
# Login: admin / admin123
```

---

## 📞 **Soporte**

- **Documentación API:** `API_DOCUMENTATION.md`
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **MongoDB Guide:** `INSTALACION_MONGODB_WINDOWS.md`

---

🎉 **¡Sistema listo para comunicación REST con otros servidores!** 🚀
