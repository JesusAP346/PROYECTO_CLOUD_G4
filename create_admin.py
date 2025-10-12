"""
Script para crear el usuario administrador inicial
"""
from werkzeug.security import generate_password_hash
from database.db_config import get_db_cursor

def create_admin():
    username = 'admin'
    email = 'admin@cloudproject.com'
    password = 'admin123'  # Cambiar después del primer login
    role = 'admin'

    password_hash = generate_password_hash(password)

    try:
        with get_db_cursor(commit=True) as cur:
            # Verificar si el admin ya existe
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            existing = cur.fetchone()

            if existing:
                print(f"⚠️  El usuario '{username}' ya existe.")
                print(f"   Si olvidaste la contraseña, puedes actualizarla con:")
                print(f"   UPDATE users SET password_hash = '{password_hash}' WHERE username = '{username}';")
                return

            # Crear el usuario admin
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (username, email, password_hash, role)
            )

            admin_id = cur.fetchone()['id']

            print("✅ Usuario administrador creado exitosamente!")
            print(f"   ID: {admin_id}")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            print(f"   Email: {email}")
            print(f"   Rol: {role}")
            print()
            print("⚠️  IMPORTANTE: Cambia esta contraseña después del primer login!")

    except Exception as e:
        print(f"❌ Error al crear usuario administrador: {e}")

if __name__ == '__main__':
    print("Creando usuario administrador...")
    create_admin()
