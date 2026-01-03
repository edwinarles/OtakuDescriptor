# Search System Package

Este módulo contiene todo el sistema de búsqueda híbrida de anime.

## 📁 Estructura

```
search_system/
├── __init__.py              # Exports del package
├── download_animes.py       # Descarga datos de AniList
├── enrich_with_llm.py       # Enriquecimiento con GPT-4o-mini
├── generate_embeddings.py   # Generación de embeddings con OpenAI
├── search_engine.py         # Motor de búsqueda vectorial (FAISS)
└── hybrid_search.py         # Motor de búsqueda híbrida (Vector + BM25)
```

## 🚀 Pipeline de Datos

### 1. Descargar Animes
```bash
python -m search_system.download_animes
```
Descarga 1000 animes de AniList y los guarda en MongoDB.

### 2. Enriquecer con LLM
```bash
python -m search_system.enrich_with_llm

# Opciones:
python -m search_system.enrich_with_llm --test-mode  # Solo 5 animes
python -m search_system.enrich_with_llm --stats      # Ver estadísticas
```
Genera campos `world_lore`, `vibe_check` y `vibe_keywords` usando GPT-4o-mini.

### 3. Generar Embeddings
```bash
python -m search_system.generate_embeddings
```
Crea embeddings vectoriales y exporta `embeddings.npy`.

## 🔍 Uso en la Aplicación

```python
from search_system import SearchEngine, HybridSearchEngine

# Inicializar motores
SearchEngine.load_data()
HybridSearchEngine.initialize()

# Búsqueda híbrida
results = HybridSearchEngine.hybrid_search(
    query_vector=embedding_vector,
    query_text="tatakae",
    top_k=10,
    auto_weights=True
)
```

## ⚙️ Componentes

### SearchEngine
Motor de búsqueda vectorial usando FAISS con similitud coseno.

### HybridSearchEngine
Combina búsqueda vectorial (FAISS) + búsqueda por keywords (BM25) usando Reciprocal Rank Fusion.

**Ajuste automático de pesos:**
- Query corta + meme/japonés → 70% BM25, 30% Vector
- Query larga descriptiva → 60% Vector, 40% BM25
- Query media → 50% / 50%

### BM25Indexer
Índice invertido para búsqueda por palabras clave con pesos especiales:
- `vibe_keywords`: peso 3x
- `vibe_check`: peso 2x
- `main_title`: peso 2x
