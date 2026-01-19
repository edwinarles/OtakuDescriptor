from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import numpy as np
import hashlib
from openai import OpenAI

from database import db
from search_system import SearchEngine
from utils import normalizar_texto, limpiar_html
from config import Config

search_bp = Blueprint('search', __name__)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

@search_bp.route('/search', methods=['POST'])
def search_semantic():
    api_key = request.headers.get('X-API-Key')
    
    # Support for anonymous users OR invalid API key
    if not api_key:
        # Create session ID based on IP and user-agent
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
        
        # Continue with anonymous search
        is_premium = False
        limit = 10
        count = anonymous_count
        search_key = session_id
        is_anonymous = True
    else:
        # Registered user - verify if API key is valid
        user = db.db.users.find_one({'api_key': api_key})
        
        # If API key is invalid, treat as anonymous user instead of returning error
        if not user:
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
            # Valid API key - normal limits logic
            is_premium = user.get('is_premium', False)
            limit = Config.PREMIUM_HOURLY_LIMIT if is_premium else Config.FREE_DAILY_LIMIT
            
            # Premium users: hourly reset, Free users: daily reset
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
    
    # Process
    MAX_QUERY_LENGTH = 250
    if len(query) > MAX_QUERY_LENGTH:
        return jsonify({
            'error': f'Query too long. Maximum {MAX_QUERY_LENGTH} characters allowed.'
        }), 400
    
    # Log search
    if is_anonymous:
        print(f"📝 ANONYMOUS SEARCH - Logging search for session_id: {search_key[:16]}...")
        print(f"   Query: '{query}'")
        print(f"   Timestamp: {datetime.now()}")
        db.db.anonymous_searches.insert_one({
            'session_id': search_key,
            'query': query,
            'timestamp': datetime.now()
        })
        print(f"   ✅ Search logged successfully")
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
        
        # Use pure vector search (embeddings only)
        results = SearchEngine.search(vector, top_k=top_k)
        
        # Recalculate count after logging to get accurate remaining searches
        if is_anonymous:
            one_day_ago = datetime.now() - timedelta(days=1)
            count = db.db.anonymous_searches.count_documents({
                'session_id': search_key,
                'timestamp': {'$gt': one_day_ago}
            })
            print(f"📊 ANONYMOUS COUNT AFTER SEARCH: {count}/{limit}")
        else:
            # Recalculate with same time period logic
            if is_premium:
                time_ago = datetime.now() - timedelta(hours=1)
            else:
                time_ago = datetime.now() - timedelta(days=1)
            
            count = db.db.searches.count_documents({
                'api_key': search_key,
                'timestamp': {'$gt': time_ago}
            })
        
        return jsonify({
            'results': results,
            'searches_remaining': limit - count,
            'is_premium': is_premium,
            'is_anonymous': is_anonymous,
            'search_mode': 'embeddings'  # Indicate vector search was used
        })

        
    except Exception as e:
        print(f"Search Error: {e}")
        import traceback
        traceback.print_exc()
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
