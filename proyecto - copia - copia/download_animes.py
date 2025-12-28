import requests
import time
from typing import List, Dict
import os
import re
from database import Database, db
from config import Config

# Inicializar conexión a DB
Database.init_db()

class AnimeDatasetDownloader:
    """
    Descarga el dataset completo de anime desde AniList GraphQL API y lo guarda en MongoDB
    """
    
    def __init__(self):
        self.api_url = "https://graphql.anilist.co"
        self.collection = db.db.animes
        
    def get_query(self) -> str:
        """Query GraphQL para obtener información completa de anime"""
        return '''
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    total
                    currentPage
                    lastPage
                    hasNextPage
                    perPage
                }
                media(type: ANIME, sort: POPULARITY_DESC) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description(asHtml: false)
                    format
                    status
                    episodes
                    duration
                    genres
                    tags {
                        name
                        rank
                    }
                    averageScore
                    popularity
                    favourites
                    season
                    seasonYear
                    startDate {
                        year
                        month
                        day
                    }
                    studios(isMain: true) {
                        nodes {
                            name
                        }
                    }
                    coverImage {
                        large
                        extraLarge
                    }
                    bannerImage
                    synonyms
                }
            }
        }
        '''
    
    def fetch_page(self, page: int, per_page: int = 50) -> Dict:
        """Obtiene una página de resultados"""
        variables = {
            'page': page,
            'perPage': per_page
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        payload = {
            'query': self.get_query(),
            'variables': variables
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Verificar si hay errores en la respuesta
            if 'errors' in data:
                print(f"❌ Errores en la API: {data['errors']}")
                return None
                
            return data
            
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout en página {page}, reintentando...")
            time.sleep(2)
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error en página {page}: {e}")
            return None
    
    def clean_description(self, description: str) -> str:
        """Limpia la descripción"""
        if not description:
            return ""
        # Remover saltos de línea excesivos
        clean = re.sub(r'\n\n+', '\n\n', description)
        return clean.strip()
    
    def process_anime(self, anime: Dict) -> Dict:
        """Procesa y limpia los datos de un anime"""
        # Crear descripción enriquecida para embeddings
        title_eng = anime['title'].get('english')
        title_rom = anime['title'].get('romaji')
        title = title_eng if title_eng else title_rom
        
        description = self.clean_description(anime.get('description', ''))
        
        # Información adicional para contexto
        genres = ', '.join(anime.get('genres', []))
        tags = ', '.join([tag['name'] for tag in anime.get('tags', [])[:10] if tag])
        studios = ', '.join([s['name'] for s in anime.get('studios', {}).get('nodes', []) if s])
        
        # Descripción enriquecida para mejor búsqueda
        enhanced_description = description
        if genres:
            enhanced_description += f"\n\nGéneros: {genres}"
        if tags:
            enhanced_description += f"\nTags: {tags}"
        if studios:
            enhanced_description += f"\nEstudio: {studios}"
        
        return {
            'id': anime['id'],
            'mal_id': anime.get('idMal'),
            'title': {
                'romaji': anime['title'].get('romaji'),
                'english': anime['title'].get('english'),
                'native': anime['title'].get('native')
            },
            'main_title': title,
            'description': description,
            'enhanced_description': enhanced_description,
            'format': anime.get('format'),
            'status': anime.get('status'),
            'episodes': anime.get('episodes'),
            'duration': anime.get('duration'),
            'genres': anime.get('genres', []),
            'tags': [tag['name'] for tag in anime.get('tags', [])[:15] if tag],
            'score': anime.get('averageScore'),
            'popularity': anime.get('popularity'),
            'favourites': anime.get('favourites'),
            'season': anime.get('season'),
            'year': anime.get('seasonYear'),
            'studios': [s['name'] for s in anime.get('studios', {}).get('nodes', []) if s],
            'cover_image': anime.get('coverImage', {}).get('extraLarge'),
            'banner_image': anime.get('bannerImage'),
            'synonyms': anime.get('synonyms', [])
        }
    
    def test_connection(self) -> bool:
        """Prueba la conexión con la API"""
        print("🔍 Probando conexión con AniList API...")
        
        test_query = '''
        query {
            Media(id: 1, type: ANIME) {
                id
                title {
                    romaji
                }
            }
        }
        '''
        
        try:
            response = requests.post(
                self.api_url,
                json={'query': test_query},
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'Media' in data['data']:
                print(f"✅ Conexión exitosa! Probado con: {data['data']['Media']['title']['romaji']}")
                return True
            else:
                print(f"❌ Respuesta inesperada: {data}")
                return False
                
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False
    
    def download_all(self, max_pages: int = None, retry_failed: bool = True):
        """Descarga todo el dataset y lo guarda en MongoDB"""
        # Primero probar conexión
        if not self.test_connection():
            print("\n❌ No se pudo conectar con la API. Verifica tu conexión a internet.")
            return
        
        print("\n🚀 Iniciando descarga del dataset de anime hacia MongoDB...")
        
        # Crear índice único para id si no existe
        self.collection.create_index("id", unique=True)
        
        page = 1
        total_pages = None
        failed_pages = []
        total_upserted = 0
        
        while True:
            if max_pages and page > max_pages:
                break
                
            print(f"📥 Página {page}/{total_pages or '?'}...", end=" ", flush=True)
            
            data = self.fetch_page(page)
            
            if not data or 'data' not in data:
                print("❌ Error")
                failed_pages.append(page)
                page += 1
                time.sleep(2)
                continue
            
            page_data = data['data']['Page']
            page_info = page_data['pageInfo']
            
            if total_pages is None:
                total_pages = page_info['lastPage']
                print(f"\n📊 Total de páginas: {total_pages} (~{total_pages * 50} animes)")
                print("-" * 60)
            
            # Procesar animes de esta página
            upserted_count = 0
            for anime in page_data['media']:
                try:
                    processed = self.process_anime(anime)
                    # Upsert en MongoDB
                    self.collection.update_one(
                        {'id': processed['id']},
                        {'$set': processed},
                        upsert=True
                    )
                    upserted_count += 1
                except Exception as e:
                    print(f"\n⚠️ Error procesando anime: {e}")
            
            total_upserted += upserted_count
            print(f"✅ (+{upserted_count} animes, total procesados: {total_upserted})")
            
            if not page_info['hasNextPage']:
                print("\n✨ ¡Todas las páginas descargadas!")
                break
            
            page += 1
            time.sleep(0.7)  # Rate limiting amigable
        
        # Reintentar páginas fallidas
        if failed_pages and retry_failed:
            print(f"\n🔄 Reintentando {len(failed_pages)} páginas fallidas...")
            for failed_page in failed_pages:
                print(f"   Reintentando página {failed_page}...", end=" ")
                data = self.fetch_page(failed_page)
                if data and 'data' in data:
                    upserted_count = 0
                    for anime in data['data']['Page']['media']:
                        try:
                            processed = self.process_anime(anime)
                            self.collection.update_one(
                                {'id': processed['id']},
                                {'$set': processed},
                                upsert=True
                            )
                            upserted_count += 1
                        except:
                            pass
                    total_upserted += upserted_count
                    print("✅")
                else:
                    print("❌")
                time.sleep(1)
        
        self.print_statistics()
    
    def print_statistics(self):
        """Imprime estadísticas del dataset en MongoDB"""
        count = self.collection.count_documents({})
        if count == 0:
            print("\n⚠️ No hay animes en la base de datos")
            return
            
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DEL DATASET EN MONGODB")
        print("="*60)
        print(f"Total de animes en DB: {count}")
        
        # Con embeddings (verificar campos) - esto será útil después de correr generate_embeddings
        with_embedding = self.collection.count_documents({'embedding': {'$exists': True}})
        print(f"Con embeddings generados: {with_embedding} ({with_embedding/count*100:.1f}%)")
        
        print("="*60)

def main():
    """Función principal"""
    print("="*60)
    print("  DESCARGADOR DE DATASET DE ANIME - AniList API -> MongoDB")
    print("="*60)
    
    downloader = AnimeDatasetDownloader()
    
    # Descarga todo el dataset
    # Para pruebas rápidas puedes descomentar la siguiente línea
    # downloader.download_all(max_pages=5) 
    
    # Descarga 2000 animes (40 páginas * 50 animes)
    downloader.download_all(max_pages=40)
    
    print("\n✅ ¡Proceso de descarga completado!")
    print("📝 Siguiente paso: Ejecutar generate_embeddings.py")
    print("="*60)


if __name__ == "__main__":
    main()
