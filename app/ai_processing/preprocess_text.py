import sqlite3
from pathlib import Path
import re
import sys # For printing progress

# --- Database Configuration ---
# Assuming medicaments.db is in the project root (parent of 'app' directory, which is parent of 'ai_processing')
DB_PATH = Path(__file__).resolve().parent.parent.parent / 'medicaments.db'

# --- Helper Functions ---
def get_db_connection():
    """
    Establishes and returns a SQLite database connection.
    The connection is configured to return rows as dictionary-like objects (sqlite3.Row).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error to {DB_PATH}: {e}")
        raise

def create_rcp_chunks_table(conn: sqlite3.Connection):
    """
    Creates the RCP_Chunks table and its index if they don't exist.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS RCP_Chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT NOT NULL,
            chunk_order INTEGER NOT NULL, -- To maintain order of chunks for a given RCP
            chunk_text TEXT NOT NULL,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rcp_chunks_code_cis ON RCP_Chunks(code_cis)
        """)
        conn.commit()
        print("RCP_Chunks table and index ensured.")
    except sqlite3.Error as e:
        print(f"Error creating RCP_Chunks table or index: {e}")
        raise # Propagate error

# --- Text Cleaning and Chunking Logic ---
def clean_text(text_content: str) -> str:
    """
    Cleans the text content.
    - Removes excessive newlines.
    - Replaces multiple spaces/tabs with a single space.
    - Strips leading/trailing whitespace from each line.
    """
    if not text_content:
        return ""

    # Replace multiple newlines (possibly with whitespace in between) with a single newline
    cleaned = re.sub(r'\n\s*\n', '\n', text_content)
    # Replace multiple spaces/tabs with a single space
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    # Strip leading/trailing whitespace from the whole text and from each line
    lines = [line.strip() for line in cleaned.splitlines()]
    cleaned = "\n".join(filter(None, lines)) # Filter out empty lines that might result from stripping

    return cleaned.strip()

def chunk_text(text_content: str, chunk_size_chars: int = 1000, overlap_chars: int = 100) -> list[str]:
    """
    Splits cleaned text into overlapping chunks.
    Attempts paragraph-based splitting first, then falls back to character-based if needed.
    """
    if not text_content:
        return []

    chunks = []
    # Attempt paragraph-based chunking
    # Paragraphs are often separated by double newlines in plain text extractions.
    # clean_text might have reduced these to single newlines if they were originally \n\s*\n.
    # If clean_text produces text where paragraphs are separated by a single \n,
    # then this split needs to be by '\n'.
    # Assuming paragraphs are separated by what results in `\n` after `clean_text`.
    paragraphs = text_content.split('\n') # Split by single newline as clean_text consolidates newlines
    
    current_chunk = ""
    current_chunk_len = 0

    for p_idx, paragraph in enumerate(paragraphs):
        if not paragraph.strip(): # Skip empty paragraphs
            continue
        
        paragraph_len = len(paragraph)

        if current_chunk_len + paragraph_len + (1 if current_chunk else 0) <= chunk_size_chars:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n" + paragraph
                current_chunk_len += 1 + paragraph_len
            else:
                current_chunk = paragraph
                current_chunk_len = paragraph_len
        else:
            # Paragraph is too large for the current chunk, or current chunk is full
            if current_chunk: # Finalize current chunk
                chunks.append(current_chunk)
            
            # Start new chunk with the current paragraph
            # If the paragraph itself is larger than chunk_size_chars, it will be a chunk on its own
            # (or could be further split by character if desired, but for now, keep paragraph intact if possible)
            current_chunk = paragraph
            current_chunk_len = paragraph_len

            # Handle paragraphs that are themselves larger than chunk_size_chars
            # This simple paragraph grouper might create chunks larger than chunk_size_chars
            # if a single paragraph is very long.
            if current_chunk_len > chunk_size_chars:
                # For simplicity now, a very long paragraph becomes its own chunk.
                # A more advanced version would split this large paragraph.
                print(f"Warning: Paragraph {p_idx} (length {current_chunk_len}) exceeds chunk size {chunk_size_chars}. Keeping as one chunk.")
                # If we decide to split it, we'd use character-based splitting for this specific paragraph.
                # For now, we accept this larger chunk.
                pass # Chunk will be added in the next iteration or at the end.

    # Add the last remaining chunk
    if current_chunk:
        chunks.append(current_chunk)

    # Implement overlap if character-based splitting was the primary method or if needed for paragraph chunks
    # The current paragraph-based chunking does not explicitly implement overlap in the same way
    # as character-based. Overlap is implicitly handled if paragraphs are small.
    # If explicit character-based overlap is required for all cases, the logic would be different:
    if not chunks or (len(chunks) == 1 and len(chunks[0]) > chunk_size_chars * 1.2): # Fallback or if paragraph chunking is insufficient
        print("Using character-based chunking due to very large single chunk or no paragraph chunks.")
        chunks = [] # Reset chunks for character-based approach
        start = 0
        while start < len(text_content):
            end = start + chunk_size_chars
            chunk = text_content[start:end]
            chunks.append(chunk)
            if end >= len(text_content):
                break
            start += (chunk_size_chars - overlap_chars)
            if start >= len(text_content): # Avoid creating an empty chunk at the very end
                break
    
    return chunks


# --- Main Processing Function ---
def process_all_rcps():
    """
    Fetches all RCP texts, cleans and chunks them, and stores them in RCP_Chunks.
    """
    print("--- Starting RCP Text Preprocessing ---")
    conn = None
    try:
        conn = get_db_connection()
        create_rcp_chunks_table(conn)

        print("Clearing existing data from RCP_Chunks table...")
        with conn: # Use 'with conn' for auto-commit/rollback of this single statement
            cursor = conn.cursor()
            cursor.execute("DELETE FROM RCP_Chunks")
        print("RCP_Chunks table cleared.")

        cursor = conn.cursor() # Re-get cursor if needed, or use same one
        cursor.execute("SELECT code_cis, texte_rcp FROM RCPs")
        rcps_to_process = cursor.fetchall()

        total_rcps = len(rcps_to_process)
        print(f"Found {total_rcps} RCPs to process.")

        for i, rcp_row in enumerate(rcps_to_process):
            code_cis = rcp_row['code_cis']
            texte_rcp = rcp_row['texte_rcp']
            
            # Basic progress printing
            sys.stdout.write(f"\rProcessing RCP {i+1}/{total_rcps} (CIS: {code_cis})")
            sys.stdout.flush()

            if not texte_rcp or not texte_rcp.strip():
                print(f"\nSkipping CIS {code_cis}: RCP text is empty or None.")
                continue

            cleaned_rcp = clean_text(texte_rcp)
            if not cleaned_rcp:
                print(f"\nSkipping CIS {code_cis}: Cleaned RCP text is empty.")
                continue
                
            chunks = chunk_text(cleaned_rcp) # Uses default chunk/overlap sizes

            if not chunks:
                print(f"\nSkipping CIS {code_cis}: No chunks generated from RCP text.")
                continue

            try:
                with conn: # Transaction for all chunks of a single RCP
                    for chunk_order, chunk_text_content in enumerate(chunks):
                        conn.execute("""
                            INSERT INTO RCP_Chunks (code_cis, chunk_order, chunk_text)
                            VALUES (?, ?, ?)
                        """, (code_cis, chunk_order, chunk_text_content))
                # print(f"\nInserted {len(chunks)} chunks for CIS {code_cis}.") # Too verbose for many RCPs
            except sqlite3.Error as e:
                print(f"\nError inserting chunks for CIS {code_cis}: {e}. Skipping this RCP.")
                # If one chunk fails, the transaction for this RCP will be rolled back.
        
        sys.stdout.write("\n") # Newline after progress bar
        print("--- RCP Text Preprocessing Finished ---")

    except sqlite3.Error as e:
        print(f"A database error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    # Ensure DB exists for testing
    if not DB_PATH.exists():
        print(f"Database file {DB_PATH} does not exist. Please run previous scripts to create and populate it.")
        print("This script (preprocess_text.py) requires an existing database with RCPs table.")
    else:
        process_all_rcps()
