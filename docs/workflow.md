# Workflow to aggregate and filter metadata files and validate classification results from the post-processing pipeline using BioCLIP2 classifier

This script serves to test and explore the results obtained from SEPPI post-processing pipeline that classifies the captured flower visitor images.

All data was processed with the following configurations: 
- Image processing: ‘Crop Detections’ and ‘Move Crops by Classification’ was enabled 
- Classification:  BioCLIP2 enabled, batch size = 8
- Metadata Processing: everything disabled

**OUTPUT of the Post-processing pipeline:**
- images: crops moved to folders by genus classification result

- metadata: 3 CSV files:

   - …metadata_merged.csv
   - …metadata_merged_crops.csv
   - …metadata_merged_crops_classified.csv

    2 json files:

   - …config_mini.json = applied configuration
   - …stats.json = duration of processing steps 

    1 txt file:

    - pipeline_log.txt

## Overview of computational steps of the workflow:

### Setting up the work enviroment

1. Download and unzip the folder `SEPPI-workflow-processing` from the shared location (e.g. Google Drive).
2. Move the folder to a permament location of your choice (best locally on your laptop).
3. Open VScode and open the folder under `File` > `Open Folder...`
4. Open a new terminal and run the following code to install all required packages:
```{}
pip install -r requirements.txt
```

### 1. **merge_meta_and_flower.py**: Find, load, and merge all metadata files 

**Short description**: `merge_meta_and_flower.py` recursively searches the raw and processed data directory for config json-files and metadata csv-files matching a given filename pattern (e.g. with suffix: `"[...]metadata_merged_crops_classified.csv"`), merges them into a single output csv, and appends source-file paths and plant species information in additional columns. The script reports the number of processed files and total rows (detections).
The scripts performs three key steps in sequence:
1. Merges all JSON configuration files (YYYY-MM-DD_hh-mm-ss_config_seppi_flower.json) into a single `merged_config_seppi_flower.csv`
2. Merges all processed metadata CSVs (e.g., *metadata_merged_crops_classified.csv) into memory (no temporary file)
3. Joins the plant_species column from the config file to the metadata based on cam_ID and time session boundaries
4. Saves a csv metadata file containig all single files plus the flower species information from the config files. `all_metadata_combined.csv`



#### USAGE

**Basic command**
```
python merge_meta_and_flower.py
```

The script will prompt you for four inputs interactively:
#### Input Parameters

| Input Parameter | Description |
|-----------------|-------------|
| `Path to raw data directory` | Path to the raw data directory (unprocessed data from camtraps) containing JSON config files (e.g., `D:\SEPPI_CAMTRAPS_DE\2025`) |
| `Output path for merged config CSV` | Path to save the merged config file containing the plant species information per recording session (e.g., `output/merged_config_seppi_flower.csv`) |
| `Path to processed data directory` | Path to the processed data directory containing processed metadata CSVs (e.g., `data_processed`) |
| `Output path for final merged metadata file` | Path to save the final output file (e.g., `output/all_metadata_combined.csv`) |

**Examples**

**Exemplary Terminal In- and Output**
```
=== SEPPI Data Pipeline: Combine JSON → Merge CSV → Join with Plant Species ===

Enter path to raw data directory (contains JSONs: [date]_config_seppi_flower.json): E:\SEPPI_CAMTRAPS_DE\2025

Enter output path for merged config CSV (call the file: merged_config_seppi_flower.csv): C:\Users\heuschel\Documents\SEPPI-processing\output\merged_config_seppi_flower.csv 

Enter path to processed data directory (contains CSVs: [date]_metadata_merged_crops_classified.csv): F:\2025_processed

Enter final output path for joined file (call the file: all_metadata_combined.csv): C:\Users\heuschel\Documents\SEPPI-processing\output\all_metadata_combined.csv 
```

**Output**

- 2 CSV files at specified output location 

**IMPORTANT**: Any typos that were made when entering the flower species information in the field into the webapp will now appear in the data. Make sure your monitored flower species were spelled correctly and best clean out the output csv files now.


### 2. **aggregate_filter_meta.py**: Aggregate and filter metadata (by detection confidence, by tracking duration, by classification probability)

**Short description**: The `aggregate_filter_meta.py` script processes raw classified metadata to:

- Filter detections based on confidence, duration, and classification probability
- Aggregate track-level statistics (e.g., duration, average confidence, bounding box size)
- Select the most confident classification per track using weighted probability
  
- Generate two output files:\
  --*_top1_all.csv – Aggregated classification results per track with top1 probability \
  --*_top1_final.csv – Aggregated classification results per track + tracking statistics (duration etc.)

The script also plots four graphs illustrating the distribution of tracking IDs across different filtering options.

It supports both Ultralytics-style (top1, top1_prob) and BioCLIP-style (bioclip_species, bioclip_score) classification formats, preserving taxonomic hierarchy when applicable.

**Output** \
The script creates a new folder named `run_YYYY-MM-DD-HH-MM-SS` inside the `output_dir`, containing:
```
run_2026-04-23-14-26-00/
├── all_metadata_combined_top1_all.csv          # Aggregated classification per track
├── all_metadata_combined_top1_final.csv        # Aggregated classification per track + track statistics
├── config.yaml                                # Full run configuration
└── plots/
    ├── pollinator_stacked_distribution.png      # Classified Pollinator orders vs non-pollinator orders (stacked)
    ├── pollinator_duration_distribution.png     # Duration distribution (0, >0-10, >10-100, >100-500, >500)
    ├── pollinator_probability_facetted_histogram.png  # Histograms of top1 weighted probability by order (4 subplots)
    └── pollinator_confidence_facetted_histogram.png   # Histograms of mean detection confidence by order (4 subplots)
```
The four plots that are created serve to visually examine the distribution of the aggregated and filter dataset.

#### USAGE
1. Set filtering threshold in command line interface (CLI) (paste in one line):
```{}
python aggregate_filter_meta.py <metadata_path> <output_dir> 
  --min-conf '>=0.3'          
  --max-conf '==0.4'          
  --min-duration '>1.0'      
  --max-duration '<600.0'     
  --min-prob '>=0.001'        
  --max-prob '1.0'           
```
`input_metadata_file`: Path to combined metadata file (Step 1)\
`output_dir`: Path to location where outputfolder will be created in.

  `--min-conf '>=0.3'`          ← Define minimum detection confidence \
  `--max-conf '==0.4'`          ← Define maximum detection confidence \
  `--min-duration '>1.0'`       ← Define minimum duration of tracking event \
  `--max-duration '<600.0'`     ← Define maximum duration of tracking event \
  `--min-prob '>=0.001'`        ← Define minimum classification probability (BioCLIP) \
  `--max-prob '1.0'`            ← Define maximum classification probability (BioCLIP) \



2. Run with config files:
```{}
python aggregate_filter_meta.py data/results.csv output/ --config config.yaml
```
3. Config file (config.yaml):
```
metadata_path: ~\all_metadata_combined.csv
output_dir: ~\output\run_YYYY-MM-DD-HH-MM-SS
frame_width: 1.0
frame_height: 1.0
min_conf: '>=0.3'
max_conf: ==0.4
min_duration: '>1.0'
max_duration: <600.0
min_prob: '>=0.001'
max_prob: null
```

4. Mix CLI and config:
```{}
python aggregate_filter_meta.py data/results.csv outputs/ --config config.yaml --min-conf 0.9
```





### 3 **stratified_random_subsampling.py**: Stratified random selection of crop images for validation 


### 4. **validate_results_ui.py**: Validation of classification results 

### 5. **validation_statistics.py**: Accuracy of classification and error rate

