from pathlib import Path
import argparse
import json
from numpy.random import sample
import pandas as pd
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from kortkat.prompt_data import PromptData, Content, TextPart

SYSTEM_INSTRUCTION = """### ROLE
You are an expert librarian and archivist. Your task is to assess whether the information in the extracted data from the catalog card matches the information in the record at the provided URL.

### ASSESSMENT CATEGORIES
#### Correct
Overall, it should be obvious that the information extraced from the catalog card describes the same work as the information in the record at the provided URL. This means that:
- The title matches, with minor discrepancies allowed.
- The author(s) match, with minor discrepancies allowed.
- The publication year matches, with NO discrepancies allowed.
- The publication place matches, with minor discrepancies allowed.
- There are NO discrepancies between the information in the extracted data from the catalog card and the information in the record at the provided URL in terms of edition, part or volumes.

#### Acceptable
Overall, the information extraced from the catalog card describes the same work as the information in the record at the provided URL, and with minor discrepancies allowed. This means that:
- The title matches, with minor discrepancies allowed.
- The author(s) match, with minor discrepancies allowed.
- The publication year matches, with NO discrepancies allowed.
- Discrepancies in publication place are allowed, but should be noted in the reasoning.
- Discrepancies in terms of edition, part or volumes are allowed, but should be noted in the reasoning.
- Discrepancies in terms of format are allowed.

#### Incorrect
The information extraced from the catalog card does NOT describe the same work as the information in the record at the provided URL."""

TEXT_PROMPT = "Assess whether the information in the extracted data from the catalog card matches the information in the record at the provided URL."

class Result(str, Enum):
    CORRECT = "Correct"
    ACCEPTABLE = "Acceptable"
    INCORRECT = "Incorrect"

class StructuredOutputSchema(BaseModel):
    result: Result = Field(description="The result of the assessment.")
    reasoning: Optional[str] = Field(description="The model's reasoning for its answer. This should be provided even if the model is not sure about the answer, and should explain why the model is not sure if that is the case.")


def build_prompt(extracted_data, libris_url):
    prompt = f"""{TEXT_PROMPT}

### Extracted data from catalog card:
{json.dumps(extracted_data)}

### URL for the matched record:
{libris_url}"""

    return prompt


def load_and_clean_extracted_data(extracted_data_directory, card_ID, edition_index, verbose):

    extracted_data_file = extracted_data_directory / f"{card_ID}.json"
    
    try:
        with open(extracted_data_file, 'r') as fp:
            extracted_data = json.load(fp)
            
        if verbose:
            print(f"✅ Successfully loaded extracted data for match: {card_ID}_{edition_index}")
    except Exception as e:
        if verbose:
            print(f"❌ Failed to load extracted data for match {card_ID}_{edition_index}: {e}")
        return None

    if "editions" not in extracted_data or not isinstance(extracted_data['editions'], list):
        if verbose:
            print(f"ℹ️  Skipping: {card_ID} has no 'editions' list.")
        return None
    
    if edition_index < len(extracted_data['editions']):        
        matching_edition = extracted_data['editions'][edition_index]
        extracted_data['editions'] = [matching_edition]
        if verbose:
            print(f"✅ Successfully filtered for edition {edition_index} in {card_ID}.json.")
    else:
        if verbose:
            print(f"⚠️ Skipping: Edition index {edition_index} is out of bounds for {card_ID}.json.")
        return None

    extracted_data.pop("subject_headings", None)
    extracted_data.pop("classification", None)
    extracted_data.pop("related_works", None)
    extracted_data.pop("is_reference_card", None)
    extracted_data.pop("is_diss", None)
    extracted_data.pop("author", None)
    extracted_data.pop("title", None)
    
    return extracted_data


def process_matches(matches, extracted_data_directory, output_directory, verbose):

    tasks = []
    output_directory.mkdir(parents=True, exist_ok=True)
    output_json_filename = output_directory / "verification_tasks.json"

    for match in matches:
        
        match_object_ID = match["match_object_ID"]
        card_ID = match["card_ID"]
        edition_index = match["edition_idx"]

        extracted_data = load_and_clean_extracted_data(extracted_data_directory, card_ID, edition_index, verbose)
        if extracted_data is None:
            if verbose:
                print(f"⚠️  Skipping match {match_object_ID} due to missing or invalid extracted data.")
            continue

        libris_url = f"{match["id"]}?vw=full&tab3=marc"

        prompt = build_prompt(extracted_data, libris_url)

        parts =[
            TextPart(type="text", data=prompt)
        ]

        task = PromptData(
            key=match_object_ID,
            prompt=[Content(role="user", parts=parts)],
            system_instruction=SYSTEM_INSTRUCTION,
            json_schema=StructuredOutputSchema.model_json_schema()
        )

        tasks.append(task)

    tasks_dicts = [task.model_dump() for task in tasks]

    with open(output_json_filename, 'w') as fp:
        json.dump(tasks_dicts, fp, indent=4)


def load_match_output(match_output_file):

    with open(match_output_file, 'r') as fp:
        match_output = json.load(fp)

    match_output = [match for match in match_output if match.get("match_stat") == "Single" and match.get("card_type") in ["Monografi", "Flerbandsverk"]]

    return match_output


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Verify the matches by generating prompts for the model to assess whether the information in the extracted data from the catalog card matches the information in the record at the provided URL.")
    parser.add_argument("source_batch_job_directory", type=Path, help="Path to the batch job directory containing the matches to verify")
    parser.add_argument("batch_job_directory", type=Path, help="Path to the batch job to run the verification task")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    source_batch_job_directory = args.source_batch_job_directory.expanduser().resolve()
    batch_job_directory = args.batch_job_directory.expanduser().resolve()

    match_output_file = source_batch_job_directory / "match" / "outputfile.json"
    extracted_data_directory = source_batch_job_directory / "post-process"

    matches = load_match_output(match_output_file)

    process_matches(matches, extracted_data_directory, batch_job_directory, args.verbose)
