import os
import time
import json
from openai import OpenAI
from database import Database, db
from config import Config
from tqdm import tqdm

# Inicializar conexión a DB
Database.init_db()

class LLMEnricher:
    """
    Enriquece los datos de anime con información contextual generada por LLM:
    - world_lore: Sistema de magia/tecnología y geopolítica del mundo
    - vibe_check: Descripción con memes y referencias culturales
    - vibe_keywords: Términos clave que la comunidad usa
    """
    
    def __init__(self, test_mode=False):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.collection = db.db.animes
        self.model = "gpt-4o-mini"
        self.test_mode = test_mode
        
    def create_enrichment_prompt(self, anime):
        """Crea el prompt para enriquecer un anime"""
        title = anime.get('main_title', 'Unknown')
        description = anime.get('description', '')[:1000]  # Limitar a 1000 chars
        genres = ', '.join(anime.get('genres', []))
        tags = ', '.join(anime.get('tags', [])[:10])
        
        prompt = f"""Eres un experto en anime y miembro activo de la comunidad otaku. Analiza este anime:

Título: {title}
Sinopsis: {description}
Géneros: {genres}
Tags: {tags}

Genera una respuesta en formato JSON con exactamente estos campos:
1. "world_lore": 2-3 oraciones explicando el sistema de magia/tecnología del mundo, las estructuras de poder, y el setting. Si no aplica magia/tecnología especial, describe el mundo y su contexto.
2. "vibe_check": 1-2 oraciones usando jerga de la comunidad, memes, y referencias culturales que los fans usan para describir este anime. Sé informal y auténtico.
3. "vibe_keywords": Array de 5-10 términos específicos, frases icónicas, o memes asociados con este anime. Incluye tanto términos en japonés como en español/inglés si son relevantes.

Responde SOLAMENTE con el JSON, sin texto adicional."""

        return prompt
    
    def enrich_anime(self, anime):
        """Enriquece un anime con LLM"""
        try:
            prompt = self.create_enrichment_prompt(anime)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en anime que genera metadatos estructurados en formato JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            enriched_data = json.loads(content)
            
            # Validar que los campos existan
            required_fields = ['world_lore', 'vibe_check', 'vibe_keywords']
            for field in required_fields:
                if field not in enriched_data:
                    print(f"⚠️ Campo faltante {field} en respuesta para {anime.get('main_title')}")
                    return None
            
            return enriched_data
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON para {anime.get('main_title')}: {e}")
            if self.test_mode:
                print(f"Respuesta: {content}")
            return None
        except Exception as e:
            print(f"❌ Error enriqueciendo {anime.get('main_title')}: {e}")
            return None
    
    def process_all(self, limit=None, skip_enriched=True):
        """Procesa todos los animes en la DB"""
        print(f"🚀 Iniciando enriquecimiento LLM con {self.model}...")
        
        # Filtro: solo los que no tienen los campos enriquecidos
        query = {}
        if skip_enriched:
            query = {
                "$or": [
                    {"world_lore": {"$exists": False}},
                    {"vibe_check": {"$exists": False}},
                    {"vibe_keywords": {"$exists": False}}
                ]
            }
        
        total_to_process = self.collection.count_documents(query)
        
        if limit:
            total_to_process = min(total_to_process, limit)
            print(f"📊 Modo de prueba: procesando {total_to_process} animes")
        else:
            print(f"📊 Animes a enriquecer: {total_to_process}")
        
        if total_to_process == 0:
            print("✅ Todos los animes ya están enriquecidos.")
            return
        
        cursor = self.collection.find(query).limit(limit) if limit else self.collection.find(query)
        
        success_count = 0
        error_count = 0
        
        # Barra de progreso
        pbar = tqdm(total=total_to_process, desc="Enriqueciendo")
        
        for anime in cursor:
            enriched_data = self.enrich_anime(anime)
            
            if enriched_data:
                # Actualizar en MongoDB
                self.collection.update_one(
                    {'id': anime['id']},
                    {'$set': enriched_data}
                )
                success_count += 1
                
                if self.test_mode and success_count <= 2:
                    print(f"\n✅ Ejemplo enriquecido: {anime.get('main_title')}")
                    print(f"   World Lore: {enriched_data['world_lore'][:100]}...")
                    print(f"   Vibe Check: {enriched_data['vibe_check'][:100]}...")
                    print(f"   Keywords: {', '.join(enriched_data['vibe_keywords'][:5])}")
            else:
                error_count += 1
            
            pbar.update(1)
            
            # Rate limiting: OpenAI tiene límite de ~3000 RPM para GPT-4o-mini
            # Con 1000 animes, vamos a hacerlo a ~10/segundo para estar seguros
            time.sleep(0.15)
        
        pbar.close()
        
        print("\n" + "="*60)
        print("📊 RESUMEN DE ENRIQUECIMIENTO")
        print("="*60)
        print(f"✅ Exitosos: {success_count}")
        print(f"❌ Errores: {error_count}")
        print(f"📈 Tasa de éxito: {success_count/total_to_process*100:.1f}%")
        print("="*60)
        
    def get_statistics(self):
        """Muestra estadísticas de enriquecimiento"""
        total = self.collection.count_documents({})
        enriched = self.collection.count_documents({
            "world_lore": {"$exists": True},
            "vibe_check": {"$exists": True},
            "vibe_keywords": {"$exists": True}
        })
        
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DE ENRIQUECIMIENTO")
        print("="*60)
        print(f"Total de animes: {total}")
        print(f"Animes enriquecidos: {enriched} ({enriched/total*100:.1f}%)")
        print(f"Pendientes: {total - enriched}")
        print("="*60)

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enriquece animes con LLM')
    parser.add_argument('--test-mode', action='store_true', help='Modo de prueba (procesa solo 5 animes)')
    parser.add_argument('--limit', type=int, help='Limitar número de animes a procesar')
    parser.add_argument('--stats', action='store_true', help='Mostrar solo estadísticas')
    parser.add_argument('--force', action='store_true', help='Forzar re-enriquecimiento de todos los animes')
    
    args = parser.parse_args()
    
    if not Config.OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY no encontrada en .env")
        return
    
    enricher = LLMEnricher(test_mode=args.test_mode)
    
    if args.stats:
        enricher.get_statistics()
        return
    
    limit = 5 if args.test_mode else args.limit
    skip_enriched = not args.force
    
    print("="*60)
    print("  ENRIQUECIMIENTO DE DATASET CON LLM")
    print("="*60)
    
    enricher.process_all(limit=limit, skip_enriched=skip_enriched)
    enricher.get_statistics()
    
    print("\n✅ ¡Proceso de enriquecimiento completado!")
    print("📝 Siguiente paso: Ejecutar generate_embeddings.py para actualizar los embeddings")
    print("="*60)

if __name__ == "__main__":
    main()
