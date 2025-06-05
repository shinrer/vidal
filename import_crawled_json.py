import argparse
import json
import re
import sqlite3
from pathlib import Path

from transformer_dp_updated import (
    PREDEFINED_COLUMNS_STRUCTURE,
    clean_title_for_mapping,
    TARGET_TITLE_TO_DB_COLUMN_MAP,
    OTHER_SECTIONS_COL_NAME,
    TABLE_NAME,
    DB_NAME,
    create_wide_table,
)


def map_json_to_columns(json_data: dict) -> tuple[dict, dict]:
    """Map JSON keys to DB columns using transformer_dp_updated mappings."""
    row = {col: None for col in PREDEFINED_COLUMNS_STRUCTURE.keys()}
    other = {}
    for key, value in json_data.items():
        cleaned = clean_title_for_mapping(key)
        db_col = TARGET_TITLE_TO_DB_COLUMN_MAP.get(cleaned)
        if db_col and db_col in PREDEFINED_COLUMNS_STRUCTURE:
            row[db_col] = value
        else:
            other[key] = value
    return row, other


def process_file(conn: sqlite3.Connection, file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    row_values, other_sections = map_json_to_columns(data)

    match = re.search(r"(\d+)", file_path.stem)
    cis_code = match.group(1) if match else data.get("cis_code")
    if not cis_code:
        print(f"Skipping {file_path.name}: unable to determine CIS code")
        return

    columns = ["cis_code", "source_filename"] + list(PREDEFINED_COLUMNS_STRUCTURE.keys()) + [OTHER_SECTIONS_COL_NAME]
    values = [cis_code, file_path.name]
    values.extend(row_values[col] for col in PREDEFINED_COLUMNS_STRUCTURE.keys())
    values.append(json.dumps(other_sections, ensure_ascii=False, indent=2) if other_sections else None)

    placeholders = ",".join(["?"] * len(columns))
    sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({','.join(columns)}) VALUES ({placeholders})"
    conn.execute(sql, values)


def main():
    parser = argparse.ArgumentParser(description="Import crawled RCP JSON files into the database")
    parser.add_argument("json_dir", help="Directory containing crawled JSON files")
    parser.add_argument("--db", default=DB_NAME, help="SQLite database path")
    args = parser.parse_args()

    json_dir = Path(args.json_dir)
    if not json_dir.is_dir():
        print(f"Provided directory {json_dir} does not exist")
        return

    conn = sqlite3.connect(args.db)
    create_wide_table(conn)

    for json_file in sorted(json_dir.glob("*.json")):
        try:
            process_file(conn, json_file)
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
