from pymongo import MongoClient
from config import Config

class Database:
    client = None
    db = None

    @classmethod
    def init_db(cls):
        if not cls.client:
            print("Conectando a MongoDB Atlas...")
            print(f"URI: {Config.MONGO_URI[:50]}...")
            print(f"Base de datos: {Config.DB_NAME}")
            try:
                # Conectar con timeout de 10 segundos
                cls.client = MongoClient(
                    Config.MONGO_URI,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )
                
                # Verificar conexión
                cls.client.admin.command('ping')
                print("✓ Ping exitoso a MongoDB Atlas")
                
                cls.db = cls.client[Config.DB_NAME]
                
                # Crear índices
                cls.db.users.create_index("email", unique=True, sparse=True)
                cls.db.users.create_index("api_key", unique=True)
                cls.db.users.create_index("google_id", unique=True, sparse=True)
                print("✓ MongoDB conectado y configurado correctamente")
            except Exception as e:
                print(f"X Error conectando a MongoDB: {e}")
                print(f"X Tipo de error: {type(e).__name__}")
                raise

db = Database
