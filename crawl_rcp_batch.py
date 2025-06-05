import json
from pathlib import Path
import datetime
import argparse

from crawl_rcp_async import get_drug_info_from_cis, save_to_json

# --- Logging utilities ---
def log_info(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    print(f"[{datetime.datetime.now().isoformat()}] ERROR: {message}")

# --- Constants ---
DEFAULT_CODES_FILE = Path("unique_cis_codes.json")
OUTPUT_DIR = Path("JSONs")


def load_cis_codes(path: Path) -> list[str]:
    """Load CIS codes from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"CIS codes file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        codes = json.load(f)
    if not isinstance(codes, list):
        raise ValueError("JSON file must contain a list of CIS codes")
    return [str(c) for c in codes]


def process_codes(codes: list[str]):
    OUTPUT_DIR.mkdir(exist_ok=True)
    total = len(codes)
    for idx, code in enumerate(codes, start=1):
        log_info(f"[{idx}/{total}] Processing CIS {code}")
        try:
            data = get_drug_info_from_cis(code)
            if data:
                filename = OUTPUT_DIR / f"rcp_cis_{code}.json"
                save_to_json(data, filename)
            else:
                log_error(f"No data returned for CIS {code}")
        except Exception as e:
            log_error(f"Failed to process CIS {code}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Batch crawl RCP pages for CIS codes")
    parser.add_argument(
        "--codes-file",
        default=str(DEFAULT_CODES_FILE),
        help="Path to JSON file containing CIS codes list",
    )
    args = parser.parse_args()

    codes_file = Path(args.codes_file)
    try:
        codes = load_cis_codes(codes_file)
    except Exception as e:
        log_error(f"Unable to load CIS codes from {codes_file}: {e}")
        return

    log_info(f"Loaded {len(codes)} CIS codes from {codes_file}")
    process_codes(codes)
    log_info("Processing complete")


if __name__ == "__main__":
    main()

