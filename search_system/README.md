# Search System Package

Este módulo contiene el sistema de búsqueda semántica de anime de OtakuDescriptor, incluyendo recuperación vectorial y re-ranking neuronal.

## 📁 Estructura

```
search_system/
├── __init__.py              # Exports del package
├── download_animes.py       # Descarga datos de AniList
├── enrich_with_llm.py       # Enriquecimiento con GPT-4o-mini (vibe, lore, keywords)
├── generate_embeddings.py   # Generación de embeddings con OpenAI
└── search_engine.py         # Motor de búsqueda en dos etapas (FAISS + Cross-Encoder Re-Ranking)
```

## 🧠 Arquitectura de Búsqueda en 2 Etapas

1. **Primera Etapa (Recuperación de Candidatos con Bi-Encoder / Similitud Coseno)**:
   - Se convierte la consulta a vector usando `text-embedding-3-large`.
   - Se busca en el índice FAISS (`IndexFlatIP`) para recuperar rápidamente los $K$ candidatos más cercanos (por defecto 30-50 candidatos) mediante similitud coseno.
   
2. **Segunda Etapa (Re-Ranking con Cross-Encoder)**:
   - Los bi-encoders comprimen el texto completo a un vector único, lo cual pierde interacciones sutiles entre palabras clave, contexto y relaciones para los mejores puestos del top.
   - El **Cross-Encoder** (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) analiza la consulta y la descripción estructurada del anime (`Title`, `Genres`, `Keywords`, `Vibe`, `Lore`, `Synopsis`) simultáneamente con atención cruzada completa (*cross-attention*).
   - Reordena los candidatos y produce un ranking mucho más preciso y contextual para el Top-K final.

## ⚙️ Configuración (en `.env` o `config.py`)

- `ENABLE_RERANKING`: Activa/desactiva el re-ranking con Cross-Encoder (`true` por defecto).
- `CROSS_ENCODER_MODEL`: Modelo HuggingFace para re-ranking (por defecto `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` para soporte multilingüe español/inglés; también configurable a `cross-encoder/ms-marco-MiniLM-L-6-v2` para inglés).
- `RERANK_CANDIDATES`: Número mínimo de candidatos recuperados en la primera etapa para alimentar al Cross-Encoder (por defecto `30`).
- `CROSS_ENCODER_DEVICE`: Dispositivo de ejecución (`cpu` o `cuda`).

## 🚀 Uso en la Aplicación

```python
from search_system import SearchEngine

# 1. Cargar datos e inicializar FAISS y Cross-Encoder
SearchEngine.load_data()

# 2. Búsqueda vectorial con Re-Ranking automático
results = SearchEngine.search(
    vector=query_vector,
    top_k=10,
    query_text="un anime donde viajan en el tiempo para salvar a sus amigos",
    rerank=True
)
```
