from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import requests

from database import db
from utils import generate_api_key
from services.email_service import send_login_email, send_reset_password_email
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Registro tradicional (Email/Key) o Login 'Magic Link' simple"""
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        # Anónimo
        new_key = generate_api_key()
        try:
            db.db.users.insert_one({
                'api_key': new_key,
                'is_premium': False,
                'created_at': datetime.now()
            })
            return jsonify({'api_key': new_key, 'is_premium': False, 'message': 'Anonymous'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Verificar si existe
    user = db.db.users.find_one({'email': email})
    if user:
        # Magic Link Login solicitado para usuario existente
        send_login_email(email, user['api_key'], request.host_url)
        return jsonify({'message': 'Magic link sent', 'require_email_check': True})
    
    # Nuevo Usuario por Email (Magic Link Flow por defecto)
    new_key = generate_api_key()
    db.db.users.insert_one({
        'email': email,
        'api_key': new_key,
        'is_premium': False,
        'created_at': datetime.now()
    })
    send_login_email(email, new_key, request.host_url)
    return jsonify({'message': 'Magic link sent', 'require_email_check': True})


@auth_bp.route('/register-password', methods=['POST'])
def register_password():
    """Registro con contraseña"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
        
    if db.db.users.find_one({'email': email}):
        return jsonify({'error': 'Email already registered'}), 409
        
    hashed = generate_password_hash(password)
    new_key = generate_api_key()
    
    db.db.users.insert_one({
        'email': email,
        'password_hash': hashed,
        'api_key': new_key,
        'is_premium': False,
        'created_at': datetime.now()
    })
    
    return jsonify({'api_key': new_key, 'message': 'User registered successfully'})

@auth_bp.route('/login-password', methods=['POST'])
def login_password():
    """Login con contraseña"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = db.db.users.find_one({'email': email})
    if not user or 'password_hash' not in user:
        return jsonify({'error': 'Invalid credentials'}), 401
        
    if check_password_hash(user['password_hash'], password):
        return jsonify({
            'api_key': user['api_key'],
            'is_premium': user.get('is_premium', False),
            'message': 'Login successful'
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    """Google Sign-In Verify"""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
        
    # Verificar token con Google
    try:
        req = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        if req.status_code != 200:
            return jsonify({'error': 'Invalid Google Token'}), 401
            
        google_data = req.json()
        google_id = google_data['sub']
        email = google_data['email']
        
        # Verificar por google_id
        user = db.db.users.find_one({'google_id': google_id})
        if not user:
            # Verificar por email (vincular cuentas)
            user = db.db.users.find_one({'email': email})
            if user:
                # Vincular google_id
                db.db.users.update_one({'_id': user['_id']}, {'$set': {'google_id': google_id}})
            else:
                # Crear nuevo
                new_key = generate_api_key()
                user_id = db.db.users.insert_one({
                    'email': email,
                    'google_id': google_id,
                    'api_key': new_key,
                    'is_premium': False,
                    'created_at': datetime.now()
                }).inserted_id
                user = db.db.users.find_one({'_id': user_id})
        
        return jsonify({
            'api_key': user['api_key'],
            'is_premium': user.get('is_premium', False),
            'message': 'Google Login Successful'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/status', methods=['GET'])
def auth_status():
    api_key = request.headers.get('X-API-Key')
    if not api_key: return jsonify({'error': 'API key required'}), 401
    
    user = db.db.users.find_one({'api_key': api_key})
    if not user: return jsonify({'error': 'Invalid API key'}), 401
    
    # Verificar Expiración Premium
    is_premium = user.get('is_premium', False)
    if is_premium and user.get('premium_until'):
        if datetime.now() > user['premium_until']:
            db.db.users.update_one({'_id': user['_id']}, {'$set': {'is_premium': False}})
            is_premium = False
            
    # Contar Búsquedas
    yesterday = datetime.now() - timedelta(days=1)
    # Asumiendo que la colección searches tiene 'user_id' referenciando user._id o api_key
    # Usando API Key por simplicidad en el registro de búsquedas
    count = db.db.searches.count_documents({
        'api_key': api_key,
        'timestamp': {'$gt': yesterday}
    })
    
    limit = Config.PREMIUM_DAILY_LIMIT if is_premium else Config.FREE_DAILY_LIMIT
    
    return jsonify({
        'is_premium': is_premium,
        'premium_until': user.get('premium_until'),
        'daily_searches': count,
        'daily_limit': limit,
        'remaining': max(0, limit - count)
    })
