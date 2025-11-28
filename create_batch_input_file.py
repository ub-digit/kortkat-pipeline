from pathlib import Path
import argparse
import json
import base64
from datetime import datetime
import importlib.util
from pydantic import BaseModel
from typing import Type

def load_pydantic_class_from_file(instance_path: str, module_file_name: str, class_name: str) -> Type[BaseModel]:
    
    file_path = Path(instance_path) / module_file_name    
    
    module_name = file_path.stem

    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    
    if spec is None:
        raise FileNotFoundError(f"Could not load spec from file: {file_path}")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"Could not execute module {file_path}") from e

    try:
        pydantic_class = getattr(module, class_name)
    except AttributeError:
        raise AttributeError(f"Class '{class_name}' not found in module: {file_path}")
        
    return pydantic_class

def process_image(image_path, generation_config, schema):

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            base64_bytes = base64.b64encode(image_bytes)
            base64_string = base64_bytes.decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file '{image_path}' was not found.")
    
    request = {
        "key": image_path.stem,
        "request": {
            "contents": [{
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": "image/jpeg", "data": base64_string}},
                        {"text": generation_config["prompt_text_part"]}
                ]
            }],
            "systemInstruction": {
                "parts": [{"text": generation_config["system_instruction"]}]
            },
            "generationConfig": {
                "temperature": generation_config["temperature"],
                "topP": generation_config["top_p"],
                "topK": generation_config["top_k"],
                "stopSequences": generation_config["stopSequences"],
                "maxOutputTokens": generation_config["max_output_tokens"],
                "responseMimeType": generation_config["response_mime_type"],
                "thinkingConfig": {
                    "thinkingBudget": generation_config["thinking_budget"]
                },
                "responseJsonSchema": schema.model_json_schema()
            }
        }
    }

    return request

def process_directory(input_directory, output_directory, pipeline_directory, generation_config, start_index, end_index, verbose):
    total_images = 0

    # Create output directory
    output_directory.mkdir(parents=True, exist_ok=True)

    # Load instance-specific schema
    SCHEMA_CLASS = "StructuredOutputSchema"
    SCHEMA_FILE = "structured_output_schema.py"
    

    try:
        # Dynamically load the class
        print(f"Loading {SCHEMA_CLASS} from {pipeline_directory}/{SCHEMA_FILE}...")
        StructuredOutputSchema = load_pydantic_class_from_file(
            pipeline_directory,
            SCHEMA_FILE, 
            SCHEMA_CLASS
        )
        
        # Now you can use it just like a regularly imported class
        print(f"Successfully loaded: {StructuredOutputSchema}")


    except (FileNotFoundError, AttributeError, RuntimeError) as e:
        print(f"\n--- ERROR ---")
        print(f"Failed to load or use dynamic schema: {e}")
        # Handle the error (e.g., stop the pipeline)


    # Save system instruction to file for future reference
    report_filename = output_directory / "batch_creation_report.json"
    report_object = {
        "time": f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}",
        "generation_config": generation_config,
        "json_schema": StructuredOutputSchema.model_json_schema()
    }
    
    with open(report_filename, 'w') as fp:
        json.dump(report_object, fp, indent=4)

    # Loop over all files in the input directory
    image_files = [f for f in sorted(input_directory.glob('*.jpg'))]

    if start_index != 0:
        start_index -= 1

    if end_index == -1:
        end_index = len(image_files)

    jsonl_filename = output_directory / "batch_input.jsonl"

    # delete existing jsonl file if exists
    if jsonl_filename.exists():
        jsonl_filename.unlink()

    for i in range(start_index, end_index):        
        result = process_image(image_files[i], generation_config, StructuredOutputSchema)
        if result:            
            with open(jsonl_filename, 'a') as fp:
                fp.write(json.dumps(result) + "\n")
            total_images += 1            
            if verbose:
                print(f"Added image {image_files[i]} successfully.")
        else:
            if verbose:
                print(f"Failed to add image {image_files[i]}")

    # Check if any images were processed, if not, halt this subprocess
    if total_images == 0:
       print("No images were processed. Please check the input directory and parameters.")
       exit(1)
    else:
       print(f"Added {total_images} images to batch input file: {jsonl_filename}")



if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("input_directory", type=Path, help="Path to the image directory")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("pipeline_directory", type=Path, help="Path to the pipeline directory")
    parser.add_argument("--start_index", type=int, default=0, help="Starting index of images to process")
    parser.add_argument("--end_index", type=int, default=-1, help="Ending index of images to process (-1 for all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    config_file_path = args.pipeline_directory / "config.json"

    try:
        with open(config_file_path, 'r') as fp:
            config_data = json.load(fp)
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise e
    
    default_generation_config = {
        "temperature": 0,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 1000,
        "response_mime_type": "application/json",
        "thinking_budget": 0,
        "system_instruction": "You are an experienced librarian. Your task is to parse the input image of the library card and extract all data points into the provided JSON schema. Do not output any narrative text or extraneous characters. Be meticulous and conservative in your extraction; only infer when absolutely necessary. The catalog conforms to the prussian instructions for cataloging.",
        "prompt_text_part": "Extract the bibliographic information according to the instructions.",
        "model": "gemini-2.5-flash"
    }
    
    generation_config = default_generation_config | config_data.get("generation_config", {})

    process_directory(args.input_directory, args.output_directory, args.pipeline_directory, generation_config, args.start_index, args.end_index, args.verbose)