import requests

def get_html_content(url):
    """
    Récupère le contenu HTML d'une URL donnée.

    Args:
        url (str): L'URL de la page à récupérer.

    Returns:
        str: Le contenu HTML de la page, ou None en cas d'erreur.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        # response.text utilise l'encodage détecté par requests, ce qui est généralement correct.
        # Pour cette page spécifique, il semble que l'encodage soit bien géré par requests.
        # Si vous aviez des soucis d'encodage, il faudrait inspecter response.encoding et
        # potentiellement décoder response.content manuellement avec le bon encodage.
        html_content = response.text
        return html_content

    except requests.exceptions.HTTPError as http_err:
        print(f"Erreur HTTP: {http_err} - Code de statut: {response.status_code}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Erreur de connexion: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout de la requête: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Erreur générale de requête: {req_err}")
    
    return None

def save_html_to_file(html_content, filename="page_output.html"):
    """
    Sauvegarde le contenu HTML dans un fichier.

    Args:
        html_content (str): La chaîne de caractères HTML à sauvegarder.
        filename (str): Le nom du fichier où sauvegarder le HTML.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Le contenu HTML a été sauvegardé avec succès dans '{filename}'")
    except IOError as e:
        print(f"Erreur lors de l'écriture du fichier '{filename}': {e}")
    except Exception as e:
        print(f"Une erreur inattendue est survenue lors de la sauvegarde du fichier: {e}")

# --- Programme Principal ---
if __name__ == "__main__":
    target_url = "https://base-donnees-publique.medicaments.gouv.fr/affichageDoc.php?specid=60219803&typedoc=R"
    output_filename = "page_medicament_recuperee.html" # Vous pouvez changer ce nom

    print(f"Récupération du HTML depuis : {target_url}...")
    html_code = get_html_content(target_url)

    if html_code:
        print(f"Contenu HTML récupéré (longueur: {len(html_code)} caractères).")
        save_html_to_file(html_code, output_filename)
    else:
        print("Impossible de récupérer le contenu HTML. Le fichier ne sera pas créé.")