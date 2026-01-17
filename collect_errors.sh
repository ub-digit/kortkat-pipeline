#!/usr/bin/env bash

# This script collects images corresponding to error files from Gemini jobs into a specified output directory, used to build a new rerun job.

# Root directory containing all images
IMAGE_ROOT="source-input/all-images/50-batch"

# Pattern to search for error files
#SEARCH_PATTERN="/Users/xkumag/dev/kat-57-pipeline/jobs/ipac-ocr-batch*/parse/fail/*error"
SEARCH_PATTERN="jobs/ipac-ocr-error-rerun2/parse/fail/*error"

# Output directory to collect images into
OUTPUT_DIR="source-input/all-images/ipac-ocr-error-batch3"

# 1. Create the output directory first
mkdir -p "$OUTPUT_DIR"

# 2. Define the index file path INSIDE the output directory
INDEX_FILE="${OUTPUT_DIR}/image_index_temp.txt"

# SAFETY: If the script is stopped (Ctrl+C) or finishes, remove the index file automatically
trap "rm -f '$INDEX_FILE'" EXIT

echo "------------------------------------------------"
echo "Phase 1: Indexing images..."
echo "Storing index at: $INDEX_FILE"

# Find all jpgs and save to the file in the output dir
find "$IMAGE_ROOT" -name "*.jpg" > "$INDEX_FILE"
echo "Index complete."
echo "------------------------------------------------"

echo "Phase 2: Processing error files..."

# Loop through error files
# We use 'ls' so wildcards expand correctly
ls $SEARCH_PATTERN | while read file; do
    
    base=$(basename "$file")
    
    # Extract Job ID (e.g., 123_456)
    job_id=$(echo "$base" | grep -oE '^[0-9]+_[0-9]+')

    # Search the index file for "/ID.jpg"
    found_image=$(grep -m 1 -F "/${job_id}.jpg" "$INDEX_FILE")

    if [[ -n "$found_image" ]]; then
        if [ -f "$found_image" ]; then
            cp "$found_image" "$OUTPUT_DIR/"
        else
            echo "  -> [ERROR] Index mismatch: $found_image"
        fi
    else
        echo "  -> [WARNING] Image not found for ID: $job_id"
    fi

done

echo "------------------------------------------------"
echo "Done. Images collected in $OUTPUT_DIR"
# The 'trap' command above will automatically delete the text file now.