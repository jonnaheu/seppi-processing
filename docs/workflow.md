# Workflow to aggregate and filter metadata and validate classification results 

This script serves to further process the results obtained from the SEPPI post-processing pipeline that classifies the captured flower visitor images using BioClip2.

All data was processed with the following configurations: 
- Image processing: ‘Crop Detections’ and ‘Move Crops by Classification’ was enabled 
- Classification:  BioCLIP2 enabled, batch size = 8
- Metadata Processing: everything disabled (if not diabled, two more csv metadata files will have been created)

**OUTPUT of the Post-processing pipeline:**
```
data_processed/
├── TIMESTAMP-of-PROCESSING_DATE-RECORDING_processed          # For each post-processing run one folder is created
    ├── images                   
        ├── crops                
            ├── insect          
                ├── GENUS1                                    # Folder containing all crops classified as this genus
                ├── GENUS2                                    # ...
                ├── ...
    ├── metadata                                              # Folder containing the output metadata files
        ├── YYYY-MM-DD_metadata_merged.csv                    # Metadata of each insect detection
        ├── YYYY-MM-DD_metadata_merged_crops.csv              # Joined path to crop per detection
        └── YYYY-MM-DD_metadata_merged_crops_classified.csv   # Classification results of each crop
    ├── YYYY-MM-DD_HH-MM-SS_config.json                       # Configuration of post-processing pipeline during classification run
    ├── YYYY-MM-DD_HH-MM-SS_stats.json                        # Statistics (duration) for different steps of classification run
    └── pipeline.log                                          # Log of terminal output during classification run
    
```


## Overview of computational steps of the workflow:

### Setting up the work enviroment

1. Download `SEPPI-workflow-processing` scripts from github (clone it using Git/GitBash - recommended) **OR** download the folder from the shared location (e.g. Google Drive).
3. Open VScode and open the folder under `File` > `Open Folder...`
4. Open a new terminal and run the following code to install all required packages (NOTE: you have to have python already installed):
```{}
  pip install -r requirements.txt
```

After setting up the work environment you can start running the next scripts one after another. Therefore you have to change the directory in the terminal to `scripts`.

Run in a new Terminal: 
```
  cd scripts 
``` 

### 1. Find, load, and merge all metadata files: **merge_meta_and_flower.py**

**Short description**: `merge_meta_and_flower.py` recursively searches the raw and processed data directory for config json-files and metadata csv-files matching a given filename pattern (e.g. with suffix: `"[...]metadata_merged_crops_classified.csv"`), merges them into a single output csv, and appends source-file paths and plant species information in additional columns. The script reports the number of processed files and total rows (detections).
The scripts performs three key steps in sequence:
1. Merges all JSON configuration files (YYYY-MM-DD_hh-mm-ss_config_seppi_flower/platform.json) > `merged_config_seppi_flower.csv`
2. Merges all processed metadata CSVs (e.g., *metadata_merged_crops_classified.csv)  > `merged_metadata.csv`
3. Joins the plant_species column from the config file to the metadata based on cam_ID and time session boundaries > `all_metadata_combined.csv`



#### Usage

```
  python merge_meta_and_flower.py
```

The script will prompt you for three inputs:
| Input Parameter | Description |
|-----------------|-------------|
| `Path to raw data directory` | Path to the raw data directory (unprocessed data from camtraps) containing JSON config files (e.g., `D:\SEPPI_CAMTRAPS_DE\2025`) |
| `Path to output directory` | Create a folder where you want to save the output of all the next steps (e.g., `C:\Users\NAME\output`) |
| `Path to processed data directory` | Path to the processed data directory containing processed metadata CSVs (e.g., `data_processed`) |


#### Output

```
output/
├── YYYY-MM-DD_HH-MM-SS_all_metadata_combined.csv   # Metadata of each insect detection
├── YYYY-MM-DD_HH-MM-SS_merged_config_json.csv      # Joined path to crop per detection
└── YYYY-MM-DD_HH-MM-SS_merged_metadata.csv         # Classification results of each crop    
```

> **IMPORTANT**: Any typos that were made when entering the flower species information in the field into the webapp will now appear in the data. Make sure your monitored flower species were spelled correctly and best clean out the output csv files now.  
> If you have not use the option to enter the flower species information, you need to join the flower species information per recording intervall individually.


### 2. Aggregate and filter metadata: **aggregate_filter_meta.py**: 

**Short description**: The `aggregate_filter_meta.py` script processes raw classified metadata to:

1. Filter detections based on confidence, duration, and classification probability
2. Aggregate track-level statistics (e.g., duration, average confidence, bounding box size)
3. Select the most confident classification per track using weighted probability
4. Plot four graphs illustrating the distribution of tracking IDs across different filtering options

#### Usage

The script can be run with a configuration file (config.yaml) [1] or directly by specifying all input parameters in the command line [2], or a mixed approach [3].

|Input parameter | Values | Default | Description |
|----------------|--------|---------|-------------|
|<metadata_path> | path/YYYY-MM-DD_HH-MM-SS_all_metadata_combined.csv | *none* | Path to combined metadata file (output previous step) |
|<output_directory>| path/output | *none* | Path to location where outputfolder will be created in|
|`--min-conf` | 0.3 - 1 | *none* | Define minimum detection confidence |
|`--max-conf` |0 - 1 |  *none* | Define maximum detection confidence |
|`--min-duration`| 0 - ~ |  *none* | Define minimum duration of tracking event|
|`--max-duration` | 0 - ~ |  *none* | Define maximum duration of tracking event |
|`--min-prob` | 0 - 1 |  *none* | Define minimum classification probability (BioCLIP) |
|`--max-prob` | 0 - 1 |  *none* | Define maximum classification probability (BioCLIP) |

To define values the following operators can be used: `==`, `>=`, `<=`, `<`, `>`

> **IMPORTANT:** If no value will be defined, the filtering option is skipped. This is what we want for the first run.


**1. Run with config file:**  

Create configuration file (config.yaml) by pasting the following text in a text editor an save as `config.yaml`, adjust the values as needed.
```
metadata_path: path/to/YYYY-MM-DD_HH-MM-SS_all_metadata_combined.csv
output_dir: path/to/output
min_conf: >=0.3
max_conf: ==0.4
min_duration: >1.0
max_duration: <600.0
min_prob: >=0.001
max_prob: null
```

Run: 
```{}
    python aggregate_filter_meta.py path/YYYY-MM-DD_HH-MM-SS_all_metadata_combined.csv path/output `
   --config path/to/config.yaml 
``` 



**2. Set filtering threshold in command line interface (CLI):**   

Paste in one line or use separator ` 

```
  python aggregate_filter_meta.py <metadata_path> <output_dir> 
    --min-conf '>=0.3'          
    --max-conf '==0.4'          
    --min-duration '>1.0'      
    --max-duration '<600.0'     
    --min-prob '>=0.001'        
    --max-prob '1.0'           
```

**3. Mix CLI and config:**

Example:
```
  python aggregate_filter_meta.py <metadata_path> <output_dir> --config config.yaml --min-conf 0.9
```

#### Output  
The script creates a new folder named `run_YYYY-MM-DD-HH-MM-SS` inside the `output_dir`, containing:
```
run_YYYY-MM-DD-HH-MM-SS/
├── all_metadata_combined_top1_all.csv                  # Aggregated classification results per track with top1 probability
├── all_metadata_combined_top1_final.csv                # Aggregated classification results per track + tracking statistics (duration etc.)
├── config.yaml                                         # Full run configuration
└── plots/
    ├── pollinator_stacked_distribution.png             # Classified Pollinator orders vs non-pollinator orders (stacked)
    ├── pollinator_duration_distribution.png            # Duration distribution (0, >0-10, >10-100, >100-500, >500)
    ├── pollinator_probability_facetted_histogram.png   # Histograms of top1 weighted probability by order (4 subplots)
    └── pollinator_confidence_facetted_histogram.png    # Histograms of mean detection confidence by order (4 subplots)
```


### 3 Stratified random selection of crop images for validation: **stratified_random_subsampling.py** 

The `stratified_random_subsampling.py` script performs multi-level stratified random sampling on aggregated pollinator detection metadata to generate balanced, representative, and reproducible subsamples for downstream tasks such as classification validation.

This script is designed to work after aggregate_filter_meta.py, using its output (*_top1_final.csv) as input.

#### Definition of strata:

|Strata | Description |
|-------|-------------|
|Strata1| Pollinator vs. non-pollinator + high/low classification probability|
|Strata2| Duration-based (single, multiple, long) for pollinators only|
|Strata3| By major pollinator order (Hymenoptera, Lepidoptera, Coleoptera, Diptera), stratified by probability bins (0.0–0.1, ..., 0.9–1.0)|
|Strata4| Median-based high/low probability per plant species (pollinators with duration > 0)|
|Strata5| One sample per genus (low/high prob) for each order|
|Strata6| One sample per family (low/high prob) for each order|
|Strata7| Multiple samples per order (up to n_per_group_strata7) split by median probability|
|Strata8| Top N most frequent species, subsampled by median-based probability per species |

#### Usage
The script requires two CSV files:
| File	| Purpose |
|-------|---------|
| all_metadata_combined.csv	| Raw metadata with detection results (used to slice by track ID)|
| all_metadata_combined_top1_final.csv	| Aggregated metadata from aggregate_filter_meta.py (used for stratification) |

#### Output
The script creates a timestamped output directory (e.g., strata_2025-04-05_14-30-22) inside the metadata_path.parent, containing:
```
strata_2025-04-05_14-30-22/
├── strata1_2025-04-05_14-30-22.csv               # Pollinator/non-pollinator + prob
├── strata2_2025-04-05_14-30-22.csv               # Duration-based (pollinator-only)
├── strata3_hym_2025-04-05_14-30-22.csv           # Hymenoptera (by prob bin)
├── strata3_lep_2025-04-05_14-30-22.csv           # Lepidoptera (by prob bin)
├── strata3_col_2025-04-05_14-30-22.csv           # Coleoptera (by prob bin)
├── strata3_dip_2025-04-05_14-30-22.csv           # Diptera (by prob bin)
├── strata4_2025-04-05_14-30-22.csv               # Median-based per plant species
├── strata5_hym_2025-04-05_14-30-22.csv           # One sample per genus (low/high prob)
├── strata5_lep_2025-04-05_14-30-22.csv           # ...
├── strata5_col_2025-04-05_14-30-22.csv           # ...
├── strata5_dip_2025-04-05_14-30-22.csv           # ...
├── strata6_hym_2025-04-05_14-30-22.csv           # One sample per family (low/high prob)
├── strata6_lep_2025-04-05_14-30-22.csv           # ...
├── strata6_col_2025-04-05_14-30-22.csv           # ...
├── strata6_dip_2025-04-05_14-30-22.csv           # ...
├── strata7_hym_2025-04-05_14-30-22.csv           # Multiple samples per order
├── strata7_lep_2025-04-05_14-30-22.csv           # ...
├── strata7_col_2025-04-05_14-30-22.csv           # ...
├── strata7_dip_2025-04-05_14-30-22.csv           # ...
├── strata8_2025-04-05_14-30-22/                  # Most common species
│   ├── strata8_bombus_rub_2025-04-05_14-30-22.csv
│   ├── strata8_apis_mel_2025-04-05_14-30-22.csv
│   └── ...
└── config.yaml                                  # Full run configuration
```

#### Usage
1. Run with CLI arguments (recommended for one-off runs):
```
python stratified_random_subsampling.py `
  --metadata-path /path/to/all_metadata_combined.csv `
  --top1-final-path /path/to/all_metadata_combined_top1_final.csv `
  --n-per-group-strata1 100 `
  --n-per-group-strata2 100 `
  --n-per-group-strata3 50 `
  --n-per-group-strata4 50 `
  --n-per-group-strata7 10 `
  --n-per-group-strata8 10 `
  --n-common-species-strata8 10 `
  --seed 123
  ```

2. Run with config file (config.yaml):
```
metadata_path: /path/to/all_metadata_combined.csv
top1_final_path: /path/to/all_metadata_combined_top1_final.csv
n_per_group_strata1: 100
n_per_group_strata2: 100
n_per_group_strata3: 50
n_per_group_strata4: 50
n_per_group_strata7: 10
n_per_group_strata8: 10
n_common_species_strata8: 10
seed: 123
```
Run command:
``` 
python stratified_random_subsampling.py --config config.yaml
```

3. Mix CLI and config (CLI overrides config):
```
python stratified_random_subsampling.py `
  --config config.yaml `
  --n-per-group-strata1 200 `
  --seed 42
```

**Configuration Parameters**
| Argument | Default |	Description |
|---------------|---------|--------------|
|--metadata-path|	required	|Path to all_metadata_combined.csv|
|--top1-final-path|	required|	Path to all_metadata_combined_top1_final.csv|
|--n-per-group-strata1	|100	|Samples per group in strata1 (pollinator/non-pollinator + prob)|
|--n-per-group-strata2|	100	|Samples per duration group (pollinator-only)|
|--n-per-group-strata3|	50|	Samples per probability bin per order (strata3)|
|--n-per-group-strata4|	50|	Samples per plant species (median-based)|
|--n-per-group-strata7|	10|	Samples per order (strata7)|
|--n-per-group-strata8|	10|	Samples per top species (strata8)|
|--n-common-species-strata8|	10|	Number of top frequent species to include in strata8|
|--seed	|123	|Random seed for reproducibility|


### 4. **validate_results_ui.py**: Validation of classification results 

The **validate_results_ui.py** script provides a graphical user interface (GUI) for manual validation of image subsamples generated by stratified_random_subsampling.py. It enables researchers to inspect and label images based on biological accuracy, ensuring high-quality ground truth for model training, annotation, or evaluation.
Designed for multi-strata workflows, the tool supports:

    - Pollinator vs. non-pollinator validation
    - Bioclip classification validation at multiple taxonomic levels (species, genus, family, order)

#### Input Requirements
| File|	Purpose|
|-----|--------|
|strataX_*.csv|	Subsampled metadata csv-file (generated in stratified_random_subsampling.py)|
|Image directory	|Folder containing all crops (data_processed) |

#### Output
Output
The script generates a new CSV file in the same directory as the input metadata:
```
strata3_hym_2026-06-24_14-44-47_validated.csv
```

Output Columns Added:
|Column	|Description|
|-------|-----------|
|valX	|Validation label (e.g., pollinator, correct)|
|comment	| User-provided notes (e.g., "Corrected to Bombus terrestris")|


All original metadata is preserved.

#### Usage
1. Run the GUI
```
python validate_results_ui.py
```

2. Workflow

    1. Select Image Directory → Browse to the processed data folder containing the crops
    2. Select Metadata CSV → Choose a csv file with the subsamples
    3. Choose Validation Mode:\
        Pollinator: For Strata 1–2\
        Bioclip: For Strata 3–8\
    4. Select Taxonomic Level (if Bioclip): Species, Genus, Family, Order
    5. Click "▶️ Start Validation"
    6. Label each image using the buttons
    7. Add comments if needed
    8. When all crops are validate the output file is automatically saved
     --> Click "💾 Save & Return to Setup" when validation needs to be interrupted (returning is not possible)

#### Example Output (CSV)
|crop_path	|bioclip_species|	val3_species|	comment|
|-----------|---------------|-------------|--------|
|crop_001.jpg	|Bombus terrestris|	correct	|correct at morphospecies level|
|crop_002.jpg	|Apis mellifera	|incorrect	|Not a bee, likely a fly|
|crop_003.jpg| Lasioglossum pauxillum	|Unclear |Not sure if a bee is present or not in the image|

### 5. **validation_statistics.py**: Accuracy of classification and error rate

Not yet developed.