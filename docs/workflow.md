# Workflow to aggregatea and filter metadata files and validate classification results from the post-processing pipeline using BioCLIP2 classifier

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

Run
```{}
pip install -r requirements.txt
```

### 1. **merge_meta.py**: Find, load, and merge all metadata files 

`merge_meta.py` recursively searches the processed data directory for metadata CSV files matching a given filename pattern (e.g. with suffix: `"[...]metadata_merged_crops_classified.csv"`), merges them into a single output CSV, and optionally appends file- and folder-derived metadata columns. The script reports the number of processed files, total rows (detections), and runtime.


#### USAGE

**Basic command**
```
python merge_meta.py <input_dir> -o <output_file>
```
`<input_dir>`: Root directory containing the folder structure with metadata files, that is the output of the post-processing pipeline ("data_processed") \
`-o <output_file>`: Filename and path to the merged output CSV (required), e.g. ~"SEPPI-processing\output\all_metadata_combined.csv"

**Common options**

`-p, --pattern`: Filename pattern to match (default: *metadata_merged_crops_classified.csv)\
`--add-metadata`: Adds columns: folder_datetime, file_date, source_file \
`--append`: Appends to existing output file instead of overwriting it

**Examples**

**Basic merge:**
```
python merge_meta.py data_processed -o combined.csv
```
**With metadata columns:**
```
python merge_meta.py data_processed -o combined.csv --add-metadata
```
**Custom file pattern:**
```
python merge_meta.py data_processed `
  -p "*metadata_merged_crops_classified_top1_all.csv" `
  -o combined.csv
```
**Append to existing file:**
```
python merge_meta.py data_processed -o combined.csv --append
```

**Output**

- Merged CSV file at specified location 
- Terminal summary including: \
-- Number of files combined \
-- Total number of rows (detections) \
-- Processing time

>**JONNA**
```{}
python merge_meta.py E:/2025_processed/data_processed ` 
-o ~/Documents/SEPPI-processing/output/all_metadata_combined.csv
```

### 1.1 **add_flower_meta.py**: Add flowering species information from raw camera trap data to merged metadata file




### 2. **aggregate_filter_meta.py**: Aggregate and filter metadata (by detection confidence, by tracking duration, by classification probability)

The `aggregate_filter_meta.py` script processes raw classified metadata to:

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

