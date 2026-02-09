import argparse
import json
from pathlib import Path
import pandas as pd
import shutil

def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config

def update_json_file(json_path, schema_version, verbose):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            if len(data) != 1:
                print(f"⚠️  Skipping {json_path.name}: expected single-object list.")
                return
            obj = data[0]
        elif isinstance(data, dict):
            obj = data
        else:
            print(f"⚠️  Skipping {json_path.name}: unexpected JSON structure.")
            return
        
        if schema_version == 1:
            obj["publication_type"] = "cross-reference"
        elif schema_version == 2:
            obj["is_reference_card"] = True
        else:
            print(f"⚠️  Skipping {json_path.name}: unsupported schema version {schema_version}.")
            return

        # Write back, preserving the original structure
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if verbose:
            print(f"✅ Updated: {json_path.name}")

    except Exception as e:
        if verbose:
            print(f"❌ Error processing {json_path.name}: {e}")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Update publication_type in JSON files for referenced cards.")
    parser.add_argument("pipeline_directory", type=Path, help="Directory containing the pipeline")
    parser.add_argument("config_file", type=Path, help="Path to pipeline config file (config.json)")
    parser.add_argument("processing_directory", type=Path, help="Directory containing JSON files to enrich")
    parser.add_argument("--schema-version", type=int, default=2, help="Schema version to use (default: 1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")
    return parser.parse_args()


def main():
    args = parse_arguments()

    pipeline_directory = args.pipeline_directory
    config_file = args.config_file
    processing_directory = args.processing_directory

    config_data = load_config(config_file)

    processing_arguments = config_data.get("post_process_arguments", {}).get("enrich_with_yolo", {})
    yolo_data_path = Path(pipeline_directory / processing_arguments.get("yolo_data_path")).resolve()

    
    # load json array
    try:
        with open(yolo_data_path, 'r', encoding='utf-8') as f:
            yolo_data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read yolo json file: {e}")
        return
   
        
    for card in yolo_data:
        json_file = processing_directory / f"{card}.json"
        if json_file.exists():
            update_json_file(json_file, args.schema_version, args.verbose)


if __name__ == "__main__":
    main()