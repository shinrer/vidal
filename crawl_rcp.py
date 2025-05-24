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
def crawl_single_rcp(conn: sqlite3.Connection, code_cis: str, retries: int = 1) -> tuple[bool, str | None]:
    """
    Crawls and processes a single RCP document for a given CIS code.
    Returns (success_status, server_last_modified_date_str).
    success_status is True if processed/skipped (404), False on persistent error.
    server_last_modified_date_str is the 'Last-Modified' header or None.
    """
    url = RCP_URL_TEMPLATE.format(code_cis)
    log_info(f"Processing CIS: {code_cis} - URL: {url}")
    server_last_modified_date_str = None

    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    try:
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
        server_last_modified_date_str = response.headers.get('Last-Modified')
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            rcp_text = extract_rcp_text(soup)

            if not rcp_text or len(rcp_text) < 100:
                log_warning(f"RCP text for CIS {code_cis} seems empty/short. Page structure might have changed.")
            
            current_datetime_iso = datetime.datetime.now().isoformat()
            insert_rcp_data(conn, code_cis, rcp_text, current_datetime_iso)
            log_info(f"Successfully crawled/saved RCP for CIS: {code_cis}")
            return True, server_last_modified_date_str

        elif response.status_code == 404:
            log_warning(f"RCP not found (404) for CIS: {code_cis} at URL: {url}")
            return True, server_last_modified_date_str # Treat as "processed" for skipping

        else:
            log_error(f"HTTP error {response.status_code} for CIS {code_cis}: {response.reason}", code_cis=code_cis)
            if retries > 0 and response.status_code >= 500:
                log_info(f"Retrying CIS {code_cis} after a longer delay...")
                time.sleep(random.uniform(5.0, 10.0))
                return crawl_single_rcp(conn, code_cis, retries - 1)
            return False, server_last_modified_date_str

    except requests.exceptions.Timeout:
        log_error(f"Timeout for CIS {code_cis}", code_cis=code_cis)
        if retries > 0:
            log_info(f"Retrying CIS {code_cis} (timeout)...")
            time.sleep(random.uniform(5.0, 10.0))
            return crawl_single_rcp(conn, code_cis, retries - 1)
        return False, server_last_modified_date_str
    except requests.exceptions.RequestException as e:
        log_error(f"Request exception for CIS {code_cis}: {e}", code_cis=code_cis)
        return False, server_last_modified_date_str
    except sqlite3.Error:
        log_error(f"DB error for CIS {code_cis} (already logged). Skipping.", code_cis=code_cis)
        return False, server_last_modified_date_str
    except Exception as e:
        log_error(f"Unexpected error processing CIS {code_cis}: {e}", code_cis=code_cis)
        return False, server_last_modified_date_str

def get_rcp_extraction_date_from_db(conn: sqlite3.Connection, code_cis: str) -> str | None:
    """Fetches the date_derniere_extraction_rcp for a given CIS from the RCPs table."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT date_derniere_extraction_rcp FROM RCPs WHERE code_cis = ?", (code_cis,))
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.Error as e:
        log_error(f"Error fetching RCP extraction date for CIS {code_cis}: {e}")
        return None

def parse_http_date(date_str: str) -> datetime.datetime | None:
    """Parses an HTTP-style date string (RFC 1123) into a datetime object."""
    if not date_str:
        return None
    try:
        # Example: "Wed, 21 Oct 2015 07:28:00 GMT"
        return datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError as e:
        log_warning(f"Could not parse HTTP date string '{date_str}': {e}")
        return None

def crawl_all_rcps():
    """Main function to orchestrate the RCP crawling process with targeted updates."""
    log_info("--- Starting RCP Crawler Script (Enhanced Update Logic) ---")
    
    latest_cis_list = load_cis_codes(JSON_CIS_CODES_FILE)
    if not latest_cis_list:
        log_error("No CIS codes loaded from JSON. Exiting.")
        return

    conn = None
    try:
        conn = get_db_connection()
        db_rcp_cis_list_set = get_processed_rcps(conn) # This returns a set
        latest_cis_set = set(latest_cis_list)

        new_cis_to_crawl = latest_cis_set - db_rcp_cis_list_set
        disappeared_cis_to_delete = db_rcp_cis_list_set - latest_cis_set
        existing_cis_to_check = latest_cis_set.intersection(db_rcp_cis_list_set)

        log_info(f"Total CIS codes from JSON: {len(latest_cis_set)}")
        log_info(f"CIS codes already in RCPs DB: {len(db_rcp_cis_list_set)}")
        log_info(f"New CIS codes to crawl: {len(new_cis_to_crawl)}")
        log_info(f"Disappeared CIS codes to delete from RCPs: {len(disappeared_cis_to_delete)}")
        log_info(f"Existing CIS codes to check for updates: {len(existing_cis_to_check)}")

        # 1. Process Disappeared CIS Codes
        if disappeared_cis_to_delete:
            log_info(f"Processing {len(disappeared_cis_to_delete)} disappeared CIS codes for RCP deletion...")
            deleted_count = 0
            for i, code_cis in enumerate(disappeared_cis_to_delete):
                try:
                    with conn: # Auto-commit/rollback for each deletion for simplicity here
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM RCPs WHERE code_cis = ?", (code_cis,))
                        if cursor.rowcount > 0:
                            log_info(f"({i+1}/{len(disappeared_cis_to_delete)}) Deleted RCP for disappeared CIS: {code_cis}")
                            deleted_count +=1
                        else:
                            log_warning(f"({i+1}/{len(disappeared_cis_to_delete)}) No RCP found in DB to delete for supposedly disappeared CIS: {code_cis}")
                except sqlite3.Error as e:
                    log_error(f"Error deleting RCP for CIS {code_cis}: {e}")
            log_info(f"Finished deleting RCPs for disappeared CIS codes. Total deleted: {deleted_count}")
        
        # 2. Process New CIS Codes
        processed_new_count = 0
        failed_new_count = 0
        if new_cis_to_crawl:
            log_info(f"Processing {len(new_cis_to_crawl)} new CIS codes for RCP crawling...")
            for i, code_cis in enumerate(new_cis_to_crawl):
                log_info(f"Crawling NEW ({i+1}/{len(new_cis_to_crawl)}): CIS {code_cis}")
                success, _ = crawl_single_rcp(conn, code_cis)
                if success:
                    processed_new_count += 1
                else:
                    failed_new_count += 1
            log_info(f"Finished crawling new CIS codes. Success: {processed_new_count}, Failed: {failed_new_count}")

        # 3. Process Existing/Common CIS Codes
        updated_existing_count = 0
        failed_existing_count = 0
        skipped_existing_count = 0 # Count those not needing update
        if existing_cis_to_check:
            log_info(f"Processing {len(existing_cis_to_check)} existing CIS codes for potential RCP update...")
            for i, code_cis in enumerate(existing_cis_to_check):
                log_info(f"Checking EXISTING ({i+1}/{len(existing_cis_to_check)}): CIS {code_cis}")
                needs_recrawl = False
                reason = ""

                # Attempt Strategy 1: Last-Modified Header
                # For this, crawl_single_rcp needs to return the header.
                # We will do a HEAD request first, if possible, or analyze response from GET.
                # For simplicity, crawl_single_rcp already does a GET and can return the header.
                
                # To avoid a full GET just for the date, let's try a HEAD request first.
                server_last_modified_header = None
                try:
                    head_url = RCP_URL_TEMPLATE.format(code_cis)
                    time.sleep(random.uniform(0.5, 1.5)) # Shorter delay for HEAD
                    head_response = requests.head(head_url, headers={'User-Agent': USER_AGENT}, timeout=10, allow_redirects=True)
                    server_last_modified_header = head_response.headers.get('Last-Modified')
                except requests.RequestException as e:
                    log_warning(f"HEAD request failed for CIS {code_cis}: {e}. Will proceed to GET or age-based check.")

                if server_last_modified_header:
                    server_date_dt = parse_http_date(server_last_modified_header)
                    if server_date_dt:
                        db_extraction_date_str = get_rcp_extraction_date_from_db(conn, code_cis)
                        if db_extraction_date_str:
                            try:
                                db_date_dt = datetime.datetime.fromisoformat(db_extraction_date_str)
                                # Make db_date_dt timezone-aware if server_date_dt is (HTTP dates are GMT/UTC)
                                # Assuming server_date_dt is UTC from parse_http_date.
                                # ISO format might or might not have TZ. If not, assume local or UTC based on how it was stored.
                                # For simplicity, if db_date_dt is naive, assume it's compatible with UTC for comparison.
                                if db_date_dt.tzinfo is None and server_date_dt.tzinfo is not None:
                                    db_date_dt = db_date_dt.replace(tzinfo=datetime.timezone.utc) 

                                if server_date_dt > db_date_dt:
                                    needs_recrawl = True
                                    reason = f"Server 'Last-Modified' ({server_last_modified_header}) is newer than DB date ({db_extraction_date_str})."
                                else:
                                    reason = "Server 'Last-Modified' not newer. Skipping re-crawl based on date header."
                            except ValueError:
                                log_warning(f"Could not parse DB date '{db_extraction_date_str}' for CIS {code_cis}. Will re-crawl.")
                                needs_recrawl = True # Fallback to re-crawl if DB date is unparseable
                                reason = "Could not parse DB date for comparison."
                        else:
                            needs_recrawl = True # No DB date, so crawl
                            reason = "No previous extraction date in DB."
                    else: # Could not parse server Last-Modified header
                        log_warning(f"Could not parse 'Last-Modified' header ('{server_last_modified_header}') for CIS {code_cis}. Falling back to age-based check.")
                        # Fall through to Strategy 2
                
                if not needs_recrawl and not server_last_modified_header: # If Strategy 1 was skipped or failed to yield a decision
                    # Strategy 2: Age-Based Re-crawl
                    db_extraction_date_str = get_rcp_extraction_date_from_db(conn, code_cis)
                    if db_extraction_date_str:
                        try:
                            db_date_dt = datetime.datetime.fromisoformat(db_extraction_date_str)
                            # Ensure comparison is between offset-naive and offset-aware or both aware.
                            # Assuming now() is naive (local time). Convert db_date_dt to naive if it's aware.
                            if db_date_dt.tzinfo is not None:
                                db_date_dt = db_date_dt.astimezone(None).replace(tzinfo=None) # Convert to local naive

                            if (datetime.datetime.now() - db_date_dt).days > 30:
                                needs_recrawl = True
                                reason = f"RCP data older than 30 days (extracted: {db_extraction_date_str})."
                            else:
                                reason = "RCP data not older than 30 days. Skipping re-crawl."
                        except ValueError:
                            log_warning(f"Could not parse DB date '{db_extraction_date_str}' for CIS {code_cis} for age check. Re-crawling.")
                            needs_recrawl = True
                            reason = "Could not parse DB date for age-based check."
                    else:
                        needs_recrawl = True # No DB date, so crawl
                        reason = "No previous extraction date in DB (age-based check)."
                
                if needs_recrawl:
                    log_info(f"Re-crawling CIS {code_cis}: {reason}")
                    success, _ = crawl_single_rcp(conn, code_cis)
                    if success:
                        updated_existing_count += 1
                    else:
                        failed_existing_count += 1
                else:
                    log_info(f"Skipping re-crawl for CIS {code_cis}: {reason}")
                    skipped_existing_count +=1
            
            log_info(f"Finished checking existing CIS codes. Updated: {updated_existing_count}, Failed: {failed_existing_count}, Skipped (up-to-date): {skipped_existing_count}")


        log_info("--- RCP Crawler Enhanced Update Finished ---")
        log_info(f"Summary - Total from JSON: {len(latest_cis_set)}")
        log_info(f"  Disappeared RCPs deleted: {deleted_count if 'deleted_count' in locals() else 0}")
        log_info(f"  New RCPs: Success: {processed_new_count}, Failed: {failed_new_count}")
        log_info(f"  Existing RCPs: Updated: {updated_existing_count}, Failed Update: {failed_existing_count}, Skipped (up-to-date): {skipped_existing_count}")

    except Exception as e:
        log_error(f"Major error in crawl_all_rcps: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging major errors
    finally:
        if conn:
            conn.close()
            log_info("Database connection closed.")

if __name__ == "__main__":
    crawl_all_rcps()
