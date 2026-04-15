import csv

def read_csv(file_path):
    """Reads the input CSV into a list of dictionaries."""
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_csv(data, file_path, fieldnames):
    """Writes the enriched list of dictionaries back to a CSV."""
    with open(file_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)