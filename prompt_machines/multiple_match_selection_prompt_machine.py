from pathlib import Path
import argparse
import json
from numpy.random import sample
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from kortkat.prompt_data import PromptData, Content, TextPart
from elasticsearch import Elasticsearch
import io
import pymarc

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "records"

SYSTEM_INSTRUCTION = """### ROLE AND TASK
You are an expert librarian and archivist. Your task is to evaluate which one of the candidate records is the best match to the data extracted from the catalog card, or declare that no correct match exists.

### Overall instructions
- **Strict Evidence-Based Evaluation:** Base your assessment solely on the provided text. Do not invent context or make assumptions about cataloger intent.
- **BIBFRAME 2.0 as a reference:** You are evaluating matches at the Work and Instance levels according to the BIBFRAME 2.0 model. A Work represents the conceptual essence of the cataloged resource (the core title, authorship, and language). An Instance represents a specific physical or digital embodiment of a Work (e.g., a specific edition published by a specific publisher in a specific year and place).
- **Evaluating Language:** The extracted iso_language_code and iso_language_name are AI-generated and frequently incorrect (e.g., guessing Latin when the text is Greek, or Swedish when the text is Sami). The MARCXML record can also contain incorrect language codes caused by cataloging mistakes. Do not fail a match based solely on the language codes. To determine if the language actually differs, you must look for concrete textual evidence (title wording, statement of responsibility).
- **Danish/Norwegian Overlap:** Historically, written Danish and Norwegian (Riksmål) were nearly identical. Treat discrepancies between Danish and Norwegian language codes as matching Works if the title, author, and year match.
- **Authorship Flexibility:** The extraction tool may occasionally put the subject of a biography, an editor, or a compiler into the main_author field. Always cross-reference the extracted author with the MARCXML 700 fields (added entries) and the title string. If the person exists in both records in any capacity, do not fail the match on authorship alone.

### CANDIDATE ASSESSMENT CATEGORIES
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
- **Series vs. Monograph:** If the catalog card describes an overarching Series or Collection, but the MARCXML record describes a specific Monograph with its own distinct title (even if it belongs to that series), they represent different Works and are Incorrect.

### CANDIDATE SELECTION RULES
When selecting the candidate record that is the best match to the information extracted from the catalog card, use the following rules:
- NEVER select a candidate that you have evaluated to be an INCORRECT match.
- When the extracted data describe a multi-volume work, prioritize set records over part records.
- Prioritize records that have holdings with any of the library codes 'G', 'Gdig', 'Ge', 'Ghdk', 'Gk', 'Gm', 'Gp' or 'Gumu'.
- If the multi-volume work or holdings rules cannot be applied, prioritize a CORRECT match over an ACCEPTABLE match.
- If you still cannot decide between two or more candidates, select the candidate with the higher encoding level or completeness.

### CANDIDATE SELECTION CRITERIA
When selecting a candidate as the best match, or declaring that no correct match exists, use the following criteria to label the selection as "Good", "Acceptable" or "No candidate selected".
#### Good
The selected candidate fulfills the highest priority selection criteria without requiring major compromises.

#### Acceptable
A candidate was selected, but you had to compromise on the selection criteria hierarchy.

#### No candidate selected
No candidate record meets the criteria of being evaluated as a Correct or Acceptable match."""

TEXT_PROMPT = "Evaluate which one of the candidate records is the best match to the data extracted from the catalog card."

class SelectionResult(str, Enum):
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    NO_CANDIDATE_SELECTED = "No candidate selected"

class EvaluationResult(str, Enum):
    CORRECT = "Correct"
    ACCEPTABLE = "Acceptable"
    INCORRECT = "Incorrect"

class CandidateEvaluation(BaseModel):
    candidate_id: str = Field(description="The Libris ID of the evaluated candidate record. The Libris ID is located in controlfield 001. Return the Libris ID as a complete URL like so: https://libris.kb.se/bib/[libris_id].")
    result: EvaluationResult = Field(description="The result of the evaluation.")
    result_reasoning: str = Field(description="Your reasoning of your evaluation.")
    has_holdings: bool = Field(description="True if the candidate record has holdings with any of the library codes 'G', 'Gdig', 'Ge', 'Ghdk', 'Gk', 'Gm', 'Gp' or 'Gumu', false otherwise.")
    is_multi_volume_set_record: bool = Field(description="True if the candidate record describes a comprehensive set record for a multi-volume work, false otherwise.")
    field_599_subfield_a_values: List[str] = Field(description="The values of all subfields 'a' in all MARC fields 599.")

class StructuredOutputSchema(BaseModel):
    evaluation_results: List[CandidateEvaluation] = Field(description="A list of evaluation results for each candidate record.")
    selected_candidate_id: Optional[str] = Field(description="The Libris ID of the candidate record that is assessed as the correct match.")
    selection_result: SelectionResult = Field(description="The result of the candidate selection.")
    selection_result_reasoning: str = Field(description="The reasoning behind the selection of the candidate.")


    
def build_prompt(extracted_data, marcxml_records):
    libris_candidates_part = ""
    for index, (candidate_id, marcxml_record) in enumerate(marcxml_records.items(), start=1):
        libris_candidates_part += f"#### Candidate {index} - Libris ID: {candidate_id}:\n{marcxml_record}\n\n"


    prompt = f"""{TEXT_PROMPT}

### Extracted data from catalog card:
{json.dumps(extracted_data)}

### Candidate records:
{libris_candidates_part}"""

    return prompt

def load_marcxml_data(candidates, verbose):

    # Build new array of candidate ids by just passing the candidate["id"] to the new new array, no checking necessary
    candidate_ids = [candidate["id"] for candidate in candidates]

    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "terms": {
                            "id.keyword": candidate_ids
                        }
                    }
                ]
            }
        }
    }

    # TODO: Adjust for multiple documents returned

    try:
        response = es.search(index=INDEX_NAME, **query)

        hits = response.get("hits", {}).get("hits", [])

        marcxml_results = {}

        if hits:
            for hit in hits:
                current_id = hit["_source"].get("id")
                marcxml = hit["_source"].get("marcxml")

                if not current_id:
                    print(f"⚠️  No ID found in hit")
                    continue

                if not marcxml:
                    print(f"⚠️  No MARCXML data found for ID: {current_id}")
                    marcxml_results[current_id] = None
                    continue

                if verbose:
                    print(f"✅ Successfully loaded MARCXML data for ID: {current_id}")
                
                marcxml_bytes = io.BytesIO(marcxml.encode('utf-8'))
                records = pymarc.parse_xml_to_array(marcxml_bytes)

                if not records:
                    print(f"⚠️  No MARCXML records found for ID: {current_id}")
                    return None

                record = records[0]

                tags_to_remove = ['887']
                fields_to_remove = record.get_fields(*tags_to_remove)
                for field in fields_to_remove:
                    record.remove_field(field)

                for field in list(record.fields):
                    if not field.is_control_field():
                        subfield_5_values = field.get_subfields('5')
                        if subfield_5_values:
                            allowed_subfield_5_values = {'G', 'Gdig', 'Ge', 'Ghdk', 'Gk', 'Gm', 'Gp', 'Gumu'}
                            keep_field = any(
                                value in allowed_subfield_5_values
                                for value in subfield_5_values
                            )
                            if not keep_field:
                                record.remove_field(field)

                modified_xml_bytes = pymarc.record_to_xml(record)
                modified_xml_string = modified_xml_bytes.decode('utf-8')

                marcxml_results[current_id] = modified_xml_string
                
            return marcxml_results
                
        else:
            print(f"⚠️  No hits found for candidate IDs: {candidate_ids}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to retrieve records from Elasticsearch. Error: {e}")
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

    merged_matches_dict = {}

    for match in matches:
        match_object_ID = match["match_object_ID"]
        if match_object_ID not in merged_matches_dict:
            merged_matches_dict[match_object_ID] = {
                "box": match["box"],
                "card": match["card"],
                "card_ID": match["card_ID"],
                "match_object_ID": match_object_ID,
                "card_type": match["card_type"],
                "edition_idx": match["edition_idx"],
                "candidates": []
            }
        
        candidate_info = {
            "matched_ID": match["matched_ID"],
            "json": match["json"],
            "title": match["title"],
            "author": match["author"],
            "location": match["location"],
            "year": match["year"],
            "match_stat": match["match_stat"],
            "id": match["id"],
            "similarity": match["similarity"],
            "zscore": match["zscore"],
            "source_title": match["source_title"],
            "source_author": match["source_author"],
            "source_location": match["source_location"],
            "source_year": match["source_year"],
            "original_similarity": match["original_similarity"],
            "overlap_score": match["overlap_score"],
            "adjusted_overlap_score": match["adjusted_overlap_score"],
            "jaro_winkler_score": match["jaro_winkler_score"]
        }

        merged_matches_dict[match_object_ID]["candidates"].append(candidate_info)


    print(f"⏳ Processing {len(merged_matches_dict)} matches for verification...")

    for match_object_ID, match_data in merged_matches_dict.items():
        
        card_ID = match_data["card_ID"]
        edition_index = match_data["edition_idx"]

        extracted_data = load_and_clean_extracted_data(extracted_data_directory, card_ID, edition_index, verbose)
        if extracted_data is None:
            print(f"⚠️  Skipping match {match_object_ID} due to missing or invalid extracted data.")
            continue

        marcxml = load_marcxml_data(match_data["candidates"], verbose)
        # also check that marcxml dict has more than one record
        if marcxml is None or len(marcxml) < 2:
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

    match_output = [match for match in match_output if match.get("match_stat") in ["Multiple", "Unqualified multiple"] and match.get("card_type") in ["Monografi", "Flerbandsverk"]]

    return match_output


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Compare multiple matches by generating prompts for the model to assess which of the candidate records is the correct match to the information in the extracted data from the catalog card.")
    parser.add_argument("--output_directory", type=Path, help="Path to the batch job to run the comparison task")
    parser.add_argument("--source_batch_job_directory", type=Path, help="Path to the batch job directory containing the matches to verify")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    source_batch_job_directory = args.source_batch_job_directory.expanduser().resolve()
    output_directory = args.output_directory.expanduser().resolve()

    match_output_file = source_batch_job_directory / "match" / "outputfile.json"
    extracted_data_directory = source_batch_job_directory / "post-process"

    matches = load_match_output(match_output_file)

    process_matches(matches, extracted_data_directory, output_directory, args.verbose)
