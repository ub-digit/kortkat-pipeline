from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Prepare batch job directories and configurations")
    parser.add_argument("--job_name", type=str, help="Name of batch job, used to identify it")
    parser.add_argument("--note", type=str, help="Notes about this batch job")
    parser.add_argument("--from_pipeline", type=Path, help="Path to pipeline to copy and use as blueprint")
    parser.add_argument("--prompt_machine", type=str, help="Name of prompt machine to use for this batch job, used to identify it")
    
    args, machine_args = parser.parse_known_args()

    # Create batch job directory

    jobs_path = BASE_DIR / "jobs"
    batch_job_path = jobs_path / args.job_name

    
    try:
        batch_job_path.mkdir(parents=True, exist_ok=False)
        print(f"✅ Created batch job directory: {batch_job_path}")
    except FileExistsError as e:
        print("❌ Failed to create batch job directory. Batch job directory already exists.")
        raise e
    except Exception as e:
        print(f"❌ Failed to create batch job directory. {e}")
        raise e

    blueprint_path = jobs_path / args.from_pipeline if args.from_pipeline else BASE_DIR / "resources"
    blueprint_config_file = blueprint_path / "config.json"
    
    
    # Read blueprint config file
    try:
        with open(blueprint_config_file, 'r') as fp:
            config_data = json.load(fp)
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise e

    # Write job name 
    config_data["batch_pipeline_name"] = args.job_name

    # If note provided, write it
    if args.note:
        config_data["batch_pipeline_note"] = args.note    

    # Write config JSON
    config_file = batch_job_path / "config.json"

    try:
        with open(config_file, 'w', encoding='utf-8') as fp:
            json.dump(config_data, fp, indent=2)
            print(f"✅ Created config file: {config_file}")
    except Exception as e:
        print(f"❌ Failed to create config file: {e}")

    # Copy schema file and GT
    files_to_copy = [
        (blueprint_path / "structured_output_schema.py", batch_job_path),
        (blueprint_path / "yolo.json", batch_job_path)
    ]

    failed_copies = []
    for source_path, dest_path in files_to_copy:
        try:
            shutil.copy2(source_path, dest_path)
            print(f"✅ Successfully copied: {source_path}")
        except Exception as e:
            # If an error occurs, log it and continue
            print(f"❌ FAILED to copy {source_path}: {e}")
            failed_copies.append((source_path, str(e)))

    # Create pipeline subdirectorys
    Path(f"{batch_job_path}/extract").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_job_path}/parse").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_job_path}/match").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_job_path}/evaluate").mkdir(parents=False, exist_ok=False)

    
    # Run prompt machine if specified
    machine_args.extend(["--output_directory", str(batch_job_path)])

    if args.prompt_machine:
        cmd = [sys.executable, "-m", f"prompt_machines.{args.prompt_machine}"] + machine_args
    
        try:
            # subprocess.run executes the terminal command and waits for it to finish
            subprocess.run(cmd, check=True)
            print(f"✅ [{args.job_name}] Machine finished successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ [{args.job_name}] Machine failed with error code: {e.returncode}")
    else:
        print("ℹ️  No prompt machine specified. Batch job setup is complete, but no prompt machine was executed.")