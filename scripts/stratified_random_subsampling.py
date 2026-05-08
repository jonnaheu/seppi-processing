from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import random
from datetime import datetime

import argparse
import polars as pl

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# === Configuration ===
DEFAULT_N_PER_GROUP = 100
DEFAULT_SEED = 123

# === Helper: Create timestamped output folder ===
def create_timestamped_output_dir(output_dir: Path) -> Path:
    """Create a new run directory with timestamped name: strata_YYYY-MM-DD_HH-MM-SS"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = output_dir / f"strata_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created output directory: {output_dir}")
    return output_dir


# === Helper: Slice metadata to one row per (cam_ID, rec_ID, track_ID) ===
def slice_metadata_by_id(df: pl.DataFrame) -> pl.DataFrame:
    """
    For each unique (cam_ID, rec_ID, track_ID), keep only the row with the highest bioclip_score.
    If bioclip_score is missing, use the first row.
    """
    # Ensure bioclip_score is float
    if "bioclip_score" in df.columns:
        df = df.with_columns(pl.col("bioclip_score").cast(pl.Float64))
    else:
        logger.warning("bioclip_score column not found. Using first row per group.")
        return df.group_by(["cam_ID", "rec_ID", "track_ID"]).first()

    # Sort by bioclip_score descending, then by row index to ensure determinism
    df = df.with_columns(
        pl.col("bioclip_score").fill_null(-1.0)  # Replace NaN with -1.0
    ).sort(
        by=["cam_ID", "rec_ID", "track_ID", "bioclip_score"],
        descending=[False, False, False, True]
    )

    # Keep only the first row per group
    df = df.group_by(["cam_ID", "rec_ID", "track_ID"]).first()
    logger.info(f"Metadata sliced to {len(df)} unique tracks.")
    return df

# === Helper: Create pollinator/non-pollinator strata ===
def create_pollinator_strata(df: pl.DataFrame) -> pl.DataFrame:
    """Create strata for pollinators vs non-pollinators based on bioclip_order"""
    pollinator_orders = ['Lepidoptera', 'Coleoptera', 'Hymenoptera', 'Diptera']
    
    df = df.with_columns([
        pl.when(pl.col("bioclip_order").is_in(pollinator_orders))
        .then(pl.lit("pollinator"))
        .otherwise(pl.lit("non_pollinator"))
        .alias("strata1")
    ])
    return df

# === Main CLI Entry Point ===
def main():
    # === Argument Parser ===
    parser = argparse.ArgumentParser(
        description="Stratified random subsampling focusing on pollinator/non-pollinator strata and duration-based strata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stratified_random_subsampling.py \
    --metadata-path /path/to/all_metadata_combined.csv \
    --top1-final-path /path/to/all_metadata_combined_top1_final.csv \
    --n-per-group-strata1 100 \
    --n-per-group-strata2 100 \
    --seed 123
        """
    )

    parser.add_argument(
        "--metadata-path",
        type=Path,
        required=True,
        help="Path to all_metadata_combined.csv"
    )
    parser.add_argument(
        "--top1-final-path",
        type=Path,
        required=True,
        help="Path to all_metadata_combined_top1_final.csv"
    )
    parser.add_argument(
        "--n-per-group-strata1",
        type=int,
        default=100,
        help="Number of subsamples per group for strata1 (pollinator/non-pollinator + prob) (default: 100)"
    )
    parser.add_argument(
        "--n-per-group-strata2", 
        type=int, 
        default=100, 
        help="Number of subsamples per duration group for strata2 (default: 100)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=123,
        help="Random seed for reproducibility (default: 123)"
    )

    args = parser.parse_args()

    # === Validate inputs ===
    if not args.metadata_path.exists():
        logger.error(f"Metadata file not found: {args.metadata_path}")
        return
    if not args.top1_final_path.exists():
        logger.error(f"Top1_final file not found: {args.top1_final_path}")
        return

    # === Parameters ===
    n_per_group_strata1 = args.n_per_group_strata1
    n_per_group_strata2 = args.n_per_group_strata2
    seed = args.seed

    # === Step 1: Create timestamped output folder ===
    output_dir = create_timestamped_output_dir(args.metadata_path.parent)

    # === Step 2: Load and slice metadata ===
    meta = pl.read_csv(args.metadata_path)
    meta_sliced = slice_metadata_by_id(meta)

    # === Step 3: Load processed metadata ===
    meta_processed = pl.read_csv(args.top1_final_path)

    # Debug: Check the original data
    logger.info(f"Original data size: {len(meta_processed)}")
    
    # Step 1: Identify pollinator and non-pollinators
    meta_processed = create_pollinator_strata(meta_processed)
    
    # Check strata distribution
    strata_counts = meta_processed.group_by("strata1").agg(pl.count().alias("count"))
    logger.info(f"Strata distribution: {strata_counts.to_dict()}")
    
    # Step 2: Group by probability
    meta_processed = meta_processed.with_columns([
        pl.when(pl.col("top1_prob_weighted") <= 0.5)
        .then(pl.lit("low_prob"))
        .otherwise(pl.lit("high_prob"))
        .alias("prob_strata1")
    ])

    # === STRATA 1: Pollinator/Non-pollinator + Probability ===
    # Use n_per_group_strata1

    # Process pollinators
    pollinator_data = meta_processed.filter(pl.col("strata1") == "pollinator")
    pollinator_sample_size = n_per_group_strata1 // 2
    low_prob_pollinators = pollinator_data.filter(pl.col("prob_strata1") == "low_prob")
    high_prob_pollinators = pollinator_data.filter(pl.col("prob_strata1") == "high_prob")
    sampled_low_pollinator = low_prob_pollinators.sample(n=min(pollinator_sample_size, len(low_prob_pollinators)), seed=seed)
    sampled_high_pollinator = high_prob_pollinators.sample(n=min(pollinator_sample_size, len(high_prob_pollinators)), seed=seed)
    pollinator_samples = pl.concat([sampled_low_pollinator, sampled_high_pollinator], how="vertical")

    # Process non-pollinators
    non_pollinator_data = meta_processed.filter(pl.col("strata1") == "non_pollinator")
    non_pollinator_sample_size = n_per_group_strata1 // 2
    low_prob_non_pollinators = non_pollinator_data.filter(pl.col("prob_strata1") == "low_prob")
    high_prob_non_pollinators = non_pollinator_data.filter(pl.col("prob_strata1") == "high_prob")
    sampled_low_non_pollinator = low_prob_non_pollinators.sample(n=min(non_pollinator_sample_size, len(low_prob_non_pollinators)), seed=seed)
    sampled_high_non_pollinator = high_prob_non_pollinators.sample(n=min(non_pollinator_sample_size, len(high_prob_non_pollinators)), seed=seed)
    non_pollinator_samples = pl.concat([sampled_low_non_pollinator, sampled_high_non_pollinator], how="vertical")

    # Combine all samples for strata1
    meta_strat1_final = pl.concat([pollinator_samples, non_pollinator_samples], how="vertical")
    
    # Join with crop_path
    meta_strat1_crop = meta_strat1_final.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save strata1
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename_strata1 = f"strata1_{timestamp}.csv"
    meta_strat1_crop.write_csv(output_dir / filename_strata1)
    logger.info(f"Saved strata1: {filename_strata1}")

     # === STRATA 2: Duration-based stratification (only for pollinators) ===
    # Filter meta_processed to include only pollinators (strata1 == "pollinator")
    pollinator_only = meta_processed.filter(pl.col("strata1") == "pollinator")

    # Define duration categories:
    #   - 0: "single_crop"
    #   - >0 and <=500: "multiple_crop"
    #   - >500: "long_crop"

    pollinator_only = pollinator_only.with_columns([
        pl.when(pl.col("duration_s") == 0)
        .then(pl.lit("single_crop"))
        .when((pl.col("duration_s") > 0) & (pl.col("duration_s") <= 500))
        .then(pl.lit("multiple_crop"))
        .when(pl.col("duration_s") > 500)
        .then(pl.lit("long_crop"))
        .otherwise(pl.lit("unknown"))
        .alias("strata2")
    ])

    # Check distribution of strata2 within pollinators
    strata2_counts = pollinator_only.group_by("strata2").agg(pl.count().alias("count"))
    logger.info(f"Strata2 (duration) distribution (pollinators only): {strata2_counts.to_dict()}")

    # === Sample 50% high_prob, 50% low_prob within each duration group ===
    strata2_samples = []

    # Define the three duration groups
    duration_groups = ["single_crop", "multiple_crop", "long_crop"]
    total_sample_size = n_per_group_strata2

    for group in duration_groups:
        group_data = pollinator_only.filter(pl.col("strata2") == group)
        if len(group_data) == 0:
            logger.warning(f"No data found for duration group: {group}")
            continue

        # Split into high_prob and low_prob
        high_prob_group = group_data.filter(pl.col("prob_strata1") == "high_prob")
        low_prob_group = group_data.filter(pl.col("prob_strata1") == "low_prob")

        # Calculate how many to sample from each (50/50)
        sample_high = min(total_sample_size // 2, len(high_prob_group))
        sample_low = min(total_sample_size // 2, len(low_prob_group))

        # Sample from each
        sampled_high = high_prob_group.sample(n=sample_high, seed=seed)
        sampled_low = low_prob_group.sample(n=sample_low, seed=seed)

        # Combine and add to list
        combined_sample = pl.concat([sampled_high, sampled_low], how="vertical")
        strata2_samples.append(combined_sample)

        logger.info(f"  - Group {group}: sampled {sample_high} high_prob, {sample_low} low_prob")

    # Combine all strata2 samples (pollinator-only)
    meta_strat2_final = pl.concat(strata2_samples, how="vertical")

    # Join with crop_path
    meta_strat2_crop = meta_strat2_final.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save strata2
    filename_strata2 = f"strata2_{timestamp}.csv"
    meta_strat2_crop.write_csv(output_dir / filename_strata2)
    logger.info(f"Saved strata2 (pollinator-only, 50% high/low prob per duration group): {filename_strata2}")
    
    # === Summary ===
    print(f"\n✅ Strata samples created!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - n_per_group_strata1: {n_per_group_strata1}")
    print(f"  - n_per_group_strata2: {n_per_group_strata2}")
    print(f"  - Total strata1 samples: {len(meta_strat1_crop)}")
    print(f"  - Total strata2 samples: {len(meta_strat2_crop)}")
    print(f"  - Strata1 file: {filename_strata1}")
    print(f"  - Strata2 file: {filename_strata2}")
if __name__ == "__main__":
    main()