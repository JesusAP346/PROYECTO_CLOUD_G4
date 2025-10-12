# Setup del Sistema de Autenticación

Este documento explica cómo configurar e iniciar el nuevo sistema de autenticación del Cloud Topology Manager.

## 📋 Requisitos Previos

1. Python 3.12
2. PostgreSQL 16
3. Entorno virtual activado

## 🚀 Pasos de Instalación

### 1. Instalar dependencias actualizadas

```bash
pip install -r requirements.txt
```

Esto instalará Flask-Login y todas las dependencias necesarias.

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# Base de datos
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cloud_topology_db
DB_USER=postgres
DB_PASSWORD=password

# Flask secret key (cambiar en producción)
SECRET_KEY=tu-clave-secreta-super-segura-cambiar-en-produccion
```

### 3. Crear la base de datos

```bash
# Conectarse a PostgreSQL
psql -U postgres

# Crear la base de datos
CREATE DATABASE cloud_topology_db;

# Salir
\q
```

### 4. Inicializar el esquema de base de datos

```bash
python database/db_config.py
```

Este comando creará todas las tablas necesarias:
- `users` (usuarios del sistema)
- `templates` (plantillas guardadas)
- `slices` (slices desplegados)

### 5. Crear usuario administrador inicial

El script de inicialización ya crea un usuario admin por defecto:

- **Username**: `admin`
- **Password**: `admin123`
- **Email**: `admin@cloudproject.com`
- **Rol**: `admin`

**⚠️ IMPORTANTE**: Cambia esta contraseña después del primer login.

Para crear el hash correcto, ejecuta:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('admin123'))"
```

Luego actualiza el hash en `database/schema.sql`.

### 6. Iniciar la aplicación

```bash
python app_new.py
```

La aplicación estará disponible en: `http://127.0.0.1:5000`

## 🎯 Funcionalidades Implementadas

### Sistema de Autenticación
- ✅ Login con usuario y contraseña
- ✅ Registro de nuevos usuarios
- ✅ Logout
- ✅ Sesiones seguras con Flask-Login
- ✅ Passwords hasheados con Werkzeug

### Roles de Usuario
- **General**: Acceso básico, máximo 3 slices activos
  - Zonas disponibles: Auto, linux-AZ-1
- **VIP**: Acceso premium, máximo 10 slices activos
  - Zonas disponibles: Auto, linux-AZ-1, linux-AZ-2
- **Admin**: Acceso completo, slices ilimitados
  - Zonas disponibles: Todas (Auto, linux-AZ-1, linux-AZ-2, openstack-AZ-1)

### Dashboard
- ✅ Vista de plantillas creadas (no desplegadas)
- ✅ Vista de slices desplegados (activos)
- ✅ Estadísticas de uso
- ✅ Límites por rol

### Gestión de Plantillas
- ✅ Crear nueva plantilla (botón que lleva al editor)
- ✅ Editar plantilla existente
- ✅ Eliminar plantilla
- ✅ Desplegar plantilla (crea slice)
- ✅ Guardar en base de datos con user_id

### Gestión de Slices
- ✅ Ver slices activos
- ✅ Eliminar slice (libera VLANs)
- ✅ Registro en base de datos
- ✅ Integración con deploy_topology.py

## 📁 Estructura de Archivos

```
PROYECTO_CLOUD_G4/
├── app_new.py                    # Aplicación principal con autenticación
├── auth.py                       # Sistema de autenticación y User model
├── database/
│   ├── schema.sql               # Esquema de base de datos
│   └── db_config.py             # Configuración y conexión a BD
├── templates/
│   ├── login.html               # Página de login
│   ├── register.html            # Página de registro
│   ├── dashboard.html           # Dashboard principal
│   └── index.html               # Editor de topologías (existente)
├── slice_manager/
│   └── deploy_topology.py       # Script de despliegue
└── requirements.txt             # Dependencias (actualizado)
```

## 🔄 Migración desde app.py

El archivo `app_new.py` es el nuevo punto de entrada con autenticación completa. El `app.py` anterior se mantiene como referencia.

### Diferencias principales:

1. **Autenticación requerida**: Todos los endpoints requieren login
2. **Gestión de sesiones**: Cada usuario tiene sus propias plantillas y slices
3. **Permisos por rol**: Filtrado de zonas de disponibilidad y límites de slices
4. **Persistencia en BD**: Todo se guarda en PostgreSQL, no en archivos JSON

## 🧪 Pruebas

### Crear un usuario de prueba

```bash
python -c "
from auth import User
user, error = User.create('testuser', 'test@example.com', 'password123', 'general')
if user:
    print(f'Usuario creado: {user.username} con rol {user.role}')
else:
    print(f'Error: {error}')
"
```

### Verificar tablas en PostgreSQL

```bash
psql -U postgres -d cloud_topology_db

# Listar usuarios
SELECT * FROM users;

# Listar plantillas
SELECT * FROM templates;

# Listar slices
SELECT * FROM slices;
```

## 🐛 Troubleshooting

### Error: "No module named 'flask_login'"
```bash
pip install Flask-Login==0.6.3
```

### Error: "could not connect to server"
Verifica que PostgreSQL esté corriendo:
```bash
sudo systemctl status postgresql
```

### Error: "relation 'users' does not exist"
Inicializa el esquema:
```bash
python database/db_config.py
```

### El password del admin no funciona
Genera un nuevo hash:
```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('tupassword'))"
```

Y actualízalo en la BD:
```sql
UPDATE users SET password_hash = 'NUEVO_HASH' WHERE username = 'admin';
```

## 📚 Próximos Pasos

1. **Cambiar secret key en producción**
2. **Actualizar password del admin**
3. **Configurar variables de entorno del servidor**
4. **Probar despliegue end-to-end**
5. **Implementar recuperación de contraseña (opcional)**
6. **Agregar logs de auditoría (opcional)**

## 🎨 Personalización

### Cambiar límites de slices por rol

Edita `auth.py`, método `get_max_slices()`:

```python
def get_max_slices(self):
    if self.role == 'admin':
        return 999
    elif self.role == 'vip':
        return 10  # Cambiar aquí
    else:  # general
        return 3   # Cambiar aquí
```

### Agregar nuevas zonas de disponibilidad

Edita `auth.py`, método `get_available_zones()`:

```python
def get_available_zones(self):
    if self.role == 'admin':
        return ['', 'linux-AZ-1', 'linux-AZ-2', 'openstack-AZ-1', 'nueva-zona']
    # ...
```

## ✅ Checklist de Verificación

- [ ] PostgreSQL 16 instalado y corriendo
- [ ] Base de datos `cloud_topology_db` creada
- [ ] Esquema inicializado (tablas creadas)
- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] Variables de entorno configuradas (.env)
- [ ] Usuario admin creado
- [ ] Aplicación inicia sin errores
- [ ] Login funciona
- [ ] Registro funciona
- [ ] Dashboard se carga correctamente
- [ ] Editor de topologías accesible desde dashboard
- [ ] Guardar plantilla funciona
- [ ] Desplegar slice funciona (si infra disponible)

¡Listo! El sistema de autenticación está completo y funcionando.
