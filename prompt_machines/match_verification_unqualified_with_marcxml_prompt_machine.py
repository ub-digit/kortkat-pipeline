from pathlib import Path
import argparse
import json
from numpy.random import sample
import pandas as pd
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from kortkat.prompt_data import PromptData, Content, TextPart
from elasticsearch import Elasticsearch
import io
import pymarc

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "records"

SYSTEM_INSTRUCTION = """### ROLE
You are an expert librarian and archivist. Your task is to assess whether the record extracted from a catalog card matches the information in the MARCXML record.

### Overall instructions
- **Strict Evidence-Based Evaluation:** Base your assessment solely on the provided text. Do not invent context or make assumptions about cataloger intent.
- **BIBFRAME 2.0 as a reference:** You are evaluating matches at the Work and Instance levels according to the BIBFRAME 2.0 model. A Work represents the conceptual essence of the cataloged resource (the core title, authorship, and language). An Instance represents a specific physical or digital embodiment of a Work (e.g., a specific edition published by a specific publisher in a specific year and place).
- **Evaluating Language:** The extracted iso_language_code and iso_language_name are AI-generated and frequently incorrect (e.g., guessing Latin when the text is Greek, or Swedish when the text is Sami). The MARCXML record can also contain incorrect language codes caused by cataloging mistakes. Do not fail a match based solely on the language codes. To determine if the language actually differs, you must look for concrete textual evidence (title wording, statement of responsibility).
- **Danish/Norwegian Overlap:** Historically, written Danish and Norwegian (Riksmål) were nearly identical. Treat discrepancies between Danish and Norwegian language codes as matching Works if the title, author, and year match.
- **Authorship Flexibility:** The extraction tool may occasionally put the subject of a biography, an editor, or a compiler into the main_author field. Always cross-reference the extracted author with the MARCXML 700 fields (added entries) and the title string. If the person exists in both records in any capacity, do not fail the match on authorship alone.

### ASSESSMENT CATEGORIES
#### Correct
It should be obvious that the catalog card and the MARCXML record describe the same Instance according to BIBFRAME 2.0. The physical details align.

#### Acceptable
It should be obvious that the catalog card and the MARCXML record describe the same Work according to BIBFRAME 2.0, even if they represent different Instances.
Note: A valid part/whole relationship is allowed ONLY if one record describes a multi-volume Work and the other describes a specific volume or page range of that exact same Work. It does NOT apply to translations or series.

You MUST tolerate the following Instance discrepancies:
- **Varying length and specificity of the title:** The core title must align, but you must tolerate missing subtitles, differing remainder-of-title text, dropped descriptive elements, or the use of legacy bracketed summaries (e.g., [M.fl. uppsatser...]).

#### Incorrect
The catalog card and the MARCXML record do NOT describe the same Work or Instance according to BIBFRAME 2.0. You MUST score the match as Incorrect in the following scenarios:
- **Translation vs. original work:** In BIBFRAME, a translation is a DIFFERENT Work. If there is textual or MARC evidence (e.g., "övers.", "overs.", or a 041 field with subfield $h) that one record is a translation and the other is the original work (or a different translation), they are Incorrect.
- **Series vs. Monograph:** If the catalog card describes an overarching Series or Collection, but the MARCXML record describes a specific Monograph with its own distinct title (even if it belongs to that series), they represent different Works and are Incorrect."""

TEXT_PROMPT = """Apply the BIBFRAME 2.0 assessment criteria to evaluate the following candidate match. 

First, provide a brief reasoning step verifying the core Work (title, authorship, language) and explicitly noting any tolerated Instance variances (e.g., publisher, place, subtitle length).
Second, output your final verdict as exactly one of the following: [Correct, Acceptable, Incorrect]."""

class Result(str, Enum):
    CORRECT = "Correct"
    ACCEPTABLE = "Acceptable"
    INCORRECT = "Incorrect"

class StructuredOutputSchema(BaseModel):
    reasoning: Optional[str] = Field(description="Your brief explanation to the result.")
    result: Result = Field(description="The result of the assessment.")

def build_prompt(extracted_data, marcxml_record):
    prompt = f"""{TEXT_PROMPT}

### Extracted data from catalog card:
{json.dumps(extracted_data)}

### MARCXML record:
{marcxml_record}"""

    return prompt

def load_marcxml_data(libris_ID, verbose):

    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "id.keyword": libris_ID
                        }
                    }
                ]
            }
        }
    }

    try:
        response = es.search(index=INDEX_NAME, **query)

        hits = response.get("hits", {}).get("hits", [])
        if hits:
            marcxml = hits[0]["_source"].get("marcxml")

            if not marcxml:
                print(f"⚠️  No MARCXML data found for ID: {libris_ID}")
                return None

            if verbose:
                print(f"✅ Successfully loaded MARCXML data for ID: {libris_ID}")
            
            marcxml_bytes = io.BytesIO(marcxml.encode('utf-8'))
            records = pymarc.parse_xml_to_array(marcxml_bytes)

            if not records:
                print(f"⚠️  No MARCXML records found for ID: {libris_ID}")
                return None

            record = records[0]

            tags_to_remove = ['887']
            fields_to_remove = record.get_fields(*tags_to_remove)
            for field in fields_to_remove:
                record.remove_field(field)

            for field in list(record.fields):
                if not field.is_control_field():
                    if field.get_subfields('5'):
                        record.remove_field(field)

            modified_xml_bytes = pymarc.record_to_xml(record)
            modified_xml_string = modified_xml_bytes.decode('utf-8')
            
            return modified_xml_string
            
        else:
            print(f"⚠️  No MARCXML data found for ID: {libris_ID}")
            return None
        
    except Exception as e:
        print(f"❌ Failed to retrieve MARCXML data for ID: {libris_ID}. Error: {e}")
        return None


def load_and_clean_extracted_data(extracted_data_directory, card_ID, edition_index, verbose):

    extracted_data_file = extracted_data_directory / f"{card_ID}.json"
    
    try:
        with open(extracted_data_file, 'r') as fp:
            extracted_data = json.load(fp)
            
        if verbose:
            print(f"✅ Successfully loaded extracted data for match: {card_ID}_{edition_index}")
    except Exception as e:
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
    output_json_filename = output_directory / "job_tasks.json"

    print(f"⏳ Processing {len(matches)} matches for verification...")

    for match in matches:
        
        match_object_ID = match["match_object_ID"]
        card_ID = match["card_ID"]
        edition_index = match["edition_idx"]

        extracted_data = load_and_clean_extracted_data(extracted_data_directory, card_ID, edition_index, verbose)
        if extracted_data is None:
            print(f"⚠️  Skipping match {match_object_ID} due to missing or invalid extracted data.")
            continue

        marcxml = load_marcxml_data(match["id"], verbose)
        if marcxml is None:
            print(f"⚠️  Skipping match {match_object_ID} due to missing MARCXML data.")
            continue

        prompt = build_prompt(extracted_data, marcxml)

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

    print(f"✅ Successfully saved {len(tasks)} match verification tasks to {output_json_filename}.")


def load_match_output(match_output_file):

    with open(match_output_file, 'r') as fp:
        match_output = json.load(fp)

    match_output = [match for match in match_output if match.get("match_stat") == "Unqualified" and match.get("card_type") in ["Monografi", "Flerbandsverk"]]

    return match_output


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Verify the matches by generating prompts for the model to assess whether the information in the extracted data from the catalog card matches the information in the record at the provided URL.")
    parser.add_argument("--output_directory", type=Path, help="Path to the batch job to run the verification task")
    parser.add_argument("--source_batch_job_directory", type=Path, help="Path to the batch job directory containing the matches to verify")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    source_batch_job_directory = args.source_batch_job_directory.expanduser().resolve()
    output_directory = args.output_directory.expanduser().resolve()

    match_output_file = source_batch_job_directory / "match" / "outputfile.json"
    extracted_data_directory = source_batch_job_directory / "post-process"

    matches = load_match_output(match_output_file)

    process_matches(matches, extracted_data_directory, output_directory, args.verbose)
