# --- Fichier : preprocess_rcp_for_ai.py ---
import sqlite3
import re
import datetime
from tqdm import tqdm
import traceback

# --- Configuration ---
DATABASE_NAME = "medicaments.db"
# Liste des sections cibles normalisées que nous voulons spécifiquement identifier.
# L'ordre ici n'est pas crucial pour l'extraction, mais peut l'être pour la présentation future.
TARGET_SECTIONS_NORMALIZED = [
    "denomination", # Souvent en début de RCP, non numéroté explicitement
    "composition_qualitative_quantitative",
    "forme_pharmaceutique",
    "donnees_cliniques_indications_therapeutiques",
    "donnees_cliniques_posologie_mode_administration",
    "donnees_cliniques_contre_indications",
    "donnees_cliniques_mises_garde_speciales_precautions_emploi",
    "donnees_cliniques_interactions_autres_medicaments_autres_formes_interaction",
    "donnees_cliniques_fertilite_grossesse_allaitement",
    "donnees_cliniques_effets_conduite_utilisation_machines",
    "donnees_cliniques_effets_indesirables",
    "donnees_cliniques_surdosage",
    "proprietes_pharmacologiques_pharmacodynamiques",
    "proprietes_pharmacologiques_pharmacocinetiques",
    "proprietes_pharmacologiques_donnees_securite_preclinique",
    "donnees_pharmaceutiques_liste_excipients",
    "donnees_pharmaceutiques_incompatibilites_majeures",
    "donnees_pharmaceutiques_duree_conservation",
    "donnees_pharmaceutiques_precautions_particulieres_conservation",
    "donnees_pharmaceutiques_nature_contenu_emballage_exterieur",
    "donnees_pharmaceutiques_precautions_particulieres_elimination_manipulation",
    "titulaire_autorisation_mise_marche",
    "numero_autorisation_mise_marche",
    "date_premiere_autorisation_renouvellement_autorisation",
    "date_mise_jour_texte",
    "instructions_posologiques_patients", # Moins fréquent, mais possible
    "informations_complementaires" # Section fourre-tout pour la fin
]

# --- Logging ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_warning(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] WARNING: {message}")

def log_error(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] ERROR: {message}")

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        log_error(f"Database connection error: {e}\n{traceback.format_exc()}")
        raise

def normalize_section_title(title: str) -> str:
    """Normalise un titre de section pour correspondre aux noms cibles."""
    # Nettoyage initial: minuscules, suppression de la ponctuation de début/fin et des numérotations
    # La regex \d+[\.\)\s]*(\w) capture "1. Mot", "1) Mot", "1 Mot" et prend "Mot"
    # ou simplement \d+[\.\)\s]* pour supprimer "1. ", "1) ", "1 "
    
    normalized = title.lower().strip()
    
    # Supprimer les numérotations communes comme "1. ", "1) ", "I. ", "A. " etc.
    normalized = re.sub(r"^[0-9ivxlcdm]+[\.\)\s]+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^[a-z][\.\)\s]+", "", normalized, flags=re.IGNORECASE) # Pour "a. ", "b) "

    # Remplacements spécifiques basés sur les mots-clés et le contexte
    # Cet ordre est important
    if "dénomination du médicament" in normalized or "denomination du medicament" in normalized: return "denomination"
    if "composition qualitative et quantitative" in normalized: return "composition_qualitative_quantitative"
    if "forme pharmaceutique" in normalized: return "forme_pharmaceutique"
    if "indications thérapeutiques" in normalized or "indications therapeutiques" in normalized: return "donnees_cliniques_indications_therapeutiques"
    if "posologie et mode d’administration" in normalized or "posologie et mode d'administration" in normalized: return "donnees_cliniques_posologie_mode_administration"
    if "contre-indications" in normalized or "contre indications" in normalized: return "donnees_cliniques_contre_indications"
    if "mises en garde spéciales et précautions d’emploi" in normalized or "mises en garde speciales et precautions d'emploi" in normalized or "mises en garde et précautions d’emploi" in normalized or "mises en garde et precautions d'emploi" in normalized: return "donnees_cliniques_mises_garde_speciales_precautions_emploi"
    if "interactions avec d’autres médicaments et autres formes d’interactions" in normalized or "interactions avec d'autres medicaments et autres formes d'interactions" in normalized: return "donnees_cliniques_interactions_autres_medicaments_autres_formes_interaction"
    if "fertilité, grossesse et allaitement" in normalized or "fertilite, grossesse et allaitement" in normalized: return "donnees_cliniques_fertilite_grossesse_allaitement"
    if "effets sur l’aptitude à conduire des véhicules et à utiliser des machines" in normalized or "effets sur l'aptitude a conduire des vehicules et a utiliser des machines" in normalized: return "donnees_cliniques_effets_conduite_utilisation_machines"
    if "effets indésirables" in normalized or "effets indesirables" in normalized: return "donnees_cliniques_effets_indesirables"
    if "surdosage" in normalized: return "donnees_cliniques_surdosage"
    if "propriétés pharmacodynamiques" in normalized or "proprietes pharmacodynamiques" in normalized: return "proprietes_pharmacologiques_pharmacodynamiques"
    if "propriétés pharmacocinétiques" in normalized or "proprietes pharmacocinetiques" in normalized: return "proprietes_pharmacologiques_pharmacocinetiques"
    if "données de sécurité préclinique" in normalized or "donnees de securite preclinique" in normalized: return "proprietes_pharmacologiques_donnees_securite_preclinique"
    if "liste des excipients" in normalized: return "donnees_pharmaceutiques_liste_excipients"
    if "incompatibilités majeures" in normalized or "incompatibilites majeures" in normalized: return "donnees_pharmaceutiques_incompatibilites_majeures"
    if "durée de conservation" in normalized or "duree de conservation" in normalized: return "donnees_pharmaceutiques_duree_conservation"
    if "précautions particulières de conservation" in normalized or "precautions particulieres de conservation" in normalized: return "donnees_pharmaceutiques_precautions_particulieres_conservation"
    if "nature et contenu de l’emballage extérieur" in normalized or "nature et contenu de l'emballage exterieur" in normalized or "nature et contenu de l’emballage" in normalized : return "donnees_pharmaceutiques_nature_contenu_emballage_exterieur"
    if "précautions particulières d’élimination et de manipulation" in normalized or "precautions particulieres d'elimination et de manipulation" in normalized or "précautions particulières d’élimination" in normalized: return "donnees_pharmaceutiques_precautions_particulieres_elimination_manipulation"
    if "titulaire de l’autorisation de mise sur le marché" in normalized or "titulaire de l'autorisation de mise sur le marche" in normalized : return "titulaire_autorisation_mise_marche"
    if "numéro(s) d’autorisation de mise sur le marché" in normalized or "numero(s) d'autorisation de mise sur le marche" in normalized or "numéro d’amm" in normalized or "numero d'amm" in normalized: return "numero_autorisation_mise_marche"
    if "date de première autorisation/de renouvellement de l’autorisation" in normalized or "date de premiere autorisation/de renouvellement de l'autorisation" in normalized: return "date_premiere_autorisation_renouvellement_autorisation"
    if "date de mise à jour du texte" in normalized or "date de mise a jour du texte" in normalized: return "date_mise_jour_texte"
    
    # Fallback plus générique, mais moins précis
    normalized = re.sub(r'[^a-z0-9_]+', '_', normalized) # Remplace tout non alphanumérique par _
    normalized = normalized.strip('_')
    
    # Si après tout ça, c'est vide, ou trop court, on met un nom générique
    if not normalized or len(normalized) < 5 : return "section_inconnue"

    return normalized[:100] # Limiter la longueur pour éviter des noms de colonnes excessifs si jamais utilisé ainsi

def segment_rcp(rcp_text: str, code_cis: str) -> list[tuple[str, str, str, int]]:
    """
    Segmente le texte d'un RCP en sections candidates.
    Retourne une liste de tuples: (code_cis, nom_section_normalise, titre_original, texte_section, ordre)
    """
    sections = []
    if not rcp_text or rcp_text.isspace():
        return sections

    # Regex pour identifier les titres de section.
    # Un titre est typiquement en majuscules, ou commence par un numéro, ou est suivi par plusieurs sauts de ligne.
    # Cette regex est une heuristique et pourrait nécessiter des ajustements.
    # Elle cherche des lignes qui :
    # - Sont entièrement en majuscules (avec des chiffres, des espaces, des apostrophes, des tirets).
    # - Ou commencent par un numéro (ex: "1.", "1)", "I.", "A.") suivi de texte.
    # - Ne sont pas trop longues (max 150 caractères pour un titre).
    # - Et sont suivies par au moins un saut de ligne (pour éviter les faux positifs dans des listes)
    #   et ne sont pas immédiatement suivies par un autre "titre" (logique de split).
    # Pattern: Ligne de titre (capture group 1), puis contenu jusqu'au prochain titre (capture group 2)
    # (?=...) est un lookahead positif.
    # Note: L'ordre des sections sera important pour les capturer correctement.
    # Les sections sont séparées par leurs titres.
    # La regex essaie de trouver "TITRE DE SECTION \n\n Texte de la section ..."
    # \n{2,} : Au moins deux sauts de ligne pour marquer une séparation (paragraphe)

    # Titres potentiels :
    # - Texte en majuscules de plus de X mots ou Y caractères
    # - Texte commençant par "X. " ou "X." (X étant un chiffre ou une lettre)
    # - Format spécifique ANSM "X. DENOMINATION DU MEDICAMENT"
    # Pour simplifier, on cherche des lignes qui ressemblent à des titres.
    # Un titre est une ligne qui ne se termine pas par un point (sauf si c'est un acronyme),
    # qui est relativement courte, et qui est suivie par du contenu.

    # Stratégie :
    # 1. Tenter de splitter par des titres numérotés clairement (e.g., "1. TITRE", "2. TITRE")
    # 2. Si peu de résultats, tenter de splitter par des lignes majoritairement en majuscules.
    # 3. Traiter le début du document comme une section potentielle "avant le premier titre".

    # Regex pour les titres numérotés (ex: "1. ", "1) ", "I. ", "A. ") OU lignes majoritairement en majuscules
    # un titre est une ligne pas trop longue, suivie d'un contenu
    # (?m) pour mode multiligne, ^ ancre au début de la ligne
    # Un titre a souvent moins de 150 caractères.
    # On cherche des lignes qui ne sont pas des phrases complètes (ne finissant pas par un point, sauf acronymes)
    # Et qui sont en majuscules ou numérotées.
    title_pattern = re.compile(
        r"^(?P<title>"
        # Soit une numérotation type ANSM (1. , 2. , etc.)
        r"(?:[0-9]{1,2}\s*[.]\s*[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ\s\(\)\-\',\/&0-9]{5,150}[^\.\n])" # Ex: "1. DENOMINATION DU MEDICAMENT"
        # Soit une ligne en majuscules (au moins 3 mots ou 15 chars, pas de point à la fin)
        r"|(?:[A-ZÀ-ÖØ-Þ]{1}[A-ZÀ-ÖØ-Þ\s\(\)\-\',\/&0-9]{10,150}[^\.\n])" # Ex: "DENOMINATION DU MEDICAMENT" mais pas "AMM."
        # Soit une numérotation plus simple (1., 1), A., A) )
        r"|(?:[0-9a-zA-Z]{1,3}[\.\)]\s+[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-ÖØ-Þ\s\(\)\-\',\/&0-9]{5,150}[^\.\n])"
        r")\s*$", 
        re.MULTILINE
    )
    
    # Pré-nettoyage léger du texte RCP global
    rcp_text_cleaned = rcp_text.replace('\r\n', '\n').replace('\r', '\n')
    rcp_text_cleaned = re.sub(r'\n{3,}', '\n\n', rcp_text_cleaned) # Max 2 sauts de ligne consécutifs
    rcp_text_cleaned = rcp_text_cleaned.strip()

    split_points = []
    for match in title_pattern.finditer(rcp_text_cleaned):
        split_points.append({'title': match.group('title').strip(), 'start': match.start(), 'end': match.end()})

    if not split_points:
        # Si aucun titre n'est trouvé avec le pattern, on considère tout le texte comme une seule section
        # ou on essaie une heuristique plus simple (par exemple, lignes courtes en majuscules).
        # Pour l'instant, si pas de titres structurés, on stocke l'intégralité.
        normalized_name = "contenu_integral_non_structure"
        sections.append((normalized_name, "Texte intégral", rcp_text_cleaned, 0))
        # log_warning(f"CIS {code_cis}: Aucun titre structuré trouvé, stockage du contenu intégral.")
        return sections

    # Ajouter une section pour le contenu avant le premier titre trouvé (si pertinent)
    first_title_start = split_points[0]['start']
    if first_title_start > 0:
        text_before_first_title = rcp_text_cleaned[:first_title_start].strip()
        if len(text_before_first_title) > 50: # Seuil pour considérer le contenu comme significatif
            # Essayer de deviner un titre (ex: "introduction" ou basé sur les premiers mots)
            # ou utiliser un nom générique.
            # Pour l'instant, on va essayer de le normaliser avec le début du texte
            guessed_title_before = text_before_first_title.split('\n')[0].strip()
            normalized_name_before = normalize_section_title(guessed_title_before if guessed_title_before else "introduction_presumee")
            if normalized_name_before == "section_inconnue" and "dénomination" in text_before_first_title.lower(): # Cas fréquent
                 normalized_name_before = "denomination"
            elif normalized_name_before == "section_inconnue" and len(text_before_first_title.split()) < 10: # Si c'est très court, c'est peut-être un vrai titre
                normalized_name_before = normalize_section_title(text_before_first_title)

            sections.append((normalized_name_before, guessed_title_before, text_before_first_title, 0))

    # Traiter les sections identifiées
    for i, point in enumerate(split_points):
        titre_original = point['title']
        nom_normalise = normalize_section_title(titre_original)
        
        start_content = point['end'] # Le contenu commence après le titre
        # Le contenu de la section va jusqu'au début du prochain titre, ou la fin du texte
        end_content = split_points[i+1]['start'] if i + 1 < len(split_points) else len(rcp_text_cleaned)
        
        texte_section = rcp_text_cleaned[start_content:end_content].strip()
        
        # Nettoyage final du texte de la section (facultatif, dépend de la qualité voulue)
        texte_section = re.sub(r'\s*\n\s*', '\n', texte_section).strip() # Normaliser les sauts de ligne internes
        texte_section = re.sub(r'\n{3,}', '\n\n', texte_section)

        if texte_section: # N'ajouter que si la section a du contenu
            sections.append((nom_normalise, titre_original, texte_section, i + 1)) # i+1 pour l'ordre

    # Filtrer les sections vides ou trop courtes (après nettoyage)
    final_sections = []
    for norm_name, orig_title, text, order in sections:
        if text and len(text) > 20 : # Seuil de longueur pour une section pertinente
             # Si une section est trop longue et non normalisée, elle peut être "contenu_integral_non_structure"
            if norm_name == "contenu_integral_non_structure" and len(text) > 50000: # Arbitraire, à ajuster
                log_warning(f"CIS {code_cis}: Section 'contenu_integral_non_structure' très longue ({len(text)} chars). Vérification manuelle peut être nécessaire.")
            final_sections.append((norm_name, orig_title, text, order))
        # else:
        #     log_info(f"CIS {code_cis}: Section '{orig_title}' ({norm_name}) skippée car trop courte après nettoyage: '{text[:50]}...'")


    if not final_sections and rcp_text_cleaned: # Si après tout ça, on a rien mais il y avait du texte
        normalized_name = "contenu_integral_difficile_a_segmenter"
        log_warning(f"CIS {code_cis}: Segmentation a échoué à produire des sections valides, stockage du contenu intégral difficile à segmenter.")
        final_sections.append((normalized_name, "Texte intégral (segmentation difficile)", rcp_text_cleaned, 0))

    return final_sections


def process_all_rcps_for_segmentation():
    log_info("--- Démarrage de la segmentation des RCPs ---")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Récupérer les code_cis des RCPs qui n'ont pas encore été segmentés
        # On vérifie si un code_cis de RCPs existe dans RCP_Sections
        # Cela évite de re-segmenter si le script est relancé.
        # ATTENTION: Si la logique de segmentation change, il faudra vider RCP_Sections avant.
        cursor.execute("""
            SELECT r.code_cis, r.texte_rcp
            FROM RCPs r
            LEFT JOIN RCP_Sections rs ON r.code_cis = rs.code_cis
            WHERE rs.code_cis IS NULL 
              AND r.texte_rcp IS NOT NULL 
              AND r.texte_rcp != '' 
              AND r.texte_rcp != 'TEXTE_VIDE_OU_COURT'
              AND r.texte_rcp != 'RCP_NON_TROUVE_404'
              AND r.texte_rcp != 'AUCUN_DOCUMENT_DISPONIBLE'
              AND NOT r.texte_rcp LIKE 'CONTENU_NON_HTML:%'
              AND NOT r.texte_rcp LIKE 'ERREUR_HTTP_%'
              AND NOT r.texte_rcp LIKE 'ERREUR_TIMEOUT%'
              AND NOT r.texte_rcp LIKE 'ERREUR_CONNECTION_EXCEPTION:%'
              AND NOT r.texte_rcp LIKE 'ERREUR_REQUEST_EXCEPTION:%'
              AND NOT r.texte_rcp LIKE 'ERREUR_INATTENDUE:%'
              AND NOT r.texte_rcp LIKE 'ERREUR_UNATTENDUE_FETCH:%'
              AND NOT r.texte_rcp LIKE 'ERREUR_WORKER_INATTENDUE%'
        """)
        
        rcps_to_process = cursor.fetchall()
        total_rcps = len(rcps_to_process)

        if total_rcps == 0:
            log_info("Aucun nouveau RCP à segmenter.")
            return

        log_info(f"Nombre de RCPs à segmenter : {total_rcps}")
        
        processed_count = 0
        commit_interval = 50 # Commit toutes les X RCPs segmentées

        for code_cis, texte_rcp in tqdm(rcps_to_process, desc="Segmentation RCPs"):
            try:
                sections = segment_rcp(texte_rcp, code_cis)
                
                if sections:
                    current_time = datetime.datetime.now().isoformat()
                    sections_data_to_insert = []
                    for norm_name, orig_title, text_section, order in sections:
                        sections_data_to_insert.append(
                            (code_cis, norm_name, orig_title, text_section, order, current_time)
                        )
                    
                    cursor.executemany("""
                        INSERT INTO RCP_Sections (code_cis, nom_section_normalise, titre_section_original, texte_section, ordre_apparition, date_segmentation)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, sections_data_to_insert)
                
                processed_count += 1
                if processed_count % commit_interval == 0:
                    conn.commit()
                    # log_info(f"{processed_count}/{total_rcps} RCPs segmentés et commités.")

            except Exception as e_segment:
                log_error(f"Erreur lors de la segmentation du RCP pour CIS {code_cis}: {e_segment}\n{traceback.format_exc(lim=1)}")
                # On pourrait vouloir marquer ce RCP comme "erreur_segmentation" pour ne pas le retenter
                # ou simplement continuer.

        conn.commit() # Commit final
        log_info(f"Segmentation terminée. {processed_count}/{total_rcps} RCPs traités.")

    except sqlite3.Error as e_sql:
        log_error(f"Erreur SQLite pendant la segmentation: {e_sql}\n{traceback.format_exc()}")
        if conn:
            conn.rollback()
    except Exception as e_main:
        log_error(f"Erreur inattendue dans process_all_rcps_for_segmentation: {e_main}\n{traceback.format_exc()}")
    finally:
        if conn:
            conn.close()
            log_info("Connexion à la base de données fermée.")

if __name__ == "__main__":
    # Avant de lancer ce script, assurez-vous que la table RCP_Sections a été créée
    # par database_setup.py et qu'elle est vide si vous voulez tout re-segmenter.
    # Pour une première exécution, ou si vous voulez forcer la re-segmentation,
    # vous pouvez vider la table RCP_Sections :
    # conn = get_db_connection()
    # conn.execute("DELETE FROM RCP_Sections;")
    # conn.commit()
    # conn.close()
    # log_info("Table RCP_Sections vidée avant la segmentation.")
    
    process_all_rcps_for_segmentation()