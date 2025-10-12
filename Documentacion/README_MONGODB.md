# 📘 Guía de MongoDB para el Proyecto

## ¿Cómo funciona MongoDB en este proyecto?

MongoDB es la base de datos **NoSQL** que almacena:
- **Usuarios** (con roles: general, vip, admin)
- **Plantillas** de topologías (creadas por cada usuario)
- **Slices** desplegados (instancias activas de plantillas)

### Estructura de la Base de Datos

```
cloud_topology_db/
├── users           # Colección de usuarios
├── templates       # Colección de plantillas
└── slices          # Colección de slices desplegados
```

## 🔧 Configuración Inicial

### 1. Instalar MongoDB

**Windows:**
```bash
# Descargar desde: https://www.mongodb.com/try/download/community
# Instalar MongoDB Community Server
# Por defecto se ejecuta en: mongodb://localhost:27017
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install -y mongodb

# macOS (con Homebrew)
brew tap mongodb/brew
brew install mongodb-community
```

### 2. Iniciar MongoDB

```bash
# Windows (como servicio)
net start MongoDB

# Linux/Mac
sudo systemctl start mongod
# o
mongod --dbpath /ruta/a/tu/data
```

### 3. Crear el Usuario Administrador Inicial

Ejecuta el script en la raíz del proyecto:

```bash
python create_admin_mongo.py
```

Esto creará el usuario administrador con las siguientes credenciales:
- **Username:** `admin`
- **Password:** `admin123` (⚠️ cámbialo después del primer login!)
- **Email:** `admin@cloudproject.com`
- **Rol:** `admin`

### 4. Verificar la Conexión

```bash
# Usar MongoDB Compass (GUI)
# Conectarse a: mongodb://localhost:27017

# O usar mongo shell
mongo
> use cloud_topology_db
> db.users.find()
```

## 👥 Compartir la Base de Datos con Compañeros

### Opción 1: Compartir un Dump de MongoDB (Recomendado)

**Exportar tu base de datos:**
```bash
# Crear un dump de toda la base de datos
mongodump --db=cloud_topology_db --out=./mongo_backup

# Esto crea una carpeta con archivos BSON
```

**Tus compañeros importan el dump:**
```bash
# Restaurar la base de datos
mongorestore --db=cloud_topology_db ./mongo_backup/cloud_topology_db

# Verificar
mongo
> use cloud_topology_db
> db.users.find()
```

### Opción 2: MongoDB Atlas (Cloud - Gratis)

Si quieren una base de datos compartida en la nube:

1. Crear cuenta en [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Crear un cluster gratuito
3. Obtener la cadena de conexión:
   ```
   mongodb+srv://usuario:password@cluster.mongodb.net/cloud_topology_db
   ```
4. Actualizar `database/mongo_config.py`:
   ```python
   MONGO_URI = "mongodb+srv://usuario:password@cluster.mongodb.net/cloud_topology_db"
   ```

### Opción 3: Cada uno corre su propia BD local

Cada compañero:
1. Instala MongoDB localmente
2. Ejecuta `python create_admin_mongo.py`
3. Crea sus propios usuarios de prueba

⚠️ **Problema:** Cada uno tendrá datos diferentes (no compartidos)

## 🗂️ Estructura de las Colecciones

### Colección: `users`
```json
{
  "_id": ObjectId("..."),
  "username": "admin",
  "email": "admin@cloudproject.com",
  "password_hash": "$2b$12$...",
  "role": "admin",  // "general" | "vip" | "admin"
  "is_active": true,
  "created_at": ISODate("2025-01-10T..."),
  "last_login": ISODate("2025-01-10T...")
}
```

### Colección: `templates`
```json
{
  "_id": ObjectId("..."),
  "user_id": "user_object_id",
  "name": "Mi Topología",
  "topology_json": {
    "nodes": [...],
    "edges": [...]
  },
  "availability_zone": "linux-AZ-1",
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### Colección: `slices`
```json
{
  "_id": ObjectId("..."),
  "template_id": "template_object_id",
  "user_id": "user_object_id",
  "slice_id": "topology-20250110-143022",
  "name": "Mi Topología",
  "topology_json": {
    "nodes": [...],
    "edges": [...]
  },
  "availability_zone": "linux-AZ-1",
  "deployed_at": ISODate("..."),
  "status": "active",
  "vm_count": 5
}
```

## 🔐 Roles y Permisos

### Usuario General (role: "general")
- ✅ Crear plantillas
- ✅ Desplegar hasta **3 slices**
- ✅ Usar solo `linux-AZ-1`
- ❌ No puede ver plantillas de otros usuarios

### Usuario VIP (role: "vip")
- ✅ Crear plantillas
- ✅ Desplegar hasta **10 slices**
- ✅ Usar `linux-AZ-1` y `linux-AZ-2`
- ❌ No puede ver plantillas de otros usuarios

### Usuario Admin (role: "admin")
- ✅ Crear plantillas
- ✅ Desplegar **slices ilimitados**
- ✅ Usar todos los AZ disponibles
- ✅ **Ver y editar plantillas de TODOS los usuarios**
- ✅ **Ver y eliminar slices de TODOS los usuarios**

## 📝 Scripts Útiles

### Crear Usuarios de Prueba

```python
# crear_usuarios_prueba.py
from auth_jwt import get_password_hash
from database.mongo_config import get_db
from datetime import datetime

def crear_usuarios_prueba():
    db = get_db()

    usuarios = [
        {
            'username': 'usuario1',
            'email': 'usuario1@test.com',
            'password_hash': get_password_hash('password123'),
            'role': 'general',
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        },
        {
            'username': 'vip1',
            'email': 'vip1@test.com',
            'password_hash': get_password_hash('password123'),
            'role': 'vip',
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        }
    ]

    for user in usuarios:
        if not db.users.find_one({'username': user['username']}):
            db.users.insert_one(user)
            print(f"✅ Usuario creado: {user['username']}")
        else:
            print(f"⚠️  Usuario ya existe: {user['username']}")

if __name__ == '__main__':
    crear_usuarios_prueba()
```

### Ver Todos los Usuarios

```bash
mongo
> use cloud_topology_db
> db.users.find().pretty()
```

### Resetear la Base de Datos

```bash
mongo
> use cloud_topology_db
> db.dropDatabase()
> exit

# Recrear el admin
python create_admin_mongo.py
```

## 🚀 Flujo de Trabajo Recomendado

### Desarrollo en Equipo (Local)

1. **Una sola persona** crea la BD inicial y el admin
2. Exporta un dump: `mongodump --db=cloud_topology_db --out=./mongo_backup`
3. Sube `./mongo_backup/` a Git o Google Drive
4. **Los demás** descargan y restauran: `mongorestore --db=cloud_topology_db ./mongo_backup/cloud_topology_db`

### Cuando alguien hace cambios importantes

```bash
# Exportar cambios
mongodump --db=cloud_topology_db --out=./mongo_backup

# Actualizar Git
git add mongo_backup/
git commit -m "Actualizar BD con nuevos usuarios"
git push

# Los demás actualizan
git pull
mongorestore --drop --db=cloud_topology_db ./mongo_backup/cloud_topology_db
```

## ❓ Preguntas Frecuentes

**Q: ¿Dónde se guardan los archivos .json físicos?**
A: En la carpeta `./templates/` con formato `{nombre}_{timestamp}.json`

**Q: ¿Los archivos .json se pushean a Git?**
A: Sí, puedes subirlos. Están separados de MongoDB.

**Q: ¿MongoDB se sube a Git?**
A: NO directamente. Sube el **dump** (archivos BSON) en `mongo_backup/`.

**Q: ¿Cómo cambio mi contraseña?**
A: Por ahora desde MongoDB shell:
```javascript
db.users.updateOne(
  {username: "admin"},
  {$set: {password_hash: "<nuevo_hash_bcrypt>"}}
)
```

## 🔗 Enlaces Útiles

- [MongoDB Docs](https://www.mongodb.com/docs/)
- [MongoDB Compass (GUI)](https://www.mongodb.com/products/compass)
- [MongoDB Atlas (Cloud)](https://www.mongodb.com/cloud/atlas)
- [Documentación de PyMongo](https://pymongo.readthedocs.io/)
