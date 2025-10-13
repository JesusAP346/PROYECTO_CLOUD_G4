"""
Sistema de autenticación con JWT para FastAPI
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from bson import ObjectId
from database.mongo_config import get_db

# Configuración JWT
SECRET_KEY = "tu-clave-secreta-super-segura-cambiar-en-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Configuración de encriptación de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de seguridad Bearer
security = HTTPBearer()

# ==========================================
# MODELOS PYDANTIC
# ==========================================

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "general"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserInDB(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool = True

# ==========================================
# FUNCIONES DE AUTENTICACIÓN
# ==========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera hash de la contraseña"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decodifica y verifica un token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# ==========================================
# FUNCIONES DE USUARIO
# ==========================================

def get_user_by_username(username: str) -> Optional[dict]:
    """Obtiene un usuario por username desde MongoDB"""
    try:
        db = get_db()
        user = db.users.find_one({'username': username})
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def get_user_by_id(user_id: str) -> Optional[dict]:
    """Obtiene un usuario por ID desde MongoDB"""
    try:
        db = get_db()
        user = db.users.find_one({'_id': ObjectId(user_id)})
        return user
    except Exception as e:
        print(f"Error getting user by id: {e}")
        return None

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Autentica un usuario con username y password"""
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user['password_hash']):
        return None
    if not user.get('is_active', True):
        return None

    # Actualizar último login
    db = get_db()
    db.users.update_one(
        {'_id': user['_id']},
        {'$set': {'last_login': datetime.now()}}
    )

    return user

def create_user(user_data: UserCreate) -> tuple:
    """Crea un nuevo usuario en MongoDB"""
    try:
        db = get_db()

        # Verificar si el usuario ya existe
        if db.users.find_one({'username': user_data.username}):
            return None, "El nombre de usuario ya existe"

        if db.users.find_one({'email': user_data.email}):
            return None, "El email ya está registrado"

        # Crear el usuario
        password_hash = get_password_hash(user_data.password)
        user_doc = {
            'username': user_data.username,
            'email': user_data.email,
            'password_hash': password_hash,
            'role': user_data.role,
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        }

        result = db.users.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id

        return user_doc, None

    except Exception as e:
        print(f"Error creating user: {e}")
        return None, f"Error al crear usuario: {str(e)}"

# ==========================================
# DEPENDENCIAS FASTAPI
# ==========================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependencia para obtener el usuario actual desde el token JWT
    Uso en endpoints: current_user: dict = Depends(get_current_user)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = decode_token(token)

        if payload is None:
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    if not user.get('is_active', True):
        raise HTTPException(status_code=400, detail="Usuario inactivo")

    return user

async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Obtiene el usuario actual verificando que esté activo"""
    if not current_user.get('is_active', True):
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user

# ==========================================
# FUNCIONES DE ROLES Y PERMISOS
# ==========================================

def get_available_zones(user: dict) -> list:
    """Retorna las zonas de disponibilidad según el rol del usuario"""
    role = user.get('role', 'general')
    if role == 'admin':
        # Admin puede usar todas las zonas de Linux (openstack se muestra como próximamente)
        return ['', 'linux-AZ-1', 'linux-AZ-2']
    elif role == 'vip':
        # VIP puede usar automático y todas las zonas de Linux
        return ['', 'linux-AZ-1', 'linux-AZ-2']
    else:  # general
        # General solo puede usar linux-AZ-1 (sin automático)
        return ['linux-AZ-1']

def get_max_slices(user: dict) -> int:
    """Retorna el número máximo de slices permitidos según el rol"""
    role = user.get('role', 'general')
    if role == 'admin':
        return 999  # Sin límite práctico
    elif role == 'vip':
        return 10
    else:  # general
        return 3

def has_role(user: dict, *roles) -> bool:
    """Verifica si el usuario tiene uno de los roles especificados"""
    return user.get('role', 'general') in roles

def is_admin(user: dict) -> bool:
    """Verifica si el usuario es administrador"""
    return user.get('role', 'general') == 'admin'

def is_vip(user: dict) -> bool:
    """Verifica si el usuario es VIP o administrador"""
    return user.get('role', 'general') in ('vip', 'admin')
