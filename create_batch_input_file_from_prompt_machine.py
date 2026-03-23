from pathlib import Path
import argparse
import json


def process_request(request_data, generation_config):

    # TODO: Process request data to build new request object.

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

    
    request = {
        # TODO: Key needs to come from somewhere, either in the request data object, or from the filename
        "key": request_data["key"],
        "request": {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": request_data["system_instruction"]}]
            },
            # TODO: Decide where to handle the generation config.
            "generationConfig": {
                "temperature": generation_config["temperature"],
                "topP": generation_config["top_p"],
                "topK": generation_config["top_k"],
                "stopSequences": generation_config["stopSequences"],
                "maxOutputTokens": generation_config["max_output_tokens"],
                "responseMimeType": generation_config["response_mime_type"],
                "mediaResolution": generation_config["media_resolution"],
                "thinkingConfig": {
                    "thinkingLevel": generation_config["thinking_level"]
                },
                "responseJsonSchema": request_data["json_schema"]
            }
        }
    }

    return request

def process_requests(input_file, output_directory, generation_config, verbose):
    total_requests = 0

    # Create output directory
    output_directory.mkdir(parents=True, exist_ok=True)

    # Save system instruction to file for future reference
    # report_filename = output_directory / "batch_input_file_creation_report.json"
    # report_object = {
    #     "time": f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}",
    #     "generation_config": generation_config
    # }
    # 
    # with open(report_filename, 'w') as fp:
    #     json.dump(report_object, fp, indent=4)

    output_jsonl_filename = output_directory / "batch_input_file.jsonl"

    if output_jsonl_filename.exists():
        output_jsonl_filename.unlink()


    # TODO: Open the input file, loop through the requests, process each request, and write to jsonl file.
    with open(input_file, 'r') as fp:
        tasks = json.load(fp)

        for i, task in enumerate(tasks):
            request = process_request(task, generation_config)

            with open(output_jsonl_filename, 'a') as fp:
                fp.write(json.dumps(request) + "\n")
            
            total_requests += 1            
            
            if verbose:
                print(f"Added request {request['key']} successfully.")

    
    # Check if any requests were processed, if not, halt this subprocess
    if total_requests == 0:
       print("No requests were processed. Please check the input directory and parameters.")
       exit(1)
    else:
       print(f"Added {total_requests} requests to batch input file: {output_jsonl_filename}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("input_file", type=Path, help="Path to the input file containing request data")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    # parser.add_argument("pipeline_directory", type=Path, help="Path to the pipeline directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()
    
    default_generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 1000,
        "response_mime_type": "application/json",
        "thinking_level": "LOW",
        "model": "gemini-3-flash-preview",
        "media_resolution": "MEDIA_RESOLUTION_MEDIUM",
        "stopSequences": ["\n\n"]
    }
    
    # generation_config = default_generation_config | config_data.get("generation_config", {})
    generation_config = default_generation_config

    process_requests(args.input_file, args.output_directory, generation_config, args.verbose)