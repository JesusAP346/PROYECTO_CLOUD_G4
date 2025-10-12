"""
Script para crear el usuario administrador inicial en MongoDB
"""
from auth_jwt import get_password_hash
from database.mongo_config import get_db
from datetime import datetime

def create_admin():
    username = 'admin'
    email = 'admin@cloudproject.com'
    password = 'admin123'  # Cambiar después del primer login
    role = 'admin'

    password_hash = get_password_hash(password)

    try:
        db = get_db()

        # Verificar si el admin ya existe
        existing = db.users.find_one({'username': username})

        if existing:
            print(f"⚠️  El usuario '{username}' ya existe.")
            response = input("   ¿Deseas recrearlo con la nueva contraseña bcrypt? (s/n): ").strip().lower()
            if response == 's':
                db.users.delete_one({'username': username})
                print(f"   Usuario '{username}' eliminado. Creando nuevo...")
            else:
                print("   Operación cancelada.")
                return

        # Crear el usuario admin
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

        print("✅ Usuario administrador creado exitosamente!")
        print(f"   ID: {result.inserted_id}")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"   Email: {email}")
        print(f"   Rol: {role}")
        print()
        print("⚠️  IMPORTANTE: Cambia esta contraseña después del primer login!")

    except Exception as e:
        print(f"❌ Error al crear usuario administrador: {e}")

if __name__ == '__main__':
    print("Creando usuario administrador en MongoDB...")
    create_admin()
