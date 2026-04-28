from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Callable, Optional, Union
from datetime import datetime
import re

import argparse
import yaml
import polars as pl
import matplotlib.pyplot as plt
import pandas as pd

# Create module-level logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# === Expression Parsing Helper ===
def parse_expression(expr: str) -> tuple[str, float]:
    """
    Parse expression like '>0.5', '<=0.8', '==0.7', '>=0.6', '<0.4'
    Supports optional spaces and quotes.
    Returns: (operator, value)
    """
    # Remove quotes and strip whitespace
    expr = expr.strip().strip('"\'')
    
    # Pattern: (operator) + (number with optional decimal)
    pattern = r"^([<>]=?|==|!=)\s*(\d+(\.\d+)?)$"
    match = re.match(pattern, expr)
    if not match:
        raise ValueError(
            f"Invalid expression format: '{expr}'. "
            "Use e.g., '>0.5', '<=0.8', '==0.7', '>=0.6', '<0.4'"
        )
    op, value_str = match.groups()[:2]  # Take only first two groups
    value = float(value_str)
    return op, value


def apply_filter(df: pl.DataFrame, column: str, op: str, value: float) -> pl.DataFrame:
    """Apply filter based on operator and value."""
    if op == ">":
        return df.filter(pl.col(column) > value)
    elif op == ">=":
        return df.filter(pl.col(column) >= value)
    elif op == "<":
        return df.filter(pl.col(column) < value)
    elif op == "<=":
        return df.filter(pl.col(column) <= value)
    elif op == "==":
        return df.filter(pl.col(column) == value)
    elif op == "!=":
        return df.filter(pl.col(column) != value)
    else:
        raise ValueError(f"Unsupported operator: {op}")


# === Config Loading ===
def load_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config {config_path}: {e}")
        return {}


# === Run Directory Creation ===
def create_run_directory(base_output_dir: Path) -> Path:
    """Create a new run directory with timestamped name: run_YYYY-MM-DD_hh-mm-ss"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = base_output_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created run directory: {run_dir}")
    return run_dir


# === Plot Generation: Taxonomic order distribution of pollinators and non-pollinators ===
def create_pollinator_plot(df: pl.DataFrame, output_dir: Path, title: str = "Pollinator vs Non-Pollinator Detection Count"):
    """
    Create a stacked bar chart of pollinator vs non-pollinator detections.
    Pollinator orders: Hymenoptera, Diptera, Lepidoptera, Coleoptera (stacked)
    Non-pollinators: all other orders (single gray bar)
    """
    pollinator_orders = {"Hymenoptera", "Diptera", "Lepidoptera", "Coleoptera"}

    # Ensure bioclip_order is string
    df = df.with_columns(pl.col("bioclip_order").cast(pl.Utf8))

    # Create order_class column
    df = df.with_columns([
        pl.when(pl.col("bioclip_order").is_in(pollinator_orders))
        .then(pl.lit("pollinator"))
        .otherwise(pl.lit("non-pollinator"))
        .alias("order_class")
    ])

    # Count by order_class and bioclip_order
    counts = (
        df
        .group_by(["order_class", "bioclip_order"])
        .agg(pl.len().alias("count"))
        .to_pandas()
    )

    # Separate pollinator and non-pollinator data
    pollinator_data = counts[counts["order_class"] == "pollinator"]
    non_pollinator_data = counts[counts["order_class"] == "non-pollinator"]

    # Define colors for pollinator orders
    color_map = {
        "Hymenoptera": "#4CAF50",   # Green
        "Diptera": "#2196F3",       # Blue
        "Lepidoptera": "#FF9800",   # Orange
        "Coleoptera": "#9C27B0",    # Purple
    }

    # Sort pollinator orders for consistent plotting
    order_order = ["Hymenoptera", "Diptera", "Lepidoptera", "Coleoptera"]

    # Prepare data for stacked bar
    pollinator_counts = []
    for order in order_order:
        count = pollinator_data[pollinator_data["bioclip_order"] == order]["count"].sum()
        pollinator_counts.append(count)

    # Non-pollinator count
    non_pollinator_count = non_pollinator_data["count"].sum()

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot stacked bar for pollinators
    bottom = 0
    for i, order in enumerate(order_order):
        count = pollinator_counts[i]
        if count > 0:
            ax.bar(
                "Pollinators",
                count,
                bottom=bottom,
                color=color_map[order],
                edgecolor="black",
                linewidth=0.5,
                label=order
            )
            # Add label on top
            ax.text(
                0, bottom + count / 2, f"{count}", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white"
            )
            bottom += count

    # Plot non-pollinator bar
    ax.bar(
        "Non-Pollinators",
        non_pollinator_count,
        color="#9E9E9E",  # Gray
        edgecolor="black",
        linewidth=0.5,
        label="Other Orders"
    )
    if non_pollinator_count > 0:
        ax.text(
            1, non_pollinator_count / 2, f"{non_pollinator_count}", ha="center", va="center",
            fontsize=10, fontweight="bold", color="white"
        )

    # Customize plot
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_ylabel("Number of Detections", fontsize=12)
    ax.set_xlabel("Order Category", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(0, bottom + non_pollinator_count + 10)

    # Add legend on the right side
    handles, labels = ax.get_legend_handles_labels()
    # Sort legend by order
    order_map = {"Hymenoptera": 0, "Diptera": 1, "Lepidoptera": 2, "Coleoptera": 3, "Other Orders": 4}
    sorted_handles_labels = sorted(zip(handles, labels), key=lambda x: order_map.get(x[1], 5))
    handles, labels = zip(*sorted_handles_labels)

    ax.legend(handles, labels, loc="upper right", bbox_to_anchor=(1.15, 1), frameon=True, fancybox=True, shadow=True)

    plt.tight_layout()

    # Save to plots/ subfolder
    plot_path = output_dir / "plots" / "pollinator_stacked_distribution.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)  # Create plots/ folder
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"Stacked plot saved to {plot_path}")

# === Plot Generation: Duration Distribution for Pollinators ===
def create_duration_distribution_plot(df: pl.DataFrame, output_dir: Path, title: str = "Duration Distribution of Pollinator Detections"):
    """
    Create a bar chart showing the number of pollinator detections in each duration bin.
    Bins: 0, >0-10, >10-100, >100-500, >500
    Only includes rows where order_category == 'pollinator'
    Bars are all gray, and bins are in increasing duration order.
    """
    # Filter for pollinator detections only
    pollinator_df = df.filter(pl.col("order_category") == "pollinator")

    # Define bins and labels in increasing duration order
    bins = [0, 10, 100, 500, float('inf')]
    labels = ["0", ">0-10", ">10-100", ">100-500", ">500"]

    # Create duration bins using pl.when().then().otherwise()
    pollinator_df = pollinator_df.with_columns([
        pl.when(pl.col("duration_s") == 0)
        .then(pl.lit("0"))
        .when(pl.col("duration_s") > 0)
        .then(
            pl.when(pl.col("duration_s") <= 10)
            .then(pl.lit(">0-10"))
            .when(pl.col("duration_s") <= 100)
            .then(pl.lit(">10-100"))
            .when(pl.col("duration_s") <= 500)
            .then(pl.lit(">100-500"))
            .otherwise(pl.lit(">500"))
        )
        .alias("duration_bin")
    ])

    # Count by bin
    counts = (
        pollinator_df
        .group_by("duration_bin")
        .agg(pl.len().alias("count"))
        .to_pandas()
    )

    # Define single color (gray)
    color = "#9E9E9E"  # Gray

    # === Fix: Explicitly set the order of categories ===
    # Define the desired order
    desired_order = ["0", ">0-10", ">10-100", ">100-500", ">500"]

    # Reorder the DataFrame
    counts["duration_bin"] = pd.Categorical(counts["duration_bin"], categories=desired_order, ordered=True)
    counts = counts.sort_values("duration_bin")

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot bars (all gray)
    bars = ax.bar(
        counts["duration_bin"],
        counts["count"],
        color=color,
        edgecolor="black",
        linewidth=0.5
    )

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                    f"{height:.0f}", ha='center', va='bottom', fontsize=10)

    # Customize plot
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_ylabel("Number of Detections", fontsize=12)
    ax.set_xlabel("Duration (seconds)", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # Set y-axis to be proportional to data
    max_count = counts["count"].max()
    ax.set_ylim(0, max_count * 1.1)

    # Adjust layout to prevent clipping
    plt.tight_layout(rect=[0, 0, 0.85, 1])  # Leave space for legend

    # Save to plots/ subfolder
    plot_path = output_dir / "plots" / "pollinator_duration_distribution.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)  # Create plots/ folder
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"Duration distribution plot saved to {plot_path}")

# === Plot Generation: Facetted Histogram of top1_prob_weighted ===
def create_facetted_probability_histogram(df: pl.DataFrame, output_dir: Path, title: str = "Distribution of top1_prob_weighted by Pollinator Order"):
    """
    Create a facetted histogram showing the distribution of top1_prob_weighted
    for each pollinator order (Hymenoptera, Diptera, Lepidoptera, Coleoptera).
    Each subplot is a histogram with smooth density.
    """
    # Filter for pollinator detections only
    pollinator_df = df.filter(pl.col("order_category") == "pollinator")

    # Define the 4 pollinator orders
    orders = ["Hymenoptera", "Diptera", "Lepidoptera", "Coleoptera"]

    # Define colors for each order
    color_map = {
        "Hymenoptera": "#4CAF50",   # Green
        "Diptera": "#2196F3",       # Blue
        "Lepidoptera": "#FF9800",   # Orange
        "Coleoptera": "#9C27B0",    # Purple
    }

    # Create a 2x2 grid of subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
    axes = axes.flatten()

    # Plot each order
    for i, order in enumerate(orders):
        order_data = pollinator_df.filter(pl.col("bioclip_order") == order)
        if order_data.is_empty():
            continue

        # Convert to pandas and extract top1_prob_weighted
        prob_data = order_data.select("top1_prob_weighted").to_pandas()["top1_prob_weighted"]

        # Clean data
        prob_data = prob_data.dropna().clip(0.0, 1.0)

        # Plot histogram
        axes[i].hist(
            prob_data,
            bins=20,  # Smooth histogram with 20 bins
            color=color_map[order],
            edgecolor="black",
            linewidth=0.5,
            alpha=0.8
        )

        # Customize subplot
        axes[i].set_title(f"{order}", fontsize=12, fontweight="bold")
        axes[i].set_ylabel("Number of Detections", fontsize=10)
        axes[i].set_xlabel("top1_prob_weighted", fontsize=10)
        axes[i].grid(axis="y", alpha=0.3, linestyle="--")

    # Adjust layout
    plt.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 0.95, 0.95])  # Leave space for title

    # Save to plots/ subfolder
    plot_path = output_dir / "plots" / "pollinator_probability_facetted_histogram.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)  # Create plots/ folder
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"Facetted histogram saved to {plot_path}")

# === Plot Generation: Facetted Histogram of det_conf_mean ===
def create_facetted_confidence_histogram(df: pl.DataFrame, output_dir: Path, title: str = "Distribution of det_conf_mean by Pollinator Order"):
    """
    Create a facetted histogram showing the distribution of det_conf_mean
    for each pollinator order (Hymenoptera, Diptera, Lepidoptera, Coleoptera).
    Each subplot is a histogram with smooth density.
    """
    # Filter for pollinator detections only
    pollinator_df = df.filter(pl.col("order_category") == "pollinator")

    # Define the 4 pollinator orders
    orders = ["Hymenoptera", "Diptera", "Lepidoptera", "Coleoptera"]

    # Define colors for each order
    color_map = {
        "Hymenoptera": "#4CAF50",   # Green
        "Diptera": "#2196F3",       # Blue
        "Lepidoptera": "#FF9800",   # Orange
        "Coleoptera": "#9C27B0",    # Purple
    }

    # Create a 2x2 grid of subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
    axes = axes.flatten()

    # Plot each order
    for i, order in enumerate(orders):
        order_data = pollinator_df.filter(pl.col("bioclip_order") == order)
        if order_data.is_empty():
            continue

        # Convert to pandas and extract det_conf_mean
        conf_data = order_data.select("det_conf_mean").to_pandas()["det_conf_mean"]

        # Clean data
        conf_data = conf_data.dropna().clip(0.0, 1.0)

        # Plot histogram
        axes[i].hist(
            conf_data,
            bins=20,  # Smooth histogram with 20 bins
            color=color_map[order],
            edgecolor="black",
            linewidth=0.5,
            alpha=0.8
        )

        # Customize subplot
        axes[i].set_title(f"{order}", fontsize=12, fontweight="bold")
        axes[i].set_ylabel("Number of Detections", fontsize=10)
        axes[i].set_xlabel("det_conf_mean", fontsize=10)
        axes[i].grid(axis="y", alpha=0.3, linestyle="--")

    # Adjust layout
    plt.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 0.95, 0.95])  # Leave space for title

    # Save to plots/ subfolder
    plot_path = output_dir / "plots" / "pollinator_confidence_facetted_histogram.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)  # Create plots/ folder
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"Facetted confidence histogram saved to {plot_path}")

# === Main Processing Function ===
def process_metadata_classified(
    metadata_path: Path,
    output_dir: Path,
    frame_width: float = 1.0,
    frame_height: float = 1.0,
    min_conf: Optional[Union[float, str]] = None,
    max_conf: Optional[Union[float, str]] = None,
    min_duration: Optional[Union[float, str]] = None,
    max_duration: Optional[Union[float, str]] = None,
    min_prob: Optional[Union[float, str]] = None,
    max_prob: Optional[Union[float, str]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Path]:
    """Process classified metadata with filtering and size estimation.

    Supports both Ultralytics (top1/top1_prob) and BioCLIP (taxonomic hierarchy) formats.
    BioCLIP results include additional taxonomy columns while maintaining standard format.

    Args:
        metadata_path: Path to classified metadata CSV
        output_dir: Base output directory (will create timestamped run subfolder)
        frame_width: Physical frame width (mm)
        frame_height: Physical frame height (mm)
        min_conf: Minimum detection confidence (e.g., 0.5 or '>0.3')
        max_conf: Maximum detection confidence (e.g., '<0.9' or 0.9)
        min_duration: Minimum track duration (seconds) (e.g., 2.0 or '>1.0')
        max_duration: Maximum track duration (seconds) (e.g., 30.0 or '<60.0')
        min_prob: Minimum classification probability (weighted) (e.g., 0.6 or '>=0.5')
        max_prob: Maximum classification probability (e.g., '<0.9' or 0.9)
        progress_callback: Optional callback(current, total, message) for progress updates

    Returns:
        dict with output paths and filtering statistics

    Raises:
        RuntimeError: If cancelled by user (with message "CANCELLED_BY_USER")
        ValueError: If no classification columns found or invalid expression
    """
    # Create a timestamped run directory
    run_dir = create_run_directory(output_dir)

    if progress_callback:
        progress_callback(0, 100, "Loading metadata...")

    # Read and prepare data
    df = pl.read_csv(metadata_path)

    # Auto-detect classification results format
    if "top1" in df.columns and "top1_prob" in df.columns:
        classifier_type = "ultralytics"
        bioclip_columns = []
        logger.info("Detected Ultralytics classification format")
    elif "bioclip_score" in df.columns:
        classifier_type = "bioclip"
        bioclip_columns = [col for col in ["bioclip_species", "bioclip_genus", "bioclip_family",
                                           "bioclip_order", "bioclip_class"] if col in df.columns]
        if not bioclip_columns:
            raise ValueError("BioCLIP format detected but no taxonomic rank columns found")

        df = df.with_columns([
            pl.coalesce([pl.col(col) for col in bioclip_columns]).alias("top1"),
            pl.col("bioclip_score").alias("top1_prob")
        ])

        logger.info("Detected BioCLIP classification format (preserving taxonomic hierarchy)")
    else:
        raise ValueError(
            "No required classification columns found ('top1'/'top1_prob' or 'bioclip_score')."
        )

    if progress_callback:
        progress_callback(10, 100, "Converting timestamps...")

    # Convert timestamp to proper datetime if needed
    if df["timestamp"].dtype != pl.Datetime:
        original_count = len(df)
        df = (
            df
            .with_columns(
                pl.col("timestamp")
                .str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%.f", strict=False)
            )
            .filter(pl.col("timestamp").is_not_null())
        )
        parsed_count = len(df)
        invalid_count = original_count - parsed_count
        if invalid_count > 0:
            logger.warning(
                "Removed %d of %d rows with unparseable timestamps", invalid_count, original_count
            )

    if progress_callback:
        progress_callback(20, 100, "Filtering detections...")

    # Filter detections by confidence (min/max)
    detections_removed = 0
    if min_conf is not None or max_conf is not None:
        detections_before = len(df)
        if min_conf is not None:
            if isinstance(min_conf, str):
                op, val = parse_expression(min_conf)
                df = apply_filter(df, "confidence", op, val)
            else:
                df = df.filter(pl.col("confidence") >= min_conf)
        if max_conf is not None:
            if isinstance(max_conf, str):
                op, val = parse_expression(max_conf)
                df = apply_filter(df, "confidence", op, val)
            else:
                df = df.filter(pl.col("confidence") <= max_conf)
        detections_removed = detections_before - len(df)

    if progress_callback:
        progress_callback(25, 100, "Calculating bbox metrics...")

    # Calculate bbox metrics
    df = (
        df.with_columns([
            ((pl.col("x_max") - pl.col("x_min")) * frame_width).round(4).alias("bbox_size_x"),
            ((pl.col("y_max") - pl.col("y_min")) * frame_height).round(4).alias("bbox_size_y"),
        ])
        .with_columns([
            pl.max_horizontal("bbox_size_x", "bbox_size_y").alias("bbox_length"),
            pl.min_horizontal("bbox_size_x", "bbox_size_y").alias("bbox_width"),
        ])
    )

    if progress_callback:
        progress_callback(30, 100, "Computing track aggregates...")

    # Track-level aggregates
    agg_track = (
        df.group_by(["cam_ID", "rec_ID", "track_ID"])
        .agg([
            pl.len().alias("track_ID_imgs"),
            pl.min("timestamp").alias("start_time"),
            pl.max("timestamp").alias("end_time"),
            pl.mean("confidence").round(2).alias("det_conf_mean"),
            pl.mean("bbox_length").round(3).alias("bbox_length_mean"),
            pl.mean("bbox_width").round(3).alias("bbox_width_mean")
        ])
        .with_columns([
            (pl.col("end_time") - pl.col("start_time"))
            .dt.total_seconds()
            .round(2)
            .alias("duration_s")
        ])
    )

    if progress_callback:
        progress_callback(50, 100, "Computing classification aggregates...")

    # Classification aggregates with weighted probability
    df_top1_all = (
        df.group_by(["cam_ID", "rec_ID", "track_ID", "top1"])
        .agg([
            pl.len().alias("top1_imgs"),
            pl.mean("top1_prob").round(2).alias("top1_prob_mean")
        ])
        .join(
            agg_track.select(["cam_ID", "rec_ID", "track_ID", "track_ID_imgs"]),
            on=["cam_ID", "rec_ID", "track_ID"]
        )
        .with_columns([
            (pl.col("top1_prob_mean") * (pl.col("top1_imgs") / pl.col("track_ID_imgs")))
            .round(2)
            .alias("top1_prob_weighted")
        ])
    )

    if classifier_type == "bioclip":
        # Re-attach taxonomic hierarchy columns
        taxonomy_map = (
            df.select(["cam_ID", "rec_ID", "track_ID", "top1"] + bioclip_columns)
            .unique(subset=["cam_ID", "rec_ID", "track_ID", "top1"], keep="first")
        )
        df_top1_all = df_top1_all.join(
            taxonomy_map,
            on=["cam_ID", "rec_ID", "track_ID", "top1"],
            how="left"
        )

    # Sort classifications per track by weighted and mean probabilities
    df_top1_all = df_top1_all.sort(
        by=["cam_ID", "rec_ID", "track_ID", "top1_prob_weighted", "top1_prob_mean"],
        descending=[False, False, False, True, True]
    )

    if progress_callback:
        progress_callback(70, 100, "Selecting best classifications...")

    # Get best classification per track
    df_top1_final = (
        df_top1_all
        .group_by(["cam_ID", "rec_ID", "track_ID"])
        .first()
        .join(agg_track, on=["cam_ID", "rec_ID", "track_ID"])
    )

    if progress_callback:
        progress_callback(80, 100, "Filtering tracks and classifications...")

    # Apply duration filtering (min/max)
    tracks_removed = 0
    if min_duration is not None or max_duration is not None:
        tracks_before = len(df_top1_final)
        if min_duration is not None:
            if isinstance(min_duration, str):
                op, val = parse_expression(min_duration)
                df_top1_final = apply_filter(df_top1_final, "duration_s", op, val)
            else:
                df_top1_final = df_top1_final.filter(pl.col("duration_s") >= min_duration)
        if max_duration is not None:
            if isinstance(max_duration, str):
                op, val = parse_expression(max_duration)
                df_top1_final = apply_filter(df_top1_final, "duration_s", op, val)
            else:
                df_top1_final = df_top1_final.filter(pl.col("duration_s") <= max_duration)
        tracks_removed = tracks_before - len(df_top1_final)

    # Apply classification probability filtering (min/max)
    classifications_removed = 0
    if min_prob is not None or max_prob is not None:
        classifications_before = len(df_top1_final)
        if min_prob is not None:
            if isinstance(min_prob, str):
                op, val = parse_expression(min_prob)
                df_top1_final = apply_filter(df_top1_final, "top1_prob_weighted", op, val)
            else:
                df_top1_final = df_top1_final.filter(pl.col("top1_prob_weighted") >= min_prob)
        if max_prob is not None:
            if isinstance(max_prob, str):
                op, val = parse_expression(max_prob)
                df_top1_final = apply_filter(df_top1_final, "top1_prob_weighted", op, val)
            else:
                df_top1_final = df_top1_final.filter(pl.col("top1_prob_weighted") <= max_prob)
        classifications_removed = classifications_before - len(df_top1_final)

    if progress_callback:
        progress_callback(90, 100, "Finalizing results...")

    # Sort the final result
    df_top1_final = df_top1_final.sort(["cam_ID", "rec_ID", "track_ID"])

    # === Add order_category column to both dataframes ===
    pollinator_orders = {"Hymenoptera", "Diptera", "Lepidoptera", "Coleoptera"}

    # Add to df_top1_all
    df_top1_all = df_top1_all.with_columns([
        pl.when(pl.col("bioclip_order").is_in(pollinator_orders))
        .then(pl.lit("pollinator"))
        .otherwise(pl.lit("non-pollinator"))
        .alias("order_category")
    ])

    # Add to df_top1_final
    df_top1_final = df_top1_final.with_columns([
        pl.when(pl.col("bioclip_order").is_in(pollinator_orders))
        .then(pl.lit("pollinator"))
        .otherwise(pl.lit("non-pollinator"))
        .alias("order_category")
    ])

    # Final column selection
    main_columns = [
        "cam_ID", "rec_ID", "track_ID",
        "track_ID_imgs", "top1_imgs",
        "top1", "top1_prob_mean", "top1_prob_weighted"
    ]

    track_level_columns = [
        "start_time", "end_time", "duration_s",
        "det_conf_mean", "bbox_length_mean", "bbox_width_mean"
    ]

    if classifier_type == "bioclip":
        main_columns.extend(bioclip_columns)

    # Add order_category to final columns
    final_columns = main_columns + track_level_columns + ["order_category"]

    # Now both dataframes have order_category
    df_top1_all = df_top1_all.select(main_columns + ["order_category"])
    df_top1_final = df_top1_final.select(final_columns)

    if progress_callback:
        progress_callback(95, 100, "Saving results...")

    # Save CSVs in the run directory
    df_top1_all.write_csv(run_dir / f"{metadata_path.stem}_top1_all.csv")
    df_top1_final.write_csv(run_dir / f"{metadata_path.stem}_top1_final.csv")

    if progress_callback:
        progress_callback(100, 100, "Metadata processing complete")

    # Save config for reproducibility
    config_save_path = run_dir / "config.yaml"
    config = {
        "metadata_path": str(metadata_path),
        "output_dir": str(run_dir),
        "frame_width": frame_width,
        "frame_height": frame_height,
        "min_conf": min_conf,
        "max_conf": max_conf,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "min_prob": min_prob,
        "max_prob": max_prob,
    }
    with open(config_save_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Configuration saved to {config_save_path}")

    # === Generate Plots ===
    try:
        create_pollinator_plot(df_top1_final, run_dir, title="Pollinator vs Non-Pollinator Detection Count (Filtered)")
        create_duration_distribution_plot(df_top1_final, run_dir, title="Duration Distribution of Pollinator Detections")
        create_facetted_probability_histogram(df_top1_final, run_dir, title="Distribution of top1_prob_weighted by Pollinator Order")
        create_facetted_confidence_histogram(df_top1_final, run_dir, title="Distribution of det_conf_mean by Pollinator Order")
    except Exception as e:
        logger.error(f"Failed to generate plots: {e}")
        raise

    return {
        "df_top1_all": run_dir / f"{metadata_path.stem}_top1_all.csv",
        "df_top1_final": run_dir / f"{metadata_path.stem}_top1_final.csv",
        "out_dir": run_dir,
        "detections_removed": detections_removed,
        "tracks_removed": tracks_removed,
        "classifications_removed": classifications_removed,
    }


# === Main CLI Entry Point ===
def main():
    parser = argparse.ArgumentParser(
        description="Process classified metadata with configurable thresholds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process_metadata.py data/results.csv outputs/ --min-conf 0.5 --max-duration 30.0
  python process_metadata.py data/results.csv outputs/ --min-conf '>0.3' --max-conf '<0.9'
  python process_metadata.py data/results.csv outputs/ --min-duration '>1.0' --max-duration '<60.0'
  python process_metadata.py data/results.csv outputs/ --config config.yaml
        """
    )

    parser.add_argument("metadata_path", type=Path, help="Path to the classified metadata CSV file")
    parser.add_argument("output_dir", type=Path, help="Base output directory (will create run_YYYY-MM-DD-HH-MM-SS subfolder)")

    # Optional parameters with defaults
    parser.add_argument("--config", type=Path, help="Path to YAML config file (overrides defaults)")
    parser.add_argument("--frame-width", type=float, default=1.0, help="Physical frame width (mm)")
    parser.add_argument("--frame-height", type=float, default=1.0, help="Physical frame height (mm)")

    # Confidence
    parser.add_argument("--min-conf", type=str, help="Minimum detection confidence (e.g., 0.5 or '>0.3')")
    parser.add_argument("--max-conf", type=str, help="Maximum detection confidence (e.g., 0.9 or '<0.9')")

    # Duration
    parser.add_argument("--min-duration", type=str, help="Minimum track duration (seconds) (e.g., 2.0 or '>1.0')")
    parser.add_argument("--max-duration", type=str, help="Maximum track duration (seconds) (e.g., 30.0 or '<60.0')")

    # Probability
    parser.add_argument("--min-prob", type=str, help="Minimum classification probability (weighted) (e.g., 0.6 or '>=0.5')")
    parser.add_argument("--max-prob", type=str, help="Maximum classification probability (e.g., 0.9 or '<0.9')")

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Load config file if provided
    config = {}
    if args.config:
        config = load_config(args.config)

    # Override config with CLI args (CLI has highest priority)
    cli_args = {k: v for k, v in vars(args).items() if v is not None and k not in ["metadata_path", "output_dir", "config"]}
    config.update(cli_args)

    # Merge config into args (for function call)
    for k, v in config.items():
        if getattr(args, k, None) is None:
            setattr(args, k, v)

    # Validate required paths
    if not args.metadata_path.exists():
        logger.error(f"Metadata file not found: {args.metadata_path}")
        sys.exit(1)

    # Call processing function
    try:
        result = process_metadata_classified(
            metadata_path=args.metadata_path,
            output_dir=args.output_dir,
            frame_width=args.frame_width,
            frame_height=args.frame_height,
            min_conf=args.min_conf,
            max_conf=args.max_conf,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            min_prob=args.min_prob,
            max_prob=args.max_prob,
            progress_callback=lambda current, total, msg: print(f"[{current}/{total}%] {msg}")
        )
        print("\n✅ Processing completed!")
        print(f"Final results saved to: {result['out_dir']}")
        print(f"Removed detections: {result['detections_removed']}")
        print(f"Removed tracks: {result['tracks_removed']}")
        print(f"Removed classifications: {result['classifications_removed']}")
    except RuntimeError as e:
        if str(e) == "CANCELLED_BY_USER":
            print("❌ Processing was cancelled by user.")
            sys.exit(1)
        else:
            raise


if __name__ == "__main__":
    main()