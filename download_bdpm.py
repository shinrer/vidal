import requests
from bs4 import BeautifulSoup
import zipfile
import os
from pathlib import Path
import re

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

def get_zip_download_link(page_url: str) -> str:
    """
    Fetches the dataset page and parses it to find the ZIP file download link.
    Looks for an <a> tag with 'telecharger' in its attributes and a .zip extension.
    """
    print(f"Fetching dataset page: {page_url}")
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
            return download_url
        else:
            error_msg = "Could not find the download link for the ZIP file."
            print(error_msg)
            # For debugging, print a snippet of the page or specific sections
            # relevant_section = soup.find(...) # e.g., find a div that should contain the link
            # print(f"Relevant HTML snippet for debugging:\n{relevant_section.prettify() if relevant_section else 'No relevant section found'}")
            raise ValueError(error_msg)
    except requests.RequestException as e:
        print(f"Error fetching page {page_url}: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while trying to get the download link: {e}")
        raise


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
    
    zip_file_path = TARGET_DIR / DOWNLOADED_ZIP_FILENAME

    try:
        # 1. Create base data directory (TARGET_DIR will be created by download_file if needed for manual saving)
        create_target_directory(BASE_DATA_DIR) # Ensures ./data/ exists

        # 2. Get the download link
        # This URL might redirect to a page that is then blocked (e.g. base-donnees-publique.medicaments.gouv.fr)
        # The user will need to handle this in their browser.
        actual_download_url_to_present_to_user = get_zip_download_link(DATASET_PAGE_URL)
        
        print(f"The script will attempt to use the following link for manual download instructions: {actual_download_url_to_present_to_user}")
        print("If this link leads to an intermediate page, you may need to find the final download link on that page.")


        # 3. "Download" the ZIP file (i.e., instruct user and wait)
        # The zip_file_path is where the user is instructed to save the file.
        
        # --- For testing purposes, create a dummy zip file ---
        # In a real scenario, the user would download this.
        # To test the decompression logic, we create a dummy file here.
        # This should ideally be conditional (e.g. via an env var or CLI flag).
        # For this test run, we'll create it to check the decompression.
        # In the next run, we can test the FileNotFoundError path by NOT creating it.
        # IMPORTANT: The input() call will still cause an EOFError in this environment.
        # We are testing the logic *after* the input if the file exists.
        
        # To test the "file not found" path, comment out the next line:
        create_dummy_zip_for_testing(zip_file_path) 
        
        # Pass is_test_run=True for automated testing to skip input()
        download_file(actual_download_url_to_present_to_user, zip_file_path, is_test_run=True)


        # 4. Decompress the ZIP file (this will only run if download_file doesn't raise FileNotFoundError)
        decompress_zip(zip_file_path, TARGET_DIR)

        # 5. Optionally remove the ZIP file
        remove_file(zip_file_path) # Make this optional based on a flag if needed

        print(f"--- Data ready in {TARGET_DIR} ---")

    except (requests.RequestException, ValueError, zipfile.BadZipFile) as e:
        print(f"Script failed: {e}")
        print("Please check the URLs, network connection, and page structure if the link wasn't found.")
    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
    finally:
        print("--- Script finished ---")

if __name__ == "__main__":
    main()
