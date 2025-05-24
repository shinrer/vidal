import json
import datetime
from pathlib import Path

# --- Configuration ---
METADATA_FILE_PATH = Path(__file__).resolve().parent.parent / 'update_metadata.json'

# --- Default Metadata Structure ---
def get_default_metadata():
    """Returns a dictionary with default initial metadata values."""
    return {
        "last_download_attempt_date": None,
        "last_successful_download_date": None,
        "last_downloaded_zip_url": None,
        "last_downloaded_zip_publication_date": None, # From data.gouv.fr resource metadata
        "last_successful_full_update_date": None, # Tracks completion of download, import, and crawl
        "files_in_last_zip": [], # List of filenames extracted from the last downloaded zip
        "database_schema_version": "1.0" # Example, could be used for migrations later
    }

# --- Metadata Functions ---
def load_metadata() -> dict:
    """
    Loads update process metadata from METADATA_FILE_PATH.
    Returns default metadata if the file doesn't exist or is invalid.
    """
    try:
        if METADATA_FILE_PATH.exists():
            with open(METADATA_FILE_PATH, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            # Ensure all default keys are present, add if missing from old file
            default_meta = get_default_metadata()
            for key, value in default_meta.items():
                metadata.setdefault(key, value)
            return metadata
        else:
            print(f"Metadata file not found at {METADATA_FILE_PATH}. Returning default metadata.")
            return get_default_metadata()
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {METADATA_FILE_PATH}: {e}. Returning default metadata.")
        return get_default_metadata()
    except Exception as e: # Catch any other unexpected errors during load
        print(f"An unexpected error occurred loading metadata: {e}. Returning default metadata.")
        return get_default_metadata()

def save_metadata(metadata_dict: dict):
    """
    Saves the provided metadata dictionary to METADATA_FILE_PATH as JSON.
    """
    try:
        with open(METADATA_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=4)
        print(f"Metadata successfully saved to {METADATA_FILE_PATH}")
    except IOError as e:
        print(f"Error saving metadata to {METADATA_FILE_PATH}: {e}")
    except Exception as e: # Catch any other unexpected errors during save
        print(f"An unexpected error occurred saving metadata: {e}")


# --- Example Usage ---
if __name__ == '__main__':
    print("--- Testing Metadata Utilities ---")

    # 1. Load initial metadata (might be default if file doesn't exist)
    print("\n1. Loading initial metadata...")
    metadata = load_metadata()
    print("Loaded metadata:")
    print(json.dumps(metadata, indent=4))

    # 2. Modify a value
    print("\n2. Modifying 'last_download_attempt_date'...")
    metadata['last_download_attempt_date'] = datetime.datetime.now().isoformat()
    metadata['files_in_last_zip'].append("CIS_bdpm_new.txt") # Example modification

    # 3. Save updated metadata
    print("\n3. Saving updated metadata...")
    save_metadata(metadata)

    # 4. Load metadata again to verify persistence
    print("\n4. Loading metadata again to verify persistence...")
    reloaded_metadata = load_metadata()
    print("Reloaded metadata:")
    print(json.dumps(reloaded_metadata, indent=4))

    # 5. Check if modification is present
    if reloaded_metadata.get('last_download_attempt_date') == metadata['last_download_attempt_date']:
        print("\nSUCCESS: 'last_download_attempt_date' was successfully persisted.")
    else:
        print("\nERROR: 'last_download_attempt_date' did not persist correctly.")
    
    if "CIS_bdpm_new.txt" in reloaded_metadata.get('files_in_last_zip', []):
        print("SUCCESS: 'files_in_last_zip' modification was successfully persisted.")
    else:
        print("ERROR: 'files_in_last_zip' modification did not persist correctly.")

    # Clean up the created metadata file after test (optional)
    # print(f"\nCleaning up by removing {METADATA_FILE_PATH}...")
    # METADATA_FILE_PATH.unlink(missing_ok=True)
