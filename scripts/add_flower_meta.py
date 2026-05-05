#!/usr/bin/env python3

import os
import json
import csv
import re
from pathlib import Path
from datetime import datetime

# -----------------------------
# Configuration
# -----------------------------
INPUT_DIR = Path(input("Enter the input directory path: ").strip())
OUTPUT_CSV = Path(input("Enter output CSV file path (e.g., merged_configs.csv): ").strip())

# Regex pattern for matching the filename
FILENAME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_config_seppi_flower\.json$')

# Pattern to match folders like seppi-cam31, seppi-cam32, etc.
SEPPI_CAM_PATTERN = re.compile(r'^seppi-cam\d+$')

# -----------------------------
# Main function
# -----------------------------
def main():
    if not INPUT_DIR.exists():
        print(f"Error: Directory '{INPUT_DIR}' does not exist.")
        return

    if not INPUT_DIR.is_dir():
        print(f"Error: '{INPUT_DIR}' is not a directory.")
        return

    # List to store all extracted data
    all_rows = []

    print("Searching for JSON files matching the pattern...")
    for json_file in INPUT_DIR.rglob("*.json"):
        # Skip if not matching the pattern
        match = FILENAME_PATTERN.match(json_file.name)
        if not match:
            continue

        # Extract date/time from filename
        date_time_str = match.group(1)
        try:
            date_time = datetime.strptime(date_time_str, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            print(f"Invalid date/time in filename: {json_file.name}")
            continue

        # Find the correct cam_ID: look for the first folder directly under INPUT_DIR
        cam_id = "unknown"
        parent = json_file.parent

        for p in parent.parents:
            if p == INPUT_DIR:
                break
            if p.parent == INPUT_DIR and SEPPI_CAM_PATTERN.match(p.name):
                cam_id = p.name
                break

        if cam_id == "unknown":
            print(f"⚠️ No matching 'seppi-cam*' folder found for: {json_file}")
            continue

        # Read JSON file
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            continue

        # Extract only the fields you want (excluding deployment.notes)
        row = {
            'filename': json_file.name,
            'date_time': date_time_str,
            'cam_ID': cam_id
        }

        # === deployment ===
        deployment = data.get("deployment", {})
        row['deployment_start'] = deployment.get("start")
        row['deployment_setting'] = deployment.get("setting")

        # Extract location
        location = deployment.get("location", {})
        row['location_latitude'] = location.get("latitude")
        row['location_longitude'] = location.get("longitude")
        row['location_accuracy'] = location.get("accuracy")

        # === camera.focus.lens_position ===
        focus = data.get("camera", {}).get("focus", {})
        lens_pos = focus.get("lens_position", {})
        row['lens_position_manual'] = lens_pos.get("manual")
        row['lens_position_min'] = lens_pos.get("range", {}).get("min")
        row['lens_position_max'] = lens_pos.get("range", {}).get("max")

        all_rows.append(row)

    # Write to CSV with full protection
    if not all_rows:
        print("No matching JSON files found.")
        return

    # Define the exact fieldnames in order 
    fieldnames = [
        'filename',
        'date_time',
        'cam_ID',
        'deployment_start',
        'deployment_setting',
        'location_latitude',
        'location_longitude',
        'location_accuracy',
        'lens_position_manual',
        'lens_position_min',
        'lens_position_max'
    ]

    # ✅ CRITICAL: Use QUOTE_ALL + Unix line endings
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            # Use QUOTE_ALL to wrap every field in quotes
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, lineterminator='\n')
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n✅ Successfully merged {len(all_rows)} files into '{OUTPUT_CSV}'")
    except PermissionError:
        print(f"\n❌ Permission denied: Cannot write to '{OUTPUT_CSV}'")
        print("💡 Try:")
        print("  - Close any programs using this file")
        print("  - Run the script as Administrator")
        print("  - Use a different output path (e.g., Desktop)")
        return
    except Exception as e:
        print(f"Error writing CSV: {e}")
        return

# -----------------------------
# Run the script
# -----------------------------
if __name__ == "__main__":
    main()