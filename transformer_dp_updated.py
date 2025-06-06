import json
import sqlite3
import re
import os
from datetime import datetime
import unicodedata
from tqdm import tqdm

DB_NAME = 'rcp_wide_database.db'
TABLE_NAME = 'MedicamentsRCP'

# Variable globale pour le débogage, à remplir avec des codes CIS si besoin
debug_specific_cis_list_global = []
# Pour activer le débogage pour les titres que vous avez mentionnés,
# il faut que le CIS du fichier JSON contenant ces titres soit dans cette liste.
# EXEMPLE: debug_specific_cis_list_global = ['CIS_DU_FICHIER_PROBLEM']

# Colonnes prédéfinies dans la base de données
PREDEFINED_COLUMNS_STRUCTURE = {
    "denomination_du_medicament": "TEXT",
    "composition_qualitative_et_quantitative": "TEXT",
    "forme_pharmaceutique": "TEXT",
    "s4_1_indications_therapeutiques": "TEXT",
    "s4_2_posologie_et_mode_d_administration": "TEXT",
    "s4_3_contre_indications": "TEXT",
    "s4_4_mises_en_garde_speciales_et_precautions_d_emploi": "TEXT",
    "s4_5_interactions_avec_d_autres_medicaments_et_autres_formes_d_interactions": "TEXT",
    "s4_6_fertilite_grossesse_et_allaitement": "TEXT",
    "s4_7_effets_sur_l_aptitude_a_conduire_des_vehicules_et_a_utiliser_des_machines": "TEXT",
    "s4_8_effets_indesirables": "TEXT",
    "s4_9_surdosage": "TEXT",
    "s5_1_proprietes_pharmacodynamiques": "TEXT",
    "s5_2_proprietes_pharmacocinetiques": "TEXT",
    "s5_3_donnees_de_securite_preclinique": "TEXT",
    "s6_1_liste_des_excipients": "TEXT",
    "s6_2_incompatibilites_majeures": "TEXT",
    "s6_3_duree_de_conservation": "TEXT",
    "s6_4_precautions_particulieres_de_conservation": "TEXT",
    "s6_5_nature_et_contenu_de_l_emballage_exterieur": "TEXT",
    "s6_6_precautions_particulieres_d_elimination_et_de_manipulation": "TEXT",
    "titulaire_de_l_autorisation_de_mise_sur_le_marche": "TEXT",
    "numero_s_d_autorisation_de_mise_sur_le_marche": "TEXT",
    "date_de_premiere_autorisation_de_renouvellement_de_l_autorisation": "TEXT",
    "date_de_mise_a_jour_du_texte": "TEXT",
    "dosimetrie": "TEXT",
    "instructions_pour_la_preparation_des_radiopharmaceutiques": "TEXT",
    "conditions_de_prescription_et_de_delivrance": "TEXT"
}
OTHER_SECTIONS_COL_NAME = "other_parsed_sections_json"
IGNORE_SECTION_MARKER = "_IGNORE_THIS_SECTION_"

# --- Titres spécifiques que vous voulez tracer ---
TITLES_TO_DEBUG = [
    "DONNEES CLINIQUES",
    "PROPRIETES PHARMACOLOGIQUES",
    "DONNEES PHARMACEUTIQUES",
    "6.6. Précautions particulières d’élimination et de manipulation", # Note: apostrophe typographique ici
    "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",         # Note: apostrophe typographique ici
    "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",        # Note: apostrophe typographique ici
    "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION" # Note: apostrophe typographique ici
]

def clean_title_for_mapping(title: str, debug_cis_code: str = None) -> str:
    # Détermine si le débogage détaillé est actif
    original_title_for_debug_display = title.split('\n')[0].strip() # Pour l'affichage avant nettoyage
    is_debug_active_for_title = original_title_for_debug_display in TITLES_TO_DEBUG or \
                                (debug_cis_code and debug_cis_code in debug_specific_cis_list_global)

    if not title:
        return ""

    cleaned = title.split('\n')[0].strip()

    # *** DEBUT MODIFICATION OPTION 1 ***
    # Remplacer les apostrophes typographiques courantes par une apostrophe droite standard
    cleaned = cleaned.replace("’", "'").replace("‘", "'").replace("`", "'")

    # Normalisation pour décomposer les caractères accentués, MAIS ATTENTION avec 'ascii', 'ignore'
    # Si on veut garder les apostrophes droites, il faut s'assurer qu'elles ne sont pas supprimées.
    # L'apostrophe droite standard (U+0027) EST un caractère ASCII.
    cleaned_normalized = unicodedata.normalize('NFKD', cleaned)
    # Encodage en ASCII, ignorant les caractères non-ASCII. L'apostrophe droite survivra.
    cleaned_ascii = cleaned_normalized.encode('ascii', 'ignore').decode('utf-8')
    cleaned = cleaned_ascii.lower()
    # *** FIN MODIFICATION OPTION 1 (PARTIE 1) ***

    # Suppression des préfixes numériques/romains/alphabétiques
    cleaned = re.sub(r"^\s*([0-9ivxlcdm]+(?:[\.\-][0-9ivxlcdm]+)*|[a-z])[\.\)]\s+", "", cleaned, 1)
    cleaned = re.sub(r"^\s*([0-9ivxlcdm]+(?:[\.\-][0-9ivxlcdm]+)*|[a-z])[\.\)]", "", cleaned, 1).strip()
    cleaned = re.sub(r"^\s*([0-9ivxlcdm]+(?:[\.\-][0-9ivxlcdm]+)*|[a-z])\s+", "", cleaned, 1).strip()

    cleaned = re.sub(r'\(s\)', 's', cleaned) # numero(s) -> numeros
    cleaned = re.sub(r'\(suite\)', '', cleaned) # Titre (suite) -> Titre
    
    # *** DEBUT MODIFICATION OPTION 1 (PARTIE 2) ***
    # Enlever la ponctuation finale et normaliser les espaces
    # S'assurer que l'apostrophe (') est CONSERVÉE dans la classe de caractères \w\s\-\+&'/\\]
    cleaned = re.sub(r"[^\w\s\-\+&'/\\]+$", "", cleaned).strip() # Garde '/' et '\' et l'apostrophe '
    # *** FIN MODIFICATION OPTION 1 (PARTIE 2) ***
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if is_debug_active_for_title:
        print(f"  [DEBUG clean_title_for_mapping] Input: '{original_title_for_debug_display}' -> Output: '{cleaned}'")
    return cleaned

TARGET_TITLE_TO_DB_COLUMN_MAP = {}

def initialize_target_title_map():
    global TARGET_TITLE_TO_DB_COLUMN_MAP
    print("[DEBUG initialize_target_title_map] Initialisation des mappings...")
    # Les chaînes ici utilisent l'apostrophe droite standard "'"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Dénomination du médicament")] = "denomination_du_medicament"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Composition qualitative et quantitative")] = "composition_qualitative_et_quantitative"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Forme pharmaceutique")] = "forme_pharmaceutique"

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Indications thérapeutiques")] = "s4_1_indications_therapeutiques"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Posologie et mode d'administration")] = "s4_2_posologie_et_mode_d_administration"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Contre-indications")] = "s4_3_contre_indications"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Mises en garde spéciales et précautions d'emploi")] = "s4_4_mises_en_garde_speciales_et_precautions_d_emploi"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Mises en garde et précautions d'emploi")] = "s4_4_mises_en_garde_speciales_et_precautions_d_emploi"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Interactions avec d'autres médicaments et autres formes d'interactions")] = "s4_5_interactions_avec_d_autres_medicaments_et_autres_formes_d_interactions"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Fertilité, grossesse et allaitement")] = "s4_6_fertilite_grossesse_et_allaitement"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Effets sur l'aptitude à conduire des véhicules et à utiliser des machines")] = "s4_7_effets_sur_l_aptitude_a_conduire_des_vehicules_et_a_utiliser_des_machines"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Effets indésirables")] = "s4_8_effets_indesirables"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Surdosage")] = "s4_9_surdosage"

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Propriétés pharmacodynamiques")] = "s5_1_proprietes_pharmacodynamiques"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Propriétés pharmacocinétiques")] = "s5_2_proprietes_pharmacocinetiques"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Données de sécurité préclinique")] = "s5_3_donnees_de_securite_preclinique"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Données de sécurité précliniques")] = "s5_3_donnees_de_securite_preclinique"

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Liste des excipients")] = "s6_1_liste_des_excipients"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Incompatibilités majeures")] = "s6_2_incompatibilites_majeures"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Incompatibilités")] = "s6_2_incompatibilites_majeures"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Durée de conservation")] = "s6_3_duree_de_conservation"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Précautions particulières de conservation")] = "s6_4_precautions_particulieres_de_conservation"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Nature et contenu de l'emballage extérieur")] = "s6_5_nature_et_contenu_de_l_emballage_exterieur"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Nature et contenu de l'emballage")] = "s6_5_nature_et_contenu_de_l_emballage_exterieur"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Précautions particulières d'élimination et de manipulation")] = "s6_6_precautions_particulieres_d_elimination_et_de_manipulation"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Précautions particulières d'élimination")] = "s6_6_precautions_particulieres_d_elimination_et_de_manipulation"

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Titulaire de l'autorisation de mise sur le marché")] = "titulaire_de_l_autorisation_de_mise_sur_le_marche"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Numéro(s) d'autorisation de mise sur le marché")] = "numero_s_d_autorisation_de_mise_sur_le_marche" # Note (s) et apostrophe '
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Numero d'autorisation de mise sur le marche")] = "numero_s_d_autorisation_de_mise_sur_le_marche"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Numeros d'amm")] = "numero_s_d_autorisation_de_mise_sur_le_marche"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Numero d'amm")] = "numero_s_d_autorisation_de_mise_sur_le_marche"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Date de première autorisation/de renouvellement de l'autorisation")] = "date_de_premiere_autorisation_de_renouvellement_de_l_autorisation"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Date de première autorisation et ou de renouvellement de l'autorisation")] = "date_de_premiere_autorisation_de_renouvellement_de_l_autorisation"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Date de mise à jour du texte")] = "date_de_mise_a_jour_du_texte"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Dosimétrie")] = "dosimetrie"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Instructions pour la préparation des radiopharmaceutiques")] = "instructions_pour_la_preparation_des_radiopharmaceutiques"
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Conditions de prescription et de délivrance")] = "conditions_de_prescription_et_de_delivrance"

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Données cliniques")] = IGNORE_SECTION_MARKER
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Propriétés pharmacologiques")] = IGNORE_SECTION_MARKER
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Données pharmaceutiques")] = IGNORE_SECTION_MARKER
    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Informations complementaires")] = IGNORE_SECTION_MARKER

    TARGET_TITLE_TO_DB_COLUMN_MAP[clean_title_for_mapping("Retour en haut de la page")] = IGNORE_SECTION_MARKER
    cleaned_ansm_title = clean_title_for_mapping("ANSM - Mis à jour le : JJ/MM/AAAA")
    if cleaned_ansm_title.startswith("ansm"): # Pour être plus générique
         TARGET_TITLE_TO_DB_COLUMN_MAP[cleaned_ansm_title.split(':')[0].strip()] = IGNORE_SECTION_MARKER

    print(f"[DEBUG initialize_target_title_map] Fin initialisation. {len(TARGET_TITLE_TO_DB_COLUMN_MAP)} mappages chargés.")
    # Optionnel: Imprimer toutes les clés mappées pour vérification
    # print("[DEBUG initialize_target_title_map] Clés mappées dans TARGET_TITLE_TO_DB_COLUMN_MAP:")
    # for k, v in TARGET_TITLE_TO_DB_COLUMN_MAP.items():
    #     print(f"  '{k}' -> '{v}'")

initialize_target_title_map()


def segment_rcp_from_old_script(rcp_text: str, code_cis_for_debug: str) -> list[tuple[str, str, str, int]]:
    sections = []
    if not rcp_text or rcp_text.isspace(): return sections
    
    # is_debug_active = code_cis_for_debug and code_cis_for_debug in debug_specific_cis_list_global

    title_pattern = re.compile(
        r"^(?P<full_title>"
            r"(?:(?:[0-9IVXLCDM]+(?:[\.\s\-][0-9IVXLCDM]+)*|[a-zA-Z])[\.\)]\s*)?" 
            r"(?P<title_text_after_prefix>"
                r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-Þæœßà-öø-ÿ0-9\s\(\)\-\',\/\&\u2019’]{2,}" 
                r"(?:[\r\n]+[A-ZÀ-ÖØ-Þ\(][A-Za-zÀ-ÖØ-Þæœßà-öø-ÿ0-9\s\(\)\-\',\/\&\u2019’]+)*" 
            r")"
        r"|"
            r"(?P<title_text_all_caps>"
                r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ\s\(\)\-\',\/\&\u2019’]{9,}" 
                r"(?:[\r\n]+[A-ZÀ-ÖØ-Þ\(][A-ZÀ-ÖØ-Þ\s\(\)\-\',\/\&\u2019’]+)*"
            r")"
        r"|"
             r"(?P<title_text_short_special_caps>[A-ZÀ-ÖØ-Þ\s()\-]{3,}[A-ZÀ-ÖØ-Þ]\))"
        r")\s*$",
        re.MULTILINE
    )
    
    rcp_text_cleaned = rcp_text.replace('\r\n', '\n').replace('\r', '\n')
    rcp_text_cleaned = re.sub(r'\n{3,}', '\n\n', rcp_text_cleaned).strip()

    split_points = []
    for match in title_pattern.finditer(rcp_text_cleaned):
        full_raw_title_multiline = match.group('full_title').strip()
        
        title_content_for_mapping = match.group('title_text_after_prefix') or \
                                    match.group('title_text_all_caps') or \
                                    match.group('title_text_short_special_caps')

        if not title_content_for_mapping: 
            title_content_for_mapping = full_raw_title_multiline
        
        temp_check_title = re.sub(r'[^a-zA-Z]', '', title_content_for_mapping.split('\n')[0])
        if len(temp_check_title) < 3 and not title_content_for_mapping.isupper():
            continue
        
        split_points.append({
            'title_for_mapping_logic': title_content_for_mapping.strip(), 
            'title_original_raw': full_raw_title_multiline,     
            'start': match.start(), 
            'end': match.end()
        })

    if not split_points:
        sections.append(("_contenu_integral_non_structure_", "Texte intégral non structuré", rcp_text_cleaned, 0))
        return sections

    current_order = 0
    first_title_start_offset = split_points[0]['start']
    if first_title_start_offset > 0:
        text_before_first_title = rcp_text_cleaned[:first_title_start_offset].strip()
        if len(text_before_first_title) > 20: 
            guessed_title_before = text_before_first_title.split('\n')[0].strip()
            if len(guessed_title_before) > 150 or not guessed_title_before : 
                 guessed_title_before = "Section initiale non titree"
            sections.append((guessed_title_before, guessed_title_before, text_before_first_title, current_order))
            current_order +=1

    for i, point in enumerate(split_points):
        title_to_pass_to_cleaner = point['title_for_mapping_logic']
        raw_original_title_capture = point['title_original_raw'] 
        
        start_content = point['end'] 
        end_content = split_points[i+1]['start'] if i + 1 < len(split_points) else len(rcp_text_cleaned)
        texte_section = rcp_text_cleaned[start_content:end_content].strip()
        
        texte_section = re.sub(r'\s*\n\s*', '\n', texte_section).strip() 
        texte_section = re.sub(r'\n{3,}', '\n\n', texte_section) 
        
        if texte_section: 
            sections.append((title_to_pass_to_cleaner, raw_original_title_capture, texte_section, current_order))
            current_order += 1
            
    final_sections = []
    for title_for_logic, original_capture, text, order in sections:
        if text and len(text.strip()) > 5: 
            final_sections.append((title_for_logic, original_capture, text, order))

    if not final_sections and rcp_text_cleaned: 
        final_sections.append(("_contenu_integral_difficile_a_segmenter_", "Texte intégral (segmentation difficile)", rcp_text_cleaned, 0))
    return final_sections


def create_wide_table(conn):
    cursor = conn.cursor()
    columns_sql_parts = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "cis_code TEXT UNIQUE NOT NULL",
        "source_filename TEXT",
        "parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ]
    for col_name, col_type in PREDEFINED_COLUMNS_STRUCTURE.items():
        columns_sql_parts.append(f"{col_name} {col_type}")
    columns_sql_parts.append(f"{OTHER_SECTIONS_COL_NAME} TEXT")
    create_table_sql = f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({', '.join(columns_sql_parts)})"
    try:
        cursor.execute(create_table_sql)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erreur SQLite lors de la création de la table {TABLE_NAME}: {e}")
        raise

def process_rcp_with_segmentation_logic(cis_code: str, rcp_text: str, source_filename: str, conn, current_debug_cis_list=None):
    if current_debug_cis_list is None:
        current_debug_cis_list = []
    is_debug_cis_active_here = cis_code in current_debug_cis_list

    if not rcp_text or isinstance(rcp_text, str) and (rcp_text.startswith("ERREUR_") or \
        rcp_text in ["TEXTE_VIDE_OU_COURT", "AUCUN_DOCUMENT_DISPONIBLE_MSG", "RCP_NON_TROUVE_404", "AUCUN_DOCUMENT_DISPONIBLE"]):
        return False

    if is_debug_cis_active_here:
        print(f"\n--- DÉBOGAGE POUR CIS {cis_code} --- Source: {source_filename} ---")
    
    segmented_sections = segment_rcp_from_old_script(rcp_text, cis_code)

    if not segmented_sections:
        if is_debug_cis_active_here: print(f"  [DEBUG {cis_code}] Aucune section trouvée par segment_rcp_from_old_script.")
        return False

    db_entry = {col_name: None for col_name in PREDEFINED_COLUMNS_STRUCTURE.keys()}
    other_sections_content = {}

    if is_debug_cis_active_here: print(f"  [DEBUG {cis_code}] Traitement des sections segmentées...")
    for title_for_logic_mapping, original_title_from_regex, texte_section, ordre in segmented_sections:
        original_title_display = original_title_from_regex.strip() # Pour la comparaison avec TITLES_TO_DEBUG
        title_logic_display = title_for_logic_mapping.strip() # Pour la comparaison avec TITLES_TO_DEBUG
        
        should_debug_this_title_cleaning = is_debug_cis_active_here or \
                                          original_title_display in TITLES_TO_DEBUG or \
                                          title_logic_display in TITLES_TO_DEBUG
                                          
        cleaned_title = clean_title_for_mapping(
            title_for_logic_mapping,
            debug_cis_code=cis_code if should_debug_this_title_cleaning else None
        )
        
        db_column_name = TARGET_TITLE_TO_DB_COLUMN_MAP.get(cleaned_title)

        if is_debug_cis_active_here or original_title_display in TITLES_TO_DEBUG or title_logic_display in TITLES_TO_DEBUG:
            print(f"    [DEBUG MAP {cis_code if cis_code else 'N/A'}] Original Raw: '{original_title_from_regex.replace('\n',' ')}'")
            print(f"      Logic Title: '{title_for_logic_mapping.replace('\n',' ')}' -> Cleaned: '{cleaned_title}'")
            print(f"      -> Mapped Column: '{db_column_name}'")

        if db_column_name == IGNORE_SECTION_MARKER:
            if is_debug_cis_active_here or original_title_display in TITLES_TO_DEBUG or title_logic_display in TITLES_TO_DEBUG:
                print(f"      -> Action: IGNORED (marker)")
            continue
        
        if db_column_name and db_column_name in PREDEFINED_COLUMNS_STRUCTURE:
            if db_entry.get(db_column_name) is None:
                db_entry[db_column_name] = texte_section
            else: 
                db_entry[db_column_name] += f"\n\n--- Autre section pour même titre '{cleaned_title}' (Original Regex: {original_title_from_regex.replace('\n',' ')}) ---\n" + texte_section
            if is_debug_cis_active_here or original_title_display in TITLES_TO_DEBUG or title_logic_display in TITLES_TO_DEBUG:
                 print(f"      -> Action: MAPPED to PREDEFINED column '{db_column_name}'")

        else: 
            key_for_other = original_title_from_regex.replace('\n', ' ').strip()
            key_for_other = re.sub(r'\s+', '_', key_for_other)
            key_for_other = re.sub(r'[^a-zA-Z0-9_]+', '', key_for_other)[:80].strip('_') 
            
            if not key_for_other: key_for_other = f"section_non_identifiee_{ordre}"

            original_key_for_other_json = key_for_other
            count = 1
            while key_for_other in other_sections_content:
                key_for_other = f"{original_key_for_other_json}_{count}"
                count += 1
            
            other_sections_content[key_for_other] = {
                "original_title_regex_capture": original_title_from_regex,
                "title_used_for_mapping_logic": title_for_logic_mapping,
                "cleaned_title_attempt": cleaned_title,
                "text": texte_section,
                "order_in_document": ordre
            }
            if is_debug_cis_active_here or original_title_display in TITLES_TO_DEBUG or title_logic_display in TITLES_TO_DEBUG:
                 print(f"      -> Action: Added to OTHER_SECTIONS (key: '{key_for_other}')")

    columns_to_insert = ["cis_code", "source_filename", "parsed_at"]
    values_to_insert = [cis_code, source_filename, datetime.now().isoformat()]
    has_valid_data = False

    for col_name_db, content_val in db_entry.items():
        columns_to_insert.append(col_name_db)
        values_to_insert.append(content_val)
        if content_val is not None:
            has_valid_data = True
            
    if other_sections_content:
        columns_to_insert.append(OTHER_SECTIONS_COL_NAME)
        values_to_insert.append(json.dumps(other_sections_content, ensure_ascii=False, indent=2))
        if not has_valid_data and any(s_val["text"] for s_val in other_sections_content.values()):
             has_valid_data = True

    if not has_valid_data:
        if is_debug_cis_active_here: print(f"  [DEBUG {cis_code}] Aucune donnée pertinente à insérer. Ignoré pour l'insertion.")
        return False

    if is_debug_cis_active_here:
        print(f"  [DEBUG {cis_code}] Données prêtes pour insertion (aperçu des colonnes remplies):")
        for col, val in zip(columns_to_insert, values_to_insert):
            if col == OTHER_SECTIONS_COL_NAME and other_sections_content:
                 print(f"    {col}: (Contient {len(other_sections_content)} sections)")
            elif val is not None: 
                print(f"    {col}: '{str(val)[:50].replace('\n',' ')}...'")

    placeholders = ["?"] * len(columns_to_insert)
    sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({', '.join(columns_to_insert)}) VALUES ({', '.join(placeholders)})"
    
    cursor = conn.cursor()
    try:
        cursor.execute(sql, values_to_insert)
        if is_debug_cis_active_here: print(f"  [DEBUG {cis_code}] Insertion réussie.")
        return True
    except sqlite3.Error as e:
        print(f"  Erreur SQLite lors de l'insertion pour CIS {cis_code} (fichier: {source_filename}): {e}")
        if is_debug_cis_active_here: print(f"--- FIN DÉBOGAGE AVEC ERREUR POUR CIS {cis_code} ---\n")
        return False


if __name__ == "__main__":
    master_json_file_path = "all_rcps_data.json" 
    
    # --- IMPORTANT POUR LE DÉBOGAGE ---
    # Pour tester avec le JSON que vous avez montré dans la question précédente :
    # 1. Mettez un identifiant (ex: 'CIS_DU_FICHIER_PROBLEM') dans debug_specific_cis_list_global
    # 2. Le bloc `if len(debug_specific_cis_list_global) == 1 and debug_specific_cis_list_global[0] == "CIS_DU_FICHIER_PROBLEM":`
    #    sera activé pour utiliser les données JSON d'exemple directement.
    debug_specific_cis_list_global = ['CIS_DU_FICHIER_PROBLEM'] # Active le mode de test spécifique
    # debug_specific_cis_list_global = [] # Décommentez pour traiter tous les CIS du master_json

    conn = sqlite3.connect(DB_NAME)
    create_wide_table(conn)
    
    items_to_process_dict = {}

    if len(debug_specific_cis_list_global) == 1 and debug_specific_cis_list_global[0] == "CIS_DU_FICHIER_PROBLEM":
        print("INFO: Mode de test pour un JSON spécifique (comme celui de la question précédente).")
        test_json_data = {
            "cis_code": "CIS_DU_FICHIER_PROBLEM",
            "source_filename": "exemple_problematique.json",
            "DONNEES CLINIQUES": "", # Titre d'exemple
            "PROPRIETES PHARMACOLOGIQUES": "", # Titre d'exemple
            "DONNEES PHARMACEUTIQUES": "", # Titre d'exemple
            "6.6. Précautions particulières d’élimination et de manipulation": "Le contenu pour 6.6...", # Apostrophe typographique
            "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE": "Le contenu pour Titulaire...", # Apostrophe typographique
            "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE": "Le contenu pour Numéro(s)...", # Apostrophe typographique
            "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION": "Le contenu pour Date..." # Apostrophe typographique
        }
        
        print(f"\n--- DÉBOGAGE POUR JSON SPÉCIFIQUE (CIS: {test_json_data['cis_code']}) ---")
        db_entry = {col_name: None for col_name in PREDEFINED_COLUMNS_STRUCTURE.keys()}
        other_sections_content = {}
        
        cis_code_test = test_json_data.get("cis_code", "UNKNOWN_CIS")
        
        for key, value in test_json_data.items():
            if key in ["cis_code", "source_filename"]:
                continue

            original_title_for_debug = key 
            title_for_logic_mapping = key
            texte_section = str(value) 
            
            # Utiliser le cis_code_test pour potentiellement activer les prints dans clean_title_for_mapping
            cleaned_title = clean_title_for_mapping(title_for_logic_mapping, debug_cis_code=cis_code_test)
            db_column_name = TARGET_TITLE_TO_DB_COLUMN_MAP.get(cleaned_title)

            print(f"    [DEBUG MAP {cis_code_test}] Original Key: '{original_title_for_debug}'")
            print(f"      -> Cleaned: '{cleaned_title}'")
            print(f"      -> Mapped DB Column: '{db_column_name}'")

            if db_column_name == IGNORE_SECTION_MARKER:
                print(f"      -> Action: IGNORED (marker)")
                continue
            
            if db_column_name and db_column_name in PREDEFINED_COLUMNS_STRUCTURE:
                if db_entry.get(db_column_name) is None:
                    db_entry[db_column_name] = texte_section
                else:
                    db_entry[db_column_name] += f"\n\n--- Autre section pour même titre '{cleaned_title}' ---\n" + texte_section
                print(f"      -> Action: MAPPED to PREDEFINED column '{db_column_name}'")
            else:
                key_for_other = original_title_for_debug 
                other_sections_content[key_for_other] = texte_section # Stockage simplifié pour le test
                print(f"      -> Action: Added to OTHER_SECTIONS (key: '{key_for_other}')")
        
        print(f"--- FIN DÉBOGAGE JSON SPÉCIFIQUE ---")
        # Ici, vous pourriez ajouter l'insertion dans la DB si vous voulez tester cette partie aussi.
        # Par exemple, en appelant une version modifiée de process_rcp_with_segmentation_logic
        # ou en reconstruisant la logique d'insertion ici.
        # Pour l'instant, on se concentre sur le mappage.

    elif os.path.exists(master_json_file_path):
        print(f"INFO: Lecture du fichier JSON maître: {master_json_file_path}...")
        try:
            with open(master_json_file_path, 'r', encoding='utf-8') as f:
                all_rcps_data = json.load(f)
            items_to_process_dict = all_rcps_data
            if debug_specific_cis_list_global: # Si la liste n'est pas pour le test spécifique ci-dessus
                items_to_process_dict = {cis: text for cis, text in all_rcps_data.items() if cis in debug_specific_cis_list_global}
                if not items_to_process_dict:
                    print(f"AVERTISSEMENT: Aucun des CIS spécifiés pour le débogage ({debug_specific_cis_list_global}) n'a été trouvé dans {master_json_file_path}.")
        except Exception as e:
            print(f"Erreur lors de la lecture ou du parsing de {master_json_file_path}: {e}")
            if conn: conn.close()
            exit()
        if not isinstance(items_to_process_dict, dict):
            print(f"Erreur: Contenu de {master_json_file_path} n'est pas un dictionnaire ou aucun CIS à traiter.")
            if conn: conn.close()
            exit()
    else:
         print(f"Erreur: Le fichier JSON maître '{master_json_file_path}' n'a pas été trouvé et le mode de test spécifique n'est pas activé.")


    if items_to_process_dict: # S'assurer qu'il y a quelque chose à traiter
        print(f"Traitement de {len(items_to_process_dict)} entrées CIS.")
        cis_processed_count = 0
        cis_inserted_count = 0
        commit_interval = 100

        for cis_code, rcp_text_content in tqdm(items_to_process_dict.items(), desc="Transformation RCPs"):
            source_filename = f"from_master_json_{cis_code}"
            if process_rcp_with_segmentation_logic(cis_code, rcp_text_content, source_filename, conn, current_debug_cis_list=debug_specific_cis_list_global):
                cis_inserted_count += 1
            
            cis_processed_count += 1
            # Commit par intervalle seulement si on ne débogue pas un CIS spécifique (pour ne pas interférer avec les logs)
            if not debug_specific_cis_list_global and cis_processed_count > 0 and cis_processed_count % commit_interval == 0:
                conn.commit()
        
        conn.commit() 
        print(f"\nTraitement terminé. {cis_processed_count} entrées CIS traitées.")
        print(f"{cis_inserted_count} RCPs valides insérés/mis à jour dans la table '{TABLE_NAME}'.")
    
    if conn: conn.close()
