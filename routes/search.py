from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import numpy as np
import hashlib
from openai import OpenAI

from database import db
from search_engine import SearchEngine
from utils import normalizar_texto, limpiar_html
from config import Config

search_bp = Blueprint('search', __name__)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

@search_bp.route('/search', methods=['POST'])
def search_semantic():
    api_key = request.headers.get('X-API-Key')
    
    # Soporte para usuarios anónimos O API key inválida
    if not api_key:
        # Crear identificador de sesión basado en IP y user-agent
        session_data = f"{request.remote_addr}:{request.headers.get('User-Agent', '')}"
        session_id = hashlib.sha256(session_data.encode()).hexdigest()
        
        # Contar búsquedas anónimas (sin límite de tiempo - 10 búsquedas en total)
        anonymous_count = db.db.anonymous_searches.count_documents({
            'session_id': session_id
        })
        
        if anonymous_count >= 10:
            return jsonify({
                'error': 'Anonymous limit reached',
                'message': 'Has usado tus 10 búsquedas gratuitas. Regístrate para comprar Premium y obtener búsquedas ilimitadas.',
                'limit': 10,
                'used': anonymous_count,
                'is_anonymous': True,
                'require_register': True
            }), 429
        
        # Continuar con búsqueda anónima
        is_premium = False
        limit = 10
        count = anonymous_count
        search_key = session_id
        is_anonymous = True
    else:
        # Usuario registrado - verificar si la API key es válida
        user = db.db.users.find_one({'api_key': api_key})
        
        # Si la API key es inválida, tratar como usuario anónimo en lugar de devolver error
        if not user:
            session_data = f"{request.remote_addr}:{request.headers.get('User-Agent', '')}"
            session_id = hashlib.sha256(session_data.encode()).hexdigest()
            
            anonymous_count = db.db.anonymous_searches.count_documents({
                'session_id': session_id
            })
            
            if anonymous_count >= 10:
                return jsonify({
                    'error': 'Anonymous limit reached',
                    'message': 'Tu API key es inválida. Has usado tus 10 búsquedas gratuitas. Regístrate para obtener una nueva API key.',
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
            # API key válida - lógica de límites normal
            is_premium = user.get('is_premium', False)
            limit = Config.PREMIUM_DAILY_LIMIT if is_premium else Config.FREE_DAILY_LIMIT
            
            yesterday = datetime.now() - timedelta(days=1)
            count = db.db.searches.count_documents({
                'api_key': api_key,
                'timestamp': {'$gt': yesterday}
            })
            
            if count >= limit:
                return jsonify({'error': 'Limit reached', 'limit': limit, 'used': count}), 429
            
            search_key = api_key
            is_anonymous = False
        
    data = request.get_json(force=True)
    query = data.get('query', '')
    top_k = data.get('top_k', 10)
    
    # Procesar
    if len(query) > 155: return jsonify({'error': 'Query too long'}), 400
    
    # Registrar Búsqueda
    if is_anonymous:
        db.db.anonymous_searches.insert_one({
            'session_id': search_key,
            'query': query,
            'timestamp': datetime.now()
        })
    else:
        db.db.searches.insert_one({
            'api_key': search_key,
            'query': query,
            'timestamp': datetime.now()
        })
    
    # Embedding
    try:
        resp = client.embeddings.create(
            model=Config.EMBEDDING_MODEL,
            input=normalizar_texto(query)
        )
        vector = resp.data[0].embedding
        
        results = SearchEngine.search(vector, top_k)
        
        return jsonify({
            'results': results,
            'searches_remaining': limit - count - 1,
            'is_premium': is_premium,
            'is_anonymous': is_anonymous
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return jsonify({'error': 'Search failed'}), 500

@search_bp.route('/animes', methods=['GET'])
def get_all():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)
    
    skip = (page - 1) * per_page
    
    try:
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
        print(f"Error en get_all: {e}")
        return jsonify({'error': 'Database error'}), 500

@search_bp.route('/anime/<int:anime_id>', methods=['GET'])
def get_one(anime_id):
    anime = SearchEngine.get_by_id(anime_id)
    if anime: return jsonify(anime)
    return jsonify({'error': 'Not found'}), 404
