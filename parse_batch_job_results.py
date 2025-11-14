
from pathlib import Path
import argparse
import json


def load_batch_job_results(batch_job_result_dir):

    batch_job_results_file_path = batch_job_result_dir / "batch_job_result.jsonl"

    try:
        with open(batch_job_results_file_path, 'r', encoding='utf-8') as f:
            # Use a list comprehension for a clean, one-line solution
            return [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"Error: The file '{batch_job_results_file_path}' was not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON on a line: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def parse_batch_job_results(batch_job_results, output_directory, verbose):
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "success").mkdir(parents=True, exist_ok=True)
    (output_directory / "fail").mkdir(parents=True, exist_ok=True)    

    total_candidate_tokens = 0
    total_prompt_tokens = 0
    total_thoughts_tokens = 0
    total_tokens = 0
    total_cached_tokens = 0

    number_of_results = len(batch_job_results)
    number_of_model_errors = 0
    number_of_parse_errors = 0

    markdown_parse_report_file_path = output_directory / f"parse_report.md"
    json_parse_report_file_path = output_directory / f"parse_report.json"
    
    for result in batch_job_results:
        key = result.get('key', 'unknown_key')
        output_json_file_path = output_directory / "success" / f"{key}.json"
        parse_error_file_path = output_directory / "fail" / f"{key}.parse_error"
        model_error_file_path = output_directory / "fail" / f"{key}.model_error"        
        
        # Safely navigate the JSON structure, result['response']['candidates'][0]['content']['parts'][0]['text']
        response = result.get("response", {})
        candidates = response.get("candidates")
        
        if candidates and len(candidates) > 0:
            # If candidates list exists and is not empty, get the text
            result_json = candidates[0].get('content', {}).get('parts', [{}])[0].get('text')
            if result_json:
                try:
                    result_json = json.loads(result_json)
                    with open(output_json_file_path, 'w', encoding='utf-8') as fp:
                        json.dump(result_json, fp, indent=4)
                    if verbose:
                        print(f"✅ Saved parsed result to {output_json_file_path}")
                except Exception as e:
                    number_of_parse_errors += 1
                    with open(parse_error_file_path, 'w', encoding='utf-8') as fp:
                        json.dump(result_json, fp, indent=4)
                    with open(output_json_file_path, 'w', encoding='utf-8') as fp:
                        json.dump(None, fp, indent=4)
                    if verbose:
                        print(f"❌ Error saving parsed result for key {key}: {e}")
            else:
                number_of_model_errors += 1
                with open(model_error_file_path, 'w', encoding='utf-8') as fp:
                        json.dump(result, fp, indent=4)
                with open(output_json_file_path, 'w', encoding='utf-8') as fp:
                        json.dump(None, fp, indent=4)
                if verbose:
                    print(f"❌ Error saving parsed result for key {key}: Model generated no response")
        else:
            # Handle cases where there are no candidates
            if verbose:
                print(f"🚫 BLOCKED/ERROR No candidates found.")

        usage_metadata = response.get("usageMetadata", {})
        candidates_token_count = usage_metadata.get("candidatesTokenCount", 0)
        prompt_token_count = usage_metadata.get("promptTokenCount", 0)
        thoughts_token_count = usage_metadata.get("thoughtsTokenCount", 0)
        total_token_count = usage_metadata.get("totalTokenCount", 0)
        cached_token_count = usage_metadata.get("cachedContentTokenCount", 0)

        total_candidate_tokens += candidates_token_count
        total_prompt_tokens += prompt_token_count
        total_thoughts_tokens += thoughts_token_count
        total_tokens += total_token_count
        total_cached_tokens += cached_token_count
    
    mean_candidate_tokens = round(total_candidate_tokens / number_of_results) if number_of_results > 0 else 0
    mean_prompt_tokens = round(total_prompt_tokens / number_of_results) if number_of_results > 0 else 0
    mean_thoughts_tokens = round(total_thoughts_tokens / number_of_results) if number_of_results > 0 else 0
    mean_total_tokens = round(total_tokens / number_of_results) if number_of_results > 0 else 0
    mean_cached_tokens = round(total_cached_tokens / number_of_results) if number_of_results > 0 else 0

    # print the statistics to a markdown file as a table
    parse_report_string = f"""
# Parse result
| Result | Count |
|--|--|
| Processed images: | {number_of_results} |
| Number of parse errors: | {number_of_parse_errors} |
| Number of model errors: | {number_of_model_errors} |

# Token count
| Category | Total | Mean |
|--|--|--|
| Input tokens | {total_prompt_tokens} | {mean_prompt_tokens} |
| Output tokens | {total_candidate_tokens} | {mean_candidate_tokens} |
| Thoughts tokens | {total_thoughts_tokens} | {mean_thoughts_tokens} |
| Total tokens | {total_tokens} | {mean_total_tokens} |
| Cached tokens | {total_cached_tokens} | {mean_cached_tokens} |
"""
    with open(markdown_parse_report_file_path, "w", encoding="utf-8") as fp:
        fp.write(parse_report_string)

    parse_report_json = {
        "processed_images": number_of_results,
        "parse_errors": number_of_parse_errors,
        "model_errors": number_of_model_errors,
        "token_count": {
            "input_tokens": {
                "total": total_prompt_tokens,
                "mean": mean_prompt_tokens
            },
            "output_tokens": {
                "total": total_candidate_tokens,
                "mean": mean_candidate_tokens
            },
            "thoughts_tokens": {
                "total": total_thoughts_tokens,
                "mean": mean_thoughts_tokens
            },
            "total_tokens": {
                "total": total_tokens,
                "mean": mean_total_tokens
            },
            "cached_tokens": {
                "total": total_cached_tokens,
                "mean": mean_cached_tokens
            }
        }
    }
    with open(json_parse_report_file_path, "w", encoding="utf-8") as fp:
        json.dump(parse_report_json, fp, indent=2, ensure_ascii=False)
        
    print(f"\nProcessed {number_of_results} images using:")    
    print(f"{"Category":<20} {"Total":<10} {"Mean":<15}")
    print("-" * 45)    
    print(f"{'Input tokens':<20} {total_prompt_tokens:<10} {mean_prompt_tokens:<15}")
    print(f"{'Output tokens':<20} {total_candidate_tokens:<10} {mean_candidate_tokens:<15}")
    print(f"{'Thoughts tokens':<20} {total_thoughts_tokens:<10} {mean_thoughts_tokens:<15}")
    print(f"{'Total tokens':<20} {total_tokens:<10} {mean_total_tokens:<15}")
    print(f"{'Cached tokens':<20} {total_cached_tokens:<10} {mean_cached_tokens:<15}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Parse batch job results JSONL file into separate JSON files')
    parser.add_argument('input_directory', type=Path, help='Path to the directory with the batch input file')
    parser.add_argument('output_directory', type=Path, help='Path to where to put the json output')
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")
    
    args = parser.parse_args()

    batch_job_results = load_batch_job_results(args.input_directory)

    parse_batch_job_results(batch_job_results , args.output_directory, args.verbose)