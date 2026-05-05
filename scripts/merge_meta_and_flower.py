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
raw_dir_input = Path(input("Enter path to raw data directory (contains JSONs: [date]_config_seppi_flower.json): ").strip())
if not raw_dir_input.exists():
    raise FileNotFoundError(f"Raw directory not found: {raw_dir_input}")

# Step 2: Output for merged config CSV
config_output = Path(input("Enter output path for merged config CSV (call the file: merged_config_seppi_flower.csv): ").strip())

# Step 3: Processed data directory (metadata CSVs)
processed_dir_input = Path(input("Enter path to processed data directory (contains CSVs: [date]_metadata_merged_crops_classified.csv): ").strip())
if not processed_dir_input.exists():
    raise FileNotFoundError(f"Processed directory not found: {processed_dir_input}")

# Step 4: Final output file (with plant_species)
final_output = Path(input("Enter final output path for joined file (call the file: all_metadata_combined.csv): ").strip())

# -----------------------------
# Step 1: Merge JSON Files → merged_config.csv
# -----------------------------
print("\n🔍 Step 1: Merging JSON configuration files...")

# Regex pattern for matching the filename
FILENAME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_config_seppi_flower\.json$')
SEPPI_CAM_PATTERN = re.compile(r'^seppi-cam\d+$')

all_rows = []

for json_file in raw_dir_input.rglob("*.json"):
    match = FILENAME_PATTERN.match(json_file.name)
    if not match:
        continue

    date_time_str = match.group(1)
    try:
        date_time = datetime.strptime(date_time_str, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        print(f"Invalid date/time in filename: {json_file.name}")
        continue

    # Extract cam_ID from first subfolder under raw_dir_input
    cam_id = "unknown"
    parent = json_file.parent
    for p in parent.parents:
        if p == raw_dir_input:
            break
        if p.parent == raw_dir_input and SEPPI_CAM_PATTERN.match(p.name):
            cam_id = p.name
            break

    if cam_id == "unknown":
        print(f"⚠️ No matching 'seppi-cam*' folder found for: {json_file}")
        continue

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_file}: {e}")
        continue

    row = {
        'filename': json_file.name,
        'date_time': date_time_str,
        'cam_ID': cam_id
    }

    deployment = data.get("deployment", {})
    row['deployment_start'] = deployment.get("start")
    row['deployment_setting'] = deployment.get("setting")

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
    'filename', 'date_time', 'cam_ID', 'deployment_start',
    'deployment_setting', 'location_latitude', 'location_longitude',
    'location_accuracy', 'lens_position_manual', 'lens_position_min',
    'lens_position_max'
]

try:
    with open(config_output, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, lineterminator='\n')
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"✅ Step 1: Merged {len(all_rows)} JSON files → '{config_output}'")
except Exception as e:
    raise RuntimeError(f"Error writing config CSV: {e}")

# -----------------------------
# Step 2: Merge Processed Metadata CSVs (No Temporary File!)
# -----------------------------
print("\n🔍 Step 2: Merging processed metadata CSV files...")

# Pattern for metadata files
pattern = "*metadata_merged_crops_classified.csv"
files = list(processed_dir_input.rglob(pattern))

if not files:
    raise ValueError(f"No metadata files found matching pattern: {pattern}")

print(f"Found {len(files)} metadata files.")

# Read and concatenate directly into df_meta (no save to disk)
all_dfs = []
for file in files:
    try:
        df = pd.read_csv(file)
        df["source_file"] = str(file)  # Only add source_file
        all_dfs.append(df)
        print(f"  ✅ Processed: {file.name} ({len(df)} rows)")
    except Exception as e:
        print(f"  ❌ Skipping {file.name}: {e}")

if not all_dfs:
    raise ValueError("No valid metadata files to merge.")

df_meta = pd.concat(all_dfs, ignore_index=True)

print(f"✅ Step 2: Merged {len(df_meta)} rows into memory")

# -----------------------------
# Step 3: Join plant_species using time-based session matching
# -----------------------------
print("\n🔍 Step 3: Joining plant_species based on cam_ID and time session...")

# Read merged metadata and config
try:
    # df_meta is already in memory
    df_config = pd.read_csv(config_output)
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
    ends = group['date_time_dt'].shift(-1).values
    ends[-1] = pd.Timestamp.max  # Last session goes to infinity
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
    df_final.to_csv(final_output, index=False)
    print(f"✅ Step 3: Joined {len(df_final)} rows → '{final_output}'")
except Exception as e:
    raise RuntimeError(f"Error writing final CSV: {e}")

# -----------------------------
# Final Summary
# -----------------------------
print(f"\n🎉 All steps completed successfully!")
print(f"✅ Final output file: '{final_output}'")
print(f"✅ Contains all original metadata + 'plant_species' column")
print(f"✅ Processed {len(df_final)} rows.")