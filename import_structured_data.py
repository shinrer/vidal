import sqlite3
import json # Added for JSON output
from pathlib import Path
from database_setup import create_tables, DATABASE_NAME # Assuming DATABASE_NAME is also in database_setup or define here

# --- Configuration ---
DATA_SOURCE_DIR = Path("./data/bdpm_source/") # Path to the decompressed BDPM files
# BDPM files usually don't have headers. Delimiter is tab. Encoding is often latin-1.

# --- Logging ---
def log_error(message: str, data_row=None):
    """Simple error logger."""
    print(f"[ERROR] {message}")
    if data_row:
        print(f"  Problematic data: {data_row}")

# --- Import Functions ---

def import_cis_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_bdpm.txt into Medicaments table."""
    print(f"Importing data from {file_path.name} into Medicaments table...")
    imported_count = 0
    skipped_count = 0
    unique_cis_set = set()
    
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    if len(fields) != 12:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 12) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue

                    # CIS_bdpm.txt: code_cis, denomination, forme_pharmaceutique, voies_administration, 
                    # statut_administratif, type_procedure_amm, etat_commercialisation, date_amm, 
                    # statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee
                    (code_cis, denomination, forme_pharmaceutique, voies_administration,
                     statut_administratif, type_procedure_amm, etat_commercialisation, date_amm,
                     statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee) = fields
                    
                    if code_cis: # Ensure code_cis is not empty before adding
                        unique_cis_set.add(code_cis)

                    cursor.execute("""
                        INSERT OR REPLACE INTO Medicaments (
                            code_cis, denomination, forme_pharmaceutique, voies_administration,
                            statut_administratif, type_procedure_amm, etat_commercialisation, date_amm,
                            statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, denomination, forme_pharmaceutique, voies_administration,
                          statut_administratif, type_procedure_amm, etat_commercialisation, date_amm,
                          statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee))
                    imported_count += 1
                except sqlite3.IntegrityError as e: # Should be less frequent with INSERT OR REPLACE for PK conflicts
                    log_error(f"Integrity error (e.g., foreign key constraint) inserting/replacing row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                except Exception as e:
                    log_error(f"Generic error inserting row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                    
    except FileNotFoundError:
        log_error(f"File not found: {file_path}. Please ensure the BDPM data is downloaded and extracted to {DATA_SOURCE_DIR}.")
        return unique_cis_set, 0, 0 # Return set and zero counts if file not found
    except UnicodeDecodeError as e:
        log_error(f"Encoding error reading {file_path.name}. Try 'windows-1252' or other encodings if 'latin-1' fails: {e}")
        # Consider adding logic here to retry with 'windows-1252' if needed
        return unique_cis_set, 0, 0
    except Exception as e:
        log_error(f"Failed to process file {file_path.name}: {e}")
        return unique_cis_set, 0, 0

    print(f"Finished importing {file_path.name}: {imported_count} rows imported, {skipped_count} rows skipped.")
    return unique_cis_set, imported_count, skipped_count

# Placeholder for other import functions (will be added incrementally)
def import_cis_cip_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    print(f"Placeholder: Importing data from {file_path.name} into Presentations table...")
    return 0, 0

def import_cis_cip_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_CIP_bdpm.txt into Presentations table."""
    print(f"Importing data from {file_path.name} into Presentations table...")
    imported_count = 0
    skipped_count = 0
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    if len(fields) != 10:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 10) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue
                    
                    # CIS_CIP_bdpm.txt: code_cis, code_cip7, libelle_presentation, statut_administratif_presentation, 
                    # etat_commercialisation_presentation, date_declaration_commercialisation, code_cip13, 
                    # taux_remboursement, prix_medicament_euros, indications_remboursement
                    (code_cis, code_cip7, libelle_presentation, statut_admin_pres, 
                     etat_commerc_pres, date_decl_commerc, code_cip13, 
                     taux_remboursement, prix_euros_str, indications_remb) = fields

                    # Data cleaning/conversion for price
                    prix_medicament_euros = None
                    if prix_euros_str:
                        try:
                            prix_medicament_euros = float(prix_euros_str.replace(',', '.'))
                        except ValueError:
                            log_error(f"Could not convert price '{prix_euros_str}' to float in {file_path.name} at line {line_num}. Setting to NULL.", fields)
                            # Keep prix_medicament_euros as None
                    
                    # Ensure code_cis is not empty, as it's a FK
                    if not code_cis:
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count +=1
                        continue
                    if not code_cip13: # Primary Key
                        log_error(f"Missing code_cip13 (PK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue


                    cursor.execute("""
                        INSERT OR REPLACE INTO Presentations (
                            code_cis, code_cip7, libelle_presentation, statut_administratif_presentation,
                            etat_commercialisation_presentation, date_declaration_commercialisation, code_cip13,
                            taux_remboursement, prix_medicament_euros, indications_remboursement
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, code_cip7, libelle_presentation, statut_admin_pres,
                          etat_commerc_pres, date_decl_commerc, code_cip13,
                          taux_remboursement, prix_medicament_euros, indications_remb))
                    imported_count += 1
                except sqlite3.IntegrityError as e: # PK conflict handled by REPLACE, this would be for FK issues
                    log_error(f"Integrity error (e.g., missing FK {fields[0]}) inserting/replacing row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                except Exception as e:
                    log_error(f"Generic error inserting row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
    except FileNotFoundError:
        log_error(f"File not found: {file_path}. Skipping import for this file.")
        return 0,0
    except UnicodeDecodeError as e:
        log_error(f"Encoding error reading {file_path.name}: {e}")
        return 0,0
    except Exception as e:
        log_error(f"Failed to process file {file_path.name}: {e}")
        return 0, 0
        
    print(f"Finished importing {file_path.name}: {imported_count} rows imported, {skipped_count} rows skipped.")
    return imported_count, skipped_count

def import_cis_compo_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_COMPO_bdpm.txt into Compositions table."""
    print(f"Importing data from {file_path.name} into Compositions table...")
    imported_count = 0
    skipped_count = 0
    
    try:
        # 1. Pre-scan file for relevant code_cis
        relevant_cis_codes_in_file = set()
        try:
            with open(file_path, 'r', encoding='latin-1') as f_prescan:
                for line in f_prescan:
                    fields = line.strip().split('\t')
                    if len(fields) > 0 and fields[0]: # Assuming code_cis is the first field and not empty
                        relevant_cis_codes_in_file.add(fields[0])
        except FileNotFoundError:
            log_error(f"File not found during pre-scan: {file_path}. Cannot proceed with import for this file.")
            return 0, 0
        except UnicodeDecodeError as e:
            log_error(f"Encoding error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0
        except Exception as e:
            log_error(f"Unexpected error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0

        # 2. Delete existing entries for these code_cis
        if relevant_cis_codes_in_file:
            log_info(f"Found {len(relevant_cis_codes_in_file)} unique CIS codes in {file_path.name}. Deleting existing compositions for these CIS codes...")
            deletions_failed_for_cis = set()
            for cis_code in relevant_cis_codes_in_file:
                try:
                    cursor.execute("DELETE FROM Compositions WHERE code_cis = ?", (cis_code,))
                except sqlite3.Error as e:
                    log_error(f"Error deleting compositions for CIS {cis_code}: {e}")
                    deletions_failed_for_cis.add(cis_code)
            
            # Only commit if deletions didn't all fail (or handle partial success if needed)
            if len(deletions_failed_for_cis) < len(relevant_cis_codes_in_file):
                 cursor.connection.commit() 
                 log_info("Finished deleting old compositions for relevant CIS codes.")
            else:
                log_error("All deletions failed. Rolling back any potential partial deletions (though usually not needed for DELETE).")
                cursor.connection.rollback() # Rollback if all deletions failed

            if deletions_failed_for_cis:
                log_warning(f"Could not delete compositions for {len(deletions_failed_for_cis)} CIS codes. Data for these might be duplicated or old.")
                # Remove CIS codes for which deletion failed from the set to avoid inserting potentially duplicate data if that's a concern
                # For now, we'll proceed to insert all, INSERT OR REPLACE will handle PKs if any were defined beyond autoincrement.
        else:
            log_info(f"No relevant CIS codes found in {file_path.name} during pre-scan, or file empty. Skipping deletions.")

        # 3. Insert new entries
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    if len(fields) != 8:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 8) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue
                    
                    (code_cis, element_pharmaceutique, code_substance, denomination_substance,
                     dosage_substance, reference_dosage, nature_composant, _ignored_sa_ft) = fields
                    
                    if not code_cis:
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT OR REPLACE INTO Compositions ( 
                            code_cis, element_pharmaceutique, code_substance, denomination_substance,
                            dosage_substance, reference_dosage, nature_composant
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, element_pharmaceutique, code_substance, denomination_substance,
                          dosage_substance, reference_dosage, nature_composant))
                    imported_count += 1
                except sqlite3.IntegrityError as e: 
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting/replacing row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                except Exception as e:
                    log_error(f"Generic error inserting row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
    except FileNotFoundError: # This outer try-except is now mainly for the main read pass if pre-scan somehow passed
        log_error(f"File not found (main read pass): {file_path}. This should have been caught by pre-scan.")
        return 0, 0
    except UnicodeDecodeError as e:
        log_error(f"Encoding error reading {file_path.name} (main read pass): {e}")
        return 0, 0
    except Exception as e:
        log_error(f"Failed to process file {file_path.name} (main read pass): {e}")
        return 0, 0

    print(f"Finished importing {file_path.name}: {imported_count} rows imported, {skipped_count} rows skipped.")
    return imported_count, skipped_count

def import_cis_gener_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_GENER_bdpm.txt into Generiques table."""
    print(f"Importing data from {file_path.name} into Generiques table...")
    imported_count = 0
    skipped_count = 0
    try:
        # 1. Pre-scan file for relevant code_cis
        relevant_cis_codes_in_file = set()
        try:
            with open(file_path, 'r', encoding='latin-1') as f_prescan:
                for line in f_prescan:
                    fields = line.strip().split('\t')
                    if len(fields) > 0 and fields[0]:
                        relevant_cis_codes_in_file.add(fields[0])
        except FileNotFoundError:
            log_error(f"File not found during pre-scan: {file_path}. Cannot proceed.")
            return 0, 0
        except UnicodeDecodeError as e:
            log_error(f"Encoding error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0
        except Exception as e:
            log_error(f"Unexpected error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0

        # 2. Delete existing entries for these code_cis
        if relevant_cis_codes_in_file:
            log_info(f"Found {len(relevant_cis_codes_in_file)} unique CIS codes in {file_path.name}. Deleting existing generiques for these CIS codes...")
            deletions_failed_for_cis = set()
            for cis_code in relevant_cis_codes_in_file:
                try:
                    cursor.execute("DELETE FROM Generiques WHERE code_cis = ?", (cis_code,))
                except sqlite3.Error as e:
                    log_error(f"Error deleting generiques for CIS {cis_code}: {e}")
                    deletions_failed_for_cis.add(cis_code)
            
            if len(deletions_failed_for_cis) < len(relevant_cis_codes_in_file):
                 cursor.connection.commit()
                 log_info("Finished deleting old generiques for relevant CIS codes.")
            else:
                log_error("All deletions for generiques failed. Rolling back.")
                cursor.connection.rollback()

            if deletions_failed_for_cis:
                log_warning(f"Could not delete generiques for {len(deletions_failed_for_cis)} CIS codes.")
        else:
            log_info(f"No relevant CIS codes found in {file_path.name} during pre-scan. Skipping deletions.")

        # 3. Insert new entries
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    if len(fields) != 4:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 4) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue

                    (code_cis, libelle_groupement, type_generique_str, numero_tri_str) = fields
                    
                    type_generique = int(type_generique_str) if type_generique_str else None
                    numero_tri = int(numero_tri_str) if numero_tri_str else None

                    if not code_cis:
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT OR REPLACE INTO Generiques (
                            code_cis, libelle_groupement_generique, type_generique, numero_tri
                        ) VALUES (?, ?, ?, ?)
                    """, (code_cis, libelle_groupement, type_generique, numero_tri))
                    imported_count += 1
                except ValueError as e: # Catch conversion errors for int
                    log_error(f"Data conversion error for row in {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count +=1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting/replacing row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                except Exception as e:
                    log_error(f"Generic error inserting row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
    except FileNotFoundError:
        log_error(f"File not found (main read pass): {file_path}. This should have been caught by pre-scan.")
        return 0, 0
    except UnicodeDecodeError as e:
        log_error(f"Encoding error reading {file_path.name} (main read pass): {e}")
        return 0, 0
    except Exception as e:
        log_error(f"Failed to process file {file_path.name} (main read pass): {e}")
        return 0, 0
        
    print(f"Finished importing {file_path.name}: {imported_count} rows imported, {skipped_count} rows skipped.")
    return imported_count, skipped_count

def import_cis_cpd_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_CPD_bdpm.txt into ConditionsPrescriptionDelivrance table."""
    print(f"Importing data from {file_path.name} into ConditionsPrescriptionDelivrance table...")
    imported_count = 0
    skipped_count = 0
    try:
        # 1. Pre-scan file for relevant code_cis
        relevant_cis_codes_in_file = set()
        try:
            with open(file_path, 'r', encoding='latin-1') as f_prescan:
                for line in f_prescan:
                    fields = line.strip().split('\t')
                    if len(fields) > 0 and fields[0]:
                        relevant_cis_codes_in_file.add(fields[0])
        except FileNotFoundError:
            log_error(f"File not found during pre-scan: {file_path}. Cannot proceed.")
            return 0, 0
        except UnicodeDecodeError as e:
            log_error(f"Encoding error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0
        except Exception as e:
            log_error(f"Unexpected error during pre-scan of {file_path.name}: {e}. Cannot proceed.")
            return 0, 0

        # 2. Delete existing entries for these code_cis
        if relevant_cis_codes_in_file:
            log_info(f"Found {len(relevant_cis_codes_in_file)} unique CIS codes in {file_path.name}. Deleting existing conditions for these CIS codes...")
            deletions_failed_for_cis = set()
            for cis_code in relevant_cis_codes_in_file:
                try:
                    cursor.execute("DELETE FROM ConditionsPrescriptionDelivrance WHERE code_cis = ?", (cis_code,))
                except sqlite3.Error as e:
                    log_error(f"Error deleting conditions for CIS {cis_code}: {e}")
                    deletions_failed_for_cis.add(cis_code)
            
            if len(deletions_failed_for_cis) < len(relevant_cis_codes_in_file):
                 cursor.connection.commit()
                 log_info("Finished deleting old conditions for relevant CIS codes.")
            else:
                log_error("All deletions for conditions failed. Rolling back.")
                cursor.connection.rollback()

            if deletions_failed_for_cis:
                log_warning(f"Could not delete conditions for {len(deletions_failed_for_cis)} CIS codes.")
        else:
            log_info(f"No relevant CIS codes found in {file_path.name} during pre-scan. Skipping deletions.")

        # 3. Insert new entries
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    if len(fields) != 2:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 2) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue
                    
                    (code_cis, condition) = fields

                    if not code_cis:
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT OR REPLACE INTO ConditionsPrescriptionDelivrance (code_cis, condition) 
                        VALUES (?, ?)
                    """, (code_cis, condition))
                    imported_count += 1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting/replacing row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
                except Exception as e:
                    log_error(f"Generic error inserting row from {file_path.name} at line {line_num}: {e}", fields)
                    skipped_count += 1
    except FileNotFoundError:
        log_error(f"File not found (main read pass): {file_path}. This should have been caught by pre-scan.")
        return 0, 0
    except UnicodeDecodeError as e:
        log_error(f"Encoding error reading {file_path.name} (main read pass): {e}")
        return 0, 0
    except Exception as e:
        log_error(f"Failed to process file {file_path.name} (main read pass): {e}")
        return 0, 0

    print(f"Finished importing {file_path.name}: {imported_count} rows imported, {skipped_count} rows skipped.")
    return imported_count, skipped_count

# --- Main Execution ---
def main():
    print("--- Starting BDPM data import script ---")

    # 1. Ensure database and tables are ready
    print(f"Ensuring database '{DATABASE_NAME}' and tables are created...")
    create_tables() # This function is from database_setup.py

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Define file paths
        file_cis_bdpm = DATA_SOURCE_DIR / "CIS_bdpm.txt"
        file_cis_cip_bdpm = DATA_SOURCE_DIR / "CIS_CIP_bdpm.txt"
        file_cis_compo_bdpm = DATA_SOURCE_DIR / "CIS_COMPO_bdpm.txt"
        file_cis_gener_bdpm = DATA_SOURCE_DIR / "CIS_GENER_bdpm.txt"
        file_cis_cpd_bdpm = DATA_SOURCE_DIR / "CIS_CPD_bdpm.txt"

        # Import data in order of dependencies
        # Medicaments must be imported first
        unique_cis_from_bdpm, _, _ = import_cis_bdpm(cursor, file_cis_bdpm)
        
        # Then other tables that depend on Medicaments
        import_cis_cip_bdpm(cursor, file_cis_cip_bdpm)
        import_cis_compo_bdpm(cursor, file_cis_compo_bdpm)
        import_cis_gener_bdpm(cursor, file_cis_gener_bdpm)
        import_cis_cpd_bdpm(cursor, file_cis_cpd_bdpm)

        conn.commit()
        print("--- All data import tasks attempted. Changes committed. ---")

        # Save unique CIS codes to JSON
        if unique_cis_from_bdpm: # Check if the set is not empty (i.e., file was processed at least partially)
            json_file_path = Path("unique_cis_codes.json")
            try:
                # Convert set to list for JSON serialization
                cis_list = sorted(list(unique_cis_from_bdpm)) # Sorting is optional but makes file consistent
                with open(json_file_path, 'w', encoding='utf-8') as jf:
                    json.dump(cis_list, jf, indent=4) # indent for readability
                print(f"Extracted {len(cis_list)} unique CIS codes to {json_file_path.name}")
            except IOError as e:
                log_error(f"Could not write unique CIS codes to JSON file {json_file_path.name}: {e}")
            except Exception as e:
                log_error(f"An unexpected error occurred while saving unique CIS codes to JSON: {e}")

    except sqlite3.Error as e:
        log_error(f"Database error during import process: {e}")
        if conn:
            conn.rollback() # Rollback changes if any error occurs at DB level
    except Exception as e:
        log_error(f"An unexpected error occurred in main: {e}")
    finally:
        if conn:
            conn.close()
        print("--- BDPM data import script finished ---")

if __name__ == "__main__":
    # The main function and individual import functions will handle file existence checks.
    main()
