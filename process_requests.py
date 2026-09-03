from pathlib import Path
import argparse
import json
from google import genai
import os
from dotenv import load_dotenv
import kortkat

load_dotenv()
API_KEY = os.getenv("API_KEY")


def log_error(filename, msg):

    with open(filename, 'w') as fp:
        fp.write(str(msg))


def generate_content(client, model, generation_config, contents, model_error_filename, retries=10):
    try:
        result = client.models.generate_content(
            model = model,
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


def process_request(request, output_directory, model):

    token_counts = {
        "prompt_token_count": 0,
        "candidates_token_count": 0,
        "thoughts_token_count": 0,
        "cached_content_token_count": 0,
        "total_token_count": 0
    }

    generation_config = request["request"]["generationConfig"]
    generation_config["system_instruction"] = request["request"]["systemInstruction"]["parts"][0]["text"]
    generation_config["tools"] = request["request"]["tools"]
    contents = request["request"]["contents"]

    client = genai.Client(api_key=API_KEY)

    json_filename = output_directory / "success" / f"{request['key']}.json"
    parse_error_filename = output_directory / "fail" / f"{request['key']}_parse_error.json"
    model_error_filename = output_directory / "fail" / f"{request['key']}_model_error.json"

    result = generate_content(client, model, generation_config, contents, model_error_filename)
    
    if not result:
        print(f"❌ Failed: {request['key']}")
        return False, None
        
    try:
        if not kortkat.validate_json(result.text):
            log_error(parse_error_filename, result)
            print(f"❌ Failed: {request['key']}")
            return False, None
        
        json_object = json.loads(result.text)        
        with open(json_filename, 'w') as fp:
            json.dump(json_object, fp, indent=4)

        if hasattr(result, 'usage_metadata') and result.usage_metadata:
            token_counts["prompt_token_count"] = result.usage_metadata.prompt_token_count or 0
            token_counts["candidates_token_count"] = result.usage_metadata.candidates_token_count or 0
            token_counts["thoughts_token_count"] = result.usage_metadata.thoughts_token_count or 0
            token_counts["cached_content_token_count"] = result.usage_metadata.cached_content_token_count or 0
            token_counts["total_token_count"] = result.usage_metadata.total_token_count or 0

        print(f"✅ Success: {request['key']} - {token_counts['prompt_token_count']} prompt tokens, {token_counts['candidates_token_count']} candidate tokens, {token_counts['thoughts_token_count']} thought tokens")
        return True, token_counts
    
    except Exception as e:
        print(f"❌ Failed: {request['key']} - {e}")
        log_error(parse_error_filename, result)        
        return False, None


def process_requests(filtered_requests_input, output_directory, model):
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "success").mkdir(parents=True, exist_ok=True)
    (output_directory / "fail").mkdir(parents=True, exist_ok=True)

    stats = {
        "successful_requests": 0,
        "failed_requests": 0,
        "total_prompt_tokens": 0,
        "total_candidate_tokens": 0,
        "total_thought_tokens": 0,
        "total_cached_content_tokens": 0,
        "total_tokens": 0
    }
    
    try:
        for request in filtered_requests_input:
            is_success, token_counts = process_request(request, output_directory, model)
            if is_success and token_counts:
                stats["successful_requests"] += 1
                stats["total_prompt_tokens"] += token_counts["prompt_token_count"]
                stats["total_candidate_tokens"] += token_counts["candidates_token_count"]
                stats["total_thought_tokens"] += token_counts["thoughts_token_count"]
                stats["total_cached_content_tokens"] += token_counts["cached_content_token_count"]
                stats["total_tokens"] += token_counts["total_token_count"]
            else:
                stats["failed_requests"] += 1
    
    except KeyboardInterrupt:
        print("\n⚠️  Processing interrupted by user. Generating summary for completed requests...")

    finally:
        total_requests = stats["successful_requests"] + stats["failed_requests"]

        print("\n" + "="*30)
        print("📊 PROCESSING SUMMARY")
        print("="*30)
        print(f"Total Requests: {total_requests}")
        print(f"Successful:     {stats['successful_requests']}")
        print(f"Failed:         {stats['failed_requests']}")
        
        if stats["successful_requests"] > 0:
            print("\n--- Token Usage (Successful Requests) ---")
            print(f"Total Tokens Used:           {stats['total_tokens']}")
            print(f"Total Prompt Tokens:         {stats['total_prompt_tokens']}")
            print(f"Total Candidate Tokens:      {stats['total_candidate_tokens']}")
            print(f"Total Thought Tokens:        {stats['total_thought_tokens']}")
            print(f"Total Cached Content Tokens: {stats['total_cached_content_tokens']}")
            
            mean_total = stats['total_tokens'] / stats["successful_requests"]
            mean_prompt = stats['total_prompt_tokens'] / stats["successful_requests"]
            mean_candidate = stats['total_candidate_tokens'] / stats["successful_requests"]
            mean_thoughts = stats['total_thought_tokens'] / stats["successful_requests"]
            mean_cached_content = stats['total_cached_content_tokens'] / stats["successful_requests"]
            
            print("\n--- Average Per Successful Request ---")
            print(f"Mean Total Tokens:     {mean_total:.0f}")
            print(f"Mean Prompt Tokens:    {mean_prompt:.0f}")
            print(f"Mean Candidate Tokens: {mean_candidate:.0f}")
            print(f"Mean Thought Tokens:   {mean_thoughts:.0f}")
            print(f"Mean Cached Content Tokens: {mean_cached_content:.0f}")


def filter_requests_input(batch_job_input, keys_to_include, keys_to_exclude):

    if len(keys_to_include) > 0:
        filtered_request_keys = keys_to_include
    else:
        filtered_request_keys = [request["key"] for request in batch_job_input]

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
        # We need to remove the suffixes from the filenames to get the request keys, which are in the format [key].json or [key]_[error_type].json where error_type can be one of
        # ["parse_error", "model_error", "api_error"]
        for f in request_files:
            key = f.stem
            for suffix in ["_parse_error", "_model_error", "_api_error"]:
                if key.endswith(suffix):
                    key = key[:-len(suffix)]
                    break
            keys.append(key)

    return keys
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process request synchronously based on batch job input file and save results to output directory. Optionally filter which requests to process based on include and exclude directories with json files beginning with [box_card] as the request key.')
    parser.add_argument('input_directory', type=Path, help='Path to the directory with the batch input file')
    parser.add_argument('output_directory', type=Path, help='Path to where to put the json output')
    parser.add_argument('model', type=str, help='Model to use for processing requests')
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

    process_requests(filtered_requests_input, args.output_directory, args.model)