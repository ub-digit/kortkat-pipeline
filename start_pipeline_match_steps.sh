#!/bin/bash

# Check if both start and end arguments are provided
if [ $# -lt 2 ]; then
  echo "Usage: $0 [start_batch] [end_batch]"
  exit 1
fi

START=$1
END=$2

JOB_NAME_BASE="phase1_extraction_batch"
IMAGE_DIRECTORY_BASE="/data/kortkat/batch-images/20-batch/batch-"

echo "Launching batches $START to $END..."

for i in $(seq $START $END); do
    echo "Launching Batch $i..."

    CURRENT_NAME="${JOB_NAME_BASE}${i}"
    CURRENT_IMAGE_DIR="${IMAGE_DIRECTORY_BASE}${i}"

    python3 run_pipeline.py "$CURRENT_NAME" "$CURRENT_IMAGE_DIR" --steps parse post-process match
    
done

echo "All requested batches have been started."