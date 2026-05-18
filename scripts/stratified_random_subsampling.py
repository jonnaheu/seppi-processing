from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import random
from datetime import datetime

import argparse
import polars as pl
from yaml import parser

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
        "--n-per-group-strata3",
        type=int,
        default=50,
        help="Number of subsamples per probability bin for strata3 (default: 50)"
    )
    parser.add_argument(
        "--n-per-group-strata4",
        type=int,
        default=50,
        help="Number of subsamples per plant species for strata4 (default: 50)"
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
    n_per_group_strata3 = args.n_per_group_strata3
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

    # === STRATA 3: Stratified sampling by bioclip_order (Hymenoptera, Lepidoptera, Coleoptera, Diptera) ===
    # Define the four orders of interest
    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Read n_per_group_strata3 from args
    n_per_group_strata3 = args.n_per_group_strata3

    # Create probability bins: 0.0–0.1, 0.1–0.2, ..., 0.9–1.0
    bin_labels = [f"{i*0.1:.1f}-{(i+1)*0.1:.1f}" for i in range(10)]
    bin_edges = [i * 0.1 for i in range(11)]  # [0.0, 0.1, ..., 1.0]

    # Create prob_bin column using pl.when().then().when().then().otherwise()
    meta_processed = meta_processed.with_columns([
        pl.when(pl.col("top1_prob_weighted") < bin_edges[1])
        .then(pl.lit(bin_labels[0]))
        .when(pl.col("top1_prob_weighted") < bin_edges[2])
        .then(pl.lit(bin_labels[1]))
        .when(pl.col("top1_prob_weighted") < bin_edges[3])
        .then(pl.lit(bin_labels[2]))
        .when(pl.col("top1_prob_weighted") < bin_edges[4])
        .then(pl.lit(bin_labels[3]))
        .when(pl.col("top1_prob_weighted") < bin_edges[5])
        .then(pl.lit(bin_labels[4]))
        .when(pl.col("top1_prob_weighted") < bin_edges[6])
        .then(pl.lit(bin_labels[5]))
        .when(pl.col("top1_prob_weighted") < bin_edges[7])
        .then(pl.lit(bin_labels[6]))
        .when(pl.col("top1_prob_weighted") < bin_edges[8])
        .then(pl.lit(bin_labels[7]))
        .when(pl.col("top1_prob_weighted") < bin_edges[9])
        .then(pl.lit(bin_labels[8]))
        .when(pl.col("top1_prob_weighted") < bin_edges[10])
        .then(pl.lit(bin_labels[9]))
        .otherwise(pl.lit("1.0-1.0"))  # Handle edge case (should be rare)
        .alias("prob_bin")
    ])

    # Now loop over each target order
    for order in target_orders:
        logger.info(f"Processing strata3 for {order}...")

        # Filter data for this order
        order_data = meta_processed.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data found for {order}. Skipping.")
            continue

        # Check how many bins are present
        bin_counts = order_data.group_by("prob_bin").agg(pl.count().alias("count"))
        logger.info(f"  - {order} has {len(bin_counts)} bins with counts: {bin_counts.to_dict()}")

        # Sample n_per_group_strata3 from each bin
        sampled_bins = []
        for bin_label in bin_labels:
            bin_data = order_data.filter(pl.col("prob_bin") == bin_label)
            if len(bin_data) == 0:
                logger.warning(f"  - No data in bin {bin_label} for {order}")
                continue
            sample_size = min(n_per_group_strata3, len(bin_data))
            sampled = bin_data.sample(n=sample_size, seed=seed)
            sampled_bins.append(sampled)

        # Combine all sampled bins
        meta_strat3_final = pl.concat(sampled_bins, how="vertical")

        # Join with crop_path
        meta_strat3_crop = meta_strat3_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Save file
        short_name = order_short[order]
        filename = f"strata3_{short_name}_{timestamp}.csv"
        meta_strat3_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat3_crop)} samples)")
        
    # === STRATA 4: Plant Species Stratification (Pollinators with duration > 0s) ===
    # Filter to pollinators with duration > 0s
    pollinator_active = meta_processed.filter(
        (pl.col("strata1") == "pollinator") &
        (pl.col("duration_s") > 0)
    )

    # Check how many unique plant species exist
    unique_plants = pollinator_active["plant_species"].unique()
    logger.info(f"Found {len(unique_plants)} unique plant species (pollinators with duration > 0s)")

    # Define probability groups
    n_per_group_strata4 = args.n_per_group_strata4
    total_sample_size = n_per_group_strata4

    # Sample 50% high_prob, 50% low_prob per plant species
    strata4_samples = []

    for plant in unique_plants:
        logger.info(f"Processing strata4 for plant: {plant}")

        # Filter data for this plant
        plant_data = pollinator_active.filter(pl.col("plant_species") == plant)

        if len(plant_data) == 0:
            logger.warning(f"No data found for plant: {plant}")
            continue

        # Split into high_prob and low_prob
        high_prob_plant = plant_data.filter(pl.col("prob_strata1") == "high_prob")
        low_prob_plant = plant_data.filter(pl.col("prob_strata1") == "low_prob")

        # Calculate how many to sample from each (50/50)
        sample_high = min(total_sample_size // 2, len(high_prob_plant))
        sample_low = min(total_sample_size // 2, len(low_prob_plant))

        # Sample from each
        sampled_high = high_prob_plant.sample(n=sample_high, seed=seed)
        sampled_low = low_prob_plant.sample(n=sample_low, seed=seed)

        # Combine and add to list
        combined_sample = pl.concat([sampled_high, sampled_low], how="vertical")
        strata4_samples.append(combined_sample)

        logger.info(f"  - Plant {plant}: sampled {sample_high} high_prob, {sample_low} low_prob")

    # Combine all strata4 samples
    meta_strat4_final = pl.concat(strata4_samples, how="vertical")

    # Join with crop_path
    meta_strat4_crop = meta_strat4_final.join(
        meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
        on=["cam_ID", "rec_ID", "track_ID"],
        how="left"
    )

    # Save strata4
    filename_strata4 = f"strata4_{timestamp}.csv"
    meta_strat4_crop.write_csv(output_dir / filename_strata4)
    logger.info(f"Saved strata4 (pollinators with duration > 0s, 50% high/low prob per plant): {filename_strata4}")

    # === STRATA 5: Two samples per genus (low and high prob) per pollinator order (duration_s > 0) ===
    # Target orders
    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Define probability thresholds
    low_prob_threshold = 0.3
    high_prob_threshold = 0.3  # > 0.3 is high

    # Ensure bioclip_genus exists
    if "bioclip_genus" not in meta_processed.columns:
        logger.error("bioclip_genus column not found. Cannot create strata5.")
        return

    # Filter meta_processed to only include rows where duration_s > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Loop over each target order
    for order in target_orders:
        logger.info(f"Processing strata5 for {order} (duration_s > 0)...")

        # Filter data for this order AND duration > 0
        order_data = duration_filtered.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data found for {order} with duration_s > 0. Skipping.")
            continue

        # Get unique genera in this order (with duration > 0)
        unique_genus = order_data["bioclip_genus"].unique()
        logger.info(f"  - {order} has {len(unique_genus)} unique genera with duration_s > 0.")

        # List to store sampled rows
        sampled_rows = []

        # For each genus, sample one low-prob and one high-prob detection
        for genus in unique_genus:
            genus_data = order_data.filter(pl.col("bioclip_genus") == genus)

            if len(genus_data) == 0:
                continue

            # Split into low and high probability
            low_prob_genus = genus_data.filter(pl.col("top1_prob_weighted") <= low_prob_threshold)
            high_prob_genus = genus_data.filter(pl.col("top1_prob_weighted") > high_prob_threshold)

            # Sample one from each (if available)
            sampled_low = low_prob_genus.sample(n=1, seed=seed) if len(low_prob_genus) > 0 else None
            sampled_high = high_prob_genus.sample(n=1, seed=seed) if len(high_prob_genus) > 0 else None

            # Add to list with strata5_prob label
            if sampled_low is not None:
                # Add strata5_prob column
                sampled_low = sampled_low.with_columns(
                    pl.lit("low_prob").alias("strata5_prob")
                )
                sampled_rows.append(sampled_low)
            if sampled_high is not None:
                # Add strata5_prob column
                sampled_high = sampled_high.with_columns(
                    pl.lit("high_prob").alias("strata5_prob")
                )
                sampled_rows.append(sampled_high)

        # Combine all sampled rows for this order
        if not sampled_rows:
            logger.warning(f"No samples collected for {order} (after filtering duration_s > 0). Skipping output.")
            continue

        meta_strat5_final = pl.concat(sampled_rows, how="vertical")

        # Join with crop_path
        meta_strat5_crop = meta_strat5_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Save file
        short_name = order_short[order]
        filename = f"strata5_{short_name}_{timestamp}.csv"
        meta_strat5_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat5_crop)} samples)")

    # === STRATA 6: Two samples per family (low and high prob) per pollinator order (duration_s > 0) ===
    # Target orders
    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Define probability thresholds
    low_prob_threshold = 0.3
    high_prob_threshold = 0.3  # > 0.3 is high

    # Ensure bioclip_family exists
    if "bioclip_family" not in meta_processed.columns:
        logger.error("bioclip_family column not found. Cannot create strata6.")
        return

    # Filter meta_processed to only include rows where duration_s > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Loop over each target order
    for order in target_orders:
        logger.info(f"Processing strata6 for {order} (duration_s > 0, family-level)...")

        # Filter data for this order AND duration > 0
        order_data = duration_filtered.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data found for {order} with duration_s > 0. Skipping.")
            continue

        # Get unique families in this order (with duration > 0)
        unique_family = order_data["bioclip_family"].unique()
        logger.info(f"  - {order} has {len(unique_family)} unique families with duration_s > 0.")

        # List to store sampled rows
        sampled_rows = []

        # For each family, sample one low-prob and one high-prob detection
        for family in unique_family:
            family_data = order_data.filter(pl.col("bioclip_family") == family)

            if len(family_data) == 0:
                continue

            # Split into low and high probability
            low_prob_family = family_data.filter(pl.col("top1_prob_weighted") <= low_prob_threshold)
            high_prob_family = family_data.filter(pl.col("top1_prob_weighted") > high_prob_threshold)

            # Sample one from each (if available)
            sampled_low = low_prob_family.sample(n=1, seed=seed) if len(low_prob_family) > 0 else None
            sampled_high = high_prob_family.sample(n=1, seed=seed) if len(high_prob_family) > 0 else None

            # Add to list with strata6_prob column
            if sampled_low is not None:
                sampled_low = sampled_low.with_columns(
                    pl.lit("low_prob").alias("strata6_prob")
                )
                sampled_rows.append(sampled_low)
            if sampled_high is not None:
                sampled_high = sampled_high.with_columns(
                    pl.lit("high_prob").alias("strata6_prob")
                )
                sampled_rows.append(sampled_high)

        # Combine all sampled rows for this order
        if not sampled_rows:
            logger.warning(f"No samples collected for {order} (after filtering duration_s > 0). Skipping output.")
            continue

        meta_strat6_final = pl.concat(sampled_rows, how="vertical")

        # Join with crop_path
        meta_strat6_crop = meta_strat6_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Save file
        short_name = order_short[order]
        filename = f"strata6_{short_name}_{timestamp}.csv"
        meta_strat6_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat6_crop)} samples)")

        # === STRATA 7: Top N most frequent species, subsample n_per_group_strata7 per species (low/high prob) ===
    parser.add_argument(
        "--n-common-species-strata7",
        type=int,
        default=10,
        help="Number of top frequent species to subsample from (default: 10)"
    )

    # Parse args again to include new argument
    args = parser.parse_args()  # Re-parse to get new arg

    # Extract new argument
    n_common_species = args.n_common_species_strata7
    n_per_group_strata7 = args.n_per_group_strata7  # Reuse same n_per_group as strata5/6

    # Ensure bioclip_species exists
    if "bioclip_species" not in meta_processed.columns:
        logger.error("bioclip_species column not found. Cannot create strata7.")
        return

    # Filter to only include duration_s > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Count frequency of each species
    species_counts = duration_filtered.group_by("bioclip_species").agg(
        pl.count().alias("count")
    ).sort("count", descending=True)

    # Get top N most frequent species
    top_species = species_counts.head(n_common_species)["bioclip_species"].to_list()
    logger.info(f"Selected top {len(top_species)} most frequent species: {top_species}")

    # Create output subfolder for strata7
    strata7_dir = output_dir / f"strata7_{timestamp}"
    strata7_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created strata7 output directory: {strata7_dir}")

    # Loop over each selected species
    for species in top_species:
        logger.info(f"Processing strata7 for species: {species}")

        # Filter data for this species
        species_data = duration_filtered.filter(pl.col("bioclip_species") == species)

        if len(species_data) == 0:
            logger.warning(f"No data found for species: {species}. Skipping.")
            continue

        # Split into low and high probability
        low_prob_species = species_data.filter(pl.col("top1_prob_weighted") <= 0.3)
        high_prob_species = species_data.filter(pl.col("top1_prob_weighted") > 0.3)

        # Calculate how many to sample from each
        total_sample = min(n_per_group_strata7, len(species_data))
        sample_low = min(total_sample // 2, len(low_prob_species))
        sample_high = min(total_sample - sample_low, len(high_prob_species))

        # Sample
        sampled_low = low_prob_species.sample(n=sample_low, seed=seed) if sample_low > 0 else None
        sampled_high = high_prob_species.sample(n=sample_high, seed=seed) if sample_high > 0 else None

        # Combine samples
        sampled_rows = []
        if sampled_low is not None:
            sampled_low = sampled_low.with_columns(pl.lit("low_prob").alias("strata7_prob"))
            sampled_rows.append(sampled_low)
        if sampled_high is not None:
            sampled_high = sampled_high.with_columns(pl.lit("high_prob").alias("strata7_prob"))
            sampled_rows.append(sampled_high)

        if not sampled_rows:
            logger.warning(f"No samples collected for {species}. Skipping output.")
            continue

        meta_strat7_final = pl.concat(sampled_rows, how="vertical")

        # Join with crop_path
        meta_strat7_crop = meta_strat7_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Generate short name: first 3 letters of genus + species
        # Extract genus and species from bioclip_species (e.g., "Apis mellifera" → "ape")
        parts = species.split()
        if len(parts) < 2:
            short_name = species[:3].lower()  # fallback
        else:
            genus = parts[0]
            species_name = parts[1]
            short_name = (genus[:2] + species_name[:1]).lower()  # e.g., "ape"

        # Save file
        filename = f"strata7_{short_name}_{timestamp}.csv"
        meta_strat7_crop.write_csv(strata7_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat7_crop)} samples)")

    # === Summary (updated) ===
    print(f"\n✅ Strata samples created!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - n_per_group_strata1: {n_per_group_strata1}")
    print(f"  - n_per_group_strata2: {n_per_group_strata2}")
    print(f"  - n_per_group_strata3: {n_per_group_strata3}")
    print(f"  - n_per_group_strata4: {n_per_group_strata4}")
    print(f"  - n_per_group_strata5/6: {n_per_group_strata3}")  # Reuse same value
    print(f"  - n_common_species_strata7: {n_common_species}")
    print(f"  - Total strata1 samples: {len(meta_strat1_crop)}")
    print(f"  - Total strata2 samples: {len(meta_strat2_crop)}")
    print(f"  - Strata1 file: {filename_strata1}")
    print(f"  - Strata2 file: {filename_strata2}")
    print(f"  - Strata3 files: strata3_hym_*.csv, strata3_lep_*.csv, strata3_col_*.csv, strata3_dip_*.csv")
    print(f"  - Strata4 file: {filename_strata4}")
    print(f"  - Strata5 files: strata5_hym_*.csv, strata5_lep_*.csv, strata5_col_*.csv, strata5_dip_*.csv")
    print(f"  - Strata6 files: strata6_hym_*.csv, strata6_lep_*.csv, strata6_col_*.csv, strata6_dip_*.csv")
    print(f"  - Strata7 files: strata7_*.csv (in subfolder: strata7_YYYY-MM-DD_HH-MM-SS)")


if __name__ == "__main__":
    main()