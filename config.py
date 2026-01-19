import os
from dotenv import load_dotenv

# Load environment variables (.env must be in the root directory)
load_dotenv()

class Config:
    # Application
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_secret')
    PORT = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('FLASK_ENV', 'production')
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')  # For CORS
    
    # MongoDB Atlas
    # MONGO_URI format for Atlas:
    # mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<db_name>?retryWrites=true&w=majority
    # Example: mongodb+srv://user:password123@cluster0.xxxxx.mongodb.net/AnimeDescriptor?retryWrites=true&w=majority
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://localhost:27017/AnimeDescriptor')
    DB_NAME = os.environ.get('DB_NAME', 'AnimeDescriptor')
    
    # OpenAI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-large"
    
    # PayPal
    PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET")
    PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
    PAYPAL_API = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"
    PREMIUM_PRICE = os.environ.get("PREMIUM_PRICE", "3.00")
    
    # Email (SMTP)
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USERNAME)
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

    # Search Limits (per day)
    FREE_DAILY_LIMIT = 10
    PREMIUM_DAILY_LIMIT = 200
    
    # Legacy names for backward compatibility
    FREE_HOURLY_LIMIT = FREE_DAILY_LIMIT
    PREMIUM_HOURLY_LIMIT = PREMIUM_DAILY_LIMIT
