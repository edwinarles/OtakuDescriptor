from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets

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
    """Registro con contraseña - cuenta creada SOLO después de verificar email"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Verificar si el email ya tiene una cuenta ACTIVA
    existing_user = db.db.users.find_one({'email': email})
    if existing_user:
        print(f"⚠️ Intento de registro con email existente: {email}")
        return jsonify({'error': 'Email already registered'}), 409
    
    # Verificar si ya hay un registro pendiente
    pending = db.db.pending_registrations.find_one({'email': email})
    if pending:
        # Ya existe un registro pendiente, enviar email nuevamente
        print(f"⚠️ Registro pendiente existente para: {email}, reenviando email")
        from services.email_service import send_verification_email
        send_verification_email(email, pending['verification_token'], request.host_url)
        return jsonify({
            'message': 'A verification email has already been sent. Please check your inbox.',
            'require_email_verification': True
        }), 200
        
    # Generar token de verificación y hash de contraseña
    hashed = generate_password_hash(password)
    verification_token = secrets.token_urlsafe(32)
    
    # Guardar en colección TEMPORAL de registros pendientes
    # NO se crea el usuario todavía
    db.db.pending_registrations.insert_one({
        'email': email,
        'password_hash': hashed,
        'verification_token': verification_token,
        'token_expires': datetime.now() + timedelta(hours=24),
        'created_at': datetime.now()
    })
    
    # Enviar email de verificación
    from services.email_service import send_verification_email
    email_sent = send_verification_email(email, verification_token, request.host_url)
    
    if email_sent:
        print(f"✅ Registro pendiente creado: {email}")
        return jsonify({
            'message': 'Registration initiated. Please check your email to complete registration.',
            'require_email_verification': True
        }), 201
    else:
        # Si falla el email, eliminar el registro pendiente
        db.db.pending_registrations.delete_one({'email': email})
        print(f"⚠️ Email de verificación falló, registro pendiente eliminado: {email}")
        return jsonify({
            'error': 'Failed to send verification email. Please try again later.'
        }), 500


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


@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """Verificar email con token y CREAR la cuenta"""
    token = request.args.get('token')
    
    if not token:
        return jsonify({'error': 'Verification token required'}), 400
    
    # Buscar en registros PENDIENTES
    pending_user = db.db.pending_registrations.find_one({'verification_token': token})
    
    if not pending_user:
        return jsonify({'error': 'Invalid verification token'}), 404
    
    # Verificar que el token no haya expirado
    if pending_user.get('token_expires') and datetime.now() > pending_user['token_expires']:
        # Eliminar registro pendiente expirado
        db.db.pending_registrations.delete_one({'_id': pending_user['_id']})
        return jsonify({'error': 'Verification token has expired. Please register again.'}), 410
    
    # CREAR el usuario AHORA (antes no existía)
    new_key = generate_api_key()
    db.db.users.insert_one({
        'email': pending_user['email'],
        'password_hash': pending_user['password_hash'],
        'api_key': new_key,
        'is_premium': False,
        'email_verified': True,  # Ya verificado
        'created_at': datetime.now()
    })
    
    # Eliminar de registros pendientes
    db.db.pending_registrations.delete_one({'_id': pending_user['_id']})
    
    print(f"✅ Cuenta creada y email verificado para: {pending_user.get('email')}")
    
    # Redirigir a la página principal con API key para auto-login
    from flask import redirect
    return redirect(f"/?api_key={new_key}&verified=true")


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
