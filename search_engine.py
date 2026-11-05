import os
import json

# Prevenir conflicto de OpenMP y DLLs entre PyTorch, pyarrow y FAISS en Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Importar pyarrow y sentence_transformers antes de FAISS para compatibilidad de memoria C en Windows
try:
    import pyarrow
    from sentence_transformers import CrossEncoder
except Exception:
    CrossEncoder = None

import numpy as np
import faiss
from config import Config
from utils import normalizar_texto, limpiar_html
from database import Database, db

class SearchEngine:
    ids = []  # Lista de IDs que corresponde índice por índice con FAISS
    index = None
    dim = 0
    cross_encoder = None
    cross_encoder_loaded = False

    @classmethod
    def load_cross_encoder(cls):
        """Inicializa el modelo Cross-Encoder para re-ranking semantico de alta precision"""
        if cls.cross_encoder_loaded:
            return cls.cross_encoder

        enable_reranking = getattr(Config, 'ENABLE_RERANKING', True)
        if not enable_reranking:
            print("[INFO] Re-ranking con Cross-Encoder desactivado en configuracion.")
            cls.cross_encoder_loaded = True
            return None

        model_name = getattr(Config, 'CROSS_ENCODER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        device = getattr(Config, 'CROSS_ENCODER_DEVICE', 'cpu')

        print(f"Cargando modelo Cross-Encoder '{model_name}' en {device}...")
        try:
            if CrossEncoder is None:
                from sentence_transformers import CrossEncoder as CE
                cls.cross_encoder = CE(model_name, device=device)
            else:
                cls.cross_encoder = CrossEncoder(model_name, device=device)
            cls.cross_encoder_loaded = True
            print(f"[OK] Cross-Encoder '{model_name}' listo para re-ranking.")
            return cls.cross_encoder
        except Exception as e:
            print(f"[AVISO] No se pudo cargar Cross-Encoder ({e}). Se continuara con similitud coseno.")
            cls.cross_encoder = None
            cls.cross_encoder_loaded = True
            return None

    @classmethod
    def load_data(cls):
        print("Inicializando motor de busqueda (conectado a MongoDB)...")
        try:
            Database.init_db()
            
            # 1. Cargar SOLO los IDs de los animes que tienen embeddings
            cursor = db.db.animes.find(
                {"embedding": {"$exists": True}},
                {"id": 1} 
            ).sort("id", 1)
            
            cls.ids = [doc['id'] for doc in cursor]
            
            if not cls.ids:
                print("! No se encontraron animes con embeddings en MongoDB.")
                return

            # 2. Cargar embeddings (FAISS)
            if not os.path.exists("embeddings.npy"):
                print("ERROR: 'embeddings.npy' no existe. Ejecuta generate_embeddings.py primero.")
                return

            embeddings = np.load("embeddings.npy")
            
            # NORMALIZAR los embeddings para usar Inner Product como similitud coseno
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
            
            cls.dim = embeddings.shape[1]
            
            # Verificación de consistencia
            if len(cls.ids) != embeddings.shape[0]:
                print(f"! ADVERTENCIA: Discrepancia entre IDs en DB ({len(cls.ids)}) y embeddings ({embeddings.shape[0]}).")
                min_len = min(len(cls.ids), embeddings.shape[0])
                cls.ids = cls.ids[:min_len]
                embeddings = embeddings[:min_len]
            
            # Crear índice FAISS con INNER PRODUCT (similitud coseno con vectores normalizados)
            print("Creando indice FAISS con similitud coseno...")
            cls.index = faiss.IndexFlatIP(cls.dim)  # IP = Inner Product
            cls.index.add(embeddings.astype('float32'))
            print(f"[OK] Motor de busqueda listo. Indice contiene {len(cls.ids)} vectores usando cosine similarity.")

            # 3. Precargar el Cross-Encoder para que las búsquedas no tengan latencia de arranque en frío
            cls.load_cross_encoder()
            
        except Exception as e:
            print(f"X Error cargando motor de busqueda: {e}")

    @classmethod
    def build_anime_text_for_rerank(cls, anime):
        """
        Construye una representación textual enriquecida del anime para alimentar el Cross-Encoder.
        Prioriza título, géneros, keywords culturales/memes, vibe check, world lore y sinopsis.
        """
        parts = []

        title = anime.get('main_title') or anime.get('title') or ''
        if title:
            parts.append(f"Title: {title}")

        genres = anime.get('genres')
        if isinstance(genres, list) and genres:
            parts.append(f"Genres: {', '.join(str(g) for g in genres[:6])}")

        keywords = anime.get('vibe_keywords')
        if isinstance(keywords, list) and keywords:
            parts.append(f"Keywords: {', '.join(str(k) for k in keywords[:8])}")
        elif isinstance(keywords, str) and keywords:
            parts.append(f"Keywords: {keywords}")

        vibe = anime.get('vibe_check')
        if vibe:
            parts.append(f"Vibe: {vibe}")

        lore = anime.get('world_lore')
        if lore:
            parts.append(f"Lore: {lore}")

        enhanced = anime.get('enhanced_description')
        if enhanced:
            parts.append(f"Synopsis: {enhanced[:600]}")
        else:
            desc = anime.get('description_clean') or anime.get('description') or ''
            clean_desc = limpiar_html(desc)
            if clean_desc:
                parts.append(f"Synopsis: {clean_desc[:600]}")

        return " | ".join(parts) if parts else (title or "Anime")

    @classmethod
    def rerank_candidates(cls, query_text, candidates, top_k):
        """
        Aplica re-ranking usando el Cross-Encoder a los candidatos recuperados por similitud coseno.
        """
        if not candidates:
            return []

        # Asegurar que el Cross-Encoder esté inicializado
        encoder = cls.load_cross_encoder()
        if encoder is None:
            # Fallback a ranking por similitud coseno
            for anime in candidates:
                anime['similarity_score'] = anime.get('cosine_score', 0.0)
                anime['reranked'] = False
            return candidates[:top_k]

        try:
            # Preparar pares (query, documento)
            pairs = [(query_text, cls.build_anime_text_for_rerank(anime)) for anime in candidates]
            
            # Predicción con el Cross-Encoder
            raw_scores = encoder.predict(pairs)

            for anime, raw_score in zip(candidates, raw_scores):
                s = float(raw_score)
                anime['cross_encoder_score'] = round(s, 4)
                # Calibración del score a porcentaje 0-100 usando la función sigmoide
                sigmoid_val = 1.0 / (1.0 + np.exp(-s))
                anime['similarity_score'] = round(float(sigmoid_val * 100.0), 2)
                anime['reranked'] = True

            # Ordenar candidatos de mayor a menor relevancia según el Cross-Encoder
            candidates.sort(key=lambda a: a['cross_encoder_score'], reverse=True)
            return candidates[:top_k]

        except Exception as e:
            print(f"[AVISO] Error durante el re-ranking con Cross-Encoder: {e}. Fallback a similitud coseno.")
            for anime in candidates:
                anime['similarity_score'] = anime.get('cosine_score', 0.0)
                anime['reranked'] = False
            return candidates[:top_k]

    @classmethod
    def search(cls, vector, top_k=10, query_text=None, rerank=None):
        if not cls.index or not cls.ids:
            return []

        # Determinar si se debe aplicar re-ranking
        enable_rerank = getattr(Config, 'ENABLE_RERANKING', True) if rerank is None else bool(rerank)
        should_rerank = bool(enable_rerank and query_text)

        # Si se usa re-ranking, recuperamos un grupo más amplio de candidatos en la primera etapa
        if should_rerank:
            min_candidates = getattr(Config, 'RERANK_CANDIDATES', 30)
            initial_k = max(int(top_k) * 3, min_candidates)
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
                # Score de coseno entre 0 y 100
                score_map[anime_id] = float(similarity * 100)

        # Traer detalles de estos IDs desde MongoDB
        cursor = db.db.animes.find({"id": {"$in": target_ids}})
        fetched_animes = {anime['id']: anime for anime in cursor}

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

        # Etapa 2: Re-ranking con Cross-Encoder si aplica
        if should_rerank:
            return cls.rerank_candidates(query_text, candidates, top_k=int(top_k))

        return candidates[:int(top_k)]

    @classmethod
    def get_by_id(cls, anime_id):
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
            print(f"Error en get_by_id: {e}")
            pass

        return None
