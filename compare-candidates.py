import argparse
import json
from pathlib import Path
import requests
import pandas as pd
from pydantic import BaseModel, Field

class ComparisonResponseSchema(BaseModel):
    result: str = Field(description="Indicates whether a correct match was found: 'one' or 'none'")
    correct_id: str = Field(description="The ID found in the tag <controlfield tag='001'>")
    reason: str = Field(description="A very short description of the reason for the assessment")


def build_request(prompt_parts, generation_config):

    request_contents_parts = []

    request_contents_parts.append(
        {"text": "Extracted data:\n" + json.dumps(prompt_parts["extracted_data"])}
    )
    for i, record in enumerate(prompt_parts["libris_records"]):
        request_contents_parts.append(
            {"text": f"Candidate {i+1}:\n{record}"}
        )

    request = {
        "key": prompt_parts["match_object_ID"],
        "request": {
            "contents": [{
                    "role": "user",
                    "parts": request_contents_parts
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
                "responseJsonSchema": ComparisonResponseSchema.model_json_schema()
            }
        }
    }

    return request


def build_input_file_contents(prompt_contents, output_directory, generation_config):

    output_directory.mkdir(parents=True, exist_ok=True)
    output_file_path = output_directory / "batch_input.jsonl"

    total_requests = 0

    for i, prompt_parts in enumerate(prompt_contents):
        request = build_request(prompt_parts, generation_config)
        with output_file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(request) + "\n")
        total_requests += 1

    if total_requests == 0:
       print("❌ No requests were processed. Please check the input directory and parameters.")
       exit(1)
    else:
       print(f"✅ Successfully wrote batch input file with {total_requests} requests to {output_file_path}")


def get_libris_record(libris_id, verbose):

    api_url = f"https://libris.kb.se/xsearch?query=ONR:{libris_id}&format_level=full"
    if verbose:
        print(f"Getting data for Libris ID {libris_id}...")

    Path("jobs/libris_data").mkdir(parents=True, exist_ok=True)

    xml_file_path = Path(f"jobs/libris_data/{libris_id}.xml")
    if xml_file_path.exists():
        if verbose:
            print(f"ℹ️  Found existing XML file for Libris ID {libris_id}")
        with xml_file_path.open("r", encoding="utf-8") as xml_file:
            return xml_file.read()
    else:
        if verbose:
            print(f"ℹ️  No existing XML file found for Libris ID {libris_id}, fetching from API...")
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            with xml_file_path.open("w", encoding="utf-8") as xml_file:
                xml_file.write(response.text)
            return response.text    
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"❌ API call failed for Libris ID {libris_id}: {e}")
            return None
        

def get_extracted_data(match_object_id, extracted_data_directory, verbose):

    card_id, edition_index = match_object_id.rsplit('_', 1)
    edition_index = int(edition_index)
    json_file_path = Path(f"{extracted_data_directory}/{card_id}.json")

    if not json_file_path.exists():
        if verbose:
            print(f"❌ Extracted data file not found for Card ID {card_id}")
        return None

    try:
        with json_file_path.open("r", encoding="utf-8") as json_file:
            extracted_data = json.load(json_file)
        if verbose:
            print(f"✅ Successfully loaded extracted data for Card ID {card_id}")            
    except json.JSONDecodeError as e:
        if verbose:
            print(f"❌ Failed to decode JSON for Card ID {card_id}: {e}")
        return None

    if "editions" not in extracted_data or not isinstance(extracted_data['editions'], list):
        if verbose:
            print(f"ℹ️  Skipping: {card_id} has no 'editions' list.")
        return None

    if edition_index < len(extracted_data['editions']):        
        matching_edition = extracted_data['editions'][edition_index]
        extracted_data['editions'] = [matching_edition]
        if verbose:
            print(f"✅ Successfully filtered for edition {edition_index} in {card_id}.")
    else:
        if verbose:
            print(f"⚠️ Skipping: Edition index {edition_index} is out of bounds for {card_id}.")

    return extracted_data
    

def get_prompt_contents(match_objects_with_candidates, extracted_data_directory, verbose):

    prompt_contents = []

    for candidate in match_objects_with_candidates:
        match_object_id = candidate['match_object_ID']
        libris_ids = candidate['libris_IDs']
        if verbose:
            print(f"Processing Match Object ID: {match_object_id} with {len(libris_ids)} candidates.")       

        extracted_data = get_extracted_data(match_object_id, extracted_data_directory, verbose)

        libris_records = []

        for libris_id in libris_ids:
            xml_data = get_libris_record(libris_id, verbose)
            if xml_data:
                if verbose:
                    print(f"✅ Successfully retrieved data for Libris ID {libris_id}")
            else:
                if verbose:
                    print(f"❌ Failed to retrieve data for Libris ID {libris_id}")

            libris_records.append(xml_data)

        prompt_contents.append(
            {
                "match_object_ID": match_object_id,
                "extracted_data": extracted_data,
                "libris_records": libris_records
            }
        )

    return prompt_contents


def get_candidates_for_match_object(matches_df, number_of_candidates = 3):

    top_n_df = (
        matches_df.sort_values(by='similarity', ascending=False)
        .groupby('match_object_ID')
        .head(number_of_candidates)
    )
    
    match_objects_with_candidates = (
        top_n_df.groupby('match_object_ID')['matched_ID']
        .apply(lambda x: [id for id in x if pd.notna(id)])
        .reset_index(name='libris_IDs')
    )
    
    match_objects_with_candidates = match_objects_with_candidates[
        match_objects_with_candidates['libris_IDs'].apply(len) > 0
    ].to_dict(orient='records')

    return match_objects_with_candidates


def load_matches(matches_file_path, verbose):

    try:
        matches_df = pd.read_excel(matches_file_path)
        if verbose:
            print(f"✅ Successfully loaded matches file: {matches_file_path}")
        return matches_df
    except Exception as e:
        print(f"❌ Failed to load matches file: {e}")
        return None


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Compare extracted data to libris records for match candidates")
    parser.add_argument("pipeline_directory", type=Path, help="Path to the pipeline directory")
    parser.add_argument("match_output_file", type=str, help="Path to excel file with matches")
    parser.add_argument("extracted_data_directory", type=Path, help="Path to folder containing extracted data")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")    
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
        "system_instruction": "You are an experienced librarian. You are presented with extracted bibliographic data from a library card and multiple candidate records from a library catalog. Your task is to compare the extracted data with each candidate record and determine if any of the candidates match the extracted information. Respond with the ID in the tag <controlfield tag='001'> for the correct candidate. Provide your answer in the specified JSON format. Be meticulous and conservative in your evaluation; only infer when absolutely necessary. The catalog conforms to the prussian instructions for cataloging.",
        "prompt_text_part": "Does any of the candidate records match the extracted bibliographic data?",
        "model": "gemini-2.5-flash"
    }
    
    generation_config = default_generation_config | config_data.get("comparison_generation_config", {})

    matches_df = load_matches(args.match_output_file, args.verbose)
    if matches_df is None:
        exit(1)
    else:
        match_objects_with_candidates = get_candidates_for_match_object(matches_df)

    prompt_contents = get_prompt_contents(match_objects_with_candidates, args.extracted_data_directory, args.verbose)

    build_input_file_contents(prompt_contents, args.output_directory, default_generation_config)
