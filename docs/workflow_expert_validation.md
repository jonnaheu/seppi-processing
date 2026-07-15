# 📊 `subsample_expert.py` – Subsampling Workflow Guide

This script enables **stratified random subsampling** of insect detection data, focusing on hoverflies (Syrphidae) while maintaining flexibility for general sampling. It supports three distinct strata, each with configurable thresholds and sample sizes.

---

## 📌 **Strata Sampling Descriptions**

### 1. `sample_all` – Random Subsampling of All Images
- **Purpose**: Create a representative random sample from the entire dataset without using any BioCLIP information.
- **Sampling Logic**:
  - Filters all rows where `det_conf_mean > threshold` (e.g., `0.7`).
  - Randomly samples `n_per_group_all` rows (e.g., 500) from the filtered dataset.
  - Ensures reproducibility using a `seed`.

---

### 2. `strata_syrphid` – BioCLIP2-Syrphidae Subsampling by Probability Score Threshold
- **Purpose**: Focus on hoverflies (Syrphidae family) classified by BioCLIP2 at different probability levels.
- **Sampling Logic**:
  - Filters data to include only rows where `bioclip_family == "Syrphidae"`.
  - For each `prob_threshold` (e.g., `0.5`, `0.7`, `0.9`), samples up to `n_per_group_syrphid` rows where `top1_prob_weighted > threshold`.
  - Each threshold gets its own output CSV.

---

### 3. `strata_syrphid_genus` – Syrphidae Subsampling by Genus
- **Purpose**: Ensure balanced representation of individual hoverfly genera classified by BioCLIP2.
- **Sampling Logic**:
  - Filters data to include only rows where `bioclip_family == "Syrphidae"`.
  - For each unique `bioclip_genus` (e.g., *Eristalis*, *Syrphus*, *Melanostoma*), samples up to `n_per_genus` rows where `top1_prob_weighted > prob_threshold_genus`.
  - Each genus gets its own output CSV with a short filename (e.g., `eri.csv` for *Eristalis*).


---

## 📚 **Wiki: How to Use `subsample_expert.py`**

### 🛠️ **Command Line Usage**
```bash
python subsample_expert.py `
  --metadata-path C:/path/to/all_metadata_combined.csv `
  --top1-final-path C:/path/to/all_metadata_combined_top1_final.csv `
  --n-per-group-all 500 `
  --det-conf-threshold 0.7 `
  --n-per-group-syrphid 100 `
  --prob-thresholds 0.5 0.7 `
  --n-per-genus 50  `
  --prob-threshold-genus 0.6 `
  --seed 42
```


  ✅ Required Arguments
|Argument|	Description|	Example|
|--------|-------------|-----------|
|--metadata-path|	Path to all_metadata_combined.csv (use forward slashes: C:/...)|	C:/data/metadata.csv|
|--top1-final-path|	Path to all_metadata_combined_top1_final.csv	|C:/data/top1_final.csv|  

🎯 Sampling Parameters
|Argument|	Description|	Default	|Example|
|--------|-------------|-----------|--------|
|--n-per-group-all	|Number of random samples from all images (after filtering by det_conf_mean)	|100	|--n-per-group-all 500|
|--det-conf-threshold	|Minimum detection confidence|	0.5	|--det-conf-threshold 0.7|
|--n-per-group-syrphid|	Number of samples classified as Syrphidae by BioCLIP2	|100	|--n-per-group-syrphid 100|
|--prob-thresholds	|List of BioCLIP probability thresholds for strata_syrphid (e.g., 0.5 0.7)|	[0.5]	|--prob-thresholds 0.5 0.7 0.9|
|--n-per-genus	|Number of samples per Syrphidae genus (used in strata_syrphid_genus)	|50	|--n-per-genus 50|
|--prob-threshold-genus	|Threshold of BioCLIP2 probability for strata_syrphid_genus|	0.5	|--prob-threshold-genus 0.6|  

🔐 Optional Arguments
|Argument	|Description	|Default|
|--------|-------------|-----------|
|--seed|	Random seed for reproducibility|	123|