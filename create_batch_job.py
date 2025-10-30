from google import genai
from google.genai import types
from pathlib import Path
import argparse
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

def create_batch_job(batch_input_file, output_directory, client, job_name, generation_config):

    batch_job = client.batches.create(
        model=generation_config["model"],
        src=batch_input_file.name,
        config={
            'display_name': job_name,
        }
    )
    if batch_job:
        batch_job_name = batch_job.name

        batch_job_info = batch_job.model_dump_json(indent=4)

    # save job info to file
    job_info_filename = output_directory / "batch_job_info.json"
    with open(job_info_filename, 'w') as fp:
        fp.write(batch_job_info)
    
    print(f"Created batch job from file: {batch_job_name}")

def upload_input_file(input_file_path, client, job_name):

    display_name = job_name + "_input_file"

    print(f"Uploading input file: {input_file_path}...")
    try:
        uploaded_batch_file = client.files.upload(
            file=input_file_path,
            # config=types.UploadFileConfig(display_name=display_name, mime_type="application/jsonl")
            config=types.UploadFileConfig(display_name=display_name, mime_type="text/plain")
        )
        print(f"Uploaded file: {uploaded_batch_file.name}")
        return uploaded_batch_file
    except Exception as e:
        print(f"Error uploading file: {e}")
        raise e   

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Create batch job from input directory.")
    parser.add_argument("input_directory", type=Path, help="Path to the batch input directory")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("config_file", type=Path, help="Path to config file for content generation")

    args = parser.parse_args()

    try:
        with open(args.config_file, 'r') as fp:
            config_data = json.load(fp)
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise e
    
    default_generation_config = {
        "model": "gemini-2.5-flash"
    }

    job_name = config_data["batch_pipeline_name"]
    generation_config = default_generation_config | config_data.get("generation_config", {})

    client = genai.Client(api_key=API_KEY)

    batch_input_file_name = args.input_directory / "batch_input.jsonl"

    uploaded_batch_input_file = upload_input_file(batch_input_file_name, client, job_name)

    create_batch_job(uploaded_batch_input_file, args.output_directory, client, job_name, generation_config)