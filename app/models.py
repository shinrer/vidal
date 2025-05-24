import sqlite3
from pathlib import Path

# --- Database Configuration ---
# Assuming medicaments.db is in the project root (parent of 'app' directory)
DB_PATH = Path(__file__).resolve().parent.parent / 'medicaments.db'

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
        # In a real app, this should be logged more robustly.
        print(f"Database connection error to {DB_PATH}: {e}")
        # Depending on the application's needs, you might raise the error,
        # or handle it in a way that allows the app to continue (e.g., show an error page).
        raise # For now, re-raise to make it evident during development

# --- Data Access Functions ---

def get_medicaments_count() -> int:
    """Returns the total number of medicaments in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Medicaments")
        count = cursor.fetchone()[0] # fetchone() returns a tuple, e.g., (count,)
        return count if count is not None else 0
    except sqlite3.Error as e:
        print(f"Error getting medicaments count: {e}")
        return 0 # Return 0 or handle as appropriate
    finally:
        if conn:
            conn.close()

def get_medicaments_count(filter_criteria: dict = None) -> int:
    """Returns the total number of medicaments in the database, optionally filtered."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        base_query = "SELECT COUNT(*) FROM Medicaments M"
        where_clauses = []
        params = []

        if filter_criteria:
            if filter_criteria.get('name'):
                where_clauses.append("M.denomination LIKE ?")
                params.append(f"%{filter_criteria['name']}%")
            if filter_criteria.get('substance'):
                # Subquery to find CIS codes matching the substance
                where_clauses.append("M.code_cis IN (SELECT DISTINCT C.code_cis FROM Compositions C WHERE C.denomination_substance LIKE ?)")
                params.append(f"%{filter_criteria['substance']}%")
        
        if where_clauses:
            query = f"{base_query} WHERE {' AND '.join(where_clauses)}"
        else:
            query = base_query.replace(" M","") # No alias needed if no WHERE clause from filters

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        return count if count is not None else 0
    except sqlite3.Error as e:
        print(f"Error getting filtered medicaments count: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def get_all_medicaments(limit: int = 20, offset: int = 0, filter_criteria: dict = None) -> list:
    """
    Retrieves a paginated list of medicaments, ordered by denomination, optionally filtered.
    Returns a list of dictionary-like Row objects.
    """
    conn = None
    medicaments = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        base_query = "SELECT M.code_cis, M.denomination, M.forme_pharmaceutique FROM Medicaments M"
        where_clauses = []
        params = []

        if filter_criteria:
            if filter_criteria.get('name'):
                where_clauses.append("M.denomination LIKE ?")
                params.append(f"%{filter_criteria['name']}%")
            if filter_criteria.get('substance'):
                where_clauses.append("M.code_cis IN (SELECT DISTINCT C.code_cis FROM Compositions C WHERE C.denomination_substance LIKE ?)")
                params.append(f"%{filter_criteria['substance']}%")
        
        if where_clauses:
            query = f"{base_query} WHERE {' AND '.join(where_clauses)} ORDER BY M.denomination LIMIT ? OFFSET ?"
        else:
            query = base_query.replace(" M","") + " ORDER BY denomination LIMIT ? OFFSET ?" # No alias needed if no WHERE
        
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        medicaments = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching filtered medicaments: {e}")
    finally:
        if conn:
            conn.close()
    return medicaments

def get_medicament_by_cis(code_cis: str) -> dict | None:
    """
    Retrieves detailed information for a single medicament by its CIS code,
    including its presentations, compositions, generics, and conditions for prescription/delivery.
    Returns a dictionary containing all details, or None if the medicament is not found.
    """
    conn = None
    result_data = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch main medicament details
        cursor.execute("SELECT * FROM Medicaments WHERE code_cis = ?", (code_cis,))
        medicament_details = cursor.fetchone()

        if not medicament_details:
            return None # Medicament not found

        result_data['details'] = dict(medicament_details) # Convert sqlite3.Row to dict for easier use

        # Fetch Presentations
        cursor.execute("SELECT * FROM Presentations WHERE code_cis = ?", (code_cis,))
        presentations = cursor.fetchall()
        result_data['presentations'] = [dict(row) for row in presentations]

        # Fetch Compositions
        cursor.execute("SELECT * FROM Compositions WHERE code_cis = ?", (code_cis,))
        compositions = cursor.fetchall()
        result_data['compositions'] = [dict(row) for row in compositions]

        # Fetch Generiques
        cursor.execute("SELECT * FROM Generiques WHERE code_cis = ?", (code_cis,))
        generiques = cursor.fetchall()
        result_data['generiques'] = [dict(row) for row in generiques]

        # Fetch ConditionsPrescriptionDelivrance
        cursor.execute("SELECT * FROM ConditionsPrescriptionDelivrance WHERE code_cis = ?", (code_cis,))
        conditions = cursor.fetchall()
        result_data['conditions'] = [dict(row) for row in conditions]
        
        # Fetch RCP (added here as it's related to a specific medicament)
        # Alternatively, get_rcp_by_cis can be called separately in routes if preferred
        rcp_data = get_rcp_by_cis(code_cis, conn_passed=conn) # Pass existing connection
        result_data['rcp'] = rcp_data # This will be a dict or None

    except sqlite3.Error as e:
        print(f"Error fetching medicament details for CIS {code_cis}: {e}")
        return None # Return None on error
    finally:
        if conn and not ('conn_passed' in locals() and conn_passed): # Only close if this function opened it
             conn.close()
    return result_data


def get_rcp_by_cis(code_cis: str, conn_passed: sqlite3.Connection = None) -> dict | None:
    """
    Retrieves the RCP text and extraction date for a given CIS code.
    Returns a dictionary-like Row object if found, else None.
    Accepts an optional existing database connection.
    """
    conn = None
    rcp_data = None
    try:
        if conn_passed:
            conn = conn_passed
        else:
            conn = get_db_connection()
        
        cursor = conn.cursor()
        query = "SELECT texte_rcp, date_derniere_extraction_rcp FROM RCPs WHERE code_cis = ?"
        cursor.execute(query, (code_cis,))
        row = cursor.fetchone()
        if row:
            rcp_data = dict(row) # Convert to dict
            
    except sqlite3.Error as e:
        print(f"Error fetching RCP for CIS {code_cis}: {e}")
        # rcp_data remains None
    finally:
        if conn and not conn_passed: # Only close if this function opened it
            conn.close()
    return rcp_data

# --- Search Functions ---

def search_medicaments(query: str, limit: int = 20, offset: int = 0) -> list:
    """
    Searches medicaments based on a keyword query across denomination,
    substance denomination, and presentation label.
    Uses DISTINCT to avoid duplicate medicaments if the query matches in multiple fields
    for the same medicament.
    Returns a list of dictionary-like Row objects.
    """
    conn = None
    results = []
    search_param = f"%{query}%"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql_query = """
            SELECT DISTINCT m.code_cis, m.denomination, m.forme_pharmaceutique
            FROM Medicaments m
            LEFT JOIN Compositions comp ON m.code_cis = comp.code_cis
            LEFT JOIN Presentations pres ON m.code_cis = pres.code_cis
            WHERE m.denomination LIKE ?
               OR comp.denomination_substance LIKE ?
               OR pres.libelle_presentation LIKE ?
            ORDER BY m.denomination
            LIMIT ? OFFSET ?;
        """
        cursor.execute(sql_query, (search_param, search_param, search_param, limit, offset))
        results = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error during medicament search for query '{query}': {e}")
        # results remains empty as initialized
    finally:
        if conn:
            conn.close()
    return results

def search_medicaments_count(query: str) -> int:
    """
    Counts the total number of unique medicaments that match the search query.
    """
    conn = None
    count = 0
    search_param = f"%{query}%"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql_query = """
            SELECT COUNT(DISTINCT m.code_cis)
            FROM Medicaments m
            LEFT JOIN Compositions comp ON m.code_cis = comp.code_cis
            LEFT JOIN Presentations pres ON m.code_cis = pres.code_cis
            WHERE m.denomination LIKE ?
               OR comp.denomination_substance LIKE ?
               OR pres.libelle_presentation LIKE ?;
        """
        cursor.execute(sql_query, (search_param, search_param, search_param))
        count_result = cursor.fetchone()
        if count_result:
            count = count_result[0]
    except sqlite3.Error as e:
        print(f"Error counting search results for query '{query}': {e}")
        # count remains 0 as initialized
    finally:
        if conn:
            conn.close()
    return count


# Example usage (for testing purposes, can be removed later)
if __name__ == '__main__':
    print(f"Database path: {DB_PATH}")
    if not DB_PATH.exists():
        print(f"Database file {DB_PATH} does not exist. Please run database_setup.py and import_structured_data.py first.")
    else:
        print("\n--- Testing get_medicaments_count ---")
        count = get_medicaments_count()
        print(f"Total medicaments: {count}")

        print("\n--- Testing get_all_medicaments (first 5) ---")
        medicaments = get_all_medicaments(limit=5)
        if medicaments:
            for med in medicaments:
                print(f"  CIS: {med['code_cis']}, Name: {med['denomination']}, Form: {med['forme_pharmaceutique']}")
        else:
            print("  No medicaments found or error occurred.")

        # Test with a CIS code known or assumed to be in the database (if populated)
        # Replace 'YOUR_TEST_CIS_CODE' with an actual CIS code from your DB after import
        test_cis_code = "60002602" # Example, replace if needed
        if count > 0 and not medicaments: # Try to get a CIS from the full list if the limited one was empty but db has data
            all_meds_for_test = get_all_medicaments(limit=1)
            if all_meds_for_test:
                test_cis_code = all_meds_for_test[0]['code_cis']


        if test_cis_code: # test_cis_code might not be set if db is empty
            print(f"\n--- Testing get_medicament_by_cis (CIS: {test_cis_code}) ---")
            medicament_details = get_medicament_by_cis(test_cis_code)
            if medicament_details and medicament_details.get('details'): # Check if details exist
                print(f"  Details for {medicament_details['details']['denomination']}:")
                print(f"    Form: {medicament_details['details']['forme_pharmaceutique']}")
                print(f"    Presentations: {len(medicament_details['presentations'])} found.")
                print(f"    Compositions: {len(medicament_details['compositions'])} found.")
                print(f"    Generiques: {len(medicament_details['generiques'])} found.")
                print(f"    Conditions: {len(medicament_details['conditions'])} found.")
                if medicament_details.get('rcp'):
                     print(f"    RCP Date: {medicament_details['rcp']['date_derniere_extraction_rcp']}")
                     print(f"    RCP Text Snippet: {medicament_details['rcp']['texte_rcp'][:100]}...")
                else:
                    print("    RCP: Not found.")
            else:
                print(f"  Medicament with CIS {test_cis_code} not found.")

            # Note: get_rcp_by_cis is tested within get_medicament_by_cis in this example.
            # To test it separately:
            # print(f"\n--- Testing get_rcp_by_cis (CIS: {test_cis_code}) ---")
            # rcp = get_rcp_by_cis(test_cis_code)
            # if rcp:
            #     print(f"  RCP Date: {rcp['date_derniere_extraction_rcp']}")
            #     print(f"  RCP Text Snippet: {rcp['texte_rcp'][:100]}...")
            # else:
            #     print(f"  RCP for CIS {test_cis_code} not found.")
            
            print("\n--- Testing search_medicaments (query: 'DOLIPRANE') ---")
            search_results = search_medicaments(query="DOLIPRANE", limit=5)
            if search_results:
                for med in search_results:
                    print(f"  Found: CIS: {med['code_cis']}, Name: {med['denomination']}")
            else:
                print("  No results for 'DOLIPRANE' or error occurred.")

            print("\n--- Testing search_medicaments_count (query: 'DOLIPRANE') ---")
            search_count = search_medicaments_count(query="DOLIPRANE")
            print(f"  Total results for 'DOLIPRANE': {search_count}")

        else:
            print("\nSkipping single medicament tests and search tests as no test_cis_code could be determined (database might be empty).")
