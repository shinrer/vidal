import requests

def get_and_save_html(url, output_filename="page_content.html"):
    """
    Récupère le contenu HTML d'une URL et le sauvegarde dans un fichier.

    Args:
        url (str): L'URL de la page web à récupérer.
        output_filename (str): Le nom du fichier où sauvegarder le HTML.
    """
    print(f"Tentative de récupération du HTML depuis : {url}")

    # Utiliser des en-têtes similaires à ceux que nous avons utilisés pour le scraping
    # pour augmenter les chances de succès et éviter les erreurs 403.
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'DNT': '1', # Do Not Track
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # Effectuer la requête GET avec les en-têtes
        response = requests.get(url, headers=headers, timeout=20) # Timeout de 20 secondes

        # Vérifier si la requête a réussi (code de statut 200)
        response.raise_for_status() # Lèvera une HTTPError pour les mauvais statuts (4xx ou 5xx)

        # Essayer de déterminer l'encodage correct.
        # response.text utilise response.apparent_encoding par défaut si response.encoding n'est pas défini.
        # Pour être sûr, on peut le définir explicitement si besoin.
        # Si l'encodage est mal détecté, les caractères spéciaux peuvent être incorrects.
        # L'en-tête Content-Type peut parfois donner l'encodage, ou response.apparent_encoding.
        
        # Pour le site BDPM, il semble souvent être 'windows-1252' ou 'iso-8859-1'
        # Si vous savez que l'encodage est spécifique, vous pouvez le forcer ici:
        # response.encoding = 'windows-1252'
        # Sinon, laissez requests le deviner ou utilisez apparent_encoding:
        if response.apparent_encoding:
            response.encoding = response.apparent_encoding
        else:
            # Fallback à UTF-8 si rien n'est détecté, bien que ce ne soit pas toujours correct.
            response.encoding = 'utf-8'

        html_content = response.text # Récupérer le contenu textuel (HTML)

        print(f"\n--- Contenu HTML de {url} (début) ---")
        print(html_content[:2000]) # Afficher les 2000 premiers caractères
        if len(html_content) > 2000:
            print("...\n[HTML complet sauvegardé dans le fichier]")
        print("--- Fin de l'aperçu HTML ---")

        # Sauvegarder le contenu HTML dans un fichier
        with open(output_filename, "w", encoding=response.encoding, errors='replace') as file:
            file.write(html_content)
        print(f"\nLe contenu HTML complet a été sauvegardé dans : {output_filename}")

    except requests.exceptions.HTTPError as http_err:
        print(f"Erreur HTTP lors de la récupération de la page : {http_err}")
        print(f"Code de statut : {http_err.response.status_code}")
        # Afficher le début du contenu de la réponse en cas d'erreur, cela peut aider
        if http_err.response and hasattr(http_err.response, 'text'):
            print(f"Contenu de la réponse (erreur) :\n{http_err.response.text[:500]}...")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Erreur de connexion : {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"La requête a expiré (timeout) : {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Erreur de requête générique : {req_err}")
    except IOError as io_err:
        print(f"Erreur lors de l'écriture du fichier {output_filename}: {io_err}")
    except Exception as e:
        print(f"Une erreur inattendue est survenue : {e}")

if __name__ == "__main__":
    # Demander l'URL à l'utilisateur
    target_url = input("Veuillez entrer l'URL de la page dont vous voulez extraire le HTML : ")

    if target_url:
        # Vous pouvez spécifier un nom de fichier de sortie différent si vous le souhaitez
        # Par exemple, basé sur le nom de domaine ou un identifiant
        # filename = "output_" + target_url.split('//')[-1].split('/')[0] + ".html"
        get_and_save_html(target_url) # Utilise "page_content.html" par défaut
    else:
        print("Aucune URL n'a été fournie.")

    # Exemple d'utilisation avec une URL prédéfinie (décommentez pour tester rapidement)
    # test_url_valium = "https://base-donnees-publique.medicaments.gouv.fr/affichageDoc.php?specid=60219803&typedoc=R"
    # get_and_save_html(test_url_valium, "valium_rcp_full.html")