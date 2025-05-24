import json
from pathlib import Path
import sqlite3
import sys # For printing errors and exiting if libraries are missing

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: SentenceTransformers library not found. Please install it: pip install sentence-transformers", file=sys.stderr)
    # Depending on how critical this is at import time, you might sys.exit(1)
    # For now, we'll let it fail later if load_ai_resources is called.
    SentenceTransformer = None 

try:
    import faiss
except ImportError:
    print("ERROR: FAISS library not found. Please install it: pip install faiss-cpu (or faiss-gpu)", file=sys.stderr)
    faiss = None

try:
    import numpy as np
except ImportError:
    print("ERROR: NumPy library not found. Please install it: pip install numpy", file=sys.stderr)
    np = None

# --- Configuration & Paths ---
AI_PROCESSING_DIR = Path(__file__).resolve().parent / 'ai_processing'
FAISS_INDEX_PATH = AI_PROCESSING_DIR / 'rcp_embeddings.faiss'
FAISS_ID_MAP_PATH = AI_PROCESSING_DIR / 'faiss_index_to_chunk_id.json'
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2' # Ensure this matches generate_embeddings.py
DB_PATH = Path(__file__).resolve().parent.parent / 'medicaments.db' # Assuming ai_models.py is in app/

# --- Global Variables for Caching AI Resources ---
sentence_model = None
faiss_index = None
id_to_chunk_id_map = None # This will be a list mapping FAISS index to original chunk_id

# --- Logging (Simple Print-Based) ---
def log_info(message: str):
    print(f"INFO: {message}", file=sys.stderr)

def log_error(message: str):
    print(f"ERROR: {message}", file=sys.stderr)

# --- Import LLM Interaction function ---
try:
    from app.ai_processing.llm_interface import test_local_llm as get_llm_response
    from app.ai_processing.llm_interface import DEFAULT_LLM_MODEL
except ImportError:
    log_error("Could not import LLM interface from app.ai_processing.llm_interface.")
    get_llm_response = None # Ensure it's defined for type hinting and checks
    DEFAULT_LLM_MODEL = "mistral:7b-instruct-q4_K_M" # Fallback if not imported

# --- Load AI Resources ---
def load_ai_resources(force_reload: bool = False):
    """
    Loads the Sentence Transformer model, FAISS index, and ID map.
    Caches them in global variables to avoid reloading on every request.
    """
    global sentence_model, faiss_index, id_to_chunk_id_map

    # 0. Check library availability
    if SentenceTransformer is None:
        log_error("SentenceTransformer library is not available. Cannot load AI model.")
        return False # Indicate failure
    if faiss is None:
        log_error("FAISS library is not available. Cannot load FAISS index.")
        return False
    if np is None:
        log_error("NumPy library is not available. Cannot proceed.")
        return False

    # 1. Load Sentence Transformer Model
    if sentence_model is None or force_reload:
        log_info(f"Loading Sentence Transformer model: {MODEL_NAME}...")
        try:
            sentence_model = SentenceTransformer(MODEL_NAME)
            log_info("Sentence Transformer model loaded successfully.")
        except Exception as e:
            log_error(f"Error loading Sentence Transformer model: {e}")
            sentence_model = None # Ensure it's None if loading failed
            return False # Indicate failure

    # 2. Load FAISS Index
    if faiss_index is None or force_reload:
        log_info(f"Loading FAISS index from: {FAISS_INDEX_PATH}...")
        if FAISS_INDEX_PATH.exists():
            try:
                faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
                log_info(f"FAISS index loaded successfully. Index has {faiss_index.ntotal} vectors.")
            except Exception as e:
                log_error(f"Error loading FAISS index: {e}")
                faiss_index = None
                return False
        else:
            log_error(f"FAISS index file not found at {FAISS_INDEX_PATH}.")
            faiss_index = None
            return False

    # 3. Load FAISS ID to Chunk ID Map
    if id_to_chunk_id_map is None or force_reload:
        log_info(f"Loading FAISS ID map from: {FAISS_ID_MAP_PATH}...")
        if FAISS_ID_MAP_PATH.exists():
            try:
                with open(FAISS_ID_MAP_PATH, 'r', encoding='utf-8') as f:
                    id_to_chunk_id_map = json.load(f) # This is a list of original chunk_ids
                log_info(f"FAISS ID map loaded successfully. Map contains {len(id_to_chunk_id_map)} entries.")
            except json.JSONDecodeError as e:
                log_error(f"Error decoding JSON from FAISS ID map file: {e}")
                id_to_chunk_id_map = None
                return False
            except Exception as e:
                log_error(f"Error loading FAISS ID map: {e}")
                id_to_chunk_id_map = None
                return False
        else:
            log_error(f"FAISS ID map file not found at {FAISS_ID_MAP_PATH}.")
            id_to_chunk_id_map = None
            return False
            
    # Verify consistency between index and map
    if faiss_index is not None and id_to_chunk_id_map is not None:
        if faiss_index.ntotal != len(id_to_chunk_id_map):
            log_error(f"Mismatch between FAISS index size ({faiss_index.ntotal}) and ID map size ({len(id_to_chunk_id_map)}). Resources might be corrupted or out of sync.")
            # Optionally, invalidate resources here
            # faiss_index = None
            # id_to_chunk_id_map = None
            # return False # Or allow to proceed with caution
    
    # Check if all critical resources are loaded
    if sentence_model and faiss_index and id_to_chunk_id_map:
        log_info("All AI resources loaded and checked.")
        return True
    else:
        log_error("One or more AI resources failed to load.")
        return False


# --- Semantic Search Function ---
def search_similar_rcp_chunks(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Searches for RCP text chunks similar to the query_text using sentence embeddings and FAISS.
    """
    # Ensure AI resources are loaded
    if not (sentence_model and faiss_index and id_to_chunk_id_map):
        log_info("AI resources not loaded yet. Attempting to load...")
        if not load_ai_resources(): # Attempt to load
            log_error("Failed to load AI resources. Cannot perform search.")
            return [] # Return empty if resources cannot be loaded

    if not query_text or not query_text.strip():
        log_info("Search query is empty. Returning no results.")
        return []

    log_info(f"Performing semantic search for query: '{query_text[:50]}...', top_k={top_k}")

    try:
        # 1. Generate Query Embedding
        query_embedding = sentence_model.encode([query_text], convert_to_numpy=True)
        if query_embedding is None or query_embedding.ndim != 2:
            log_error("Failed to generate a valid query embedding.")
            return []

        # 2. Perform FAISS Search
        # Ensure faiss_index.ntotal is checked if index might be empty
        if faiss_index.ntotal == 0:
            log_warning("FAISS index is empty. No search can be performed.")
            return []
            
        # Adjust top_k if it's larger than the number of items in the index
        actual_top_k = min(top_k, faiss_index.ntotal)
        if actual_top_k == 0: # Should be caught by ntotal check, but good practice
            log_warning("No items in FAISS index to search.")
            return []

        distances, indices = faiss_index.search(query_embedding, actual_top_k)
        
        result_indices = indices[0]
        result_distances = distances[0]
        
        retrieved_db_chunk_ids = []
        scores = []

        for i, faiss_idx in enumerate(result_indices):
            if faiss_idx >= 0 and faiss_idx < len(id_to_chunk_id_map):
                retrieved_db_chunk_ids.append(id_to_chunk_id_map[faiss_idx])
                # L2 distance; smaller is better. Convert to a "similarity score" (0-1, higher is better)
                # This is a simple way; more sophisticated scoring might be needed.
                # Max distance is not bounded, so 1 / (1 + distance) is a common way to map.
                score = 1 / (1 + result_distances[i]) 
                scores.append(score)
            else:
                log_warning(f"FAISS index {faiss_idx} is out of bounds for id_to_chunk_id_map. Skipping.")


        if not retrieved_db_chunk_ids:
            log_info("No valid chunk IDs retrieved from FAISS search.")
            return []

        # 3. Fetch Chunk Texts from Database
        results_with_text = []
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Create a placeholder string like (?, ?, ?) for the IN clause
            placeholders = ', '.join(['?'] * len(retrieved_db_chunk_ids))
            query_sql = f"""
                SELECT rc.chunk_id, rc.code_cis, rc.chunk_text, m.denomination 
                FROM RCP_Chunks rc
                JOIN Medicaments m ON rc.code_cis = m.code_cis
                WHERE rc.chunk_id IN ({placeholders})
            """
            # Fetch chunks and preserve the order from FAISS results
            db_chunks_dict = {}
            for row in cursor.execute(query_sql, retrieved_db_chunk_ids):
                db_chunks_dict[row['chunk_id']] = dict(row)

            # Reconstruct results in the order of similarity, adding score
            for i, chunk_id in enumerate(retrieved_db_chunk_ids):
                if chunk_id in db_chunks_dict:
                    chunk_data = db_chunks_dict[chunk_id]
                    results_with_text.append({
                        'chunk_id': chunk_id,
                        'code_cis': chunk_data['code_cis'],
                        'denomination': chunk_data['denomination'],
                        'text': chunk_data['chunk_text'],
                        'score': scores[i] 
                    })
                else:
                    log_warning(f"Chunk ID {chunk_id} retrieved from FAISS not found in database. Skipping.")
            
            log_info(f"Retrieved {len(results_with_text)} chunks from database with their text.")

        except sqlite3.Error as e:
            log_error(f"Database error while fetching chunk texts: {e}")
            return [] # Return empty on DB error
        finally:
            if conn:
                conn.close()
        
        return results_with_text

    except Exception as e:
        log_error(f"An unexpected error occurred during semantic search: {e}")
        import traceback
        traceback.print_exc()
        return []

# --- Initialization Call (Optional) ---
# Uncomment the line below to pre-load models when this module is imported.
# This is useful if the Flask app imports this module at startup.
# Be mindful of server startup time if models are large or loading is slow.
# print("Attempting to pre-load AI resources on module import...")
# load_ai_resources()

if __name__ == '__main__':
    print("--- Testing AI Models Module ---")
    
    print(f"DB_PATH: {DB_PATH}")
    print(f"FAISS_INDEX_PATH: {FAISS_INDEX_PATH}")
    print(f"FAISS_ID_MAP_PATH: {FAISS_ID_MAP_PATH}")

    # 1. Test loading resources
    print("\n1. Testing load_ai_resources()...")
    resources_loaded = load_ai_resources()
    if resources_loaded:
        print("AI resources loaded successfully for testing.")
        print(f"  Sentence model: {'Loaded' if sentence_model else 'Not Loaded'}")
        print(f"  FAISS index: {'Loaded' if faiss_index else 'Not Loaded'}")
        if faiss_index:
            print(f"    Index ntotal: {faiss_index.ntotal}")
        print(f"  ID map: {'Loaded' if id_to_chunk_id_map else 'Not Loaded'}")
        if id_to_chunk_id_map:
            print(f"    Map size: {len(id_to_chunk_id_map)}")

        # 2. Test search (only if resources loaded)
        if faiss_index and faiss_index.ntotal > 0: # Check if index has items
            print("\n2. Testing search_similar_rcp_chunks()...")
            # Example query, replace with something relevant if you have data
            test_query = "Quels sont les effets secondaires de ce médicament ?" 
            search_results = search_similar_rcp_chunks(test_query, top_k=3)
            
            if search_results:
                print(f"\nFound {len(search_results)} results for query: '{test_query}'")
                for i, result in enumerate(search_results):
                    print(f"\nResult {i+1}:")
                    print(f"  CIS: {result['code_cis']}")
                    print(f"  Denomination: {result['denomination']}")
                    print(f"  Chunk ID: {result['chunk_id']}")
                    print(f"  Score: {result['score']:.4f}")
                    print(f"  Text snippet: {result['text'][:200]}...")
            else:
                print(f"No results found for query: '{test_query}' or an error occurred during search.")
        else:
            print("\nSkipping search test as FAISS index is empty or not loaded.")
            print("This is expected if 'generate_embeddings.py' has not been run successfully with data.")

    else:
        print("\nAI resources failed to load. Cannot perform further tests.")
        print("Please ensure that 'generate_embeddings.py' has been run successfully and all paths are correct.")
        print("Also check if required libraries (sentence-transformers, faiss-cpu/gpu, numpy) are installed.")
