from pathlib import Path
import argparse
import json
from google import genai
import os
from dotenv import load_dotenv
import kortkat

load_dotenv()
API_KEY = os.getenv("API_KEY")
MODEL = "gemini-3-flash-preview"


def log_error(filename, msg):

    with open(filename, 'w') as fp:
        fp.write(str(msg))


def generate_content(client, generation_config, contents, model_error_filename, retries=10):
    try:
        result = client.models.generate_content(
            model = MODEL,
            contents=contents,
            config=generation_config
        )
        return result
    except Exception as e:
        if retries <= 0:
            log_error(model_error_filename, str(e))        
            print(e)
            return False
        else:
            print("Retrying...")
            return generate_content(client, generation_config, contents, model_error_filename, retries-1)


def process_request(request, output_directory):    
    generation_config = request["request"]["generationConfig"]
    generation_config["system_instruction"] = request["request"]["systemInstruction"]["parts"][0]["text"]
    contents = request["request"]["contents"]

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "success").mkdir(parents=True, exist_ok=True)
    (output_directory / "fail").mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=API_KEY)

    json_filename = output_directory / "success" / f"{request['key']}.json"
    parse_error_filename = output_directory / "fail" / f"{request['key']}_parse_error.json"
    model_error_filename = output_directory / "fail" / f"{request['key']}_model_error.json"

    result = generate_content(client, generation_config, contents, model_error_filename)

    if result == False:
        print(f"❌ Failed: {request['key']}")
        return False
    
    try:
        if not kortkat.validate_json(result.text):
            log_error(parse_error_filename, result)
            print(f"❌ Failed: {request['key']}")
            return False
        json_object = json.loads(result.text)        
        with open(json_filename, 'w') as fp:
            json.dump(json_object, fp, indent=4)

        print(f"✅ Success: {request['key']}")    
        return result
    except:
        log_error(parse_error_filename, result)
        print(f"❌ Failed: {request['key']}")
        return False


def process_requests(filtered_requests_input, output_directory):
    for request in filtered_requests_input:
        process_request(request, output_directory)


def filter_requests_input(batch_job_input, keys_to_include, keys_to_exclude):

    # IF length of keys_to_include is greater than 0, use it as the filtered_request_keys, otherwise use all keys from batch_job_input
    if len(keys_to_include) > 0:
        filtered_request_keys = keys_to_include
    else:
        filtered_request_keys = [request["key"] for request in batch_job_input]

    # Filter out keys that are in keys_to_exclude
    filtered_request_keys = [key for key in filtered_request_keys if key not in keys_to_exclude]

    filtered_requests_input = [request for request in batch_job_input if request["key"] in filtered_request_keys]

    return filtered_requests_input


def load_batch_job_input(batch_job_input_directory: Path):
    batch_job_input_file_path = batch_job_input_directory / "batch_input_file.jsonl"
    with open(batch_job_input_file_path, "r", encoding="utf-8") as fp:
        batch_job_input = [json.loads(line) for line in fp]

    return batch_job_input


def load_keys(directory: Path):
    keys = []
    if directory:
        request_files = [f for f in sorted(directory.glob('*.json'))]
        keys = ["_".join(f.stem.split("_")[:2]) for f in request_files]

    return keys
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process request synchronously based on batch job input file and save results to output directory. Optionally filter which requests to process based on include and exclude directories with json files beginning with [box_card] as the request key.')
    parser.add_argument('input_directory', type=Path, help='Path to the directory with the batch input file')
    parser.add_argument('output_directory', type=Path, help='Path to where to put the json output')
    parser.add_argument('-i', '--include_directory', type=Path, help='Path to directory with files to include in processing', default=None)
    parser.add_argument('-e', '--exclude_directory', type=Path, help='Path to directory with files to exclude from processing', default=None)

    args = parser.parse_args()

    keys_to_include = load_keys(args.include_directory)
    keys_to_exclude = load_keys(args.exclude_directory)

    batch_job_input = load_batch_job_input(args.input_directory)
    filtered_requests_input = filter_requests_input(batch_job_input, keys_to_include, keys_to_exclude)
    if len(filtered_requests_input) == 0:
        print("⚠️  No requests to process after filtering. Exiting.")
        exit(0)

    process_requests(filtered_requests_input, args.output_directory)