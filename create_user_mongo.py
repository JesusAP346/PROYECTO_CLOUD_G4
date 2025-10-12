"""
Script para crear usuarios (general, vip o admin) en MongoDB
"""
from auth_mongo import User
from database.mongo_config import get_db

def create_user():
    print("=" * 50)
    print("CREAR NUEVO USUARIO EN MONGODB")
    print("=" * 50)

    username = input("Username: ").strip()
    email = input("Email: ").strip()
    password = input("Password: ").strip()

    print("\nSelecciona el rol del usuario:")
    print("1. General (3 slices max, solo linux-AZ-1)")
    print("2. VIP (10 slices max, linux-AZ-1 y linux-AZ-2)")
    print("3. Admin (sin límites, todas las zonas)")

    role_option = input("Opción (1/2/3): ").strip()

    role_map = {
        '1': 'general',
        '2': 'vip',
        '3': 'admin'
    }

    role = role_map.get(role_option, 'general')

    print(f"\nCreando usuario con rol: {role}...")
    user, error = User.create(username, email, password, role)

    if user:
        print("\n✅ Usuario creado exitosamente!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Rol: {role}")

        # Mostrar permisos según el rol
        if role == 'admin':
            print(f"   Límite de slices: Sin límite")
            print(f"   Zonas disponibles: Todas (linux-AZ-1, linux-AZ-2, openstack-AZ-1)")
        elif role == 'vip':
            print(f"   Límite de slices: 10")
            print(f"   Zonas disponibles: linux-AZ-1, linux-AZ-2")
        else:  # general
            print(f"   Límite de slices: 3")
            print(f"   Zonas disponibles: linux-AZ-1")
    else:
        print(f"\n❌ Error al crear usuario: {error}")

if __name__ == '__main__':
    create_user()
