"""
Configuración de base de datos PostgreSQL
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager

# Configuración de la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'cloud_topology_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        raise

@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager para obtener un cursor de base de datos

    Args:
        commit: Si es True, hace commit automáticamente al finalizar

    Usage:
        with get_db_cursor(commit=True) as cur:
            cur.execute("INSERT INTO ...")
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def init_database():
    """Inicializa la base de datos ejecutando el schema.sql"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Leer y ejecutar el schema
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        cursor.execute(schema_sql)
        conn.commit()

        cursor.close()
        conn.close()

        print("✅ Base de datos inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al inicializar base de datos: {e}")
        return False

if __name__ == '__main__':
    # Script para inicializar la base de datos
    print("Inicializando base de datos...")
    init_database()
