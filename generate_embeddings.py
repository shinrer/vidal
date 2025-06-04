import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
import datetime
from tqdm import tqdm
import traceback
import pickle # Pour sérialiser/désérialiser les embeddings (numpy arrays)

# --- Configuration ---
DATABASE_NAME = "medicaments.db"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2' # Bon modèle multilingue, dimension 768
# Alternative plus légère: 'all-MiniLM-L6-v2' (dimension 384)
BATCH_SIZE = 32  # Nombre de textes à encoder en parallèle par le modèle
COMMIT_INTERVAL = 100 # Nombre d'embeddings traités avant un commit

# --- Logging ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] ERROR: {message}")

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        log_error(f"Database connection error: {e}\n{traceback.format_exc()}")
        raise

def generate_and_store_embeddings():
    log_info(f"--- Démarrage de la génération d'embeddings avec le modèle : {MODEL_NAME} ---")
    
    try:
        log_info("Chargement du modèle SentenceTransformer...")
        model = SentenceTransformer(MODEL_NAME)
        log_info("Modèle chargé.")
    except Exception as e:
        log_error(f"Erreur lors du chargement du modèle SentenceTransformer: {e}\n{traceback.format_exc()}")
        return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Compter le nombre total de sections à traiter (où embedding IS NULL)
        cursor.execute("SELECT COUNT(id_section) FROM RCP_Sections WHERE embedding IS NULL")
        total_to_process = cursor.fetchone()[0]

        if total_to_process == 0:
            log_info("Aucune section à traiter pour l'embedding (toutes les sections ont déjà un embedding ou la table est vide).")
            return

        log_info(f"Nombre total de sections à traiter pour l'embedding : {total_to_process}")

        # Récupérer les sections sans embedding par lots
        cursor.execute("SELECT id_section, texte_section FROM RCP_Sections WHERE embedding IS NULL")
        
        rows_processed_since_commit = 0
        texts_batch = []
        ids_batch = []

        with tqdm(total=total_to_process, unit="section", desc="Génération Embeddings") as pbar:
            while True:
                db_rows = cursor.fetchmany(BATCH_SIZE) # Récupère BATCH_SIZE lignes de la DB
                if not db_rows:
                    break # Plus de lignes à traiter dans la DB

                current_batch_texts = [row[1] for row in db_rows]
                current_batch_ids = [row[0] for row in db_rows]
                
                try:
                    # Générer les embeddings pour le lot actuel de textes
                    # L'option convert_to_numpy=True est par défaut.
                    embeddings_batch_np = model.encode(current_batch_texts, show_progress_bar=False)

                    # Stocker les embeddings
                    for section_id, embedding_np in zip(current_batch_ids, embeddings_batch_np):
                        # Convertir l'array numpy en bytes pour le stockage BLOB
                        # pickle est une option, .tobytes() une autre. pickle est plus général.
                        embedding_blob = pickle.dumps(embedding_np)
                        try:
                            conn.execute("UPDATE RCP_Sections SET embedding = ? WHERE id_section = ?", 
                                         (sqlite3.Binary(embedding_blob), section_id))
                            rows_processed_since_commit += 1
                        except sqlite3.Error as e_update:
                            log_error(f"Erreur SQLite lors de la mise à jour de l'embedding pour id_section {section_id}: {e_update}")
                            # Potentiellement, ajouter à une liste d'échecs pour retenter plus tard

                    pbar.update(len(db_rows))

                    if rows_processed_since_commit >= COMMIT_INTERVAL:
                        conn.commit()
                        log_info(f"{rows_processed_since_commit} embeddings traités et commit en base.")
                        rows_processed_since_commit = 0
                
                except Exception as e_encode:
                    log_error(f"Erreur lors de l'encodage ou du stockage d'un lot d'embeddings: {e_encode}\n{traceback.format_exc()}")
                    # On pourrait choisir de sauter ce lot ou d'arrêter. Pour l'instant, on continue.

            # Commit final pour les dernières opérations non encore commitées
            if rows_processed_since_commit > 0:
                conn.commit()
                log_info(f"Commit final de {rows_processed_since_commit} embeddings.")
        
        log_info("--- Génération et stockage des embeddings terminés ---")

    except sqlite3.Error as e:
        log_error(f"Erreur SQLite pendant le processus d'embedding: {e}\n{traceback.format_exc()}")
        if conn:
            conn.rollback()
    except Exception as e:
        log_error(f"Erreur inattendue pendant la génération des embeddings: {e}\n{traceback.format_exc()}")
    finally:
        if conn:
            conn.close()
            log_info("Connexion à la base de données fermée.")

if __name__ == "__main__":
    # Assurez-vous que les dépendances sont installées:
    # pip install sentence-transformers torch numpy tqdm
    generate_and_store_embeddings()