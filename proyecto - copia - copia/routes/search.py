from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import numpy as np
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
    if not api_key: return jsonify({'error': 'API key required'}), 401
    
    user = db.db.users.find_one({'api_key': api_key})
    if not user: return jsonify({'error': 'Invalid API key'}), 401
    
    # Lógica de límites
    is_premium = user.get('is_premium', False)
    limit = Config.PREMIUM_DAILY_LIMIT if is_premium else Config.FREE_DAILY_LIMIT
    
    yesterday = datetime.now() - timedelta(days=1)
    count = db.db.searches.count_documents({
        'api_key': api_key,
        'timestamp': {'$gt': yesterday}
    })
    
    if count >= limit:
        return jsonify({'error': 'Limit reached', 'limit': limit, 'used': count}), 429
        
    data = request.get_json(force=True)
    query = data.get('query', '')
    top_k = data.get('top_k', 10)
    
    # Procesar
    if len(query) > 155: return jsonify({'error': 'Query too long'}), 400
    
    # Registrar Búsqueda
    db.db.searches.insert_one({
        'api_key': api_key,
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
            'is_premium': is_premium
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
