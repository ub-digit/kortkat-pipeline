import pandas as pd
from pathlib import Path
import argparse
import json

def process_directory(input_folder, output_folder):

    # Create output directory
    output_folder.mkdir(parents=True, exist_ok=True)

    # Loop over all files in the input folder    
    json_files = [f for f in sorted(input_folder.glob('*.json'))]

    for file in json_files:        
        try:
            with open(file, 'r', encoding='utf-8') as f: #Explicit encoding to handle various characters
                data = json.load(f)

                authors = []

                if "main_author" in data and data["main_author"]:
                    authors.append(data["main_author"]["name"])

                if "additional_persons" in data:
                    for person in data["additional_persons"]:
                        authors.append(person["name"])

                data["author"] = " ".join(authors)

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

    process_directory(args.processing_directory, args.processing_directory)


if __name__ == "__main__":
    main()

    