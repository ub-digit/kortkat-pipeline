from pathlib import Path
import argparse
import json
import shutil

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Prepare batch job directories and configurations")
    parser.add_argument("batch_pipeline_name", type=str, help="Name of batch job, used to identify it")
    parser.add_argument("--from_pipeline", type=Path, help="Path to pipeline to copy and use as blueprint")
    
    args = parser.parse_args()

    blueprint_path = f"jobs/{args.from_pipeline}" if args.from_pipeline else "resources"

    print(blueprint_path)

    blueprint_config_file = Path(f"{blueprint_path}/config.json")
    
    batch_pipeline_directory = Path(f"jobs/{args.batch_pipeline_name}")
    # Read blueprint config file
    try:
        with open(blueprint_config_file, 'r') as fp:
            config_data = json.load(fp)
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise e

    # Write job name 
    config_data["batch_pipeline_name"] = args.batch_pipeline_name

    # Create batch pipeline directory
    try:
        batch_pipeline_directory.mkdir(parents=True, exist_ok=False)
        print(f"✅ Created batch job directory: {batch_pipeline_directory}")
    except FileExistsError as e:
        print("❌ Failed to create batch job directory. Batch job directory alread exists.")
        raise e
    except Exception as e:
        print(f"❌ Failed to create batch job directory. {e}")
        raise e

    # Write config JSON with
    config_file = batch_pipeline_directory / "config.json"

    try:
        with open(config_file, 'w', encoding='utf-8') as fp:
            json.dump(config_data, fp, indent=2)
            print(f"✅ Created config file: {config_file}")
    except Exception as e:
        print(f"❌ Failed to create config file: {e}")

    # Copy schema file and GT
    files_to_copy = [
        (f"{blueprint_path}/json_schema2.py", batch_pipeline_directory),
        (f"{blueprint_path}/gt.xlsx", batch_pipeline_directory)
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
    Path(f"{batch_pipeline_directory}/batch_job_input").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_pipeline_directory}/batch_job").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_pipeline_directory}/parsed_output").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_pipeline_directory}/matched").mkdir(parents=False, exist_ok=False)
    Path(f"{batch_pipeline_directory}/evaluated").mkdir(parents=False, exist_ok=False)