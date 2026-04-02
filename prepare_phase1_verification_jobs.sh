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

JOB_NAME_PREFIX="phase1_verification_batch"
TEMPLATE_JOB_NAME="phase1_verification_template"
PROMPT_MACHINE_NAME="match_verification_prompt_machine"
SOURCE_BATCH_JOB_PREFIX="jobs/phase1_extraction_batch"

echo "Preparing batches $START to $END..."

for i in $(seq $START $END); do
    echo "Preparing Batch $i..."

    CURRENT_NAME="${JOB_NAME_PREFIX}${i}"

    # --output_directory is appended by prepare_job.py to the current batch job directory, so we don't need to include it here
    python3 prepare_job.py --job_name "$CURRENT_NAME" --from "$TEMPLATE_JOB_NAME" --prompt_machine "$PROMPT_MACHINE_NAME" --source_batch_job_directory "$SOURCE_BATCH_JOB_PREFIX${i}" "-v"
    
done

echo "All requested batches have been prepared."