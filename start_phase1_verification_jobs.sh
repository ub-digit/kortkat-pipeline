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

JOB_NAME_BASE="phase1_verification_batch"

echo "Launching batches $START to $END..."

for i in $(seq $START $END); do
    echo "Launching Batch $i..."

    CURRENT_NAME="${JOB_NAME_BASE}${i}"
    
    python3 run_pipeline.py "$CURRENT_NAME" --steps create-input create-job
    
done

echo "All requested batches have been started."