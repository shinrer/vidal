import sqlite3
import requests
from bs4 import BeautifulSoup
import json
import time
import datetime
import random
from pathlib import Path

# --- Configuration ---
DATABASE_NAME = "medicaments.db"
JSON_CIS_CODES_FILE = Path("unique_cis_codes.json")
RCP_URL_TEMPLATE = "https://base-donnees-publique.medicaments.gouv.fr/affichageDoc.php?specid={}&typedoc=R"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
REQUEST_TIMEOUT = 15  # seconds
MIN_DELAY = 1.0  # seconds
MAX_DELAY = 3.0  # seconds

# --- Logging (Simple Print-Based) ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_warning(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] WARNING: {message}")

def log_error(message: str, code_cis: str = None):
    error_msg = f"[{datetime.datetime.now().isoformat()}] ERROR: {message}"
    if code_cis:
        error_msg += f" (CIS: {code_cis})"
    print(error_msg)

# --- Database Functions ---
def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        return conn
    except sqlite3.Error as e:
        log_error(f"Database connection error: {e}")
        raise # Propagate error if DB connection fails

def load_cis_codes(json_file_path: Path) -> list:
    """Loads unique CIS codes from the specified JSON file."""
    log_info(f"Loading CIS codes from {json_file_path}...")
    if not json_file_path.exists():
        log_error(f"CIS codes JSON file not found: {json_file_path}")
        return [] # Return empty list to allow script to exit gracefully if main checks this
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            cis_codes = json.load(f)
        log_info(f"Loaded {len(cis_codes)} CIS codes.")
        return cis_codes
    except json.JSONDecodeError as e:
        log_error(f"Error decoding JSON from {json_file_path}: {e}")
        return []
    except Exception as e:
        log_error(f"Error loading CIS codes from {json_file_path}: {e}")
        return []

def get_processed_rcps(conn: sqlite3.Connection) -> set:
    """Fetches all CIS codes for which RCPs already exist in the database."""
    log_info("Fetching already processed RCP CIS codes from database...")
    processed_cis_set = set()
    try:
        with conn: # Using 'with conn' handles commit/rollback automatically for reads
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT code_cis FROM RCPs")
            rows = cursor.fetchall()
            for row in rows:
                if row[0]: # Ensure not None
                    processed_cis_set.add(row[0])
        log_info(f"Found {len(processed_cis_set)} already processed RCPs.")
        return processed_cis_set
    except sqlite3.Error as e:
        log_error(f"Error fetching processed RCPs: {e}")
        return processed_cis_set # Return whatever was fetched, or empty set

def extract_rcp_text(soup: BeautifulSoup) -> str:
    """
    Extracts and cleans the main RCP text from the parsed HTML (soup).
    This function will need refinement based on actual page structure.
    """
    # Common selectors to try (these are guesses and need verification)
    selectors = [
        '#textCont',             # Generic ID that might contain text
        '.textOnly',             # Class often used for text content
        'div[itemprop="description"]', # Schema.org itemprop
        '.doc-content',          # Common class for document content
        'article',               # HTML5 article tag
        '#document',             # Another common ID
        '#RCP',                  # Specific for RCP?
        '.content',              # General content class
        # More specific selectors if known, e.g., from inspecting actual pages
        # 'div.summary_section', # Example if RCP is broken into sections
    ]
    
    extracted_texts = []

    # Remove script and style tags first
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            log_info(f"Found elements with selector: '{selector}'")
            for element in elements:
                # Get text, ensuring spaces between inline elements, and strip leading/trailing whitespace
                text = element.get_text(separator=' ', strip=True) 
                if text:
                    extracted_texts.append(text)
            if extracted_texts: # If any selector yields text, assume it's the best one for now
                break 
    
    if not extracted_texts: # Fallback: try to get all text from body if no specific selector works
        log_warning("No specific selectors yielded RCP text, trying body...")
        body_text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""
        if body_text:
            extracted_texts.append(body_text)

    full_text = "\n\n".join(extracted_texts) # Join sections if multiple elements were found by one selector
    
    # Further cleaning (optional, can be expanded)
    # Remove excessive newlines (more than two consecutive)
    full_text = "\n".join([line for line in full_text.splitlines() if line.strip()]) # remove empty lines
    # full_text = re.sub(r'\n{3,}', '\n\n', full_text) # Reduce multiple newlines to max two

    return full_text.strip()


def insert_rcp_data(conn: sqlite3.Connection, code_cis: str, texte_rcp: str, extraction_date: str):
    """Inserts or replaces RCP data into the RCPs table."""
    try:
        with conn: # Context manager handles commit/rollback
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO RCPs (code_cis, texte_rcp, date_derniere_extraction_rcp)
                VALUES (?, ?, ?)
            """, (code_cis, texte_rcp, extraction_date))
        # log_info(f"Successfully inserted/replaced RCP for CIS: {code_cis}") # Logged by caller
    except sqlite3.Error as e:
        log_error(f"Database error inserting RCP for CIS {code_cis}: {e}")
        raise # Propagate to allow main loop to handle (e.g., skip)


# --- Main Crawling Logic ---
def crawl_single_rcp(conn: sqlite3.Connection, code_cis: str, retries: int = 1):
    """
    Crawls and processes a single RCP document for a given CIS code.
    Returns True if successfully processed or skipped (404), False if a persistent error occurred.
    """
    url = RCP_URL_TEMPLATE.format(code_cis)
    log_info(f"Processing CIS: {code_cis} - URL: {url}")

    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY)) # Polite delay

    try:
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            rcp_text = extract_rcp_text(soup)

            if not rcp_text or len(rcp_text) < 100: # Arbitrary short length check
                log_warning(f"RCP text extracted for CIS {code_cis} seems empty or too short. Page structure might have changed or text is minimal.")
                # Decide if to save or not. For now, save what's found.
                # If it's consistently an issue, this might warrant not saving.

            current_datetime_iso = datetime.datetime.now().isoformat()
            insert_rcp_data(conn, code_cis, rcp_text, current_datetime_iso)
            log_info(f"Successfully crawled and saved RCP for CIS: {code_cis}")
            return True

        elif response.status_code == 404:
            log_warning(f"RCP not found (404) for CIS: {code_cis} at URL: {url}")
            # Optionally, insert a record indicating it's a known 404? For now, just skip.
            return True # Treat as "processed" for skipping purposes

        else:
            log_error(f"HTTP error {response.status_code} for CIS {code_cis}: {response.reason}", code_cis=code_cis)
            if retries > 0 and response.status_code >= 500: # Retry for server errors
                log_info(f"Retrying CIS {code_cis} after a longer delay...")
                time.sleep(random.uniform(5.0, 10.0))
                return crawl_single_rcp(conn, code_cis, retries - 1)
            return False # Persistent non-404 client error or server error after retries

    except requests.exceptions.Timeout:
        log_error(f"Timeout occurred for CIS {code_cis}", code_cis=code_cis)
        if retries > 0:
            log_info(f"Retrying CIS {code_cis} after a longer delay (timeout)...")
            time.sleep(random.uniform(5.0, 10.0))
            return crawl_single_rcp(conn, code_cis, retries - 1)
        return False
    except requests.exceptions.RequestException as e:
        log_error(f"Request exception for CIS {code_cis}: {e}", code_cis=code_cis)
        # Could implement more nuanced retry for specific request exceptions (e.g. ConnectionError)
        return False # Generally, non-timeout request exceptions are not retried here
    except sqlite3.Error: # Handled by insert_rcp_data by raising, caught here
        log_error(f"Database error during processing of CIS {code_cis} (already logged by insert_rcp_data). Skipping.", code_cis=code_cis)
        return False # DB error, don't retry this CIS in this run
    except Exception as e:
        log_error(f"Unexpected error processing CIS {code_cis}: {e}", code_cis=code_cis)
        return False


def crawl_all_rcps():
    """Main function to orchestrate the RCP crawling process."""
    log_info("--- Starting RCP Crawler Script ---")
    
    cis_codes_to_process = load_cis_codes(JSON_CIS_CODES_FILE)
    if not cis_codes_to_process:
        log_error("No CIS codes loaded. Exiting.")
        return

    conn = None
    try:
        conn = get_db_connection()
        processed_cis_set = get_processed_rcps(conn)
        
        total_codes = len(cis_codes_to_process)
        skipped_due_to_existing = 0
        successfully_processed_new = 0
        failed_processing = 0

        for i, code_cis in enumerate(cis_codes_to_process):
            log_info(f"Processing {i+1}/{total_codes}: CIS {code_cis}")
            if code_cis in processed_cis_set:
                log_info(f"Skipping CIS {code_cis}, RCP already in database.")
                skipped_due_to_existing += 1
                continue
            
            if crawl_single_rcp(conn, code_cis):
                successfully_processed_new +=1
            else:
                failed_processing +=1
            
            if (i + 1) % 50 == 0: # Log progress every 50 CISS
                log_info(f"Progress: {i+1}/{total_codes} CISS processed. Current stats: {successfully_processed_new} new, {skipped_due_to_existing} skipped, {failed_processing} failed.")

        log_info("--- RCP Crawling Finished ---")
        log_info(f"Summary: Total CIS codes: {total_codes}")
        log_info(f"  Skipped (already in DB): {skipped_due_to_existing}")
        log_info(f"  Successfully processed new: {successfully_processed_new}")
        log_info(f"  Failed to process: {failed_processing}")

    except Exception as e: # Catch-all for major issues during setup or loop
        log_error(f"Major error in crawl_all_rcps: {e}")
    finally:
        if conn:
            conn.close()
            log_info("Database connection closed.")

if __name__ == "__main__":
    crawl_all_rcps()
