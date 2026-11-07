import os
import json
import numpy as np
import faiss
from config import Config
from utils import normalizar_texto, limpiar_html
from database import Database, db

class SearchEngine:
    ids = []  # Lista de IDs que corresponde índice por índice con FAISS
    index = None
    dim = 0

    @classmethod
    def load_data(cls):
        print("[INFO] Inicializando motor de busqueda...")
        try:
            Database.init_db()
            
            if db.db is None:
                print("[AVISO] Base de datos no disponible todavia. FAISS se inicializara cuando este lista.")
                return

            # 1. Cargar SOLO los IDs de los animes que tienen embeddings
            cursor = db.db.animes.find(
                {"embedding": {"$exists": True}},
                {"id": 1} 
            ).sort("id", 1)
            
            cls.ids = [doc['id'] for doc in cursor if 'id' in doc]
            
            if not cls.ids:
                print("[INFO] No se encontraron animes con embeddings en MongoDB.")
                return

            # 2. Cargar embeddings (FAISS)
            if not os.path.exists("embeddings.npy"):
                print("[AVISO] 'embeddings.npy' no existe. Ejecuta generate_embeddings.py.")
                return

            embeddings = np.load("embeddings.npy")
            
            # NORMALIZAR los embeddings para usar Inner Product como similitud coseno
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
            
            cls.dim = embeddings.shape[1]
            
            # Verificación de consistencia
            if len(cls.ids) != embeddings.shape[0]:
                print(f"[AVISO] Discrepancia entre IDs en DB ({len(cls.ids)}) y embeddings ({embeddings.shape[0]}).")
                min_len = min(len(cls.ids), embeddings.shape[0])
                cls.ids = cls.ids[:min_len]
                embeddings = embeddings[:min_len]
            
            # Crear índice FAISS con INNER PRODUCT (similitud coseno)
            cls.index = faiss.IndexFlatIP(cls.dim)
            cls.index.add(embeddings.astype('float32'))
            print(f"[OK] Motor de busqueda listo. Indice contiene {len(cls.ids)} vectores usando similitud coseno.")
            
        except Exception as e:
            print(f"[AVISO] Error cargando motor de busqueda: {e}")

    @classmethod
    def rerank_with_llm(cls, query_text, candidates, top_k):
        """
        Re-ranking semantico de alta precision usando Cross-Attention via LLM (gpt-4o-mini).
        Consumo de memoria RAM en el servidor: 0 MiB (ideal para el plan de 512MB de Render).
        """
        if not candidates or not Config.OPENAI_API_KEY:
            for a in candidates:
                a['reranked'] = False
            return candidates[:top_k]

        try:
            from openai import OpenAI
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            
            # Pool configurable (por defecto 30 candidatos para no perder animes en la primera etapa)
            pool_size = getattr(Config, 'RERANK_CANDIDATES', 30)
            pool = candidates[:min(len(candidates), pool_size)]
            
            items_desc = []
            for idx, a in enumerate(pool):
                title = a.get('main_title') or a.get('title') or 'Sin titulo'
                # Extraemos hasta 750 caracteres para preservar giros de trama y detalles clave
                raw_desc = limpiar_html(a.get('description', ''))
                desc = raw_desc[:750].strip()
                genres = ', '.join(str(g) for g in a.get('genres', [])[:3])
                vibe = a.get('vibe_check', '')
                items_desc.append(f"[{idx+1}] ID:{a['id']} | Titulo: {title} | Generos: {genres} | Vibe: {vibe}\nSinopsis: {desc}")

            prompt = f"""Actúa como un experto sistema de Re-ranking semántico (Cross-Encoder) para búsqueda de anime por descripción de trama.
Consulta del usuario:
"{query_text}"

A continuación se presentan los candidatos recuperados por búsqueda vectorial.
Analiza cuidadosamente la sinopsis de cada uno para identificar coincidencias narrativas específicas (elementos de trama, objetos clave, hechos o giros argumentales como comerse un dedo de un demonio, hechicería, maldiciones, etc.):

{chr(10).join(items_desc)}

Ordena los candidatos del más relevante al menos relevante con respecto a la consulta del usuario.
Si algún anime coincide exactamente con la trama descrita, colócalo en el puesto #1.
Responde ÚNICAMENTE en formato JSON con la lista ordenada de números de opción:
{{"ranking": [<numero_opcion_1>, <numero_opcion_2>, ...]}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Responde exclusivamente en formato JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=350,
                response_format={"type": "json_object"}
            )
            
            content = json.loads(response.choices[0].message.content)
            raw_list = content.get("ranking") or content.get("ranked_indices") or content.get("ranked_ids") or []
            
            cand_by_id = {str(a['id']): a for a in pool}
            reranked = []
            seen_ids = set()

            for rank_idx, item in enumerate(raw_list):
                anime = None
                # Si el LLM devolvió el número de opción (1 a len(pool))
                if isinstance(item, int) and 1 <= item <= len(pool):
                    candidate = pool[item - 1]
                    if candidate['id'] not in seen_ids:
                        anime = candidate
                # Si el LLM devolvió el ID real de la base de datos
                elif str(item) in cand_by_id:
                    candidate = cand_by_id[str(item)]
                    if candidate['id'] not in seen_ids:
                        anime = candidate

                if anime:
                    anime['reranked'] = True
                    anime['similarity_score'] = round(max(99.0 - (rank_idx * 2.5), 60.0), 2)
                    reranked.append(anime)
                    seen_ids.add(anime['id'])

            # Agregar candidatos restantes de pool manteniendo orden
            for a in pool:
                if a['id'] not in seen_ids:
                    a['reranked'] = False
                    reranked.append(a)
                    seen_ids.add(a['id'])

            return reranked[:top_k]
                
        except Exception as e:
            print(f"[AVISO] Fallo re-ranking LLM ({e}). Se mantiene orden por similitud coseno.")
            
        for a in candidates:
            a['reranked'] = False
        return candidates[:top_k]

    @classmethod
    def search(cls, vector, top_k=10, query_text=None, rerank=None):
        if not cls.index or not cls.ids:
            return []

        if db.db is None:
            print("[AVISO] Base de datos no disponible durante SearchEngine.search")
            return []

        # Determinar si se debe aplicar re-ranking
        enable_rerank = getattr(Config, 'ENABLE_RERANKING', True) if rerank is None else bool(rerank)
        should_rerank = bool(enable_rerank and query_text)

        # Si se usa re-ranking, recuperamos un grupo mas amplio de candidatos en la primera etapa
        if should_rerank:
            min_candidates = getattr(Config, 'RERANK_CANDIDATES', 30)
            initial_k = max(int(top_k) * 2, min_candidates)
            search_k = max(1, min(initial_k, len(cls.ids)))
        else:
            search_k = max(1, min(int(top_k), len(cls.ids)))

        # Normalizar el vector de búsqueda (Inner Product = Similitud Coseno)
        vector = np.array([vector], dtype="float32")
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        # D contiene las similitudes coseno (más alto = más similar)
        D, I = cls.index.search(vector, k=search_k)

        found_indices = I[0]
        similarities = D[0]

        target_ids = []
        score_map = {}

        for similarity, idx in zip(similarities, found_indices):
            if idx < len(cls.ids):
                anime_id = cls.ids[idx]
                target_ids.append(anime_id)
                score_map[anime_id] = float(similarity * 100)

        # Traer detalles de estos IDs desde MongoDB
        try:
            cursor = db.db.animes.find({"id": {"$in": target_ids}})
            fetched_animes = {anime['id']: anime for anime in cursor if 'id' in anime}
        except Exception as e:
            print(f"[AVISO] Error al consultar animes en MongoDB: {e}")
            fetched_animes = {}

        candidates = []
        for anime_id in target_ids:
            anime = fetched_animes.get(anime_id)
            if anime:
                if '_id' in anime:
                    anime['_id'] = str(anime['_id'])
                anime['cosine_score'] = score_map.get(anime_id, 0.0)
                anime['similarity_score'] = anime['cosine_score']
                anime['description_clean'] = limpiar_html(anime.get('description', ''))
                anime['reranked'] = False

                if 'embedding' in anime:
                    del anime['embedding']

                candidates.append(anime)

        # Etapa 2: Re-ranking si aplica
        if should_rerank and candidates:
            return cls.rerank_with_llm(query_text, candidates, top_k=int(top_k))

        return candidates[:int(top_k)]

    @classmethod
    def get_by_id(cls, anime_id):
        if db.db is None:
            return None
        try:
            query = {
                "$or": [
                    {"id": anime_id},
                    {"idMal": anime_id}
                ]
            }
            anime = db.db.animes.find_one(query)

            if anime:
                if '_id' in anime:
                    anime['_id'] = str(anime['_id'])
                if 'embedding' in anime:
                    del anime['embedding']
                anime['description_clean'] = limpiar_html(anime.get('description', ''))
                return anime
        except Exception as e:
            print(f"[AVISO] Error en get_by_id: {e}")

        return None
