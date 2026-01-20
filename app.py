from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from database import db
from search_system import SearchEngine
import os

# Blueprints (Planos de rutas)
from routes.auth import auth_bp
from routes.payment import payment_bp
from routes.search import search_bp

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)

# CORS configuration for production (Render) and development
# Get allowed origins from environment variable or use defaults
allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')

CORS(app, 
     resources={r"/api/*": {"origins": allowed_origins}},
     supports_credentials=True,
     allow_headers=['Content-Type', 'X-API-Key', 'Authorization'],
     expose_headers=['Content-Type'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
)

# Inicialización
db.init_db()
SearchEngine.load_data()

# Registro de rutas
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(search_bp, url_prefix='/api')

# Global error handlers to prevent HTML 500 errors
@app.errorhandler(500)
def internal_error(error):
    """Handle all 500 errors with JSON response"""
    from flask import jsonify
    print(f"❌ 500 ERROR HANDLER TRIGGERED: {error}")
    return jsonify({
        'error': 'Internal server error',
        'details': str(error)
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Catch-all handler for unhandled exceptions"""
    from flask import jsonify
    import traceback
    print(f"❌ UNHANDLED EXCEPTION: {type(error).__name__}")
    print(f"   Details: {error}")
    traceback.print_exc()
    return jsonify({
        'error': 'Unexpected server error',
        'type': type(error).__name__,
        'details': str(error)
    }), 500

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

@app.route('/favicon.ico')
def favicon():
    """Return empty response for favicon to prevent 404 errors"""
    from flask import Response
    return Response(status=204)

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