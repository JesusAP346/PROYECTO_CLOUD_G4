"""
Sistema de autenticación y gestión de usuarios
"""
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database.db_config import get_db_cursor
from datetime import datetime

login_manager = LoginManager()

class User(UserMixin):
    def __init__(self, id, username, email, role, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.is_active = is_active

    @staticmethod
    def get_by_id(user_id):
        """Obtiene un usuario por su ID"""
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, email, role, is_active FROM users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return User(row['id'], row['username'], row['email'], row['role'], row['is_active'])
        return None

    @staticmethod
    def get_by_username(username):
        """Obtiene un usuario por su username"""
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, email, role, is_active FROM users WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
            if row:
                return User(row['id'], row['username'], row['email'], row['role'], row['is_active'])
        return None

    @staticmethod
    def authenticate(username, password):
        """Autentica un usuario con username y password"""
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, email, role, password_hash, is_active FROM users WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
            if row and check_password_hash(row['password_hash'], password):
                if not row['is_active']:
                    return None, "Usuario desactivado"

                # Actualizar último login
                with get_db_cursor(commit=True) as update_cur:
                    update_cur.execute(
                        "UPDATE users SET last_login = %s WHERE id = %s",
                        (datetime.now(), row['id'])
                    )

                return User(row['id'], row['username'], row['email'], row['role'], row['is_active']), None
            return None, "Usuario o contraseña incorrectos"

    @staticmethod
    def create(username, email, password, role='general'):
        """Crea un nuevo usuario"""
        password_hash = generate_password_hash(password)
        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, username, email, role, is_active
                    """,
                    (username, email, password_hash, role)
                )
                row = cur.fetchone()
                if row:
                    return User(row['id'], row['username'], row['email'], row['role'], row['is_active']), None
        except Exception as e:
            if 'duplicate key' in str(e).lower():
                if 'username' in str(e).lower():
                    return None, "El nombre de usuario ya existe"
                elif 'email' in str(e).lower():
                    return None, "El email ya está registrado"
            return None, f"Error al crear usuario: {str(e)}"
        return None, "Error desconocido"

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
