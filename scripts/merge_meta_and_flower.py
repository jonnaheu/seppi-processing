#!/usr/bin/env python3

import os
import json
import csv
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

# -----------------------------
# Configuration & Input
# -----------------------------
print("=== SEPPI Data Pipeline: Combine JSON → Merge CSV → Join with Plant Species ===\n")

# Step 1: Raw data directory (JSONs)
raw_dir_input = Path(input("Enter path to raw data directory (contains JSONs: [date]_config_seppi_flower.json or [date]_config_seppi_platform.json): ").strip())
if not raw_dir_input.exists():
    raise FileNotFoundError(f"Raw directory not found: {raw_dir_input}")

# Step 2: Output directory (all files saved here)
output_dir = Path(input("Enter path to output directory (all CSVs will be saved here): ").strip())
output_dir.mkdir(parents=True, exist_ok=True)  # Create if not exists

# Step 3: Processed data directory (metadata CSVs)
processed_dir_input = Path(input("Enter path to processed data directory (contains CSVs: [date]_metadata_merged_crops_classified.csv): ").strip())
if not processed_dir_input.exists():
    raise FileNotFoundError(f"Processed directory not found: {processed_dir_input}")

# -----------------------------
# Step 1: Generate Timestamp for Output Files
# -----------------------------
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
merged_config_file = output_dir / f"{timestamp}_merged_config_json.csv"
merged_metadata_file = output_dir / f"{timestamp}_merged_metadata.csv"
final_output_file = output_dir / f"{timestamp}_all_metadata_combined.csv"

print(f"\n Output directory: {output_dir}")
print(f"  Timestamp: {timestamp}")
print(f" Output files will be saved as:")
print(f"  - {merged_config_file.name}")
print(f"  - {merged_metadata_file.name}")
print(f"  - {final_output_file.name}")
# -----------------------------
# Step 1: Merge JSON Files → merged_config_json.csv (Robust with Warnings)
# -----------------------------
print("\n Step 1: Merging JSON configuration files...")

# Regex pattern for both file types
FILENAME_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_config_seppi_(flower|platform)\.json$'
)

all_rows = []

for json_file in raw_dir_input.rglob("*.json"):
    match = FILENAME_PATTERN.match(json_file.name)
    if not match:
        continue

    date_time_str = match.group(1)
    try:
        date_time = datetime.strptime(date_time_str, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        print(f"❌ Invalid date/time in filename: {json_file.name}")
        continue

    # ✅ Extract cam_ID with fallbacks
    cam_id = "unknown"
    deployment_setting = "unknown"
    missing_fields = []

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Try common keys for cam_ID
        possible_cam_keys = [
            "network.hotspot.ssid",
            "network.wifi.ssid",
            "device.id",
            "camera.id",
            "camera_name",
            "device_name",
            "cam_id",
            "ssid"
        ]

        for key_path in possible_cam_keys:
            keys = key_path.split('.')
            value = data
            valid = True
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    valid = False
                    break
            if valid and value:
                cam_id = str(value).strip()
                break
        else:
            missing_fields.append("cam_ID")

        # Try to get deployment_setting
        deployment = data.get("deployment", {})
        setting = deployment.get("setting")
        if setting:
            deployment_setting = str(setting).strip()
        else:
            missing_fields.append("deployment_setting")

        # If no missing fields, proceed
        if missing_fields:
            print(f"⚠️ Missing fields in {json_file.name}: {', '.join(missing_fields)}")

    except Exception as e:
        print(f"❌ Error reading {json_file}: {e}")
        missing_fields.append("JSON parsing failed")

    # ✅ Build row with all available data
    row = {
        'filename': json_file.name,
        'date_time': date_time_str,
        'cam_ID': cam_id,
        'deployment_setting': deployment_setting
    }

    # Add location and lens data (optional, but safe)
    location = deployment.get("location", {})
    row['location_latitude'] = location.get("latitude")
    row['location_longitude'] = location.get("longitude")
    row['location_accuracy'] = location.get("accuracy")

    focus = data.get("camera", {}).get("focus", {})
    lens_pos = focus.get("lens_position", {})
    row['lens_position_manual'] = lens_pos.get("manual")
    row['lens_position_min'] = lens_pos.get("range", {}).get("min")
    row['lens_position_max'] = lens_pos.get("range", {}).get("max")

    all_rows.append(row)

if not all_rows:
    raise ValueError("No JSON files matched the pattern.")

# Write merged config CSV
fieldnames = [
    'filename', 'date_time', 'cam_ID', 'deployment_setting',
    'location_latitude', 'location_longitude', 'location_accuracy',
    'lens_position_manual', 'lens_position_min', 'lens_position_max'
]

try:
    with open(merged_config_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"✅ Step 1: Merged {len(all_rows)} JSON files → '{merged_config_file}'")
except Exception as e:
    raise RuntimeError(f"Error writing config CSV: {e}")

# -----------------------------
# Step 2: Merge Processed Metadata CSVs → merged_metadata.csv (Pure Concatenation)
# -----------------------------
print("\n Step 2: Merging processed metadata CSV files (pure concatenation)...")

# Pattern for metadata files
pattern = "*metadata_merged_crops_classified.csv"
files = list(processed_dir_input.rglob(pattern))

if not files:
    raise ValueError(f"No metadata files found matching pattern: {pattern}")

print(f"Found {len(files)} metadata files.")

# ✅ Read all files and concatenate rows without any transformation
# Use low-level CSV reading to avoid pandas quirks
all_rows = []

# Open output file in write mode
try:
    with open(merged_metadata_file, 'w', newline='', encoding='utf-8') as outfile:
        # We'll write the header only once
        header_written = False

        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as infile:
                    first_line = True
                    for line in infile:
                        if first_line:
                            # Write header only once
                            if not header_written:
                                outfile.write(line)
                                header_written = True
                            first_line = False
                        else:
                            # Write all data lines
                            outfile.write(line)
                print(f"  ✅ Processed: {file.name}")
            except Exception as e:
                print(f"  ❌ Skipping {file.name}: {e}")

    print(f"✅ Step 2: Merged {len(files)} files → '{merged_metadata_file}'")
except Exception as e:
    raise RuntimeError(f"Error writing merged metadata CSV: {e}")

# -----------------------------
# Step 3: Join plant_species using time-based session matching
# -----------------------------
print("\n Step 3: Joining plant_species based on cam_ID and time session...")

# ✅ Read merged config and metadata
try:
    df_config = pd.read_csv(merged_config_file)
    df_meta = pd.read_csv(merged_metadata_file)
except Exception as e:
    raise RuntimeError(f"Error reading merged files: {e}")

# Validate required columns
required_meta = {'cam_ID', 'timestamp'}
required_config = {'cam_ID', 'date_time', 'deployment_setting'}

if not required_meta.issubset(df_meta.columns):
    raise ValueError(f"Missing required columns in metadata: {required_meta - set(df_meta.columns)}")

if not required_config.issubset(df_config.columns):
    raise ValueError(f"Missing required columns in config: {required_config - set(df_config.columns)}")

# Convert timestamps
df_meta['timestamp_dt'] = pd.to_datetime(df_meta['timestamp'])
df_config['date_time_dt'] = df_config['date_time'].apply(
    lambda x: datetime.strptime(x, "%Y-%m-%d_%H-%M-%S") if x else None
)
df_config = df_config.dropna(subset=['date_time_dt'])

# Sort config by cam_ID and date_time_dt
df_config = df_config.sort_values(['cam_ID', 'date_time_dt'])

# Create session intervals
intervals_list = []
for cam_id, group in df_config.groupby('cam_ID'):
    starts = group['date_time_dt'].values
    ends = group['date_time_dt'].shift(-1).values.copy()  # ✅ Make it writable
    ends[-1] = pd.Timestamp.max  # ✅ Now this works
    for start, end in zip(starts, ends):
        intervals_list.append({
            'cam_ID': cam_id,
            'start': start,
            'end': end,
            'plant_species': group.loc[group['date_time_dt'] == start, 'deployment_setting'].iloc[0]
        })

df_intervals = pd.DataFrame(intervals_list)
df_intervals['interval'] = pd.IntervalIndex.from_arrays(
    df_intervals['start'], df_intervals['end'], closed='left'
)

# Vectorized assignment using pd.cut
print("Assigning plant_species using vectorized interval lookup...")
results = []

for cam_id, group in df_meta.groupby('cam_ID'):
    if cam_id not in df_intervals['cam_ID'].values:
        results.append(group.assign(plant_species=None))
        continue

    intervals = df_intervals[df_intervals['cam_ID'] == cam_id]
    interval_index = pd.IntervalIndex(intervals['interval'])
    timestamps = group['timestamp_dt'].values

    bin_indices = pd.cut(
        timestamps,
        bins=interval_index,
        include_lowest=True,
        right=False
    )

    if hasattr(bin_indices, 'codes'):
        codes = bin_indices.codes
        species = [intervals.iloc[i]['plant_species'] if i >= 0 else None for i in codes]
        group = group.copy()
        group['plant_species'] = species
        results.append(group)
    else:
        group = group.copy()
        group['plant_species'] = None
        results.append(group)

df_final = pd.concat(results, ignore_index=True)

# ✅ Remove timestamp_dt (duplicate of timestamp)
df_final = df_final.drop(columns=['timestamp_dt'])

# Save final output
try:
    df_final.to_csv(final_output_file, index=False)
    print(f"✅ Step 3: Joined {len(df_final)} rows → '{final_output_file}'")
except Exception as e:
    raise RuntimeError(f"Error writing final CSV: {e}")
    
        
# -----------------------------
# Final Summary
# -----------------------------
print(f"\n All steps completed successfully!")
print(f"✅ Final output directory: '{output_dir}'")
print(f"✅ Output files:")
print(f"  - {merged_config_file.name}")
print(f"  - {merged_metadata_file.name}")
print(f"  - {final_output_file.name}")
print(f"✅ Processed {len(df_final)} rows.")