import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sys
import traceback
import numpy as np

# Asegurar importaciones locales
sys.path.insert(0, os.path.abspath("."))

from config import Config
from search_system.search_engine import SearchEngine
from utils import normalizar_texto

def run_tests():
    print("=" * 60)
    print("TEST SUITE: CROSS-ENCODER RE-RANKING FOR OTAKUDESCRIPTOR")
    print("=" * 60)

    try:
        # 1. Test build_anime_text_for_rerank
        print("\n[TEST 1] Formateo de texto de anime para Cross-Encoder...")
        sample_anime = {
            'id': 101,
            'main_title': 'Steins;Gate',
            'genres': ['Sci-Fi', 'Drama', 'Suspense'],
            'vibe_keywords': ['mad scientist', 'el psy kongroo', 'd-mail'],
            'vibe_check': 'Un clasico absoluto sobre viajes en el tiempo y lineas temporales.',
            'world_lore': 'Divergencia temporal medida con el Divergence Meter en Akihabara.',
            'description': '<p>Rintaro Okabe accidentally invents a microwave that sends text messages to the past.</p>'
        }
        
        formatted_text = SearchEngine.build_anime_text_for_rerank(sample_anime)
        print("Texto formateado:")
        print("  ->", formatted_text)
        assert 'Title: Steins;Gate' in formatted_text
        assert 'Sci-Fi' in formatted_text
        assert 'mad scientist' in formatted_text
        assert '<p>' not in formatted_text, "HTML no fue limpiado correctamente"
        print("[OK] [TEST 1 PASSED]: Formateo de texto correcto y limpio de HTML.")

        # 2. Test CrossEncoder Loading
        print("\n[TEST 2] Carga e inicializacion de CrossEncoder...")
        encoder = SearchEngine.load_cross_encoder()
        assert encoder is not None, "El CrossEncoder deberia cargarse exitosamente"
        print(f"[OK] [TEST 2 PASSED]: Cross-Encoder cargado correctamente: {encoder.__class__.__name__}")

        # 3. Test rerank_candidates
        print("\n[TEST 3] Re-ranking de candidatos con Cross-Encoder...")
        query = "anime sobre viajes en el tiempo para salvar a sus amigos"

        candidates = [
            {
                'id': 1,
                'main_title': 'Naruto',
                'genres': ['Action', 'Adventure', 'Fantasy'],
                'vibe_keywords': ['ninja', 'hokage', 'rasengan'],
                'description': 'A ninja boy seeks recognition from his peers and dreams of becoming the Hokage.'
            },
            {
                'id': 2,
                'main_title': 'Tokyo Revengers',
                'genres': ['Action', 'Drama', 'Supernatural'],
                'vibe_keywords': ['time leap', 'gangs', 'save friends'],
                'vibe_check': 'Viajes en el tiempo para rescatar a su exnovia y amigos de una pandilla.',
                'description': 'Takemichi Hanagaki travels 12 years into the past to save his friends.'
            },
            {
                'id': 3,
                'main_title': 'K-On!',
                'genres': ['Comedy', 'Slice of Life'],
                'vibe_keywords': ['moe', 'tea and cake', 'after school tea time'],
                'description': 'Four high school girls join the light music club to keep it from being disbanded.'
            },
            {
                'id': 4,
                'main_title': 'Boku dake ga Inai Machi (ERASED)',
                'genres': ['Mystery', 'Psychological', 'Supernatural'],
                'vibe_keywords': ['revival', 'save the girl', 'butterfly effect'],
                'vibe_check': 'Un joven vuelve 18 anos atras para detener crimenes y salvar a sus amigos.',
                'description': 'Satoru Fujinuma is sent back in time to prevent a series of kidnappings.'
            }
        ]

        reranked = SearchEngine.rerank_candidates(query, candidates, top_k=3)
        
        print(f"Resultados re-rankeados para la consulta: '{query}'")
        for idx, anime in enumerate(reranked, 1):
            print(f"  {idx}. {anime['main_title']:<35} | CE Score: {anime.get('cross_encoder_score', 0):.4f} | Similitud: {anime.get('similarity_score', 0):.2f}%")

        assert len(reranked) == 3, f"top_k=3 esperado, recibido {len(reranked)}"
        top_titles = [a['main_title'] for a in reranked[:2]]
        assert 'Tokyo Revengers' in top_titles or 'Boku dake ga Inai Machi (ERASED)' in top_titles, "Los animes de viajes en el tiempo deben liderar el ranking"
        assert 'K-On!' not in top_titles, "K-On! no debe estar en el top 2 para esta consulta"
        assert 'Naruto' not in top_titles, "Naruto no debe estar en el top 2 para esta consulta"
        assert all(a.get('reranked') is True for a in reranked), "Todos deben tener flag reranked=True"
        print("[OK] [TEST 3 PASSED]: Re-ranking coloco con precision tematica los mejores animes en el Top!")

        # 4. Test Fallback when empty or error
        print("\n[TEST 4] Casos borde y listas vacias...")
        fallback_res = SearchEngine.rerank_candidates(query, [], top_k=2)
        assert fallback_res == [], "Lista vacia debe retornar lista vacia"
        print("[OK] [TEST 4 PASSED]: Casos borde manejados adecuadamente.")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)
        return True

    except Exception as e:
        print("\n[ERROR EN TEST]:", e)
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
