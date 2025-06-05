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
                        INSERT INTO Medicaments (
                            code_cis, denomination, forme_pharmaceutique, voies_administration,
                            statut_administratif, type_procedure_amm, etat_commercialisation, date_amm,
                            statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, denomination, forme_pharmaceutique, voies_administration,
                          statut_administratif, type_procedure_amm, etat_commercialisation, date_amm,
                          statut_bdpv, numero_autorisation_europeenne, titulaires, surveillance_renforcee))
                    imported_count += 1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g., duplicate primary key {fields[0]}) inserting row from {file_path.name} at line {line_num}: {e}", fields)
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
                        INSERT INTO Presentations (
                            code_cis, code_cip7, libelle_presentation, statut_administratif_presentation,
                            etat_commercialisation_presentation, date_declaration_commercialisation, code_cip13,
                            taux_remboursement, prix_medicament_euros, indications_remboursement
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, code_cip7, libelle_presentation, statut_admin_pres,
                          etat_commerc_pres, date_decl_commerc, code_cip13,
                          taux_remboursement, prix_medicament_euros, indications_remb))
                    imported_count += 1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g., duplicate PK {fields[6]} or missing FK {fields[0]}) inserting row from {file_path.name} at line {line_num}: {e}", fields)
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
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    # CIS_COMPO_bdpm.txt: code_cis, designation_element_pharmaceutique, code_substance, 
                    # denomination_substance, dosage_substance, reference_dosage, nature_composant, 
                    # numero_liaison_sa_ft (SA_FT in some docs)
                    if len(fields) != 8:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 8) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue
                    
                    (code_cis, element_pharmaceutique, code_substance, denomination_substance,
                     dosage_substance, reference_dosage, nature_composant, _ignored_sa_ft) = fields
                    
                    if not code_cis: # Foreign Key
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT INTO Compositions (
                            code_cis, element_pharmaceutique, code_substance, denomination_substance,
                            dosage_substance, reference_dosage, nature_composant
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (code_cis, element_pharmaceutique, code_substance, denomination_substance,
                          dosage_substance, reference_dosage, nature_composant))
                    imported_count += 1
                except sqlite3.IntegrityError as e: # Should not happen with AUTOINCREMENT PK if FK is valid
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting row from {file_path.name} at line {line_num}: {e}", fields)
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

def import_cis_gener_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_GENER_bdpm.txt into Generiques table."""
    print(f"Importing data from {file_path.name} into Generiques table...")
    imported_count = 0
    skipped_count = 0
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    # CIS_GENER_bdpm.txt: code_cis, libelle_groupement_generique, type_generique, numero_tri
                    if len(fields) != 4:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 4) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue

                    (code_cis, libelle_groupement, type_generique_str, numero_tri_str) = fields
                    
                    type_generique = None
                    try:
                        if type_generique_str: type_generique = int(type_generique_str)
                    except ValueError:
                        log_error(f"Could not convert type_generique '{type_generique_str}' to int in {file_path.name} at line {line_num}.", fields)
                        # Decide if to skip or insert with NULL based on column constraints (assuming nullable for now)

                    numero_tri = None
                    try:
                        if numero_tri_str: numero_tri = int(numero_tri_str)
                    except ValueError:
                        log_error(f"Could not convert numero_tri '{numero_tri_str}' to int in {file_path.name} at line {line_num}.", fields)

                    if not code_cis: # Foreign Key
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT INTO Generiques (
                            code_cis, libelle_groupement_generique, type_generique, numero_tri
                        ) VALUES (?, ?, ?, ?)
                    """, (code_cis, libelle_groupement, type_generique, numero_tri))
                    imported_count += 1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting row from {file_path.name} at line {line_num}: {e}", fields)
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

def import_cis_cpd_bdpm(cursor: sqlite3.Cursor, file_path: Path):
    """Imports data from CIS_CPD_bdpm.txt into ConditionsPrescriptionDelivrance table."""
    print(f"Importing data from {file_path.name} into ConditionsPrescriptionDelivrance table...")
    imported_count = 0
    skipped_count = 0
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    fields = line.strip().split('\t')
                    # CIS_CPD_bdpm.txt: code_cis, condition
                    if len(fields) != 2:
                        log_error(f"Incorrect number of fields ({len(fields)} instead of 2) in {file_path.name} at line {line_num}.", fields)
                        skipped_count += 1
                        continue
                    
                    (code_cis, condition) = fields

                    if not code_cis: # Foreign Key
                        log_error(f"Missing code_cis (FK) in {file_path.name} at line {line_num}. Skipping row.", fields)
                        skipped_count += 1
                        continue

                    cursor.execute("""
                        INSERT INTO ConditionsPrescriptionDelivrance (code_cis, condition) 
                        VALUES (?, ?)
                    """, (code_cis, condition))
                    imported_count += 1
                except sqlite3.IntegrityError as e:
                    log_error(f"Integrity error (e.g. missing FK {fields[0]}) inserting row from {file_path.name} at line {line_num}: {e}", fields)
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
