from pymongo import MongoClient
from config import Config

class Database:
    client = None
    db = None

    @classmethod
    def init_db(cls):
        if not cls.client:
            print(f"🔌 Conectando a MongoDB: {Config.MONGO_URI}")
            try:
                cls.client = MongoClient(Config.MONGO_URI)
                cls.db = cls.client[Config.DB_NAME]
                
                # Crear índices
                cls.db.users.create_index("email", unique=True, sparse=True)
                cls.db.users.create_index("api_key", unique=True)
                cls.db.users.create_index("google_id", unique=True, sparse=True)
                print("✅ MongoDB conectado y configurado")
            except Exception as e:
                print(f"❌ Error conectando a MongoDB: {e}")

db = Database
