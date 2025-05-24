import sqlite3

DATABASE_NAME = "medicaments.db"

def create_tables():
    """
    Connects to (or creates if not existing) a SQLite database file 
    named medicaments.db and creates the necessary tables.
    """
    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Table: Medicaments (Based on CIS_bdpm.txt)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Medicaments (
            code_cis TEXT PRIMARY KEY,
            denomination TEXT,
            forme_pharmaceutique TEXT,
            voies_administration TEXT,
            statut_administratif TEXT,
            type_procedure_amm TEXT,
            etat_commercialisation TEXT,
            date_amm TEXT,
            statut_bdpv TEXT,
            numero_autorisation_europeenne TEXT,
            titulaires TEXT,
            surveillance_renforcee TEXT
        )
        """)

        # Table: Presentations (Based on CIS_CIP_bdpm.txt)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Presentations (
            code_cip7 TEXT,
            code_cip13 TEXT PRIMARY KEY,
            code_cis TEXT,
            libelle_presentation TEXT,
            statut_administratif_presentation TEXT,
            etat_commercialisation_presentation TEXT,
            date_declaration_commercialisation TEXT,
            prix_medicament_euros REAL,
            taux_remboursement TEXT,
            indications_remboursement TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)

        # Table: Compositions (Based on CIS_COMPO_bdpm.txt)
        # Note: This table structure assumes one row per component.
        # The source file has one row per CIS with components listed horizontally.
        # Data loading will need to handle this transformation.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Compositions (
            id_composition INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT,
            element_pharmaceutique TEXT,
            code_substance TEXT,
            denomination_substance TEXT,
            dosage_substance TEXT,
            reference_dosage TEXT,
            nature_composant TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)

        # Table: RCPs (Resumes des Caracteristiques du Produit)
        # This table is intended to store links or references to RCP documents,
        # or potentially the full text if manageable. The actual source/format of RCP data
        # from BDPM needs to be clarified for data loading. For now, a placeholder structure.
        # Assuming one RCP per CIS.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS RCPs (
            code_cis TEXT PRIMARY KEY,
            texte_rcp TEXT, 
            date_derniere_extraction_rcp TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)
        # The actual BDPM does not directly provide RCP texts in a simple downloadable file.
        # RCPs are typically accessed via ANSM or EMA websites.
        # This table might store links or summaries if available through other BDPM files or related data sources.
        # For the scope of current BDPM text files, this table might remain unpopulated or store references from other files if found.

        # Table: Generiques (Based on CIS_GENER_bdpm.txt)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Generiques (
            id_generique INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT,
            libelle_groupement_generique TEXT,
            type_generique INTEGER,
            numero_tri INTEGER,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)

        # Table: ConditionsPrescriptionDelivrance (Based on CIS_CPD_bdpm.txt)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ConditionsPrescriptionDelivrance (
            id_cpd INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT,
            condition TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis)
        )
        """)

        conn.commit()
        print(f"Database '{DATABASE_NAME}' created/updated successfully with tables.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

# Note on other BDPM files not implemented in this iteration:
# The BDPM dataset contains several other files that could be incorporated into this database.
# For future consideration, these include:
# - CIS_InfoImportantes_bdpm.txt: Information and alerts about specific drugs.
# - CIS_VALSIL_bdpm.txt: Information on marketing authorization validity.
# - CIS_HAS_SMR_bdpm.txt: Service Médical Rendu (SMR) evaluations by HAS.
# - CIS_HAS_ASMR_bdpm.txt: Amélioration du Service Médical Rendu (ASMR) evaluations by HAS.
# These files provide valuable clinical and regulatory information and could be added as new tables
# or by extending existing ones, depending on their content and relationships.

if __name__ == "__main__":
    create_tables()
