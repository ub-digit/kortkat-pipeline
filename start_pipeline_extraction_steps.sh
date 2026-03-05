#!/bin/bash

# Check if both start and end arguments are provided
if [ $# -lt 2 ]; then
  echo "Usage: $0 [start_batch] [end_batch]"
  exit 1
fi

START=$1
END=$2

VENV_PATH="./venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
fi

JOB_NAME_BASE="phase1_extraction_batch"
IMAGE_DIRECTORY_BASE="/data/kortkat/batch-images/20-batch/batch-"

echo "Launching batches $START to $END..."

for i in $(seq $START $END); do
    echo "Launching Batch $i..."

    CURRENT_NAME="${JOB_NAME_BASE}${i}"
    CURRENT_IMAGE_DIR="${IMAGE_DIRECTORY_BASE}${i}"
    
    #nohup python3 run_pipeline.py phase1_extraction_batch1 /data/kortkat/batch-images/20-batch/batch-1 --steps create-input create-job check-job & sleep 600
    nohup python3 run_pipeline.py "$CURRENT_NAME" "$CURRENT_IMAGE_DIR" --steps create-input create-job check-job &
    
    # Wait 10 minutes (600 seconds) before launching the next one
    # Note: We don't sleep after the very last batch to finish the loop faster
    if [ $i -lt $END ]; then
        echo "Sleeping 600s..."
        sleep 600
    fi
done

echo "All requested batches have been started."