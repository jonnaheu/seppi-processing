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

# === Helper: Stratified random sampling ===
def stratified_random_sample(
    df: pl.DataFrame,
    group_column: str,
    n_per_group: int = DEFAULT_N_PER_GROUP,
    seed: int = DEFAULT_SEED
) -> pl.DataFrame:
    """
    Perform stratified random sampling: select n_per_group rows from each group.

    Args:
        df: Input DataFrame
        group_column: Column to group by
        n_per_group: Number of rows to sample per group
        seed: Random seed for reproducibility

    Returns:
        Sampled DataFrame
    """
    # Set seed
    random.seed(seed)  # ← Only use random.seed()

    # Group by specified column
    groups = df.group_by(group_column)

    # Sample n_per_group from each group
    sampled_dfs = []
    for name, group_df in groups:
        if len(group_df) < n_per_group:
            logger.warning(f"Group {name} has only {len(group_df)} rows. Sampling all.")
            sampled_dfs.append(group_df)
        else:
            sampled = group_df.sample(n=n_per_group, shuffle=True)
            sampled_dfs.append(sampled)

    # Concatenate all samples
    sampled_df = pl.concat(sampled_dfs, how="vertical")
    logger.info(f"Stratified sampling completed: {len(sampled_df)} rows selected.")
    return sampled_df

# === Helper: Create duration bins ===
def create_duration_bins(df: pl.DataFrame) -> pl.DataFrame:
    """Create duration bins: ==0, >0-500, >500"""
    df = df.with_columns([
        pl.when(pl.col("duration_s") == 0)
        .then(pl.lit("0"))
        .when(pl.col("duration_s") <= 500)
        .then(pl.lit(">0-500"))
        .otherwise(pl.lit(">500"))
        .alias("duration_bin")
    ])
    return df


# === Helper: Create probability bins ===
def create_probability_bins(df: pl.DataFrame) -> pl.DataFrame:
    """Create 10 bins: 0.0-0.1, 0.1-0.2, ..., 0.9-1.0"""
    df = df.with_columns([
        pl.when(pl.col("top1_prob_weighted") < 0.1)
        .then(pl.lit("0.0-0.1"))
        .when(pl.col("top1_prob_weighted") < 0.2)
        .then(pl.lit("0.1-0.2"))
        .when(pl.col("top1_prob_weighted") < 0.3)
        .then(pl.lit("0.2-0.3"))
        .when(pl.col("top1_prob_weighted") < 0.4)
        .then(pl.lit("0.3-0.4"))
        .when(pl.col("top1_prob_weighted") < 0.5)
        .then(pl.lit("0.4-0.5"))
        .when(pl.col("top1_prob_weighted") < 0.6)
        .then(pl.lit("0.5-0.6"))
        .when(pl.col("top1_prob_weighted") < 0.7)
        .then(pl.lit("0.6-0.7"))
        .when(pl.col("top1_prob_weighted") < 0.8)
        .then(pl.lit("0.7-0.8"))
        .when(pl.col("top1_prob_weighted") < 0.9)
        .then(pl.lit("0.8-0.9"))
        .otherwise(pl.lit("0.9-1.0"))
        .alias("prob_bin")
    ])
    return df

# === Main CLI Entry Point ===
def main():
    # === Argument Parser ===
    parser = argparse.ArgumentParser(
        description="Stratified random subsampling of metadata with crop_path.",
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

    # === Strata 1: order_category (pollinator vs non-pollinator) ===
    meta_strat1 = stratified_random_sample(
        df=meta_processed,
        group_column="order_category",
        n_per_group=n_per_group,
        seed=seed
    )

    # Join with crop_path
    meta_strat1_crop = meta_strat1.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save
    meta_strat1_crop.write_csv(output_dir / "meta_strat1_crop.csv")
    logger.info(f"Saved meta_strat1_crop.csv")

    # Split
    meta_strat1_crop_polli = meta_strat1_crop.filter(pl.col("order_category") == "pollinator")
    meta_strat1_crop_non_polli = meta_strat1_crop.filter(pl.col("order_category") == "non-pollinator")

    meta_strat1_crop_polli.write_csv(output_dir / "meta_strat1_crop_polli.csv")
    meta_strat1_crop_non_polli.write_csv(output_dir / "meta_strat1_crop_non_polli.csv")

    # === Strata 2: duration_s (bins: 0, >0-500, >500) ===
    meta_processed = create_duration_bins(meta_processed)

    meta_strat2 = stratified_random_sample(
        df=meta_processed,
        group_column="duration_bin",
        n_per_group=n_per_group,
        seed=seed
    )

    # Join with crop_path
    meta_strat2_crop = meta_strat2.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save each bin
    for bin_name in ["0", ">0-500", ">500"]:
        bin_data = meta_strat2_crop.filter(pl.col("duration_bin") == bin_name)
        bin_data.write_csv(output_dir / f"meta_strat2_{bin_name.replace('>', 'gt').replace('-', '_')}.csv")
        logger.info(f"Saved meta_strat2_{bin_name.replace('>', 'gt').replace('-', '_')}.csv")

    # === Strata 3: top1_prob_weighted (10 bins: 0.0-0.1, ..., 0.9-1.0) ===
    meta_processed = create_probability_bins(meta_processed)

    meta_strat3 = stratified_random_sample(
        df=meta_processed,
        group_column="prob_bin",
        n_per_group=n_per_group,
        seed=seed
    )

    # Join with crop_path
    meta_strat3_crop = meta_strat3.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save each bin
    for bin_name in [f"{i:.1f}-{(i+0.1):.1f}" for i in range(10)]:
        bin_data = meta_strat3_crop.filter(pl.col("prob_bin") == bin_name)
        bin_data.write_csv(output_dir / f"meta_strat3_{bin_name.replace('-', '_')}.csv")
        logger.info(f"Saved meta_strat3_{bin_name.replace('-', '_')}.csv")

    # === Summary ===
    print(f"\n✅ Strata samples created!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - n_per_group: {n_per_group}")
    print(f"  - Total files saved: 14")

if __name__ == "__main__":
    main()