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
        description="Stratified random subsampling focusing on pollinator/non-pollinator strata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stratified_random_subsampling.py \
    --metadata-path /path/to/all_metadata_combined.csv \
    --top1-final-path /path/to/all_metadata_combined_top1_final.csv \
    --n-per-group 100 \
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
        "--n-per-group",
        type=int,
        default=100,
        help="Number of subsamples per group (default: 100)"
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
    n_per_group = args.n_per_group
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
    
    # Step 2: Group both according to probability
    meta_processed = meta_processed.with_columns([
        pl.when(pl.col("top1_prob_weighted") <= 0.5)
        .then(pl.lit("low_prob"))
        .otherwise(pl.lit("high_prob"))
        .alias("prob_strata")
    ])
    
    # Step 3: Sample half of the indicated sample size per group
    # For each strata (pollinator and non-pollinator), sample n_per_group/2 from each probability group
    
    # Process pollinators
    pollinator_data = meta_processed.filter(pl.col("strata1") == "pollinator")
    logger.info(f"Pollinator data size: {len(pollinator_data)}")
    
    # Sample from low probability group
    low_prob_pollinators = pollinator_data.filter(pl.col("prob_strata") == "low_prob")
    high_prob_pollinators = pollinator_data.filter(pl.col("prob_strata") == "high_prob")
    
    pollinator_sample_size = n_per_group // 2
    sampled_low_pollinator = low_prob_pollinators.sample(n=min(pollinator_sample_size, len(low_prob_pollinators)), seed=seed)
    sampled_high_pollinator = high_prob_pollinators.sample(n=min(pollinator_sample_size, len(high_prob_pollinators)), seed=seed)
    
    pollinator_samples = pl.concat([sampled_low_pollinator, sampled_high_pollinator], how="vertical")
    
    # Process non-pollinators
    non_pollinator_data = meta_processed.filter(pl.col("strata1") == "non_pollinator")
    logger.info(f"Non-pollinator data size: {len(non_pollinator_data)}")
    
    # Sample from low probability group
    low_prob_non_pollinators = non_pollinator_data.filter(pl.col("prob_strata") == "low_prob")
    high_prob_non_pollinators = non_pollinator_data.filter(pl.col("prob_strata") == "high_prob")
    
    non_pollinator_sample_size = n_per_group // 2
    sampled_low_non_pollinator = low_prob_non_pollinators.sample(n=min(non_pollinator_sample_size, len(low_prob_non_pollinators)), seed=seed)
    sampled_high_non_pollinator = high_prob_non_pollinators.sample(n=min(non_pollinator_sample_size, len(high_prob_non_pollinators)), seed=seed)
    
    non_pollinator_samples = pl.concat([sampled_low_non_pollinator, sampled_high_non_pollinator], how="vertical")
    
    # Combine all samples
    meta_strat1_final = pl.concat([pollinator_samples, non_pollinator_samples], how="vertical")
    
    # Join with crop_path
    meta_strat1_crop = meta_strat1_final.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save the main strata1 file with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"strata1_{timestamp}.csv"
    meta_strat1_crop.write_csv(output_dir / filename)
    logger.info(f"Saved {filename}")

    # === Summary ===
    print(f"\n✅ Strata samples created!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - n_per_group: {n_per_group}")
    print(f"  - Total samples: {len(meta_strat1_crop)}")
    print(f"  - Main file: {filename}")

if __name__ == "__main__":
    main()