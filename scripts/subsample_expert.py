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
DEFAULT_N_PER_GROUP_ALL = 100
DEFAULT_N_PER_GROUP_SYRPHID = 100
DEFAULT_N_PER_GENUS = 50
DEFAULT_DET_CONF_THRESHOLD = 0.5
DEFAULT_PROB_THRESHOLDS = [0.5]
DEFAULT_PROB_THRESHOLD_GENUS = 0.5
DEFAULT_SEED = 123


# === Helper: Create timestamped output folder ===
def create_timestamped_output_dir(output_dir: Path) -> Path:
    """Create a new run directory with timestamped name: sample_all_YYYY-MM-DD_HH-MM-SS"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = output_dir / f"sample_all_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created output directory: {output_dir}")
    return output_dir


# === Helper: Slice metadata to one row per (cam_ID, rec_ID, track_ID) ===
def slice_metadata_by_id(df: pl.DataFrame) -> pl.DataFrame:
    """
    For each unique (cam_ID, rec_ID, track_ID), keep only the row with the highest bioclip_score.
    If bioclip_score is missing, use the first row.
    """
    if "bioclip_score" in df.columns:
        df = df.with_columns(pl.col("bioclip_score").cast(pl.Float64))
    else:
        logger.warning("bioclip_score column not found. Using first row per group.")
        return df.group_by(["cam_ID", "rec_ID", "track_ID"]).first()

    # Sort by bioclip_score descending, then by row index to ensure determinism
    df = df.with_columns(
        pl.col("bioclip_score").fill_null(-1.0)
    ).sort(
        by=["cam_ID", "rec_ID", "track_ID", "bioclip_score"],
        descending=[False, False, False, True]
    )

    df = df.group_by(["cam_ID", "rec_ID", "track_ID"]).first()
    logger.info(f"Metadata sliced to {len(df)} unique tracks.")
    return df


# === Helper: Create strata_syrphid with multiple probability thresholds ===
def create_strata_syrphid(
    meta_processed: pl.DataFrame,
    meta_sliced: pl.DataFrame,
    prob_thresholds: List[float],
    n_per_group_syrphid: int,
    seed: int,
    output_dir: Path
) -> None:
    """
    Create strata_syrphid: only rows where bioclip_family == "Syrphidae"
    For each prob_threshold, sample up to n_per_group_syrphid rows with top1_prob_weighted > threshold.
    Save each as a separate CSV.
    """
    # Filter for Syrphidae
    syrphid_data = meta_processed.filter(pl.col("bioclip_family") == "Syrphidae")
    logger.info(f"Found {len(syrphid_data)} rows with bioclip_family == 'Syrphidae'")

    if len(syrphid_data) == 0:
        logger.warning("No data found for Syrphidae. Skipping strata_syrphid.")
        return

    # Loop over each probability threshold
    for threshold in prob_thresholds:
        filtered = syrphid_data.filter(pl.col("top1_prob_weighted") > threshold)
        logger.info(f"  - Threshold {threshold}: {len(filtered)} rows with top1_prob_weighted > {threshold}")

        if len(filtered) == 0:
            logger.warning(f"  - No data for threshold {threshold}. Skipping.")
            continue

        # Sample up to n_per_group_syrphid
        sample_size = min(n_per_group_syrphid, len(filtered))
        sampled = filtered.sample(n=sample_size, seed=seed)

        # Join with crop_path
        meta_with_crop = sampled.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Save file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"strata_syrphid_{threshold:.1f}_{timestamp}.csv"
        meta_with_crop.write_csv(output_dir / filename)
        logger.info(f"Saved strata_syrphid: {filename} ({len(meta_with_crop)} samples)")


# === Helper: Create strata_syrphid_genus (per genus, with threshold) ===
def create_strata_syrphid_genus(
    meta_processed: pl.DataFrame,
    meta_sliced: pl.DataFrame,
    n_per_genus: int,
    prob_threshold_genus: float,
    seed: int,
    output_dir: Path
) -> None:
    """
    Create strata_syrphid_genus: only rows where bioclip_family == "Syrphidae"
    For each unique bioclip_genus, sample n_per_genus rows with top1_prob_weighted > prob_threshold_genus.
    Save one CSV per genus.
    """
    # Filter for Syrphidae
    syrphid_data = meta_processed.filter(pl.col("bioclip_family") == "Syrphidae")
    logger.info(f"Found {len(syrphid_data)} rows with bioclip_family == 'Syrphidae'")

    if len(syrphid_data) == 0:
        logger.warning("No data found for Syrphidae. Skipping strata_syrphid_genus.")
        return

    # Get unique genera
    unique_genus = syrphid_data["bioclip_genus"].unique()
    logger.info(f"Found {len(unique_genus)} unique genera in Syrphidae: {unique_genus.to_list()}")

    # Loop over each genus
    for genus in unique_genus:
        genus_data = syrphid_data.filter(pl.col("bioclip_genus") == genus)
        logger.info(f"  - Genus: {genus} → {len(genus_data)} rows")

        if len(genus_data) == 0:
            logger.warning(f"  - No data for genus {genus}. Skipping.")
            continue

        # Filter by probability threshold
        filtered = genus_data.filter(pl.col("top1_prob_weighted") > prob_threshold_genus)
        logger.info(f"    - After prob threshold {prob_threshold_genus}: {len(filtered)} rows")

        if len(filtered) == 0:
            logger.warning(f"    - No data after threshold for genus {genus}. Skipping.")
            continue

        # Sample up to n_per_genus
        sample_size = min(n_per_genus, len(filtered))
        sampled = filtered.sample(n=sample_size, seed=seed)

        # Join with crop_path
        meta_with_crop = sampled.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Generate short filename: first 3 chars of genus + _ + first 3 chars after space
        parts = genus.split(maxsplit=1)
        if len(parts) < 2:
            short_name = genus[:3].lower()
        else:
            genus_part = parts[0]
            species_part = parts[1]
            short_name = f"{genus_part[:3].lower()}_{species_part[:3].lower()}"

        # Save file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"strata_syrphid_genus_{short_name}_{timestamp}.csv"
        meta_with_crop.write_csv(output_dir / filename)
        logger.info(f"Saved strata_syrphid_genus: {filename} ({len(meta_with_crop)} samples)")


# === Main CLI Entry Point ===
def main():
    # === Argument Parser ===
    parser = argparse.ArgumentParser(
        description="Random subsampling of all images with det_conf_mean > threshold, "
                    "plus optional strata_syrphid and strata_syrphid_genus with thresholds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python subsample_expert.py \
    --metadata-path C:/path/to/all_metadata_combined.csv \
    --top1-final-path C:/path/to/all_metadata_combined_top1_final.csv \
    --n-per-group-all 500 \
    --det-conf-threshold 0.7 \
    --n-per-group-syrphid 100 \
    --prob-thresholds 0.5 0.7 \
    --n-per-genus 50 \
    --prob-threshold-genus 0.6 \
    --seed 42
        """
    )

    parser.add_argument(
        "--metadata-path",
        type=Path,
        required=True,
        help="Path to all_metadata_combined.csv (use forward slashes: C:/...)"
    )
    parser.add_argument(
        "--top1-final-path",
        type=Path,
        required=True,
        help="Path to all_metadata_combined_top1_final.csv"
    )
    parser.add_argument(
        "--n-per-group-all",
        type=int,
        default=DEFAULT_N_PER_GROUP_ALL,
        help=f"Number of random samples to select from all images (default: {DEFAULT_N_PER_GROUP_ALL})"
    )
    parser.add_argument(
        "--det-conf-threshold",
        type=float,
        default=DEFAULT_DET_CONF_THRESHOLD,
        help=f"Minimum det_conf_mean value to include (default: {DEFAULT_DET_CONF_THRESHOLD})"
    )
    parser.add_argument(
        "--n-per-group-syrphid",
        type=int,
        default=DEFAULT_N_PER_GROUP_SYRPHID,
        help=f"Number of samples per Syrphidae threshold (default: {DEFAULT_N_PER_GROUP_SYRPHID})"
    )
    parser.add_argument(
        "--prob-thresholds",
        type=float,
        nargs="+",
        default=DEFAULT_PROB_THRESHOLDS,
        help=f"List of top1_prob_weighted thresholds for strata_syrphid (default: {DEFAULT_PROB_THRESHOLDS})"
    )
    parser.add_argument(
        "--n-per-genus",
        type=int,
        default=DEFAULT_N_PER_GENUS,
        help=f"Number of samples per Syrphidae genus (default: {DEFAULT_N_PER_GENUS})"
    )
    parser.add_argument(
        "--prob-threshold-genus",
        type=float,
        default=DEFAULT_PROB_THRESHOLD_GENUS,
        help=f"Minimum top1_prob_weighted for strata_syrphid_genus (default: {DEFAULT_PROB_THRESHOLD_GENUS})"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
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
    n_per_group_all = args.n_per_group_all
    det_conf_threshold = args.det_conf_threshold
    n_per_group_syrphid = args.n_per_group_syrphid
    prob_thresholds = args.prob_thresholds
    n_per_genus = args.n_per_genus
    prob_threshold_genus = args.prob_threshold_genus
    seed = args.seed

    # === Step 1: Create timestamped output folder ===
    output_dir = create_timestamped_output_dir(args.metadata_path.parent)

    # === Step 2: Load and slice metadata ===
    meta = pl.read_csv(args.metadata_path)
    meta_sliced = slice_metadata_by_id(meta)

    # === Step 3: Load processed metadata ===
    meta_processed = pl.read_csv(args.top1_final_path)

    # === Filter by det_conf_mean threshold ===
    filtered_meta = meta_processed.filter(
        pl.col("det_conf_mean") > det_conf_threshold
    )
    logger.info(f"Filtered to {len(filtered_meta)} rows with det_conf_mean > {det_conf_threshold}")

    if len(filtered_meta) == 0:
        logger.warning("No data meets the det_conf_mean threshold. Exiting.")
        return

    # === Random sampling (sample_all) ===
    sampled_all = filtered_meta.sample(n=min(n_per_group_all, len(filtered_meta)), seed=seed)
    logger.info(f"Randomly sampled {len(sampled_all)} rows (requested: {n_per_group_all})")

    # === Join with crop_path ===
    meta_with_crop_all = sampled_all.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # === Save sample_all ===
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename_all = f"sample_all_{timestamp}.csv"
    meta_with_crop_all.write_csv(output_dir / filename_all)
    logger.info(f"Saved sample_all: {filename_all}")

    # === Create strata_syrphid ===
    create_strata_syrphid(
        meta_processed=meta_processed,
        meta_sliced=meta_sliced,
        prob_thresholds=prob_thresholds,
        n_per_group_syrphid=n_per_group_syrphid,
        seed=seed,
        output_dir=output_dir
    )

    # === Create strata_syrphid_genus ===
    create_strata_syrphid_genus(
        meta_processed=meta_processed,
        meta_sliced=meta_sliced,
        n_per_genus=n_per_genus,
        prob_threshold_genus=prob_threshold_genus,
        seed=seed,
        output_dir=output_dir
    )

    # === Summary ===
    print(f"\n✅ Subsampling complete!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - Threshold: det_conf_mean > {det_conf_threshold}")
    print(f"  - Sampled (all): {len(sampled_all)} images → {filename_all}")
    print(f"  - Strata_syrphid: {len(prob_thresholds)} thresholds: {prob_thresholds}")
    for t in prob_thresholds:
        print(f"    - strata_syrphid_{t:.1f}.csv")
    print(f"  - Strata_syrphid_genus: {n_per_genus} samples per genus, threshold {prob_threshold_genus}")


if __name__ == "__main__":
    main()