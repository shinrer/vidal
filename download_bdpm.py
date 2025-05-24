import requests
from bs4 import BeautifulSoup
import zipfile
import os
from pathlib import Path
import re
import datetime # Added
from app.update_utils import load_metadata, save_metadata # Added

# Configuration
DATASET_PAGE_URL = "https://www.data.gouv.fr/fr/datasets/base-de-donnees-publique-des-medicaments-base-officielle/"
TARGET_DIR_NAME = "bdpm_source"
BASE_DATA_DIR = Path("./data")
TARGET_DIR = BASE_DATA_DIR / TARGET_DIR_NAME
DOWNLOADED_ZIP_FILENAME = "bdpm_data.zip"

def create_target_directory(path: Path):
    """Creates the target directory if it doesn't exist."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        print(f"Directory '{path}' ensured.")
    except Exception as e:
        print(f"Error creating directory {path}: {e}")
        raise

def get_bdpm_resource_info(page_url: str) -> tuple[str | None, str | None]:
    """
    Fetches the dataset page and parses it to find the resource download link 
    and its publication/last modified date.
    Returns (download_url, publication_date_str) or (None, None) if not found.
    """
    print(f"Fetching dataset page for resource info: {page_url}")
    try:
        response = requests.get(page_url, timeout=30) # Added timeout
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')

        # Refined strategy for finding the download link on data.gouv.fr:
        # 1. Primary: Look for any <a> tag with href ending in .zip (case-insensitive)
        #    that also seems relevant (contains 'telecharger', 'download', 'bdpm').
        # 2. Secondary: Look for data.gouv specific resource links (/fr/datasets/r/...) that end in .zip.
        # 3. Tertiary: Fallback to the first data.gouv resource link (/fr/datasets/r/...) found,
        #    as this was previously identified (though led to a 403 on redirection).
        # Corrected DeprecationWarning: use string= instead of text= for BeautifulSoup.

        link_tag = None
        
        # Strategy 1: Broad search for a relevant .zip link anywhere on the page
        potential_zip_links = soup.find_all('a', href=re.compile(r'\.zip$', re.IGNORECASE))
        for link in potential_zip_links:
            href = link.get('href', '').lower()
            text = link.get_text(strip=True).lower()
            title = link.get('title', '').lower()
            # Check for relevance
            if 'telecharger' in text or 'télécharger' in text or \
               'download' in text or 'bdpm' in text or \
               'telecharger' in title or 'télécharger' in title or \
               'download' in title or 'bdpm' in title or \
               'telecharger' in href or 'télécharger' in href or \
               'download' in href or 'bdpm' in href:
                link_tag = link
                print(f"Strategy 1: Found relevant .zip link: {link.get('href')}")
                break
        
        # Strategy 2: More specific search for data.gouv resource links ending in .zip
        if not link_tag:
            resource_zip_links = soup.find_all('a', href=re.compile(r'/fr/datasets/r/[\w-]+\.zip$', re.IGNORECASE))
            if resource_zip_links:
                link_tag = resource_zip_links[0] # Take the first one
                print(f"Strategy 2: Found data.gouv resource .zip link: {link_tag.get('href')}")

        # Strategy 3: Fallback to any data.gouv resource link (as before)
        if not link_tag:
            stable_link_pattern = re.compile(r'/fr/datasets/r/[\w-]+')
            all_stable_links = soup.find_all('a', href=stable_link_pattern)
            if all_stable_links:
                # Iterate to find one that is explicitly marked as primary or has "URL stable" text if possible
                # The one we found before was in a div with class "resource-item" and title "Télécharger la ressource"
                # or text "URL stable"
                for stable_link in all_stable_links:
                    # This is a heuristic. The link we want is typically the one with "URL stable" as text,
                    # or within a section detailing the primary file.
                    # The previous attempt correctly found:
                    # https://www.data.gouv.fr/fr/datasets/r/056b6732-cbaf-447f-9f20-e3b5f655919a
                    # So, we can prioritize this if no direct .zip link is found.
                    if "056b6732-cbaf-447f-9f20-e3b5f655919a" in stable_link.get('href',''): # Prioritize known good resource ID
                        link_tag = stable_link
                        print(f"Strategy 3: Found specific known data.gouv resource link: {link_tag.get('href')}")
                        break
                if not link_tag and all_stable_links: # Default to first stable link if specific one not found
                    link_tag = all_stable_links[0]
                    print(f"Strategy 3: Found generic data.gouv resource link: {link_tag.get('href')}")


        # Fallback to original broad .zip search if absolutely nothing else is found (less likely now)
        if not link_tag:
            link_tag = soup.find('a', attrs={'download': True, 'href': re.compile(r'\.zip$', re.IGNORECASE)})
        if not link_tag:
            link_tag = soup.find('a', href=re.compile(r'\.zip$', re.IGNORECASE), string=re.compile(r'télécharger', re.IGNORECASE))


        if link_tag and link_tag.get('href'):
            download_url = link_tag.get('href')
            # If the URL is relative, make it absolute
            if not download_url.startswith('http'):
                from urllib.parse import urljoin
                download_url = urljoin(page_url, download_url)
            print(f"Found download link: {download_url}")

            # Attempt to find the publication date associated with this resource
            # This logic is highly dependent on the page structure of data.gouv.fr
            # We'll look for a <time> element or text like "Mis à jour le" near the resource link.
            # The "URL stable" link is often within a <div class="resource-item"> or similar.
            publication_date_str = None
            resource_container = link_tag.find_parent(class_=["resource-item", "resource"]) # Common parent class
            
            if resource_container:
                # Try to find a <time> element
                time_tag = resource_container.find("time")
                if time_tag and time_tag.get("datetime"):
                    publication_date_str = time_tag["datetime"]
                    print(f"Found publication date (datetime attribute): {publication_date_str}")
                else:
                    # Fallback: Look for text patterns like "Mis à jour le" or "Publié le"
                    # This is less reliable and might need specific selectors if page structure is known
                    date_texts = resource_container.find_all(string=re.compile(r"(Mis à jour le|Publié le|Modifié le)\s+([\w\s\d]+)", re.IGNORECASE))
                    if date_texts:
                        # Extract the date part. Example: "Mis à jour le 24 juin 2024"
                        # This will need more robust parsing to convert to YYYY-MM-DD
                        # For now, just store the matched string if specific parsing is too complex.
                        # A better approach would be to look for specific tags/classes around the date.
                        # For example, if the date is in a <p class="fr-text--sm fr-mb-1v">Modifié le 24 juin 2024</p>
                        date_element = resource_container.find(lambda tag: tag.name == 'p' and 'Modifié le' in tag.get_text(strip=True))
                        if not date_element: # Try another common pattern
                             date_element = resource_container.find(lambda tag: tag.name == 'p' and 'Mis à jour le' in tag.get_text(strip=True))

                        if date_element:
                            full_date_text = date_element.get_text(strip=True)
                            # Example: "Modifié le 24 juin 2024" -> "24 juin 2024"
                            match = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", full_date_text, re.IGNORECASE)
                            if match:
                                publication_date_str = match.group(1)
                                print(f"Found publication date (text pattern): {publication_date_str}")
                            else:
                                publication_date_str = full_date_text # Store full string if specific pattern fails
                                print(f"Found publication date text (fallback): {publication_date_str}")
            
            if not publication_date_str:
                # General fallback if not found within a resource container
                # Look for a general last update on the page, this is less ideal as it might not be for the file itself
                general_update_tag = soup.find(string=re.compile(r"Dernière mise à jour", re.IGNORECASE))
                if general_update_tag and general_update_tag.parent:
                    date_text_sibling = general_update_tag.parent.find_next_sibling(string=re.compile(r"\d{1,2}\s+\w+\s+\d{4}"))
                    if date_text_sibling:
                         publication_date_str = date_text_sibling.strip()
                         print(f"Found general page publication date (less reliable): {publication_date_str}")

            return download_url, publication_date_str
        else:
            error_msg = "Could not find the download link for the ZIP file."
            print(error_msg)
            raise ValueError(error_msg) # Raise to be caught by main try-except
            
    except requests.RequestException as e:
        print(f"Error fetching page {page_url}: {e}")
        raise # Re-raise to be caught by main try-except
    except Exception as e:
        print(f"An unexpected error occurred while trying to get resource info: {e}")
        raise # Re-raise


def download_file(url: str, destination_path: Path, is_test_run: bool = False):
    """
    Instructs the user to manually download the file, as direct download is blocked.
    Pauses execution until the user confirms the download.
    If is_test_run is True, skips the input() prompt.
    """
    print("-" * 50)
    print("MANUAL DOWNLOAD REQUIRED")
    print("-" * 50)
    print(f"The script cannot automatically download the file due to server restrictions (403 Forbidden).")
    print(f"Please download the file manually using the following URL:")
    print(f"\n  >> URL: {url}\n")
    print(f"Save the downloaded file as '{DOWNLOADED_ZIP_FILENAME}'")
    print(f"in the directory: '{destination_path.parent}'")
    print("-" * 50)
    
    # Ensure the target directory for manual download exists
    create_target_directory(destination_path.parent) # Ensures ./data/bdpm_source/ exists

    if not is_test_run: # Skip input for automated testing
        input(f"Press Enter after you have downloaded the file to '{destination_path}' and named it '{DOWNLOADED_ZIP_FILENAME}'...")
    else:
        print("Test run: Skipping input() for manual download confirmation.")
    
    # Check if the file was actually downloaded by the user
    if not destination_path.exists():
        error_msg = f"File not found: {destination_path}. Please make sure the file was downloaded and saved correctly."
        print(error_msg)
        raise FileNotFoundError(error_msg)
    else:
        print(f"File {destination_path} found. Proceeding with script.")

def create_dummy_zip_for_testing(zip_path: Path):
    """Creates a small, empty dummy ZIP file for testing purposes."""
    # Ensure the parent directory exists
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Add a small dummy file inside the zip to make it valid
            zf.writestr("dummy.txt", "this is a dummy file for testing")
        print(f"Created dummy ZIP file for testing: {zip_path}")
    except Exception as e:
        print(f"Could not create dummy ZIP: {e}")


def decompress_zip(zip_path: Path, extract_to_path: Path):
    """Decompresses a ZIP file to a specified directory."""
    print(f"Decompressing {zip_path} to {extract_to_path}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to_path)
        print("Decompression complete.")
    except zipfile.BadZipFile:
        print(f"Error: {zip_path} is not a valid ZIP file or is corrupted.")
        raise
    except Exception as e:
        print(f"Error decompressing ZIP file {zip_path}: {e}")
        raise

def remove_file(filepath: Path):
    """Removes a file."""
    try:
        filepath.unlink()
        print(f"Removed file: {filepath}")
    except OSError as e:
        print(f"Error removing file {filepath}: {e}")
        # Not raising here, as it's an optional step

def main():
    """Main function to orchestrate the download and decompression."""
    print("--- Starting BDPM data download script ---")
    
    metadata = load_metadata()
    zip_file_path = TARGET_DIR / DOWNLOADED_ZIP_FILENAME
    proceed_with_download = False
    current_zip_url = None
    current_publication_date = None

    try:
        create_target_directory(BASE_DATA_DIR) # Ensures ./data/ exists

        current_zip_url, current_publication_date = get_bdpm_resource_info(DATASET_PAGE_URL)

        if not current_zip_url:
            # get_bdpm_resource_info already prints error, main will catch and exit.
            raise ValueError("Could not retrieve current ZIP URL from the website.")

        # Normalize current_publication_date if possible, for now, use as string
        # A more robust solution would parse various date formats to datetime objects.
        # For this version, string comparison will be used if dates are consistently formatted,
        # or we rely more on URL change if dates are messy.
        
        last_downloaded_url = metadata.get('last_downloaded_zip_url')
        last_publication_date = metadata.get('last_downloaded_zip_publication_date')

        print(f"Currently available version: URL='{current_zip_url}', Published='{current_publication_date}'")
        print(f"Previously downloaded version: URL='{last_downloaded_url}', Published='{last_publication_date}'")

        is_new_version = False
        if last_publication_date is None: # First run or no previous date stored
            is_new_version = True
            print("No previous download date found, assuming new version.")
        elif current_publication_date and current_publication_date != last_publication_date:
            # This assumes dates are comparable strings (e.g., "YYYY-MM-DD" or consistent "dd mois YYYY")
            # More robust: parse dates to datetime objects for comparison.
            is_new_version = True # Simplified: any difference in date string means new
            print(f"Publication date changed: '{last_publication_date}' -> '{current_publication_date}'.")
        elif current_zip_url != last_downloaded_url:
            is_new_version = True
            print(f"Download URL changed: '{last_downloaded_url}' -> '{current_zip_url}'.")

        if is_new_version:
            print(f"A new version of the BDPM data seems to be available (Published: {current_publication_date}).")
            proceed_with_download = True
        else:
            print(f"The currently available version (Published: {current_publication_date}) appears to be the same as previously downloaded.")
            # The input() call below will fail in the non-interactive environment.
            # For testing, we assume 'no' if not is_test_run.
            # In a real execution, this would pause for user.
            if 'is_test_run' in locals() and is_test_run: # Check if is_test_run is defined (from previous subtask version)
                force_download = False 
                print("Test run: Assuming 'no' for force download.")
            else:
                try:
                    force_download_input = input("Do you want to proceed with download and processing anyway? (yes/no): ").lower()
                    force_download = force_download_input == 'yes'
                except EOFError: # Handle non-interactive environment for tests
                    print("Non-interactive environment detected, assuming 'no' for force download.")
                    force_download = False
            proceed_with_download = force_download
        
        if proceed_with_download:
            print("Proceeding with download and processing...")
            # The 'is_test_run' flag was part of a previous subtask's testing setup.
            # For this subtask, we'll assume it's a real run if it gets to input(),
            # or handle EOF for non-interactive.
            test_mode_for_download = False # Default to real user interaction
            if 'is_test_run' in locals() and is_test_run: # If that testing variable is still around
                test_mode_for_download = True

            download_file(current_zip_url, zip_file_path, is_test_run=test_mode_for_download)
            decompress_zip(zip_file_path, TARGET_DIR)
            remove_file(zip_file_path) # Optional: remove ZIP after decompression

            # Update metadata for successful download and processing
            metadata['last_successful_download_date'] = datetime.datetime.now().isoformat()
            metadata['last_downloaded_zip_url'] = current_zip_url
            metadata['last_downloaded_zip_publication_date'] = current_publication_date
            # metadata['files_in_last_zip'] could be populated here if decompress_zip returned filenames
            print(f"--- Data ready in {TARGET_DIR} ---")
        else:
            print("Skipping download and decompression.")

    except (requests.RequestException, ValueError, zipfile.BadZipFile) as e:
        print(f"Script failed: {e}")
        if current_zip_url: # Only update attempt date if we got far enough to know the URL
             metadata['last_download_attempt_date'] = datetime.datetime.now().isoformat()
    except Exception as e: # Catch any other unexpected error
        print(f"An unexpected error occurred in main: {e}")
        if current_zip_url:
            metadata['last_download_attempt_date'] = datetime.datetime.now().isoformat()
    finally:
        # Always save metadata to capture attempt dates or successful download info
        if current_zip_url: # Ensure we at least attempted to get URL
             metadata['last_download_attempt_date'] = metadata.get('last_download_attempt_date', datetime.datetime.now().isoformat())
        save_metadata(metadata)
        print("--- Script finished ---")

if __name__ == "__main__":
    main()
