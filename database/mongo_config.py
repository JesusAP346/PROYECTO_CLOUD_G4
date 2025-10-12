"""
Configuración de MongoDB
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os

# Configuración de MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('MONGO_DB_NAME', 'cloud_topology_db')

# Cliente global
_client = None
_db = None

def get_mongo_client():
    """Obtiene el cliente de MongoDB"""
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Verificar conexión
            _client.admin.command('ping')
            print("✅ Conectado a MongoDB exitosamente")
        except ConnectionFailure as e:
            print(f"❌ Error al conectar a MongoDB: {e}")
            raise
    return _client

def get_db():
    """Obtiene la base de datos"""
    global _db
    if _db is None:
        client = get_mongo_client()
        _db = client[DB_NAME]
    return _db

def init_database():
    """Inicializa la base de datos y crea índices"""
    try:
        db = get_db()

        # Crear colecciones si no existen
        collections = db.list_collection_names()

        if 'users' not in collections:
            db.create_collection('users')
            print("✅ Colección 'users' creada")

        if 'templates' not in collections:
            db.create_collection('templates')
            print("✅ Colección 'templates' creada")

        if 'slices' not in collections:
            db.create_collection('slices')
            print("✅ Colección 'slices' creada")

        # Crear índices únicos
        db.users.create_index('username', unique=True)
        db.users.create_index('email', unique=True)
        print("✅ Índices creados en 'users'")

        # Índices para templates
        db.templates.create_index([('user_id', 1), ('name', 1)])
        print("✅ Índices creados en 'templates'")

        # Índices para slices
        db.slices.create_index('slice_id', unique=True)
        db.slices.create_index([('user_id', 1), ('status', 1)])
        print("✅ Índices creados en 'slices'")

        print("\n✅ Base de datos MongoDB inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al inicializar base de datos: {e}")
        return False

def close_connection():
    """Cierra la conexión a MongoDB"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None

if __name__ == '__main__':
    print("Inicializando MongoDB...")
    init_database()
