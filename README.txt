SEPPI-PROCESSING/
│
├── scripts/
│   ├── 01_merge_meta_and_flower.py             # find and combine individual output metadata files, find and join plant species information
│   ├── 02_aggregate_filter_meta.py             # aggregate at track ID level and filter detections
│   ├── 03_stratified_random_subsampling.py     # stratify data and randomly subsample images for subsampling
│   ├── 04_validate_results_ui.py               # validate classification results of random selection of images per strata
│   └── 05_validation_statistics.py             # calculate general validation statistics (error rate, accuracy)
│
├── docs/
│   └── workflow.md                # Markdown guide (WIKI)
│
├── .gitignore
├── requirements.txt
├── README.md                      