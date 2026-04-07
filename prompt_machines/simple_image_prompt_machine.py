from pathlib import Path
import argparse
import json
import base64
from typing import Optional
from pydantic import BaseModel, Field
from kortkat.prompt_data import PromptData, Content, TextPart, InlineDataPart

SYSTEM_INSTRUCTION = "You are the worlds best librarian. Your task is to tell me the title and author of the book described by a catalog card. The catalog card is represented as an image. Please provide the title and author in the output, and nothing else. If you are not sure about the title or author, please provide your best guess based on the information available in the image."
TEXT_PROMPT = "Extract the title and author from this library card."

class StructuredOutputSchema(BaseModel):
    title: Optional[str] = Field(description="The title of the book described by the catalog card.")
    author: Optional[str] = Field(description="The author of the book described by the catalog card.")

def process_directory(input_directory, output_directory, start_index, end_index, verbose):
    total_images = 0

    output_directory.mkdir(parents=True, exist_ok=True)

    image_files = [f for f in sorted(input_directory.glob('*.jpg'))]

    if start_index != 0:
        start_index -= 1

    if end_index == -1:
        end_index = len(image_files)

    output_json_filename = output_directory / "image_tasks.json"

    tasks = []

    for i in range(start_index, end_index):
        image_file = image_files[i]
        with open(image_file, "rb") as image:            
            base64_string = base64.b64encode(image.read()).decode("utf-8")
        
        parts =[
            InlineDataPart(type="inlineData", mimeType="image/jpeg", data=base64_string),
            TextPart(type="text", data=TEXT_PROMPT)
        ]

        task = PromptData(
            key=image_file.stem,
            prompt=[Content(role="user", parts=parts)],
            system_instruction=SYSTEM_INSTRUCTION,
            json_schema=StructuredOutputSchema.model_json_schema()
        )

        tasks.append(task)
        
        total_images += 1
        if verbose:
            print(f"Added image {image_files[i]} successfully.")

    tasks_dicts = [task.model_dump() for task in tasks]

    with open(output_json_filename, 'w') as fp:
        json.dump(tasks_dicts, fp, indent=4)

    if total_images == 0:
       print("No images were processed. Please check the input directory and parameters.")
       exit(1)
    else:
       print(f"Added {total_images} images to batch input file: {output_json_filename}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("input_directory", type=Path, help="Path to the image directory")
    parser.add_argument("output_directory", type=Path, help="Path to where to put the json output")
    parser.add_argument("--start_index", type=int, default=0, help="Starting index of images to process")
    parser.add_argument("--end_index", type=int, default=-1, help="Ending index of images to process (-1 for all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")

    args = parser.parse_args()

    process_directory(args.input_directory, args.output_directory, args.start_index, args.end_index, args.verbose)