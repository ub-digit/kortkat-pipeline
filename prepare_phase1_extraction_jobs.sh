#!/bin/bash

# Check if both start and end arguments are provided
if [ $# -lt 2 ]; then
  echo "Usage: $0 [start_batch] [end_batch]"
  exit 1
fi

VENV_PATH="./venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
fi

START=$1
END=$2

JOB_NAME_PREFIX="phase1_extraction_batch"
TEMPLATE_JOB_NAME="phase1_extraction_template"

echo "Preparing batches $START to $END..."

for i in $(seq $START $END); do
    echo "Preparing Batch $i..."

    CURRENT_NAME="${JOB_NAME_PREFIX}${i}"
    
    python3 prepare_pipeline.py "$CURRENT_NAME" --from "$TEMPLATE_JOB_NAME"
    
done

echo "All requested batches have been prepared."