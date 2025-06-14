import sqlite3
from sentence_transformers import SentenceTransformer
import torch
import datetime
from tqdm import tqdm
import time
import traceback
import argparse

# --- Configuration ---
DATABASE_NAME = "medicaments.db"

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

# --- Encoding helper ---
def encode_batch(model, device: str, texts, batch_size: int):
    """Encode a batch of texts with optional CUDA autocast."""
    if device == "cuda":
        with torch.cuda.amp.autocast():
            return model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
    else:
        return model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

def generate_and_store_embeddings(model_name: str, batch_size: int, commit_interval: int):
    log_info(
        f"--- Démarrage de la génération d'embeddings avec le modèle : {model_name} ---"
    )
    
    try:
        # Initialize model on the appropriate device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"👉  Using {device}")

        log_info("Chargement du modèle SentenceTransformer...")
        model = SentenceTransformer(model_name, device=device)

        if device == "cuda":
            model.half()  # load weights in FP16/BF16
            torch.set_default_dtype(torch.float16)

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
        total_rows = cursor.fetchone()[0]

        if total_rows == 0:
            log_info("Aucune section à traiter pour l'embedding (toutes les sections ont déjà un embedding ou la table est vide).")
            return

        log_info(f"Nombre total de sections à traiter pour l'embedding : {total_rows}")

        # Récupérer les sections sans embedding par lots
        cursor.execute("SELECT id_section, texte_section FROM RCP_Sections WHERE embedding IS NULL")
        
        rows_processed_since_commit = 0
        rows_to_update = []

        pbar = tqdm(total=total_rows, desc="Embedding")
        start_time = time.time()
        while True:
            db_rows = cursor.fetchmany(batch_size)  # Récupère batch_size lignes de la DB
            if not db_rows:
                break  # Plus de lignes à traiter dans la DB

            current_batch_texts = [row[1] for row in db_rows]
            current_batch_ids = [row[0] for row in db_rows]

            try:
                # Encode the current batch
                embeddings_batch_np = encode_batch(
                    model, device, current_batch_texts, batch_size
                )

                # Store embeddings for later commit
                for section_id, embedding_np in zip(current_batch_ids, embeddings_batch_np):
                    embedding_blob = embedding_np.tobytes()
                    rows_to_update.append((sqlite3.Binary(embedding_blob), section_id))

                if len(rows_to_update) >= commit_interval:
                    cursor.executemany(
                        "UPDATE RCP_Sections SET embedding=? WHERE id_section=?",
                        rows_to_update,
                    )
                    conn.commit()
                    rows_to_update.clear()

                pbar.update(len(db_rows))

            except Exception as e_encode:
                log_error(
                    f"Erreur lors de l'encodage ou du stockage d'un lot d'embeddings: {e_encode}\n{traceback.format_exc()}"
                )
                # On pourrait choisir de sauter ce lot ou d'arrêter. Pour l'instant, on continue.

        # Flush remaining updates
        if rows_to_update:
            cursor.executemany(
                "UPDATE RCP_Sections SET embedding=? WHERE id_section=?",
                rows_to_update,
            )
            conn.commit()
            rows_to_update.clear()

        pbar.close()
        time_elapsed = time.time() - start_time
        print(
            f"\u23f1\ufe0f  Done in {time_elapsed:.1f}s \u21d2 {total_rows/time_elapsed:.0f} rows/s"
        )

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

    parser = argparse.ArgumentParser(description="Generate and store embeddings")
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-base",
        help="SentenceTransformer model to use",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=128,
        help="Number of texts to encode per batch",
    )
    parser.add_argument(
        "--commit_interval",
        type=int,
        default=500,
        help="Number of embeddings processed before committing to the database",
    )

    args = parser.parse_args()

    generate_and_store_embeddings(args.model, args.batch_size, args.commit_interval)
