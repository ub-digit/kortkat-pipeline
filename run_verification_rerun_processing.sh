#!/bin/bash

# Check if the batch argument is provided
if [ $# -lt 1 ]; then
  echo "Usage: $0 [batch_number]"
  exit 1
fi

BATCH=$1

VENV_PATH="./venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
fi


JOBS_PATH_BASE="/Users/xkumag/dev/kat-57-pipeline/jobs/phase2_verification_batch"
CURRENT_JOBS_PATH="${JOBS_PATH_BASE}${BATCH}"
EXTRACT_DIR="${CURRENT_JOBS_PATH}/extract"
ERROR_RERUN_PARSE_DIR="/Users/xkumag/dev/kat-57-pipeline/jobs/phase2_verification_error_rerun/parse"


# python3 process_requests.py /Users/xkumag/dev/kat-57-pipeline/jobs/phase1_verification_batch5/extract /Users/xkumag/dev/kat-57-pipeline/jobs/phase1_verification_error_rerun/parse -i /Users/xkumag/dev/kat-57-pipeline/jobs/phase1_verification_batch5/parse/fail -e /Users/xkumag/dev/kat-57-pipeline/jobs/phase1_verification_error_rerun/parse/success



echo "Checking Batch $BATCH..."

python3 process_requests.py "$EXTRACT_DIR" "$ERROR_RERUN_PARSE_DIR" -i "$CURRENT_JOBS_PATH/parse/fail" -e "$ERROR_RERUN_PARSE_DIR/success"

echo "All requested batches have been checked."


