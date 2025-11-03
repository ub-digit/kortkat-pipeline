from resources.json_schema2 import StructuredOutputSchema
from pathlib import Path
import argparse
import json
import base64
from datetime import datetime

def process_image(image_path, generation_config):

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
                "maxOutputTokens": generation_config["max_output_tokens"],
                "responseMimeType": generation_config["response_mime_type"],
                "thinkingConfig": {
                    "thinkingBudget": generation_config["thinking_budget"]
                },
                "responseJsonSchema": StructuredOutputSchema.model_json_schema()
            }
        }
    }

    return request

def process_directory(input_directory, output_directory, generation_config, start_index, end_index, verbose):
    total_images = 0

    # Create output directory
    output_directory.mkdir(parents=True, exist_ok=True)

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
        result = process_image(image_files[i], generation_config)
        if result:            
            with open(jsonl_filename, 'a') as fp:
                fp.write(json.dumps(result) + "\n")
            total_images += 1            
            if verbose:
                print(f"Added image {image_files[i]} successfully.")
        else:
            if verbose:
                print(f"Failed to add image {image_files[i]}")
    print(f"Added {total_images} images to batch input file: {jsonl_filename}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("input_directory", type=Path, help="Path to the image directory")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("config_file", type=Path, help="Path to config file for content generation")
    parser.add_argument("--start_index", type=int, default=0, help="Starting index of images to process")
    parser.add_argument("--end_index", type=int, default=-1, help="Ending index of images to process (-1 for all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    try:
        with open(args.config_file, 'r') as fp:
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

    process_directory(args.input_directory, args.output_directory, generation_config, args.start_index, args.end_index, args.verbose)