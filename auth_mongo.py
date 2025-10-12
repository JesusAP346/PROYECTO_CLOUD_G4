"""
Sistema de autenticación con MongoDB
"""
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database.mongo_config import get_db
from datetime import datetime
from bson import ObjectId

login_manager = LoginManager()

class User(UserMixin):
    def __init__(self, user_id, username, email, role, active=True):
        self.id = str(user_id)  # Convertir ObjectId a string
        self.username = username
        self.email = email
        self.role = role
        self._active = active

    @property
    def is_active(self):
        return self._active

    @staticmethod
    def get_by_id(user_id):
        """Obtiene un usuario por su ID"""
        try:
            db = get_db()
            user_doc = db.users.find_one({'_id': ObjectId(user_id)})
            if user_doc:
                return User(
                    user_doc['_id'],
                    user_doc['username'],
                    user_doc['email'],
                    user_doc['role'],
                    user_doc.get('is_active', True)
                )
        except Exception as e:
            print(f"Error getting user by id: {e}")
        return None

    @staticmethod
    def get_by_username(username):
        """Obtiene un usuario por su username"""
        try:
            db = get_db()
            user_doc = db.users.find_one({'username': username})
            if user_doc:
                return User(
                    user_doc['_id'],
                    user_doc['username'],
                    user_doc['email'],
                    user_doc['role'],
                    user_doc.get('is_active', True)
                )
        except Exception as e:
            print(f"Error getting user by username: {e}")
        return None

    @staticmethod
    def authenticate(username, password):
        """Autentica un usuario con username y password"""
        try:
            db = get_db()
            user_doc = db.users.find_one({'username': username})

            if user_doc and check_password_hash(user_doc['password_hash'], password):
                if not user_doc.get('is_active', True):
                    return None, "Usuario desactivado"

                # Actualizar último login
                db.users.update_one(
                    {'_id': user_doc['_id']},
                    {'$set': {'last_login': datetime.now()}}
                )

                return User(
                    user_doc['_id'],
                    user_doc['username'],
                    user_doc['email'],
                    user_doc['role'],
                    user_doc.get('is_active', True)
                ), None

            return None, "Usuario o contraseña incorrectos"
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None, f"Error al autenticar: {str(e)}"

    @staticmethod
    def create(username, email, password, role='general'):
        """Crea un nuevo usuario"""
        password_hash = generate_password_hash(password)
        try:
            db = get_db()

            # Verificar si el usuario ya existe
            if db.users.find_one({'username': username}):
                return None, "El nombre de usuario ya existe"

            if db.users.find_one({'email': email}):
                return None, "El email ya está registrado"

            # Crear el usuario
            user_doc = {
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'role': role,
                'is_active': True,
                'created_at': datetime.now(),
                'last_login': None
            }

            result = db.users.insert_one(user_doc)

            return User(
                result.inserted_id,
                username,
                email,
                role,
                True
            ), None

        except Exception as e:
            print(f"Error creating user: {e}")
            return None, f"Error al crear usuario: {str(e)}"

    def has_role(self, *roles):
        """Verifica si el usuario tiene uno de los roles especificados"""
        return self.role in roles

    def is_admin(self):
        """Verifica si el usuario es administrador"""
        return self.role == 'admin'

    def is_vip(self):
        """Verifica si el usuario es VIP o administrador"""
        return self.role in ('vip', 'admin')

    def get_available_zones(self):
        """Retorna las zonas de disponibilidad según el rol del usuario"""
        if self.role == 'admin':
            return ['', 'linux-AZ-1', 'linux-AZ-2', 'openstack-AZ-1']
        elif self.role == 'vip':
            return ['', 'linux-AZ-1', 'linux-AZ-2']
        else:  # general
            return ['', 'linux-AZ-1']

    def get_max_slices(self):
        """Retorna el número máximo de slices permitidos según el rol"""
        if self.role == 'admin':
            return 999  # Sin límite práctico
        elif self.role == 'vip':
            return 10
        else:  # general
            return 3

@login_manager.user_loader
def load_user(user_id):
    """Callback requerido por Flask-Login para cargar usuario"""
    return User.get_by_id(user_id)
