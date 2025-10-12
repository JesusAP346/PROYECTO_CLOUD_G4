# 🔐 API Documentation - FastAPI + JWT

## 🚀 **Inicio Rápido**

### **1. Instalar Dependencias**
```bash
pip install -r requirements.txt
```

### **2. Iniciar Servidor FastAPI**
```bash
python main_fastapi.py
```

**Servidor corriendo en:** `http://127.0.0.1:8000`
**Documentación interactiva:** `http://127.0.0.1:8000/docs` (Swagger UI)

---

## 🔑 **Autenticación JWT**

### **Flujo de Autenticación:**
1. **Registro o Login** → Obtener token JWT
2. **Incluir token en headers** de todas las peticiones:
   ```
   Authorization: Bearer <tu-token-jwt>
   ```

---

## 📌 **Endpoints de Autenticación**

### **POST /api/auth/register**
Registrar nuevo usuario

**Request Body:**
```json
{
  "username": "usuario1",
  "email": "usuario1@example.com",
  "password": "mipassword",
  "role": "general"  // "general", "vip" o "admin"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Usuario creado exitosamente",
  "user": {
    "id": "...",
    "username": "usuario1",
    "email": "usuario1@example.com",
    "role": "general"
  }
}
```

---

### **POST /api/auth/login**
Iniciar sesión y obtener token JWT

**Request Body:**
```json
{
  "username": "usuario1",
  "password": "mipassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "username": "usuario1",
    "email": "usuario1@example.com",
    "role": "general",
    "is_active": true
  }
}
```

**⚠️ IMPORTANTE:** Guarda el `access_token` - lo necesitas para todas las demás peticiones.

---

### **GET /api/auth/me**
Obtener información del usuario actual

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "id": "...",
  "username": "usuario1",
  "email": "usuario1@example.com",
  "role": "general",
  "is_active": true,
  "available_zones": ["", "linux-AZ-1"],
  "max_slices": 3
}
```

---

## 📋 **Endpoints de Templates (Plantillas)**

### **GET /api/templates**
Obtener todas las plantillas del usuario

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "templates": [
    {
      "_id": "...",
      "name": "mi_plantilla",
      "topology_json": {
        "nodes": [...],
        "edges": [...]
      },
      "availability_zone": "linux-AZ-1",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

---

### **POST /api/topology/save**
Guardar nueva plantilla

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Request Body:**
```json
{
  "name": "mi_plantilla",
  "az": "linux-AZ-1"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Plantilla guardada",
  "template_id": "..."
}
```

---

### **PUT /api/templates/{template_id}**
Actualizar plantilla existente

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Request Body:**
```json
{
  "name": "nuevo_nombre",
  "az": "linux-AZ-2"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Plantilla actualizada"
}
```

---

### **DELETE /api/templates/{template_id}**
Eliminar plantilla

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "success": true
}
```

---

### **POST /api/templates/{template_id}/deploy**
Desplegar plantilla como slice (la plantilla se elimina)

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "success": true,
  "slice_id": "mi_plantilla-20250111-153045"
}
```

---

## 🚀 **Endpoints de Slices**

### **GET /api/slices**
Obtener todos los slices del usuario

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "slices": [
    {
      "_id": "...",
      "slice_id": "mi_plantilla-20250111-153045",
      "name": "mi_plantilla",
      "topology_json": {...},
      "availability_zone": "linux-AZ-1",
      "deployed_at": "...",
      "status": "active",
      "vm_count": 5
    }
  ]
}
```

---

### **DELETE /api/slices/{slice_id}**
Eliminar slice

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "success": true
}
```

---

## 🛠️ **Endpoints de Topología**

### **POST /api/topology/generate**
Generar topología automáticamente

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Request Body:**
```json
{
  "type": "tree",  // "tree", "star", "ring", "mesh", etc.
  "config": {
    "tree_levels": 3,
    "tree_branching": 2
  }
}
```

**Response:**
```json
{
  "success": true,
  "topology": {
    "nodes": [...],
    "edges": [...]
  }
}
```

---

### **POST /api/topology/sync**
Sincronizar topología del frontend con backend

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Request Body:**
```json
{
  "nodes": [...],
  "edges": [...]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Topología sincronizada"
}
```

---

### **GET /api/topology/state**
Obtener estado actual de la topología

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "nodes": [...],
  "edges": [...]
}
```

---

### **POST /api/topology/clear**
Limpiar topología actual

**Headers:**
```
Authorization: Bearer <tu-token>
```

**Response:**
```json
{
  "success": true,
  "topology": {
    "nodes": [],
    "edges": []
  }
}
```

---

## 🔐 **Roles y Permisos**

| Rol | Slices Máximos | Zonas Disponibles |
|-----|---------------|-------------------|
| **general** | 3 | linux-AZ-1 |
| **vip** | 10 | linux-AZ-1, linux-AZ-2 |
| **admin** | 999 (sin límite) | linux-AZ-1, linux-AZ-2, openstack-AZ-1 |

---

## 📡 **Comunicación con Otro Servidor**

### **Ejemplo: Enviar Datos desde Otro Servidor**

```python
import requests

# 1. Login para obtener token
login_response = requests.post(
    "http://127.0.0.1:8000/api/auth/login",
    json={
        "username": "usuario1",
        "password": "mipassword"
    }
)
token = login_response.json()["access_token"]

# 2. Usar token para hacer peticiones
headers = {"Authorization": f"Bearer {token}"}

# Ejemplo: Obtener templates
templates_response = requests.get(
    "http://127.0.0.1:8000/api/templates",
    headers=headers
)
templates = templates_response.json()["templates"]

# Ejemplo: Desplegar template
deploy_response = requests.post(
    f"http://127.0.0.1:8000/api/templates/{template_id}/deploy",
    headers=headers
)
slice_id = deploy_response.json()["slice_id"]
```

---

## 🔧 **Ejemplo con cURL**

### **Login:**
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### **Obtener Templates (con token):**
```bash
curl -X GET http://127.0.0.1:8000/api/templates \
  -H "Authorization: Bearer <tu-token-aqui>"
```

---

## 📝 **Notas Importantes**

1. **Token JWT expira en 24 horas** - después debes hacer login nuevamente
2. **Todos los endpoints (excepto login/register) requieren token JWT**
3. **Los roles se asignan al crear usuario** - no se pueden cambiar por API
4. **Cuando despliegas una plantilla, esta se elimina** (se convierte en slice)
5. **Documentación interactiva disponible en:** `http://127.0.0.1:8000/docs`

---

## 🚨 **Códigos de Error Comunes**

- `401 Unauthorized` - Token inválido o expirado
- `400 Bad Request` - Datos incorrectos en el request
- `404 Not Found` - Recurso no encontrado
- `500 Internal Server Error` - Error del servidor

---

## 🎯 **Comandos Rápidos**

```bash
# Iniciar servidor FastAPI
python main_fastapi.py

# Ver documentación interactiva
# Navegar a: http://127.0.0.1:8000/docs

# Crear usuario admin
python create_admin_mongo.py

# Crear usuario con rol específico
python create_user_mongo.py
```

---

**¡API lista para comunicarse con otros servidores mediante endpoints REST + JWT!** 🚀
