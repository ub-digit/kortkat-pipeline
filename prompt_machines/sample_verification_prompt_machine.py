from pathlib import Path
import argparse
import json
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
The information extraced from the catalog card does NOT describe the same work as the information in the record at the provided URL.
"""

TEXT_PROMPT = "Assess whether the information in the extracted data from the catalog card matches the information in the record at the provided URL."

class Result(str, Enum):
    CORRECT = "Correct"
    ACCEPTABLE = "Acceptable"
    INCORRECT = "Incorrect"

class StructuredOutputSchema(BaseModel):
    result: Result = Field(description="The result of the assessment.")
    reasoning: Optional[str] = Field(description="The model's reasoning for its answer. This should be provided even if the model is not sure about the answer, and should explain why the model is not sure if that is the case.")


def build_prompt(extracted_data, libris_url):
    prompt = f"""
{TEXT_PROMPT}

### Extracted data from catalog card:
{json.dumps(extracted_data)}

### URL for the matched record:
{libris_url}
"""

    return prompt


def load_and_clean_extracted_data(extracted_data_directory, match_object_ID, verbose):

    box, card, edition_index = match_object_ID.split('_')
    edition_index = int(edition_index)
    card_ID = f"{box}_{card}"

    extracted_data_file = extracted_data_directory / f"{card_ID}.json"
    
    try:
        with open(extracted_data_file, 'r') as fp:
            extracted_data = json.load(fp)
            
        if verbose:
            print(f"✅ Successfully loaded extracted data for match_object_ID: {match_object_ID}")
    except Exception as e:
        if verbose:
            print(f"❌ Failed to load extracted data for match_object_ID {match_object_ID}: {e}")
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


def process_samples(samples, extracted_data_directory, output_directory, verbose):

    tasks = []
    output_directory.mkdir(parents=True, exist_ok=True)
    output_json_filename = output_directory / "verification_tasks.json"

    for sample in samples:
        
        match_object_ID = sample["match_object_ID"]

        # TODO Chech if samples match_object_ID returns a valid extracted data file, if not skip and print empty row
        extracted_data = load_and_clean_extracted_data(extracted_data_directory, match_object_ID, verbose)

        libris_url = f"https://libris.kb.se/bib/{sample['matched.matched_ID']}?vw=full&tab3=marc"

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


def load_sample_report(sample_report_file):
    # loads an excel file and convert to dictionary
    df = pd.read_excel(sample_report_file)
    return df.to_dict(orient="records")    


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("sample_report_file", type=Path, help="Path to the sample report file to use for generating the prompt")
    parser.add_argument("extracted_data_directory", type=Path, help="Path to the directory containing extracted data")    
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    samples = load_sample_report(args.sample_report_file)

    process_samples(samples, args.extracted_data_directory, args.output_directory, args.verbose)
