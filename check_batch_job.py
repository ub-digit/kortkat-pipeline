from google import genai
from google.genai import types
from pathlib import Path
import argparse
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

def check_batch_job(batch_job_directory, client):
    batch_info_file = batch_job_directory / "batch_job_info.json"
    try:
        with open(batch_info_file, 'r') as fp:
            batch_job_info = json.load(fp)
    except Exception as e:
        print(f"Error loading batch job info: {e}")
        raise e
    
    batch_job_name = batch_job_info.get("name")
    
    print(f"Polling status for job: {batch_job_name}")

    # Poll the job status until it's completed.
    while True:
        batch_job = client.batches.get(name=batch_job_name)
        if batch_job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            break
        print(f"Job not finished. Current state: {batch_job.state.name}. Waiting 10 seconds...")
        time.sleep(10)

    print(f"Job finished with state: {batch_job.state.name}")
    if batch_job.state.name == 'JOB_STATE_FAILED':
        print(f"Error: {batch_job.error}")

    if batch_job.state.name == 'JOB_STATE_SUCCEEDED':
        # The output is in another file.
        result_file_name = batch_job.dest.file_name
        print(f"Results are in file: {result_file_name}")

        print("\nDownloading result file content...")
        file_content_bytes = client.files.download(file=result_file_name)
        file_content = file_content_bytes.decode('utf-8')
        #save file content to output directory
        output_file_path = batch_job_directory / "batch_job_result.jsonl"
        with open(output_file_path, 'w', encoding='utf-8') as fp:
            fp.write(file_content)
        print(f"Results saved to {output_file_path}")

    else:
        print(f"Job did not succeed. Final state: {batch_job.state.name}")

    batch_job_info_filename = batch_job_directory / "batch_job_info.json"
    batch_job_info = batch_job.model_dump_json(indent=4)
    with open(batch_job_info_filename, 'w') as fp:
        fp.write(batch_job_info)


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Check status of batch job.")
    parser.add_argument("batch_job_directory", type=Path, help="Path to the directory containing a batch info file")
    parser.add_argument("pipeline_directory", type=Path, help="Path to the pipeline directory")

    args = parser.parse_args()

    client = genai.Client(api_key=API_KEY)

    check_batch_job(args.batch_job_directory, client)

    