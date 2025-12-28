import os
from dotenv import load_dotenv

# Cargar variables (.env debe estar en la raíz)
load_dotenv()

class Config:
    # Aplicación
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_secret')
    PORT = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('FLASK_ENV', 'production')
    
    # MongoDB
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    DB_NAME = 'anime_search'
    
    # OpenAI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-large"
    
    # PayPal
    PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET")
    PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
    PAYPAL_API = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"
    PREMIUM_PRICE = "9.99"
    
    # Email (SMTP)
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USERNAME)
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

    # Límites
    FREE_DAILY_LIMIT = 10
    PREMIUM_DAILY_LIMIT = 1000
