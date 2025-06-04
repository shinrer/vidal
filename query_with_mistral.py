# --- Fichier : query_with_mistral.py ---
import sqlite3
import numpy as np
import pickle
import faiss
from sentence_transformers import SentenceTransformer
import ollama # Bibliothèque Python pour Ollama
import datetime
import traceback
from pathlib import Path

# --- Configuration ---
DATABASE_NAME = "medicaments.db"
# DOIT être le même modèle que celui utilisé dans generate_embeddings.py
EMBEDDING_MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'
# Nom du modèle Ollama (assurez-vous qu'il est téléchargé via `ollama pull <nom_modele>`)
OLLAMA_MODEL_NAME = 'mistral:7b-instruct-q4_K_M' # Ou le nom de votre modèle Mistral quantizé
FAISS_INDEX_FILE = "rcp_sections.index" # Fichier pour sauvegarder/charger l'index FAISS
TOP_K_RESULTS = 5  # Nombre de sections les plus pertinentes à récupérer

# --- Logging ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] ERROR: {message}")

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=10)
        # OPTIONNEL: Mettre en row_factory pour un accès par nom de colonne plus facile
        # conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        log_error(f"Database connection error: {e}\n{traceback.format_exc()}")
        raise

def load_data_and_embeddings(conn: sqlite3.Connection) -> tuple[list[np.ndarray] | None, list[int] | None, dict | None]:
    """
    Charge les embeddings, les ID de section et les textes depuis la base de données.
    Retourne:
        - une liste d'arrays numpy (embeddings),
        - une liste des id_section correspondants (pour mapper les résultats FAISS aux id_section),
        - un dictionnaire mappant id_section aux données textuelles (texte_section, nom_section_normalise, code_cis).
    """
    log_info("Chargement des données et des embeddings depuis la base de données...")
    cursor = conn.cursor()
    try:
        # Récupérer uniquement les sections qui ont un embedding
        cursor.execute("""
            SELECT id_section, embedding, texte_section, nom_section_normalise, code_cis
            FROM RCP_Sections
            WHERE embedding IS NOT NULL
        """)
        rows = cursor.fetchall()
        if not rows:
            log_error("Aucune section avec embedding trouvée dans la base de données.")
            return None, None, None

        embeddings_list = []
        section_ids_ordered = [] # Pour mapper l'index FAISS à l'id_section
        section_data_map = {}    # Pour récupérer le texte par id_section

        for row_id_section, embedding_blob, texte, nom_norm, code_cis_val in rows:
            try:
                embedding_np = pickle.loads(embedding_blob)
                embeddings_list.append(embedding_np.astype('float32')) # FAISS préfère float32
                section_ids_ordered.append(row_id_section)
                section_data_map[row_id_section] = {
                    "texte_section": texte,
                    "nom_section_normalise": nom_norm,
                    "code_cis": code_cis_val
                }
            except pickle.UnpicklingError as e_pickle:
                log_warning(f"Impossible de désérialiser l'embedding pour id_section {row_id_section}: {e_pickle}. Cette section sera ignorée.")
            except Exception as e_inner:
                 log_warning(f"Erreur lors du traitement de l'embedding pour id_section {row_id_section}: {e_inner}. Cette section sera ignorée.")


        if not embeddings_list:
            log_error("Aucun embedding n'a pu être chargé correctement.")
            return None, None, None

        log_info(f"{len(embeddings_list)} embeddings chargés avec succès.")
        return embeddings_list, section_ids_ordered, section_data_map

    except sqlite3.Error as e:
        log_error(f"Erreur SQLite lors du chargement des embeddings: {e}\n{traceback.format_exc()}")
        return None, None, None
    finally:
        cursor.close()

def build_or_load_faiss_index(embeddings_list: list[np.ndarray], index_file_path: str) -> faiss.Index | None:
    """
    Construit un index FAISS si non existant, sinon le charge depuis le fichier.
    """
    index_path = Path(index_file_path)
    if index_path.exists():
        try:
            log_info(f"Chargement de l'index FAISS depuis {index_file_path}...")
            index = faiss.read_index(index_file_path)
            # Vérification simple : le nombre d'éléments dans l'index doit correspondre
            if index.ntotal != len(embeddings_list):
                log_warning(f"Le nombre d'éléments dans l'index FAISS chargé ({index.ntotal}) "
                            f"ne correspond pas au nombre d'embeddings actuels ({len(embeddings_list)}). "
                            f"Reconstruction de l'index.")
                # Forcer la reconstruction
                return _build_faiss_index(embeddings_list, index_file_path)
            log_info("Index FAISS chargé.")
            return index
        except Exception as e:
            log_error(f"Impossible de charger l'index FAISS depuis {index_file_path}: {e}. Reconstruction de l'index.")
            # Tentative de reconstruction si le chargement échoue
            return _build_faiss_index(embeddings_list, index_file_path)
    else:
        return _build_faiss_index(embeddings_list, index_file_path)

def _build_faiss_index(embeddings_list: list[np.ndarray], index_file_path: str) -> faiss.Index | None:
    """ Fonction interne pour construire et sauvegarder l'index FAISS. """
    if not embeddings_list:
        log_error("La liste d'embeddings est vide. Impossible de construire l'index FAISS.")
        return None

    try:
        embeddings_np = np.array(embeddings_list).astype('float32')
        dimension = embeddings_np.shape[1]
        log_info(f"Construction de l'index FAISS avec {embeddings_np.shape[0]} vecteurs de dimension {dimension}...")

        # IndexFlatL2 est simple et bon pour un nombre modéré de vecteurs.
        # Pour des millions de vecteurs, IndexIVFFlat serait plus performant après entraînement.
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_np)
        log_info("Index FAISS construit.")

        log_info(f"Sauvegarde de l'index FAISS vers {index_file_path}...")
        faiss.write_index(index, index_file_path)
        log_info("Index FAISS sauvegardé.")
        return index
    except Exception as e:
        log_error(f"Erreur lors de la construction ou sauvegarde de l'index FAISS: {e}\n{traceback.format_exc()}")
        return None

def embed_query_text(query_text: str, embedding_model: SentenceTransformer) -> np.ndarray | None:
    """Génère l'embedding pour le texte de la requête."""
    try:
        log_info(f"Génération de l'embedding pour la requête: '{query_text[:50]}...'")
        query_embedding = embedding_model.encode([query_text], convert_to_numpy=True)
        return query_embedding.astype('float32') # Assurer float32 pour FAISS
    except Exception as e:
        log_error(f"Erreur lors de la génération de l'embedding pour la requête: {e}\n{traceback.format_exc()}")
        return None

def search_similar_sections(
    faiss_index: faiss.Index,
    query_embedding: np.ndarray,
    k: int,
    section_ids_ordered: list[int],
    section_data_map: dict
) -> list[dict]:
    """
    Recherche dans l'index FAISS et retourne les textes des sections les plus similaires.
    """
    if query_embedding is None or query_embedding.ndim == 0 : # Vérification si query_embedding est vide ou non initialisé
        log_error("L'embedding de la requête est invalide ou vide.")
        return []
    if query_embedding.ndim == 1: # S'assurer que l'embedding est 2D pour la recherche
        query_embedding_2d = query_embedding.reshape(1, -1)
    else:
        query_embedding_2d = query_embedding

    log_info(f"Recherche des {k} sections les plus similaires...")
    try:
        distances, indices = faiss_index.search(query_embedding_2d, k)
        
        results = []
        for i in range(len(indices[0])):
            faiss_idx = indices[0][i]
            if faiss_idx == -1: # Peut arriver si k > nombre d'éléments dans l'index
                continue
            
            original_section_id = section_ids_ordered[faiss_idx] # Mapper l'index FAISS à notre id_section
            section_info = section_data_map.get(original_section_id)
            
            if section_info:
                results.append({
                    "id_section": original_section_id,
                    "code_cis": section_info["code_cis"],
                    "nom_section_normalise": section_info["nom_section_normalise"],
                    "texte_section": section_info["texte_section"],
                    "distance": float(distances[0][i])
                })
            else:
                log_warning(f"Aucune donnée trouvée pour section_id {original_section_id} (index FAISS {faiss_idx})")
        
        log_info(f"{len(results)} sections similaires trouvées.")
        return results
    except Exception as e:
        log_error(f"Erreur lors de la recherche FAISS: {e}\n{traceback.format_exc()}")
        return []

def query_llm_with_context(user_query: str, context_sections: list[dict], llm_model_name: str) -> str:
    """Construit le prompt et interroge le LLM via Ollama."""
    if not context_sections:
        log_warning("Aucun contexte fourni au LLM. La réponse pourrait être moins pertinente.")
        context_text = "Aucun contexte pertinent n'a été trouvé dans la base de données."
    else:
        context_text = "\n\n---\n\n".join(
            [f"Section Pertinente (CIS: {s['code_cis']}, Nom: {s['nom_section_normalise']}, ID: {s['id_section']}, Similarité: {1/(1+s['distance']):.2f}):\n{s['texte_section']}" 
             for s in context_sections]
        )

    prompt = f"""Tu es un assistant spécialisé dans l'analyse de Résumés des Caractéristiques du Produit (RCP) de médicaments.
Utilise UNIQUEMENT les informations fournies dans le CONTEXTE ci-dessous pour répondre à la QUESTION.
Sois précis, concis et factuel. Si l'information n'est pas dans le contexte, indique "L'information n'est pas disponible dans le contexte fourni."
Ne fais pas d'hypothèses et ne cherche pas d'informations en dehors du contexte.

CONTEXTE:
{context_text}

QUESTION:
{user_query}

RÉPONSE:
"""
    log_info("Envoi de la requête au LLM Ollama...")
    # print(f"\n--- PROMPT POUR OLLAMA (premiers 500 caractères) ---\n{prompt[:500]}...\n---------------------------------------------------\n")

    try:
        # Utilisation de ollama.chat pour les modèles "instruct"
        response = ollama.chat(
            model=llm_model_name,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                },
            ],
            # Options pour contrôler la génération (facultatif)
            # options={
            #     "temperature": 0.3, # Plus bas = plus déterministe
            #     "num_predict": 256  # Max tokens à générer
            # }
        )
        answer = response['message']['content']
        log_info("Réponse reçue du LLM.")
        return answer
    except Exception as e:
        log_error(f"Erreur lors de l'interrogation du LLM Ollama ({llm_model_name}): {e}\n{traceback.format_exc()}")
        return "Désolé, une erreur est survenue lors de la communication avec le modèle de langage."

def main():
    log_info(f"--- Démarrage de l'application de questions/réponses avec {OLLAMA_MODEL_NAME} ---")

    # 1. Connexion à la base de données
    conn = None
    try:
        conn = get_db_connection()

        # 2. Chargement des données et embeddings
        embeddings_list, section_ids_ordered, section_data_map = load_data_and_embeddings(conn)
        if not embeddings_list or not section_ids_ordered or not section_data_map:
            log_error("Impossible de charger les données nécessaires depuis la base. Arrêt.")
            return

        # 3. Chargement du modèle d'embedding (SentenceTransformer)
        log_info(f"Chargement du modèle d'embedding: {EMBEDDING_MODEL_NAME}...")
        try:
            embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            log_info("Modèle d'embedding chargé.")
        except Exception as e:
            log_error(f"Erreur lors du chargement du modèle SentenceTransformer: {e}\n{traceback.format_exc()}")
            return
            
        # 4. Construction ou chargement de l'index FAISS
        faiss_index = build_or_load_faiss_index(embeddings_list, FAISS_INDEX_FILE)
        if not faiss_index:
            log_error("Impossible de construire ou charger l'index FAISS. Arrêt.")
            return

        # 5. Boucle de questions/réponses
        log_info("Prêt à recevoir des questions. Tapez 'quitter' pour terminer.")
        while True:
            user_query = input("\nVotre question: ")
            if user_query.lower() == 'quitter':
                break
            if not user_query.strip():
                continue

            # a. Générer l'embedding de la requête
            query_embedding = embed_query_text(user_query, embedding_model)
            if query_embedding is None:
                print("Impossible de traiter la question.")
                continue

            # b. Recherche FAISS
            similar_sections = search_similar_sections(
                faiss_index,
                query_embedding,
                TOP_K_RESULTS,
                section_ids_ordered,
                section_data_map
            )

            # c. Interrogation du LLM avec le contexte
            llm_response = query_llm_with_context(user_query, similar_sections, OLLAMA_MODEL_NAME)

            # d. Affichage de la réponse
            print("\nRéponse du LLM:")
            print(llm_response)
            if similar_sections: # Afficher les sources si pertinent
                print("\nSources (sections les plus pertinentes utilisées comme contexte):")
                for i, sec in enumerate(similar_sections):
                    print(f"  {i+1}. CIS: {sec['code_cis']}, Section: '{sec['nom_section_normalise']}' (ID: {sec['id_section']}), Similarité: {1/(1+sec['distance']):.2f}")


    except Exception as e:
        log_error(f"Une erreur majeure est survenue dans le script principal: {e}\n{traceback.format_exc()}")
    finally:
        if conn:
            conn.close()
            log_info("Connexion à la base de données fermée.")
        log_info("--- Application terminée ---")

if __name__ == "__main__":
    # Avant de lancer :
    # 1. Assurez-vous qu'Ollama est lancé (`ollama serve` ou l'application de bureau Ollama)
    # 2. Assurez-vous que le modèle OLLAMA_MODEL_NAME est téléchargé (`ollama pull nom_du_modele`)
    main()