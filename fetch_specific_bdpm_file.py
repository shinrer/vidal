import requests
import json
from pathlib import Path
import datetime

# --- Configuration ---
# URL pattern pour télécharger les fichiers texte individuels de la BDPM
BDPM_TEXT_FILE_URL_TEMPLATE = "https://base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier={filename}"
# Répertoire où sauvegarder le fichier texte téléchargé
TEXT_FILE_DOWNLOAD_DIR = Path("./data/downloaded_text_files")
# Fichier à télécharger (CIS_bdpm.txt est un bon choix pour une liste complète de CIS)
# Tu peux changer pour "CIS_CPD_bdpm.txt" si tu préfères ce fichier spécifiquement.
TARGET_BDPM_FILENAME = "CIS_bdpm.txt"
# Fichier JSON de sortie pour les codes CIS uniques
OUTPUT_JSON_CIS_CODES_FILE = Path("unique_cis_codes.json")

REQUEST_TIMEOUT = 30  # seconds

# --- Logging (Simple Print-Based) ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] ERROR: {message}")

# --- Fonctions ---

def download_specific_text_file(filename: str, download_dir: Path, url_template: str) -> Path | None:
    """
    Télécharge un fichier texte spécifique depuis la base de données publique des médicaments.
    Retourne le chemin vers le fichier téléchargé, ou None en cas d'erreur.
    """
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log_error(f"Impossible de créer le répertoire de téléchargement {download_dir}: {e}")
        return None

    file_url = url_template.format(filename=filename)
    destination_path = download_dir / filename

    log_info(f"Tentative de téléchargement de {filename} depuis {file_url}...")
    try:
        response = requests.get(file_url, timeout=REQUEST_TIMEOUT, stream=True)
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)

        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log_info(f"Téléchargement réussi de {filename} vers {destination_path}")
        return destination_path
    except requests.exceptions.Timeout:
        log_error(f"Timeout lors du téléchargement de {filename} depuis {file_url}.")
        return None
    except requests.exceptions.HTTPError as e:
        log_error(f"Erreur HTTP {e.response.status_code} lors du téléchargement de {filename}: {e.response.reason}")
        return None
    except requests.exceptions.RequestException as e:
        log_error(f"Erreur réseau ou de requête lors du téléchargement de {filename}: {e}")
        return None
    except IOError as e:
        log_error(f"Erreur d'écriture du fichier {filename} vers {destination_path}: {e}")
        return None
    except Exception as e:
        log_error(f"Une erreur inattendue est survenue lors du téléchargement de {filename}: {e}")
        return None


def extract_cis_codes_from_file(file_path: Path, output_json_path: Path) -> list[str]:
    """
    Extrait les codes CIS (supposés être dans la première colonne, séparés par des tabulations)
    du fichier texte donné et les sauvegarde dans un fichier JSON.
    Les fichiers BDPM sont généralement encodés en latin-1.
    Retourne une liste de codes CIS uniques et triés.
    """
    if not file_path or not file_path.exists():
        log_error(f"Le fichier source {file_path} n'a pas été trouvé pour l'extraction des codes CIS.")
        return []

    unique_cis_set = set()
    log_info(f"Extraction des codes CIS depuis {file_path.name}...")
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            # Optionnel: sauter la première ligne si c'est un en-tête (non standard pour BDPM mais au cas où)
            # next(f, None) # Décommenter si la première ligne est un header à ignorer
            for line_num, line in enumerate(f, 1):
                fields = line.strip().split('\t')
                if fields and fields[0]:  # Vérifie que la ligne n'est pas vide et que le premier champ existe
                    code_cis = fields[0]
                    # Validation basique d'un code CIS (typiquement 8 chiffres, mais on reste flexible)
                    # La documentation officielle indique que le code CIS est numérique.
                    if code_cis.isdigit() and len(code_cis) >= 6 and len(code_cis) <= 8 : # ex: 60480337
                        unique_cis_set.add(code_cis)
                    # else:
                    #     if line_num > 1: # Ne pas logger pour la première ligne si c'est un header potentiel
                    #         print(f"DEBUG: Ligne {line_num}: Code CIS non valide ou vide trouvé: '{code_cis}' dans {file_path.name}")
                # else:
                #     if line_num > 1:
                #         print(f"DEBUG: Ligne {line_num}: Ligne vide ou malformée dans {file_path.name}")

        if not unique_cis_set:
            log_warning(f"Aucun code CIS valide n'a été extrait de {file_path.name}. "
                        f"Vérifiez le contenu du fichier ou le format attendu.")
            return []

        cis_list = sorted(list(unique_cis_set))

        with open(output_json_path, 'w', encoding='utf-8') as jf:
            json.dump(cis_list, jf, indent=4)
        log_info(f"{len(cis_list)} codes CIS uniques ont été extraits et sauvegardés dans {output_json_path.name}")
        return cis_list

    except UnicodeDecodeError as e:
        log_error(f"Erreur d'encodage lors de la lecture de {file_path.name}. "
                  f"Assurez-vous qu'il est en 'latin-1' ou ajustez l'encodage: {e}")
        return []
    except IOError as e:
        log_error(f"Erreur d'entrée/sortie lors de la lecture de {file_path.name} "
                  f"ou de l'écriture de {output_json_path.name}: {e}")
        return []
    except Exception as e:
        log_error(f"Une erreur inattendue est survenue lors de l'extraction des codes CIS: {e}")
        return []

# --- Exécution principale ---
def main():
    log_info(f"--- Démarrage du script pour récupérer le fichier {TARGET_BDPM_FILENAME} et extraire les codes CIS ---")

    # Étape 1: Télécharger le fichier texte spécifié
    downloaded_file_path = download_specific_text_file(
        filename=TARGET_BDPM_FILENAME,
        download_dir=TEXT_FILE_DOWNLOAD_DIR,
        url_template=BDPM_TEXT_FILE_URL_TEMPLATE
    )

    if downloaded_file_path:
        # Étape 2: Extraire les codes CIS du fichier téléchargé
        extracted_codes = extract_cis_codes_from_file(
            file_path=downloaded_file_path,
            output_json_path=OUTPUT_JSON_CIS_CODES_FILE
        )
        if extracted_codes:
            log_info(f"Processus terminé avec succès. {len(extracted_codes)} codes CIS prêts dans {OUTPUT_JSON_CIS_CODES_FILE}.")
        else:
            log_error("Échec de l'extraction des codes CIS.")
    else:
        log_error(f"Échec du téléchargement de {TARGET_BDPM_FILENAME}. Impossible de continuer.")

    log_info("--- Script terminé ---")

if __name__ == "__main__":
    main()