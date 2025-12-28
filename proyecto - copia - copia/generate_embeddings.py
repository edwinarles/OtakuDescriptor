import os
import time
import numpy as np
from openai import OpenAI
from database import Database, db
from config import Config
from utils import normalizar_texto
from tqdm import tqdm

# Inicializar conexión a DB
Database.init_db()

class EmbeddingGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.collection = db.db.animes
        self.model = Config.EMBEDDING_MODEL
        
    def generate_embedding(self, text):
        """Genera embedding para un texto"""
        try:
            text = text.replace("\n", " ")
            return self.client.embeddings.create(input=[text], model=self.model).data[0].embedding
        except Exception as e:
            print(f"Error generando embedding: {e}")
            return None

    def process_all(self, batch_size=100, force_regenerate=False):
        """Genera embeddings para todos los animes en la DB"""
        print(f"🚀 Iniciando generación de embeddings usando {self.model}...")
        
        # Filtro: solo los que no tienen embedding o todos si force_regenerate
        query = {} if force_regenerate else {"embedding": {"$exists": False}}
        total_to_process = self.collection.count_documents(query)
        
        print(f"📊 Animes a procesar: {total_to_process}")
        
        if total_to_process == 0:
            print("✅ Todos los animes ya tienen embeddings.")
            self.export_numpy()
            return

        cursor = self.collection.find(query)
        batch = []
        
        # Barra de progreso
        pbar = tqdm(total=total_to_process)
        
        for anime in cursor:
            # Usar enhanced_description si existe, sino description, sino titulo
            text = anime.get('enhanced_description') or anime.get('description') or anime.get('main_title')
            
            # NORMALIZAR TEXTO (Importante para coincidir con la búsqueda)
            text = normalizar_texto(text)
            
            if not text:
                pbar.update(1)
                continue
                
            batch.append({
                'id': anime['id'],
                'text': text
            })
            
            if len(batch) >= batch_size:
                self.process_batch(batch)
                pbar.update(len(batch))
                batch = []
                time.sleep(0.1) # Rate limiting
        
        # Procesar remanente
        if batch:
            self.process_batch(batch)
            pbar.update(len(batch))
            
        pbar.close()
        self.export_numpy()

    def process_batch(self, batch):
        """Procesa un lote de animes"""
        try:
            texts = [item['text'] for item in batch]
            # OpenAI permite batches
            response = self.client.embeddings.create(input=texts, model=self.model)
            
            for i, data in enumerate(response.data):
                embedding = data.embedding
                anime_id = batch[i]['id']
                
                # Guardar en MongoDB
                self.collection.update_one(
                    {'id': anime_id},
                    {'$set': {'embedding': embedding}}
                )
                
        except Exception as e:
            print(f"❌ Error en batch: {e}")
            # Fallback: intentar uno por uno si falla el batch
            for item in batch:
                # Ya está normalizado en process_all
                embedding = self.generate_embedding(item['text'])
                if embedding:
                    self.collection.update_one(
                        {'id': item['id']},
                        {'$set': {'embedding': embedding}}
                    )
                else:
                    print(f"⚠️ Falló embedding para anime {item['id']}")
 
    def export_numpy(self):
        """Exporta todos los embeddings a un archivo .npy para FAISS"""
        print("\n💾 Exportando embeddings a archivo numpy...")
        
        # Obtener todos los animes con embeddings ordenados por algún criterio estable si es necesario
        # IMPORTANTE: search_engine asume que el índice del array corresponde al índice en la lista de animes loaded
        # Por lo tanto, necesitamos asegurarnos de que el orden sea consistente.
        # En la implementación de search_engine modificada, cargaremos TODO de Mongo.
        
        # Para ser consistentes, recuperamos todo y guardamos en orden de ID
        cursor = self.collection.find(
            {"embedding": {"$exists": True}},
            {"embedding": 1}
        ).sort('id', 1)
        
        embeddings_list = []
        count = 0
        
        for doc in cursor:
            embeddings_list.append(doc['embedding'])
            count += 1
            
        if not embeddings_list:
            print("⚠️ No hay embeddings para exportar.")
            return

        embeddings_array = np.array(embeddings_list, dtype='float32')
        np.save("embeddings.npy", embeddings_array)
        print(f"✅ Archivo 'embeddings.npy' guardado con {count} vectores.")

def main():
    if not Config.OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY no encontrada en .env")
        return
        
    generator = EmbeddingGenerator()
    # Forzar regeneración para aplicar normalización
    generator.process_all(force_regenerate=True)

if __name__ == "__main__":
    main()
