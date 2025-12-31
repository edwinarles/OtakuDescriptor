from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from database import db
from search_engine import SearchEngine

# Blueprints (Planos de rutas)
from routes.auth import auth_bp
from routes.payment import payment_bp
from routes.search import search_bp

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)
CORS(app, supports_credentials=True)

# Inicialización
db.init_db()
SearchEngine.load_data()

# Registro de rutas
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(search_bp, url_prefix='/api')

# Rutas estáticas
@app.route('/')
def home():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/payment-success')
def payment_success():
    return send_from_directory(app.static_folder, 'payment-success.html')

@app.route('/payment-cancel')
def payment_cancel():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    # Render proporciona el puerto en la variable de entorno PORT
    import os
    port = int(os.environ.get('PORT', 5000))
    
    # En producción, Render usa Gunicorn, este código solo se ejecuta en desarrollo local
    app.run(
        host='0.0.0.0',
        port=port,
        debug=(Config.ENV == 'development')
    )
