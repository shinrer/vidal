# --- Fichier : database_setup.py ---
import sqlite3

DATABASE_NAME = "medicaments.db"

def create_tables():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Activer la vérification des clés étrangères pour cette connexion
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Table: Medicaments
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

        # Table: Presentations
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
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis) ON DELETE CASCADE
        )
        """)
        # Table: Compositions
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
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis) ON DELETE CASCADE
        )
        """)
        # Table: Generiques
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Generiques (
            id_generique INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT,
            libelle_groupement_generique TEXT,
            type_generique INTEGER,
            numero_tri INTEGER,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis) ON DELETE CASCADE
        )
        """)
        # Table: ConditionsPrescriptionDelivrance
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ConditionsPrescriptionDelivrance (
            id_cpd INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT,
            condition TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis) ON DELETE CASCADE
        )
        """)

        # Table: RCPs (Resumes des Caracteristiques du Produit)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS RCPs (
            code_cis TEXT PRIMARY KEY,
            texte_rcp TEXT,
            date_derniere_extraction_rcp TEXT,
            FOREIGN KEY(code_cis) REFERENCES Medicaments(code_cis) ON DELETE CASCADE
        )
        """)

        # Table: RCP_Sections (Sections normalisées des RCPs pour l'IA)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS RCP_Sections (
            id_section INTEGER PRIMARY KEY AUTOINCREMENT,
            code_cis TEXT NOT NULL,
            nom_section_normalise TEXT NOT NULL, -- Ex: "indications", "posologie", "effets_indesirables"
            titre_section_original TEXT,        -- Le titre tel qu'extrait du RCP
            texte_section TEXT NOT NULL,        -- Le contenu textuel de la section
            ordre_apparition INTEGER,           -- Pour potentiellement reconstituer l'ordre
            embedding BLOB,                     -- Stockage du vecteur d'embedding
            date_segmentation TEXT NOT NULL,
            FOREIGN KEY(code_cis) REFERENCES RCPs(code_cis) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rcp_sections_code_cis ON RCP_Sections(code_cis);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rcp_sections_nom_normalise ON RCP_Sections(nom_section_normalise);")
        # Index sur la colonne embedding n'est pas utile pour SQLite pour la recherche de similarité.
        # Il sera utilisé par des bibliothèques externes comme FAISS.

        conn.commit()
        print(f"Database '{DATABASE_NAME}' created/updated successfully with tables. Foreign key checks are ON for this session during creation.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables()