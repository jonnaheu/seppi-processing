#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import argparse
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge metadata CSV files from nested folders."
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Base directory to search in"
    )

    parser.add_argument(
        "-p", "--pattern",
        default="*metadata_merged_crops_classified.csv",
        help="Filename pattern to match (default: %(default)s)"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        help="Output CSV file path"
    )

    parser.add_argument(
        "--add-metadata",
        action="store_true",
        help="Add folder_datetime, file_date, and source_file columns"
    )

    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output instead of overwriting"
    )

    return parser.parse_args()


def extract_metadata(file: Path):
    parent_folder = file.parent.name
    folder_datetime = parent_folder[:19]

    file_base = file.name
    file_date = file_base[:10]

    return folder_datetime, file_date


def main():
    args = parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    if args.output.exists() and not args.append:
        args.output.unlink()

    files = list(args.input_dir.rglob(args.pattern))

    if not files:
        print("No files found matching pattern.")
        return

    print(f"Found {len(files)} files.\n")

    # --- NEW: stats tracking ---
    start_time = time.time()
    file_count = 0
    total_rows = 0
    # --------------------------

    first = not args.append

    for file in files:
        try:
            df = pd.read_csv(file)

            rows = len(df)
            total_rows += rows
            file_count += 1

            if args.add_metadata:
                folder_datetime, file_date = extract_metadata(file)
                df["folder_datetime"] = folder_datetime
                df["file_date"] = file_date
                df["source_file"] = str(file)

            if first:
                df.to_csv(args.output, index=False)
                first = False
            else:
                df.to_csv(args.output, mode="a", header=False, index=False)

            print(f"Processed: {file} ({rows} rows)")

        except Exception as e:
            print(f"Skipping {file} due to error: {e}")

    # --- NEW: summary ---
    end_time = time.time()
    duration = end_time - start_time
    mins, secs = divmod(duration, 60)

    print("\n--- Summary ---")
    print(f"Files combined: {file_count}")
    print(f"Total rows (detections): {total_rows:,}")  # nice formatting
    print(f"Processing time: {int(mins)} min {secs:.2f} sec")
    print(f"Output file: {args.output}")
    # --------------------

    print("\nDone.")


if __name__ == "__main__":
    main()