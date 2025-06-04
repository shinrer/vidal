import requests
from bs4 import BeautifulSoup
import json
import re

# SECTION_TITLES_MAP (tel que vous l'avez fourni, il est complet)
SECTION_TITLES_MAP = {
    "1. denomination du medicament": "DENOMINATION DU MEDICAMENT",
    "1. denomination du médicament": "DENOMINATION DU MEDICAMENT",
    "2. composition qualitative et quantitative": "COMPOSITION QUALITATIVE ET QUANTITATIVE",
    "3. forme pharmaceutique": "FORME PHARMACEUTIQUE",
    "4. donnees cliniques": "DONNEES CLINIQUES",
    "4. données cliniques": "DONNEES CLINIQUES",
    "5. proprietes pharmacologiques": "PROPRIETES PHARMACOLOGIQUES",
    "5. propriétés pharmacologiques": "PROPRIETES PHARMACOLOGIQUES",
    "6. donnees pharmaceutiques": "DONNEES PHARMACEUTIQUES",
    "6. données pharmaceutiques": "DONNEES PHARMACEUTIQUES",
    "7. titulaire de l’autorisation de mise sur le marche": "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",
    "7. titulaire de l'autorisation de mise sur le marche": "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",
    "8. numero(s) d’autorisation de mise sur le marche": "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",
    "8. numero(s) d'autorisation de mise sur le marche": "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",
    "9. date de premiere autorisation/de renouvellement de l’autorisation": "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION",
    "9. date de premiere autorisation/de renouvellement de l'autorisation": "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION",
    "10. date de mise a jour du texte": "DATE DE MISE A JOUR DU TEXTE",
    "11. dosimetrie": "DOSIMETRIE",
    "12. instructions pour la preparation des radiopharmaceutiques": "INSTRUCTIONS POUR LA PREPARATION DES RADIOPHARMACEUTIQUES",

    "denomination du medicament": "DENOMINATION DU MEDICAMENT",
    "denomination du médicament": "DENOMINATION DU MEDICAMENT",
    "composition qualitative et quantitative": "COMPOSITION QUALITATIVE ET QUANTITATIVE",
    "forme pharmaceutique": "FORME PHARMACEUTIQUE",
    "donnees cliniques": "DONNEES CLINIQUES",
    "données cliniques": "DONNEES CLINIQUES",
    "proprietes pharmacologiques": "PROPRIETES PHARMACOLOGIQUES",
    "propriétés pharmacologiques": "PROPRIETES PHARMACOLOGIQUES",
    "donnees pharmaceutiques": "DONNEES PHARMACEUTIQUES",
    "données pharmaceutiques": "DONNEES PHARMACEUTIQUES",
    "titulaire de l’autorisation de mise sur le marche": "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",
    "titulaire de l'autorisation de mise sur le marche": "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",
    "numero(s) d’autorisation de mise sur le marche": "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",
    "numero(s) d'autorisation de mise sur le marche": "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",
    "date de premiere autorisation/de renouvellement de l’autorisation": "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION",
    "date de premiere autorisation/de renouvellement de l'autorisation": "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION",
    "date de mise a jour du texte": "DATE DE MISE A JOUR DU TEXTE",
    "dosimetrie": "DOSIMETRIE",
    "instructions pour la preparation des radiopharmaceutiques": "INSTRUCTIONS POUR LA PREPARATION DES RADIOPHARMACEUTIQUES",

    "4.1. indications thérapeutiques": "4.1. Indications thérapeutiques",
    "4.1 indications thérapeutiques": "4.1. Indications thérapeutiques", 
    "indications thérapeutiques": "4.1. Indications thérapeutiques",
    "4.2. posologie et mode d'administration": "4.2. Posologie et mode d'administration",
    "4.2 posologie et mode d'administration": "4.2. Posologie et mode d'administration",
    "posologie et mode d'administration": "4.2. Posologie et mode d'administration",
    "4.3. contre-indications": "4.3. Contre-indications",
    "4.3 contre-indications": "4.3. Contre-indications",
    "contre-indications": "4.3. Contre-indications",
    "4.4. mises en garde spéciales et précautions d'emploi": "4.4. Mises en garde spéciales et précautions d'emploi",
    "4.4 mises en garde spéciales et précautions d'emploi": "4.4. Mises en garde spéciales et précautions d'emploi",
    "mises en garde spéciales et précautions d'emploi": "4.4. Mises en garde spéciales et précautions d'emploi",
    "4.4. mises en garde spéciales et précautions d’emploi": "4.4. Mises en garde spéciales et précautions d'emploi", 
    "4.5. interactions avec d'autres médicaments et autres formes d'interactions": "4.5. Interactions avec d'autres médicaments et autres formes d'interactions",
    "4.5 interactions avec d'autres médicaments et autres formes d'interactions": "4.5. Interactions avec d'autres médicaments et autres formes d'interactions",
    "interactions avec d'autres médicaments et autres formes d'interactions": "4.5. Interactions avec d'autres médicaments et autres formes d'interactions",
    "4.6. fertilité, grossesse et allaitement": "4.6. Fertilité, grossesse et allaitement",
    "4.6 fertilité, grossesse et allaitement": "4.6. Fertilité, grossesse et allaitement",
    "fertilité, grossesse et allaitement": "4.6. Fertilité, grossesse et allaitement",
    "grossesse et allaitement": "4.6. Fertilité, grossesse et allaitement",
    "4.7. effets sur l'aptitude à conduire des véhicules et à utiliser des machines": "4.7. Effets sur l'aptitude à conduire des véhicules et à utiliser des machines",
    "4.7 effets sur l'aptitude à conduire des véhicules et à utiliser des machines": "4.7. Effets sur l'aptitude à conduire des véhicules et à utiliser des machines",
    "effets sur l'aptitude à conduire des véhicules et à utiliser des machines": "4.7. Effets sur l'aptitude à conduire des véhicules et à utiliser des machines",
    "4.8. effets indésirables": "4.8. Effets indésirables",
    "4.8 effets indésirables": "4.8. Effets indésirables",
    "effets indésirables": "4.8. Effets indésirables",
    "4.9. surdosage": "4.9. Surdosage",
    "4.9 surdosage": "4.9. Surdosage",
    "surdosage": "4.9. Surdosage",
    "5.1. propriétés pharmacodynamiques": "5.1. Propriétés pharmacodynamiques",
    "5.1 propriétés pharmacodynamiques": "5.1. Propriétés pharmacodynamiques",
    "propriétés pharmacodynamiques": "5.1. Propriétés pharmacodynamiques",
    "5.2. propriétés pharmacocinétiques": "5.2. Propriétés pharmacocinétiques",
    "5.2 propriétés pharmacocinétiques": "5.2. Propriétés pharmacocinétiques",
    "propriétés pharmacocinétiques": "5.2. Propriétés pharmacocinétiques",
    "5.3. données de sécurité préclinique": "5.3. Données de sécurité préclinique",
    "5.3 données de sécurité préclinique": "5.3. Données de sécurité préclinique",
    "données de sécurité préclinique": "5.3. Données de sécurité préclinique",
    "données de sécurité préclinique": "5.3. Données de sécurité préclinique", 
    "6.1. liste des excipients": "6.1. Liste des excipients",
    "6.1 liste des excipients": "6.1. Liste des excipients",
    "liste des excipients": "6.1. Liste des excipients",
    "6.2. incompatibilités": "6.2. Incompatibilités",
    "6.2 incompatibilités": "6.2. Incompatibilités",
    "incompatibilités": "6.2. Incompatibilités",
    "6.3. durée de conservation": "6.3. Durée de conservation",
    "6.3 durée de conservation": "6.3. Durée de conservation",
    "durée de conservation": "6.3. Durée de conservation",
    "6.4. précautions particulières de conservation": "6.4. Précautions particulières de conservation",
    "6.4 précautions particulières de conservation": "6.4. Précautions particulières de conservation",
    "précautions particulières de conservation": "6.4. Précautions particulières de conservation",
    "6.5. nature et contenu de l'emballage extérieur": "6.5. Nature et contenu de l'emballage extérieur",
    "6.5 nature et contenu de l'emballage extérieur": "6.5. Nature et contenu de l'emballage extérieur",
    "nature et contenu de l'emballage extérieur": "6.5. Nature et contenu de l'emballage extérieur",
    "6.6. précautions particulières d’élimination et de manipulation": "6.6. Précautions particulières d’élimination et de manipulation", 
    "6.6. précautions particulières d'élimination et de manipulation": "6.6. Précautions particulières d’élimination et de manipulation", 
    "6.6 précautions particulières d'élimination et de manipulation": "6.6. Précautions particulières d’élimination et de manipulation",
    "précautions particulières d'élimination et de manipulation": "6.6. Précautions particulières d’élimination et de manipulation",

    "INDICATIONS THERAPEUTIQUES": "4.1. Indications thérapeutiques",
    "POSOLOGIE ET MODE D'ADMINISTRATION": "4.2. Posologie et mode d'administration",
    "CONTRE-INDICATIONS": "4.3. Contre-indications",
    "MISES EN GARDE SPECIALES ET PRECAUTIONS D'EMPLOI": "4.4. Mises en garde spéciales et précautions d'emploi",
    "INTERACTIONS AVEC D'AUTRES MEDICAMENTS ET AUTRES FORMES D'INTERACTIONS": "4.5. Interactions avec d'autres médicaments et autres formes d'interactions",
    "FERTILITE, GROSSESSE ET ALLAITEMENT": "4.6. Fertilité, grossesse et allaitement",
    "EFFETS SUR L'APTITUDE A CONDUIRE DES VEHICULES ET A UTILISER DES MACHINES": "4.7. Effets sur l'aptitude à conduire des véhicules et à utiliser des machines",
    "EFFETS INDESIRABLES": "4.8. Effets indésirables",
    "SURDOSAGE": "4.9. Surdosage",
    "PROPRIETES PHARMACODYNAMIQUES": "5.1. Propriétés pharmacodynamiques",
    "PROPRIETES PHARMACOCINETIQUES": "5.2. Propriétés pharmacocinétiques",
    "DONNEES DE SECURITE PRECLINIQUE": "5.3. Données de sécurité préclinique",
    "LISTE DES EXCIPIENTS": "6.1. Liste des excipients",
    "INCOMPATIBILITES": "6.2. Incompatibilités",
    "DUREE DE CONSERVATION": "6.3. Durée de conservation",
    "PRECAUTIONS PARTICULIERES DE CONSERVATION": "6.4. Précautions particulières de conservation",
    "NATURE ET CONTENU DE L'EMBALLAGE EXTERIEUR": "6.5. Nature et contenu de l'emballage extérieur",
    "PRECAUTIONS PARTICULIERES D’ELIMINATION ET DE MANIPULATION": "6.6. Précautions particulières d’élimination et de manipulation",
}

ORDERED_SECTION_KEYS = [
    "DENOMINATION DU MEDICAMENT", "COMPOSITION QUALITATIVE ET QUANTITATIVE", "FORME PHARMACEUTIQUE",
    "DONNEES CLINIQUES", "4.1. Indications thérapeutiques", "4.2. Posologie et mode d'administration",
    "4.3. Contre-indications", "4.4. Mises en garde spéciales et précautions d'emploi",
    "4.5. Interactions avec d'autres médicaments et autres formes d'interactions",
    "4.6. Fertilité, grossesse et allaitement",
    "4.7. Effets sur l'aptitude à conduire des véhicules et à utiliser des machines",
    "4.8. Effets indésirables", "4.9. Surdosage", "PROPRIETES PHARMACOLOGIQUES",
    "5.1. Propriétés pharmacodynamiques", "5.2. Propriétés pharmacocinétiques",
    "5.3. Données de sécurité préclinique", "DONNEES PHARMACEUTIQUES",
    "6.1. Liste des excipients", "6.2. Incompatibilités", "6.3. Durée de conservation",
    "6.4. Précautions particulières de conservation", "6.5. Nature et contenu de l'emballage extérieur",
    "6.6. Précautions particulières d’élimination et de manipulation",
    "TITULAIRE DE L’AUTORISATION DE MISE SUR LE MARCHE",
    "NUMERO(S) D’AUTORISATION DE MISE SUR LE MARCHE",
    "DATE DE PREMIERE AUTORISATION/DE RENOUVELLEMENT DE L’AUTORISATION",
    "DATE DE MISE A JOUR DU TEXTE", "DOSIMETRIE",
    "INSTRUCTIONS POUR LA PREPARATION DES RADIOPHARMACEUTIQUES"
]

def normalize_text(text):
    if not text: return ""
    text = str(text)
    text = text.lower()
    text = text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    text = text.replace('œ', 'oe').replace('æ', 'ae')
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def get_drug_info_from_cis(cis_code, debug_mode=False):
    url = f"https://base-donnees-publique.medicaments.gouv.fr/affichageDoc.php?specid={cis_code}&typedoc=R"
    print(f"Récupération des données pour le CIS {cis_code} depuis : {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6',
        'Connection': 'keep-alive', 'DNT': '1', 'Upgrade-Insecure-Requests': '1',
    }
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"Page récupérée (status {response.status_code}, encodage apparent: {response.apparent_encoding})")
        encoding_to_use = 'windows-1252' if response.apparent_encoding and '1252' in response.apparent_encoding.lower() else 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding=encoding_to_use)
        print(f"Soup créé avec encodage: {encoding_to_use}")
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête HTTP pour {cis_code}: {e}")
        return None

    extracted_data = {key: "" for key in ORDERED_SECTION_KEYS} # Correction de la NameError
    current_section_key = None
    active_section_content_parts = []
    content_container = soup.find('div', id='textDocument')
    if not content_container:
        print("Div principal 'textDocument' non trouvé.")
        return None # Ou retourner extracted_data vide
        
    elements_to_process = content_container.find_all(['p', 'table'], recursive=True)
    print(f"Traitement de {len(elements_to_process)} tags <p> ou <table> trouvés.")
    if debug_mode:
        print("\n[DEBUG] SECTION_TITLES_MAP (échantillon ciblé):")
        # Correction de la boucle pour afficher l'échantillon
        missing_example_titles = ["4.1. indications", "4.4. mises en garde", "6. donnees pharmaceutiques", "6.2. incompatibilites", "grossesse et allaitement"]
        for k_map_key in SECTION_TITLES_MAP:
            if any(sub in k_map_key for sub in missing_example_titles):
                 print(f"  '{k_map_key}' -> '{SECTION_TITLES_MAP[k_map_key]}'")
        print("------\n")

    suffix_to_remove = "Retour en haut de la page"

    for element in elements_to_process:
        raw_element_text = element.get_text(separator=' ', strip=True)
        if not raw_element_text:
            continue

        text_for_title_check_cleaned = raw_element_text
        if text_for_title_check_cleaned.endswith(suffix_to_remove):
            text_for_title_check_cleaned = text_for_title_check_cleaned[:-len(suffix_to_remove)].strip()
        
        normalized_title_candidate = normalize_text(text_for_title_check_cleaned)
        
        identified_section_name_if_title = None

        if debug_mode and normalized_title_candidate:
             print(f"    [DEBUG CHECK TITLE] Candidate (cleaned, normalized): REPR='{repr(normalized_title_candidate)}' VALUE='{normalized_title_candidate[:80]}'")

        if normalized_title_candidate in SECTION_TITLES_MAP:
            identified_section_name_if_title = SECTION_TITLES_MAP[normalized_title_candidate]
            if debug_mode:
                print(f"        [DEBUG] >>> TITRE MATCH 1 (cleaned normalized): '{normalized_title_candidate[:80]}' -> '{identified_section_name_if_title}'")
        
        if not identified_section_name_if_title: # Uniquement si le premier match a échoué
            normalized_raw_text_original = normalize_text(raw_element_text) # Texte brut original, juste normalisé
            if normalized_raw_text_original in SECTION_TITLES_MAP:
                identified_section_name_if_title = SECTION_TITLES_MAP[normalized_raw_text_original]
                if debug_mode:
                    print(f"        [DEBUG] >>> TITRE MATCH 2 (raw original normalized): '{normalized_raw_text_original[:80]}' -> '{identified_section_name_if_title}'")

        if not identified_section_name_if_title and element.name == 'p': # Uniquement si les précédents ont échoué et c'est un <p>
            strong_tag = element.find('strong') or element.find('b')
            if strong_tag:
                strong_text_content = strong_tag.get_text(separator=' ', strip=True)
                cleaned_strong_text_for_check = strong_text_content
                if cleaned_strong_text_for_check.endswith(suffix_to_remove):
                    cleaned_strong_text_for_check = cleaned_strong_text_for_check[:-len(suffix_to_remove)].strip()
                
                strong_text_normalized = normalize_text(cleaned_strong_text_for_check)
                if debug_mode and strong_text_normalized:
                    print(f"    [DEBUG CHECK STRONG/B] Candidate (strong cleaned, normalized): REPR='{repr(strong_text_normalized)}' VALUE='{strong_text_normalized[:80]}'")
                if strong_text_normalized in SECTION_TITLES_MAP:
                    identified_section_name_if_title = SECTION_TITLES_MAP[strong_text_normalized]
                    if debug_mode:
                        print(f"        [DEBUG] >>> TITRE MATCH 3 (strong/b): '{strong_text_normalized[:80]}' -> '{identified_section_name_if_title}'")
        
        if identified_section_name_if_title:
            if current_section_key and active_section_content_parts:
                full_content = "\n".join(part.strip() for part in active_section_content_parts if part.strip()).strip()
                if current_section_key in extracted_data:
                    if extracted_data[current_section_key] and full_content:
                        extracted_data[current_section_key] += "\n" + full_content
                    elif full_content:
                        extracted_data[current_section_key] = full_content
                elif debug_mode:
                     print(f"        [WARN] Clé précédente '{current_section_key}' non trouvée dans extracted_data pour sauvegarde.")
            
            current_section_key = identified_section_name_if_title
            active_section_content_parts = []
            if debug_mode: print(f"            --> Section active MAJ: {current_section_key}")
        
        elif current_section_key: 
            if raw_element_text: 
                active_section_content_parts.append(raw_element_text)
                if debug_mode and len(active_section_content_parts) < 5:
                    print(f"            [DEBUG]     + Contenu à '{current_section_key}': '{raw_element_text[:100]}...'")
        
        elif debug_mode and raw_element_text:
            normalized_debug_text = normalize_text(raw_element_text)
            if len(normalized_debug_text) > 5 and len(normalized_debug_text) < 150:
                print(f"    [DEBUG] Texte HORS SECTION (non titre ou titre manquant?): '{raw_element_text[:80]}' (Normalized: '{normalized_debug_text[:80]}')")

    if current_section_key and active_section_content_parts:
        full_content = "\n".join(part.strip() for part in active_section_content_parts if part.strip()).strip()
        if current_section_key in extracted_data:
            if extracted_data[current_section_key] and full_content:
                extracted_data[current_section_key] += "\n" + full_content
            elif full_content:
                extracted_data[current_section_key] = full_content
        elif debug_mode:
            print(f"        [WARN] Clé finale '{current_section_key}' non trouvée dans extracted_data pour sauvegarde.")

    final_ordered_data = {key: extracted_data.get(key, "").strip() for key in ORDERED_SECTION_KEYS}
    return final_ordered_data

def save_to_json(data, filename):
    if data is None:
        print(f"Aucune donnée à sauvegarder pour {filename}.")
        return
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Données sauvegardées avec succès dans {filename}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde JSON pour {filename}: {e}")

if __name__ == "__main__":
    default_cis_code = "60219803" 
    user_cis_code = input(f"Entrez le code CIS (ex: {default_cis_code}): ").strip()
    if not user_cis_code:
        user_cis_code = default_cis_code
    
    debug_parsing = True 

    if not user_cis_code.isdigit():
        print("Le code CIS doit être numérique.")
    else:
        drug_data = get_drug_info_from_cis(user_cis_code, debug_mode=debug_parsing)
        if drug_data:
            found_sections_count = sum(1 for section_content in drug_data.values() if section_content)
            print(f"\n--- {found_sections_count}/{len(ORDERED_SECTION_KEYS)} sections avec contenu pour CIS {user_cis_code} ---")
            
            print("\nSections VIDES ou NON TROUVÉES (dans le JSON final):")
            for section_key_ordered in ORDERED_SECTION_KEYS: 
                if not drug_data.get(section_key_ordered): 
                    print(f"  - {section_key_ordered}")
            
            if found_sections_count > 0 :
                output_filename = f"rcp_cis_{user_cis_code}.json"
                save_to_json(drug_data, output_filename)
            else:
                print(f"Aucun contenu de section n'a été extrait pour le CIS {user_cis_code}. Vérifiez les logs de debug.")
        else:
            print(f"Impossible de récupérer ou de traiter les données pour le CIS {user_cis_code}.")
    
    print("\nFin du processus de scraping.")
