import argparse
import subprocess
import json
import os
from pathlib import Path
import shutil


def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config

def run_process_step(step_name, pipeline_directory, config_file, processing_directory):
    print(f"Running post-process step: {step_name}")
    
    command = ["python3", f"{step_name}.py", pipeline_directory, config_file, processing_directory]
    
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True
    )

def parse_arguments():
    parser = argparse.ArgumentParser(description="Update publication_type in JSON files for referenced cards.")
    parser.add_argument("pipeline_directory", type=Path, help="Directory containing the pipeline")
    parser.add_argument("config_file", type=Path, help="Path to pipeline config file (config.json)")
    parser.add_argument("input_directory", type=Path, help="Directory containing JSON files to enrich")
    parser.add_argument("output_directory", type=Path, help="Directory to save enriched JSON files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")
    return parser.parse_args()


def main():
    args = parse_arguments()

    pipeline_directory = args.pipeline_directory
    config_file = args.config_file
    input_dir = args.input_directory
    output_dir = args.output_directory

    os.makedirs(output_dir, exist_ok=True)

    post_process_steps = load_config(config_file).get("post_process_steps", [])

   
    print(f"Copying JSON files from {input_dir}")
    try:
        shutil.copytree(input_dir, output_dir, dirs_exist_ok=True)
        print("Directory copied successfully!")
    except Exception as e:
        print(f"Error copying directory: {e}")
        raise e

    for step in post_process_steps:        
        run_process_step(step, pipeline_directory, config_file, output_dir)
    

    

if __name__ == "__main__":
    main()