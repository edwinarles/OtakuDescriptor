# Search System Package

Este módulo contiene el sistema de búsqueda semántica de anime de OtakuDescriptor, optimizado para despliegue en la nube (Render) con bajo consumo de memoria RAM (< 70 MiB).

## 📁 Estructura

```
search_system/
├── __init__.py              # Exports del package
├── download_animes.py       # Descarga datos de AniList
├── enrich_with_llm.py       # Enriquecimiento con GPT-4o-mini (vibe, lore, keywords)
├── generate_embeddings.py   # Generación de embeddings con OpenAI
└── search_engine.py         # Motor de búsqueda en dos etapas (FAISS + LLM Cross-Encoder Re-Ranking)
```

## 🧠 Arquitectura de Búsqueda en 2 Etapas (Zero-RAM Overhead)

1. **Primera Etapa (Recuperación de Candidatos con FAISS)**:
   - Se convierte la consulta a vector usando `text-embedding-3-large`.
   - FAISS (`IndexFlatIP`) recupera en microsegundos los 15-20 candidatos más cercanos por similitud coseno.
   
2. **Segunda Etapa (Re-Ranking con Cross-Attention)**:
   - La lista de candidatos se evalúa con atención cruzada mediante `gpt-4o-mini` (Cross-Encoder vía LLM).
   - Analiza simultáneamente la consulta con el título, sinopsis, géneros y *vibe check* de cada anime.
   - **Consumo de memoria en el servidor: 0 MiB** (evita el error `Out of memory (used over 512Mi)` en el plan gratuito de Render).
   - Reordena los candidatos para que el Top-K final tenga la máxima precisión semántica.

## ⚙️ Configuración (en `.env` o variables de Render)

- `PORT`: Puerto de escucha del servicio (Render inyecta `10000`).
- `ENABLE_RERANKING`: Activa/desactiva el re-ranking (`true` por defecto).
- `RERANK_CANDIDATES`: Cantidad de candidatos de la primera etapa enviados a re-ranking (por defecto `15`).
- `OPENAI_API_KEY`: Clave de API de OpenAI para embeddings y re-ranking.
