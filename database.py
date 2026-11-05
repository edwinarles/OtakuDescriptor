from pymongo import MongoClient
from config import Config

class Database:
    client = None
    db = None

    @classmethod
    def init_db(cls):
        if not cls.client:
            print("[INFO] Conectando a MongoDB Atlas...")
            try:
                # Conectar con timeout de 10 segundos
                cls.client = MongoClient(
                    Config.MONGO_URI,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )
                
                # Verificar conexión
                cls.client.admin.command('ping')
                print("[OK] Ping exitoso a MongoDB Atlas")
                
                cls.db = cls.client[Config.DB_NAME]
                
                # Crear índices
                cls.db.users.create_index("email", unique=True, sparse=True)
                cls.db.users.create_index("api_key", unique=True)
                cls.db.users.create_index("google_id", unique=True, sparse=True)
                print("[OK] MongoDB conectado y configurado correctamente")
            except Exception as e:
                print(f"[AVISO] No se pudo conectar inmediatamente a MongoDB ({e}). El servidor continuara iniciando.")

db = Database
