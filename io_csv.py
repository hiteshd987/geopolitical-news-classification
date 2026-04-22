import os
import csv

# def read_csv(file_path):
#     """Reads the input CSV into a list of dictionaries."""
#     with open(file_path, mode='r', encoding='utf-8-sig') as f:
#         reader = csv.DictReader(f)
#         return list(reader)

def read_csv(file_path):
    """Reads the input CSV into a list of dictionaries."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Input CSV is empty: {file_path}")

    required_columns = {'pubDate', 'link', 'content', 'source_id'}
    actual_columns = set(rows[0].keys())
    missing = required_columns - actual_columns

    if missing:
        raise ValueError(
            f"Input CSV missing required columns: {missing}\n"
            f"Found columns: {actual_columns}"
        )

    print(f"Loaded {len(rows)} articles from {file_path}")
    return rows

def write_csv(data, file_path, fieldnames):
    """Writes the enriched list of dictionaries back to a CSV."""
    with open(file_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)