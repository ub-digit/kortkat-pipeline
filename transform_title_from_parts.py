import pandas as pd
from pathlib import Path
import argparse
import json

def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config

def process_directory(input_folder, output_folder, parts_to_include):
    
    # Create output directory
    output_folder.mkdir(parents=True, exist_ok=True)

    # Loop over all files in the input folder    
    json_files = [f for f in sorted(input_folder.glob('*.json'))]

    for file in json_files:        
        try:
            with open(file, 'r', encoding='utf-8') as f: #Explicit encoding to handle various characters
                data = json.load(f)

                titles = []
                fields_to_concatenate = []

                for part in parts_to_include:
                    fields_to_concatenate.append(data["title_statement"].get(part, ""))
                
                full_title = " ".join([field for field in fields_to_concatenate if field])
                data["title"] = full_title


            output_file = output_folder / file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
        except FileNotFoundError:
            print(f"Error: File not found at {file}")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {file}")
        except Exception as e: # Catch other potential errors
            print(f"An unexpected error occurred while processing {file}: {e}")


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

    config_file = args.config_file
    processing_directory = args.processing_directory

    config_data = load_config(config_file)

    processing_arguments = config_data.get("post_process_arguments", {}).get("transform_title_from_parts", {})
    parts_to_include = processing_arguments.get("parts_to_include")

    process_directory(processing_directory, processing_directory, parts_to_include)


if __name__ == "__main__":
    main()