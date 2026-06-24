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
    "--n-per-group-strata5",
    type=int,
    default=10,
    help="Number of subsamples per genus for strata5 (default: 10)"
    )
    parser.add_argument(
        "--n-per-group-strata6",
        type=int,
        default=10,
        help="Number of subsamples per family for strata6 (default: 10)"
    )
    parser.add_argument(
        "--n-per-group-strata7",
        type=int,
        default=10,
        help="Number of subsamples per species for strata7 (default: 10)"
    )
    parser.add_argument(
        "--n-per-group-strata8",
        type=int,
        default=10,
        help="Number of subsamples per species for strata8 (default: 10)"
    )
    parser.add_argument(
        "--n-common-species-strata8",
        type=int,
        default=10,
        help="Number of top frequent species to subsample from in strata8 (default: 10)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=123,
        help="Random seed for reproducibility (default: 123)"
    )
    parser.add_argument(
    "--config",
    type=Path,
    help="Path to YAML config file (overrides CLI arguments if present)"
    )   

    args = parser.parse_args()
    n_per_group_strata5 = args.n_per_group_strata5
    n_per_group_strata6 = args.n_per_group_strata6

    # === Load config file if provided ===
    if args.config and args.config.exists():
        import yaml
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)

        # Override CLI args with config values (if present)
        for key, value in config.items():
            if hasattr(args, key) and value is not None:
                setattr(args, key, value)
        logger.info(f"Loaded configuration from: {args.config}")
    else:
        logger.info("No config file provided or file not found.")

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
        
    # === STRATA 4: Plant Species Stratification using median-based low/high prob per plant ===
        pollinator_active = meta_processed.filter(
            (pl.col("strata1") == "pollinator") &
            (pl.col("duration_s") > 0)
        )

        unique_plants = pollinator_active["plant_species"].unique()
        logger.info(f"Found {len(unique_plants)} unique plant species (pollinators with duration > 0s)")

        n_per_group_strata4 = args.n_per_group_strata4

        # Step 1: Compute median probability per plant species
        median_by_plant = pollinator_active.group_by("plant_species").agg(
            pl.col("top1_prob_weighted").median().alias("s4_median")
        )

        # Step 2: Join median back
        pollinator_active = pollinator_active.join(median_by_plant, on="plant_species", how="left")

        # Step 3: Create low/high prob labels per plant
        pollinator_active = pollinator_active.with_columns([
            pl.when(pl.col("top1_prob_weighted") < pl.col("s4_median"))
            .then(pl.lit("low_prob"))
            .otherwise(pl.lit("high_prob"))
            .alias("s4_prob_cat")
        ])

        # Step 4: Sample per plant
        strata4_samples = []

        for plant in unique_plants:
            logger.info(f"Processing strata4 for plant: {plant}")

            plant_data = pollinator_active.filter(pl.col("plant_species") == plant)

            if len(plant_data) == 0:
                logger.warning(f"No data found for plant: {plant}")
                continue

            # Split by median-based prob
            low_prob_plant = plant_data.filter(pl.col("s4_prob_cat") == "low_prob")
            high_prob_plant = plant_data.filter(pl.col("s4_prob_cat") == "high_prob")

            # Sample up to n_per_group_strata4/2 from each
            sample_high = min(n_per_group_strata4 // 2, len(high_prob_plant))
            sample_low = min(n_per_group_strata4 // 2, len(low_prob_plant))

            sampled_high = high_prob_plant.sample(n=sample_high, seed=seed)
            sampled_low = low_prob_plant.sample(n=sample_low, seed=seed)

            combined_sample = pl.concat([sampled_high, sampled_low], how="vertical")
            strata4_samples.append(combined_sample)

            logger.info(f"  - Plant {plant}: sampled {sample_high} high_prob, {sample_low} low_prob")

        # Combine and save
        meta_strat4_final = pl.concat(strata4_samples, how="vertical")
        meta_strat4_crop = meta_strat4_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        filename_strata4 = f"strata4_{timestamp}.csv"
        meta_strat4_crop.write_csv(output_dir / filename_strata4)
        logger.info(f"Saved strata4 (median-based per plant): {filename_strata4}")
   
    # === STRATA 5: N-samples per genus (low/high prob) using median per group ===
    n_per_group_strata5 = args.n_per_group_strata5

    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Define group column and sample count
    group_col = "bioclip_genus"
    strata_name = "strata5"
    median_col = "s5_median"
    prob_col = "s5_prob_cat"

    # Filter duration > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Process each order
    for order in target_orders:
        logger.info(f"Processing {strata_name} for {order} (duration_s > 0, {n_per_group_strata5} samples per group)...")

        order_data = duration_filtered.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data for {order} with duration_s > 0. Skipping.")
            continue

        # Compute median per group (genus)
        median_by_group = order_data.group_by(group_col).agg(
            pl.col("top1_prob_weighted").median().alias(median_col)
        )

        # Join back
        order_data = order_data.join(median_by_group, on=group_col, how="left")

        # Create low/high prob labels
        order_data = order_data.with_columns([
            pl.when(pl.col("top1_prob_weighted") < pl.col(median_col))
            .then(pl.lit("low_prob"))
            .otherwise(pl.lit("high_prob"))
            .alias(prob_col)
        ])

        # Get unique groups
        unique_groups = order_data[group_col].unique()

        sampled_rows = []

        for group in unique_groups:
            group_data = order_data.filter(pl.col(group_col) == group)

            if len(group_data) == 0:
                continue

            low_prob = group_data.filter(pl.col(prob_col) == "low_prob")
            high_prob = group_data.filter(pl.col(prob_col) == "high_prob")

            # Sample up to n_per_group_strata5 from each group
            sample_low = min(n_per_group_strata5, len(low_prob))
            sample_high = min(n_per_group_strata5, len(high_prob))

            sampled_low = low_prob.sample(n=sample_low, seed=seed) if sample_low > 0 else None
            sampled_high = high_prob.sample(n=sample_high, seed=seed) if sample_high > 0 else None

            if sampled_low is not None:
                sampled_low = sampled_low.with_columns(pl.lit("low_prob").alias(prob_col))
                sampled_rows.append(sampled_low)
            if sampled_high is not None:
                sampled_high = sampled_high.with_columns(pl.lit("high_prob").alias(prob_col))
                sampled_rows.append(sampled_high)

        if not sampled_rows:
            logger.warning(f"No samples for {order} (after filtering). Skipping.")
            continue

        meta_strat_final = pl.concat(sampled_rows, how="vertical")
        meta_strat_crop = meta_strat_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        short_name = order_short[order]
        filename = f"{strata_name}_{short_name}_{timestamp}.csv"
        meta_strat_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat_crop)} samples)")

   # === STRATA 6: N-samples per family (low/high prob) using median per group ===
    n_per_group_strata6 = args.n_per_group_strata6

    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Define group column and sample count
    group_col = "bioclip_family"
    strata_name = "strata6"
    median_col = "s6_median"
    prob_col = "s6_prob_cat"

    # Filter duration > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Process each order
    for order in target_orders:
        logger.info(f"Processing {strata_name} for {order} (duration_s > 0, {n_per_group_strata6} samples per group)...")

        order_data = duration_filtered.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data for {order} with duration_s > 0. Skipping.")
            continue

        # Compute median per group (family)
        median_by_group = order_data.group_by(group_col).agg(
            pl.col("top1_prob_weighted").median().alias(median_col)
        )

        # Join back
        order_data = order_data.join(median_by_group, on=group_col, how="left")

        # Create low/high prob labels
        order_data = order_data.with_columns([
            pl.when(pl.col("top1_prob_weighted") < pl.col(median_col))
            .then(pl.lit("low_prob"))
            .otherwise(pl.lit("high_prob"))
            .alias(prob_col)
        ])

        # Get unique groups
        unique_groups = order_data[group_col].unique()

        sampled_rows = []

        for group in unique_groups:
            group_data = order_data.filter(pl.col(group_col) == group)

            if len(group_data) == 0:
                continue

            low_prob = group_data.filter(pl.col(prob_col) == "low_prob")
            high_prob = group_data.filter(pl.col(prob_col) == "high_prob")

            # Sample up to n_per_group_strata6 from each group
            sample_low = min(n_per_group_strata6, len(low_prob))
            sample_high = min(n_per_group_strata6, len(high_prob))

            sampled_low = low_prob.sample(n=sample_low, seed=seed) if sample_low > 0 else None
            sampled_high = high_prob.sample(n=sample_high, seed=seed) if sample_high > 0 else None

            if sampled_low is not None:
                sampled_low = sampled_low.with_columns(pl.lit("low_prob").alias(prob_col))
                sampled_rows.append(sampled_low)
            if sampled_high is not None:
                sampled_high = sampled_high.with_columns(pl.lit("high_prob").alias(prob_col))
                sampled_rows.append(sampled_high)

        if not sampled_rows:
            logger.warning(f"No samples for {order} (after filtering). Skipping.")
            continue

        meta_strat_final = pl.concat(sampled_rows, how="vertical")
        meta_strat_crop = meta_strat_final.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        short_name = order_short[order]
        filename = f"{strata_name}_{short_name}_{timestamp}.csv"
        meta_strat_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat_crop)} samples)")

    # =# === STRATA 7: N-samples per order (low/high prob) using median per group ===
    # Use n_per_group_strata7 from args
    n_per_group_strata7 = args.n_per_group_strata7

    target_orders = ["Hymenoptera", "Lepidoptera", "Coleoptera", "Diptera"]
    order_short = {
        "Hymenoptera": "hym",
        "Lepidoptera": "lep",
        "Coleoptera": "col",
        "Diptera": "dip"
    }

    # Filter duration > 0
    duration_filtered = meta_processed.filter(pl.col("duration_s") > 0)

    # Process each order
    for order in target_orders:
        logger.info(f"Processing strata7 for {order} (duration_s > 0, {n_per_group_strata7} samples per group)...")

        order_data = duration_filtered.filter(pl.col("bioclip_order") == order)

        if len(order_data) == 0:
            logger.warning(f"No data for {order} with duration_s > 0. Skipping.")
            continue

        # Compute median per group (order)
        median_by_order = order_data.group_by("bioclip_order").agg(
            pl.col("top1_prob_weighted").median().alias("s7_median")
        )

        # Join back
        order_data = order_data.join(median_by_order, on="bioclip_order", how="left")

        # Create low/high prob labels
        order_data = order_data.with_columns([
            pl.when(pl.col("top1_prob_weighted") < pl.col("s7_median"))
            .then(pl.lit("low_prob"))
            .otherwise(pl.lit("high_prob"))
            .alias("s7_prob_cat")
        ])

        # Split into low and high prob
        low_prob_data = order_data.filter(pl.col("s7_prob_cat") == "low_prob")
        high_prob_data = order_data.filter(pl.col("s7_prob_cat") == "high_prob")

        # Sample up to n_per_group_strata7 from each group
        sample_low = min(n_per_group_strata7, len(low_prob_data))
        sample_high = min(n_per_group_strata7, len(high_prob_data))

        sampled_low = low_prob_data.sample(n=sample_low, seed=seed)
        sampled_high = high_prob_data.sample(n=sample_high, seed=seed)

        # Combine
        sampled = pl.concat([sampled_low, sampled_high], how="vertical")

        # Join with crop_path
        meta_strat7_crop = sampled.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Save file
        short_name = order_short[order]
        filename = f"strata7_{short_name}_{timestamp}.csv"
        meta_strat7_crop.write_csv(output_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat7_crop)} samples)")
        
    # === STRATA 8: Top N most frequent species, subsample using median-based low/high prob per species ===
    # Extract parameters
    n_common_species = args.n_common_species_strata8
    n_per_group_strata8 = args.n_per_group_strata8  # Now used correctly

    # Ensure bioclip_species exists
    if "bioclip_species" not in meta_processed.columns:
        logger.error("bioclip_species column not found. Cannot create strata8.")
        return

    # Define pollinator orders
    pollinator_orders = ["Lepidoptera", "Hymenoptera", "Diptera", "Coleoptera"]

    # Filter to only include rows where bioclip_order is in pollinator_orders AND duration_s > 0
    pollinator_filtered = meta_processed.filter(
        (pl.col("bioclip_order").is_in(pollinator_orders)) &
        (pl.col("duration_s") > 0)
    )

    # Count frequency of each species
    species_counts = pollinator_filtered.group_by("bioclip_species").agg(
        pl.count().alias("count")
    ).sort("count", descending=True)

    # Get top N most frequent species
    top_species = species_counts.head(n_common_species)["bioclip_species"].to_list()
    logger.info(f"Selected top {len(top_species)} most frequent pollinator species: {top_species}")

    # Create output subfolder for strata8
    strata8_dir = output_dir / f"strata8_{timestamp}"
    strata8_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created strata8 output directory: {strata8_dir}")

    # Compute median per species
    median_by_species = pollinator_filtered.group_by("bioclip_species").agg(
        pl.col("top1_prob_weighted").median().alias("s8_median")
    )

    # Join back
    pollinator_filtered = pollinator_filtered.join(median_by_species, on="bioclip_species", how="left")

    # Create low/high prob labels using median per species
    pollinator_filtered = pollinator_filtered.with_columns([
        pl.when(pl.col("top1_prob_weighted") < pl.col("s8_median"))
        .then(pl.lit("low_prob"))
        .otherwise(pl.lit("high_prob"))
        .alias("s8_prob_cat")
    ])

    # Loop over each selected species
    for species in top_species:
        logger.info(f"Processing strata8 for species: {species}")

        species_data = pollinator_filtered.filter(pl.col("bioclip_species") == species)

        if len(species_data) == 0:
            logger.warning(f"No data found for species: {species}. Skipping.")
            continue

        # Split by median-based prob
        low_prob_data = species_data.filter(pl.col("s8_prob_cat") == "low_prob")
        high_prob_data = species_data.filter(pl.col("s8_prob_cat") == "high_prob")

        # Sample up to n_per_group_strata8 from each group
        sample_low = min(n_per_group_strata8, len(low_prob_data))
        sample_high = min(n_per_group_strata8, len(high_prob_data))

        sampled_low = low_prob_data.sample(n=sample_low, seed=seed)
        sampled_high = high_prob_data.sample(n=sample_high, seed=seed)

        # Combine
        sampled = pl.concat([sampled_low, sampled_high], how="vertical")

        # Join with crop_path
        meta_strat8_crop = sampled.join(
            meta_sliced.select(["cam_ID", "rec_ID", "track_ID", "crop_path"]),
            on=["cam_ID", "rec_ID", "track_ID"],
            how="left"
        )

        # Generate short name: first 3 chars of genus + "_" + first 3 chars after space
        parts = species.split(maxsplit=1)
        if len(parts) < 2:
            short_name = species[:3].lower()
        else:
            genus_part = parts[0]
            species_part = parts[1]
            short_name = f"{genus_part[:3].lower()}_{species_part[:3].lower()}"

        # Save file
        filename = f"strata8_{short_name}_{timestamp}.csv"
        meta_strat8_crop.write_csv(strata8_dir / filename)
        logger.info(f"Saved {filename} ({len(meta_strat8_crop)} samples)")

   
# === Summary (updated) ===
    print(f"\n✅ Strata samples created!")
    print(f"  - Output directory: {output_dir}")
    print(f"  - Seed: {seed}")
    print(f"  - Strata1: N/group: {n_per_group_strata1}, total samples: {len(meta_strat1_crop)}, filename: {filename_strata1}")
    print(f"  - Strata2: N/group: {n_per_group_strata2}, total samples: {len(meta_strat2_crop)}, filename: {filename_strata2}")
    print(f"  - Strata3: N/group: {n_per_group_strata3}, files: strata3_hym_*.csv, strata3_lep_*.csv, strata3_col_*.csv, strata3_dip_*.csv")
    print(f"  - Strata4: N/group: {n_per_group_strata4}, total samples: {len(meta_strat4_crop)}, filename: {filename_strata4}")
    print(f"  - Strata5: N/group: {n_per_group_strata5}, files: strata5_hym_*.csv, strata5_lep_*.csv, strata5_col_*.csv, strata5_dip_*.csv")
    print(f"  - Strata6: N/group: {n_per_group_strata6},  files: strata6_hym_*.csv, strata6_lep_*.csv, strata6_col_*.csv, strata6_dip_*.csv")
    print(f"  - Strata7: N/group: {n_per_group_strata7}, files: strata7_hym_*.csv, strata7_lep_*.csv, strata7_col_*.csv, strata7_dip_*.csv")
    print(f"  - Strata8: N-Top species: {n_common_species}, N/group: {n_per_group_strata8}, foldername: strata8_YYYY-MM-DD_HH-MM-SS)")
  

if __name__ == "__main__":
    main()