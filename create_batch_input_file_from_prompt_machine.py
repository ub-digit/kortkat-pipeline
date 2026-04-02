from pathlib import Path
import argparse
import json
from datetime import datetime


def process_request(request_data, batch_config):

    contents = []

    for prompt_part in request_data["prompt"]:
        content = {}
        content["role"] = prompt_part["role"]

        content["parts"] = []
        for p in prompt_part["parts"]:
            if p["type"] == "text":
                content["parts"].append({"text": p["data"]})                
            elif p["type"] == "inlineData":
                content["parts"].append({"inlineData": {"mimeType": p["mimeType"], "data": p["data"]}})
        
        contents.append(content)


    generation_config = batch_config["generation_config"]
    generation_config["responseJsonSchema"] = request_data["json_schema"]

    
    request = {
        "key": request_data["key"],
        "request": {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": request_data["system_instruction"]}]
            },
            "generationConfig": generation_config,
            "tools": batch_config["tools"]
        }
    }

    return request

def process_requests(input_file, output_directory, batch_config, verbose):
    total_requests = 0

    # Create output directory
    output_directory.mkdir(parents=True, exist_ok=True)

    # Save system instruction to file for future reference
    report_filename = output_directory / "batch_input_file_creation_report.json"
    report_object = {
        "time": f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}",
        "batch_config": batch_config
    }
    
    with open(report_filename, 'w') as fp:
        json.dump(report_object, fp, indent=4)

    output_jsonl_filename = output_directory / "batch_input_file.jsonl"

    if output_jsonl_filename.exists():
        output_jsonl_filename.unlink()

    with open(input_file, 'r') as fp:
        tasks = json.load(fp)

        for i, task in enumerate(tasks):
            request = process_request(task, batch_config)

            with open(output_jsonl_filename, 'a') as fp:
                fp.write(json.dumps(request) + "\n")
            
            total_requests += 1            
            
            if verbose:
                print(f"Added request {request['key']} successfully.")

    
    # Check if any requests were processed, if not, halt this subprocess
    if total_requests == 0:
       print("⚠️ No requests were processed. Please check the input directory and parameters.")
       exit(1)
    else:
       print(f"✅ Added {total_requests} requests to batch input file: {output_jsonl_filename}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("batch_job_directory", type=Path, help="Path to the batch job directory")
    parser.add_argument("input_file", type=Path, help="Path to the input file containing request data")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    config_file_path = args.batch_job_directory / "config.json"

    try:
        with open(config_file_path, 'r') as fp:
            config_data = json.load(fp)
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise e    

    process_requests(args.input_file, args.output_directory, config_data.get("batch_config"), args.verbose)