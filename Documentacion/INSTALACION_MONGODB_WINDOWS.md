# 🚀 Guía de Instalación MongoDB para Windows

Esta guía te llevará paso a paso para instalar y configurar todo el sistema con MongoDB.

## ✅ Ventajas de MongoDB
- ✨ **Más fácil de instalar en Windows**
- ✨ **No necesitas configurar usuarios/passwords complicados**
- ✨ **Inicia automáticamente como servicio**
- ✨ **Interfaz gráfica incluida (MongoDB Compass)**

---

## 📥 Paso 1: Descargar MongoDB

### Opción A: Descarga Rápida
1. Ve a: https://www.mongodb.com/try/download/community
2. Selecciona:
   - **Version**: 7.0.x (latest)
   - **Platform**: Windows
   - **Package**: msi
3. Click en **Download**

### Opción B: Descarga Directa
https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.5-signed.msi

---

## 💿 Paso 2: Instalar MongoDB

1. **Ejecuta el instalador** (.msi que descargaste)
2. Click en **Next** → **Accept** los términos
3. Selecciona **Complete** (instalación completa)
4. **IMPORTANTE**: En "Service Configuration":
   - ✅ Deja marcado **"Install MongoDB as a Service"**
   - ✅ Deja **"Run service as Network Service user"**
   - ✅ Nombre del servicio: `MongoDB`
   - ✅ Data Directory: `C:\Program Files\MongoDB\Server\7.0\data\`
   - ✅ Log Directory: `C:\Program Files\MongoDB\Server\7.0\log\`
5. **OPCIONAL**: Instala MongoDB Compass (interfaz gráfica) - se marca automáticamente
6. Click en **Install** y espera...
7. Click en **Finish**

✅ **MongoDB ya está instalado y corriendo como servicio de Windows**

---

## 🔍 Paso 3: Verificar que MongoDB está corriendo

### Método 1: Servicios de Windows
1. Presiona `Windows + R`
2. Escribe `services.msc` y Enter
3. Busca **"MongoDB"** en la lista
4. Debe decir **"En ejecución"** (Running)

### Método 2: Símbolo del sistema
```cmd
mongod --version
```

Deberías ver algo como:
```
db version v7.0.5
```

---

## 🐍 Paso 4: Instalar Dependencias de Python

Abre **PowerShell** o **CMD**:

```powershell
# Navegar al proyecto
cd "C:\Users\Adrian Lopez\Desktop\Cloud_versionfinal\PROYECTO_CLOUD_G4"

# Activar entorno virtual (si lo tienes)
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

Esto instalará:
- Flask
- Flask-Login
- pymongo (driver de MongoDB)
- Todas las demás dependencias

---

## 🔧 Paso 5: Inicializar MongoDB

```powershell
# Crear colecciones e índices
python database\mongo_config.py
```

Deberías ver:
```
✅ Conectado a MongoDB exitosamente
✅ Colección 'users' creada
✅ Colección 'templates' creada
✅ Colección 'slices' creada
✅ Índices creados en 'users'
✅ Índices creados en 'templates'
✅ Índices creados en 'slices'
✅ Base de datos MongoDB inicializada correctamente
```

---

## 👤 Paso 6: Crear Usuario Administrador

```powershell
python create_admin_mongo.py
```

Deberías ver:
```
Creando usuario administrador en MongoDB...
✅ Usuario administrador creado exitosamente!
   Username: admin
   Password: admin123
   Email: admin@cloudproject.com
   Rol: admin
```

---

## 🎯 Paso 7: Iniciar la Aplicación

```powershell
python app_mongo.py
```

Deberías ver:
```
✅ Conectado a MongoDB exitosamente
 * Serving Flask app 'app_mongo'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

**⚠️ NO CIERRES ESTA VENTANA** - La aplicación está corriendo aquí.

---

## 🌐 Paso 8: Abrir en el Navegador

1. Abre tu navegador (Chrome, Edge, Firefox, etc.)
2. Ve a: **http://127.0.0.1:5000**
3. Deberías ver la pantalla de **Login**

### Credenciales de prueba:
- **Usuario**: `admin`
- **Contraseña**: `admin123`

---

## 🎨 ¿Qué verás después del login?

### Dashboard con:
- ✅ **Estadísticas** (plantillas, slices activos, límites)
- ✅ **Botón "Crear Nueva Plantilla"** → Te lleva al editor
- ✅ **Tabla de Plantillas** con botones:
  - 📝 Editar
  - 🚀 Desplegar
  - 🗑️ Eliminar
- ✅ **Tabla de Slices Desplegados** con botón:
  - 🗑️ Eliminar

---

## 🛠️ Herramientas Opcionales

### MongoDB Compass (Interfaz Gráfica)

Si instalaste MongoDB Compass, puedes ver tus datos gráficamente:

1. Abre **MongoDB Compass**
2. Conectar a: `mongodb://localhost:27017`
3. Verás la base de datos `cloud_topology_db`
4. Explora las colecciones:
   - `users` - Usuarios del sistema
   - `templates` - Plantillas guardadas
   - `slices` - Slices desplegados

---

## 🐛 Solución de Problemas

### Error: "No module named 'pymongo'"

```powershell
pip install pymongo
```

### Error: "pymongo.errors.ServerSelectionTimeoutError"

**Problema**: MongoDB no está corriendo

**Solución 1**: Inicia el servicio
```powershell
# Como administrador:
net start MongoDB
```

**Solución 2**: Desde Servicios de Windows
1. Presiona `Windows + R`
2. Escribe `services.msc`
3. Busca **MongoDB**
4. Click derecho → **Iniciar**

### Error: "python no se reconoce como comando"

Usa `py` en lugar de `python`:
```powershell
py app_mongo.py
```

### El puerto 5000 está ocupado

**Opción 1**: Cerrar la aplicación que lo está usando

**Opción 2**: Cambiar el puerto en `app_mongo.py` (última línea):
```python
app.run(debug=True, port=5001)  # Cambiar a 5001
```

### MongoDB Compass no se instaló

Descárgalo por separado:
https://www.mongodb.com/try/download/compass

---

## 📊 Ver tus datos en MongoDB

### Opción 1: MongoDB Compass (Gráfico)
```
mongodb://localhost:27017
```

### Opción 2: Shell de MongoDB (Terminal)
```powershell
# Abrir MongoDB Shell
mongosh

# Cambiar a tu base de datos
use cloud_topology_db

# Ver usuarios
db.users.find()

# Ver plantillas
db.templates.find()

# Ver slices
db.slices.find()

# Salir
exit
```

---

## 🎯 Resumen de Comandos

### Iniciar todo desde cero:
```powershell
# 1. Navegar al proyecto
cd "C:\Users\Adrian Lopez\Desktop\Cloud_versionfinal\PROYECTO_CLOUD_G4"

# 2. Activar entorno virtual
.venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Inicializar MongoDB
python database\mongo_config.py

# 5. Crear admin
python create_admin_mongo.py

# 6. Iniciar app
python app_mongo.py
```

### Luego abre el navegador:
```
http://127.0.0.1:5000
```

---

## 🔄 Diferencias con PostgreSQL

| Característica | PostgreSQL | MongoDB |
|----------------|------------|---------|
| Instalación en Windows | Complicada | Simple |
| Configuración inicial | Usuarios, passwords, psql | Automática |
| Interfaz gráfica | pgAdmin (complejo) | Compass (simple) |
| Comandos | SQL | JavaScript-like |
| Servicio Windows | Manual | Automático |

---

## 📁 Archivos Importantes

```
PROYECTO_CLOUD_G4/
├── app_mongo.py                 ← Aplicación principal (USAR ESTE)
├── auth_mongo.py                ← Autenticación MongoDB
├── create_admin_mongo.py        ← Crear usuario admin
├── database/
│   └── mongo_config.py          ← Configuración MongoDB
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   └── index.html (editor)
└── requirements.txt
```

---

## ✅ Checklist Final

- [ ] MongoDB instalado y corriendo como servicio
- [ ] MongoDB Compass instalado (opcional)
- [ ] Dependencias de Python instaladas
- [ ] Base de datos inicializada
- [ ] Usuario admin creado
- [ ] Aplicación corriendo (`python app_mongo.py`)
- [ ] Login funciona en el navegador
- [ ] Dashboard se muestra correctamente

---

## 🎉 ¡Listo!

Tu sistema está completamente funcional con MongoDB.

**Próximos pasos**:
1. Inicia sesión con `admin` / `admin123`
2. Crea una plantilla desde el dashboard
3. Despliégala como slice
4. ¡Disfruta tu sistema de topologías!

---

## 📞 Soporte

Si algo no funciona, revisa:
1. MongoDB está corriendo (Servicios de Windows)
2. El entorno virtual está activado
3. Todas las dependencias están instaladas
4. El puerto 5000 no está ocupado

¡Todo debería funcionar perfectamente! 🚀
