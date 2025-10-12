"""
Script para crear usuarios de prueba en MongoDB
Ejecutar: python crear_usuarios_prueba.py
"""
from auth_jwt import get_password_hash
from database.mongo_config import get_db
from datetime import datetime

def crear_usuarios_prueba():
    """Crea usuarios de prueba para desarrollo"""
    db = get_db()

    usuarios = [
        {
            'username': 'usuario1',
            'email': 'usuario1@test.com',
            'password_hash': get_password_hash('password123'),
            'role': 'general',  # Solo linux-AZ-1, máximo 3 slices
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        },
        {
            'username': 'usuario2',
            'email': 'usuario2@test.com',
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
            'role': 'vip',  # linux-AZ-1 y linux-AZ-2, máximo 10 slices
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        },
        {
            'username': 'vip2',
            'email': 'vip2@test.com',
            'password_hash': get_password_hash('password123'),
            'role': 'vip',
            'is_active': True,
            'created_at': datetime.now(),
            'last_login': None
        }
    ]

    print("=" * 60)
    print("🔧 CREANDO USUARIOS DE PRUEBA")
    print("=" * 60)

    for user in usuarios:
        if not db.users.find_one({'username': user['username']}):
            db.users.insert_one(user)
            print(f"✅ Usuario creado: {user['username']} ({user['role']})")
            print(f"   📧 Email: {user['email']}")
            print(f"   🔑 Password: password123")
            print()
        else:
            print(f"⚠️  Usuario ya existe: {user['username']}")

    print("=" * 60)
    print("USUARIOS DISPONIBLES:")
    print("=" * 60)
    print("Usuario General (max 3 slices, solo linux-AZ-1):")
    print("  - usuario1 / password123")
    print("  - usuario2 / password123")
    print()
    print("Usuario VIP (max 10 slices, linux-AZ-1 y linux-AZ-2):")
    print("  - vip1 / password123")
    print("  - vip2 / password123")
    print()
    print("Usuario Admin (slices ilimitados, todos los AZ):")
    print("  - admin / admin123")
    print("=" * 60)

if __name__ == '__main__':
    crear_usuarios_prueba()
