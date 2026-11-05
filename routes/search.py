from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import numpy as np
import hashlib
import openai
from openai import OpenAI

from database import db
from search_system import SearchEngine
from utils import normalizar_texto, limpiar_html
from config import Config

search_bp = Blueprint('search', __name__)

def get_openai_client():
    if not Config.OPENAI_API_KEY:
        return None
    try:
        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None

@search_bp.route('/search', methods=['POST'])
def search_semantic():
    if db.db is None:
        return jsonify({
            'error': 'Base de datos no disponible',
            'message': 'No se pudo conectar con MongoDB Atlas. Revisa la variable MONGO_URI y la lista de IPs permitidas (0.0.0.0/0 en Atlas).'
        }), 503

    api_key = request.headers.get('X-API-Key')
    
    # Support for anonymous users OR invalid API key
    if not api_key:
        session_data = f"{request.remote_addr}:{request.headers.get('User-Agent', '')}"
        session_id = hashlib.sha256(session_data.encode()).hexdigest()
        
        # Count anonymous searches in the last day
        one_day_ago = datetime.now() - timedelta(days=1)
        anonymous_count = db.db.anonymous_searches.count_documents({
            'session_id': session_id,
            'timestamp': {'$gt': one_day_ago}
        })
        
        if anonymous_count >= 10:
            return jsonify({
                'error': 'Anonymous limit reached',
                'message': 'You have used your 10 free searches today. Register to get more or wait for the daily refresh.',
                'limit': 10,
                'used': anonymous_count,
                'is_anonymous': True,
                'require_register': True
            }), 429
        
        is_premium = False
        limit = 10
        count = anonymous_count
        search_key = session_id
        is_anonymous = True
    else:
        user = db.db.users.find_one({'api_key': api_key})
        
        if not user:
            session_data = f"{request.remote_addr}:{request.headers.get('User-Agent', '')}"
            session_id = hashlib.sha256(session_data.encode()).hexdigest()
            
            one_day_ago = datetime.now() - timedelta(days=1)
            anonymous_count = db.db.anonymous_searches.count_documents({
                'session_id': session_id,
                'timestamp': {'$gt': one_day_ago}
            })
            
            if anonymous_count >= 10:
                return jsonify({
                    'error': 'Anonymous limit reached',
                    'message': 'Your API key is invalid. You have used your 10 free searches today. Register to get a new API key.',
                    'limit': 10,
                    'used': anonymous_count,
                    'is_anonymous': True,
                    'require_register': True,
                    'invalid_api_key': True
                }), 429
            
            is_premium = False
            limit = 10
            count = anonymous_count
            search_key = session_id
            is_anonymous = True
        else:
            is_premium = user.get('is_premium', False)
            limit = Config.PREMIUM_HOURLY_LIMIT if is_premium else Config.FREE_DAILY_LIMIT
            
            if is_premium:
                time_ago = datetime.now() - timedelta(hours=1)
            else:
                time_ago = datetime.now() - timedelta(days=1)
            
            count = db.db.searches.count_documents({
                'api_key': api_key,
                'timestamp': {'$gt': time_ago}
            })
            
            if count >= limit:
                return jsonify({'error': 'Limit reached', 'limit': limit, 'used': count}), 429
            
            search_key = api_key
            is_anonymous = False
        
    data = request.get_json(force=True)
    query = data.get('query', '')
    top_k = data.get('top_k', 10)
    rerank_requested = data.get('rerank', None)
    rerank = getattr(Config, 'ENABLE_RERANKING', True) if rerank_requested is None else bool(rerank_requested)
    
    # Process
    MAX_QUERY_LENGTH = 250
    if len(query) > MAX_QUERY_LENGTH:
        return jsonify({
            'error': f'Query too long. Maximum {MAX_QUERY_LENGTH} characters allowed.'
        }), 400

    # 1. Obtener cliente OpenAI y generar embeddings
    client = get_openai_client()
    if not client:
        return jsonify({
            'error': 'OpenAI API key not configured',
            'message': 'Por favor configura OPENAI_API_KEY en las variables de entorno de Render.'
        }), 503

    try:
        resp = client.embeddings.create(
            model=Config.EMBEDDING_MODEL,
            input=normalizar_texto(query)
        )
        vector = resp.data[0].embedding
    except openai.RateLimitError as e:
        error_details = str(e)
        print(f"[ERROR] OpenAI Quota / RateLimit: {error_details}")
        return jsonify({
            'error': 'Cuota de OpenAI agotada (insufficient_quota). Recarga saldo en platform.openai.com/billing.',
            'message': 'Tu cuenta de OpenAI se ha quedado sin saldo o creditos. Recarga saldo en https://platform.openai.com/billing para habilitar las busquedas semanticas.',
            'details': error_details
        }), 500
    except openai.AuthenticationError as e:
        error_details = str(e)
        print(f"[ERROR] OpenAI Authentication Error: {error_details}")
        return jsonify({
            'error': 'Clave OPENAI_API_KEY invalida en Render',
            'message': 'La API key configurada en Render no es valida o fue revocada por OpenAI. Revisa tus variables de entorno.',
            'details': error_details
        }), 500
    except openai.OpenAIError as e:
        error_details = str(e)
        print(f"[ERROR] OpenAI API Error: {error_details}")
        return jsonify({
            'error': f'Error en el servicio de OpenAI: {error_details}',
            'details': error_details
        }), 500
    except Exception as e:
        error_details = str(e)
        print(f"[ERROR] Error inesperado en embeddings: {error_details}")
        return jsonify({
            'error': f'Error al procesar vector de busqueda: {error_details}',
            'details': error_details
        }), 500

    # 2. Búsqueda vectorial + Re-ranking Cross-Encoder
    try:
        results = SearchEngine.search(
            vector=vector,
            top_k=top_k,
            query_text=query,
            rerank=rerank
        )
    except Exception as e:
        print(f"[ERROR] SearchEngine.search Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Error ejecutando busqueda: {str(e)}',
            'details': str(e)
        }), 500

    # 3. Registrar búsqueda en base de datos
    try:
        if is_anonymous:
            print(f"[INFO] ANONYMOUS SEARCH - Logging search for session_id: {search_key[:16]}... | Query: '{query}'")
            db.db.anonymous_searches.insert_one({
                'session_id': search_key,
                'query': query,
                'timestamp': datetime.now()
            })
            one_day_ago = datetime.now() - timedelta(days=1)
            count = db.db.anonymous_searches.count_documents({
                'session_id': search_key,
                'timestamp': {'$gt': one_day_ago}
            })
            print(f"[INFO] ANONYMOUS COUNT AFTER SEARCH: {count}/{limit}")
        else:
            db.db.searches.insert_one({
                'api_key': search_key,
                'query': query,
                'timestamp': datetime.now()
            })
            time_ago = datetime.now() - timedelta(hours=1) if is_premium else datetime.now() - timedelta(days=1)
            count = db.db.searches.count_documents({
                'api_key': search_key,
                'timestamp': {'$gt': time_ago}
            })
    except Exception as e:
        print(f"[AVISO] No se pudo registrar la busqueda en BD: {e}")
        count = count + 1

    remaining = max(0, limit - count)

    return jsonify({
        'results': results,
        'searches_remaining': remaining,
        'is_premium': is_premium,
        'is_anonymous': is_anonymous,
        'search_mode': 'vector + cross-encoder rerank' if any(r.get('reranked') for r in results) else 'embeddings'
    })

@search_bp.route('/animes', methods=['GET'])
def get_all():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)
    
    skip = (page - 1) * per_page
    
    try:
        if db.db is None:
            return jsonify({'animes': [], 'total': 0, 'page': page})
            
        total = db.db.animes.count_documents({})
        cursor = db.db.animes.find({}, {'embedding': 0}).skip(skip).limit(per_page)
        animes = []
        for anime in cursor:
            if '_id' in anime:
                anime['_id'] = str(anime['_id'])
            anime['description_clean'] = limpiar_html(anime.get('description', ''))
            animes.append(anime)
            
        return jsonify({
            'animes': animes,
            'total': total,
            'page': page
        })
    except Exception as e:
        print(f"[ERROR] Error en get_all: {e}")
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

@search_bp.route('/anime/<int:anime_id>', methods=['GET'])
def get_one(anime_id):
    anime = SearchEngine.get_by_id(anime_id)
    if anime:
        return jsonify(anime)
    return jsonify({'error': 'Not found'}), 404
