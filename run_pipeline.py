import os
import subprocess
import sys
import argparse
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()
MATCH_WORKING_DIR = os.getenv("MATCH_WORKING_DIR")

@contextmanager
def change_dir(destination):
    """A context manager to safely and temporarily change the working directory."""
    try:
        original_dir = os.getcwd()
        os.chdir(destination)
        yield
    finally:
        os.chdir(original_dir)


def define_pipeline_steps(batch_pipeline_directory, input_directory):
    pipeline_steps = [
        {
            "name": "Create batch input file",
            # python3 create_batch_input_file.py [input_directory] [output_directory] [config_file] --start_index [start_image_number] --end_index [end_image_number]
            "command": ["python3", "create_batch_input_file.py", f"{input_directory}", f"{batch_pipeline_directory}/batch_job_input", f"{batch_pipeline_directory}/config.json"]
        },
        {
            "name": "Create batch job",
            # python3 create_batch_job.py [input_directory] [output_directory] [config_file]
            "command": ["python3", "create_batch_job.py", f"{batch_pipeline_directory}/batch_job_input", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/config.json"]
        },
        {
            "name": "Check batch job",
            # python3 check_batch_job.py [batch_job_directory] [config_file]
            "command": ["python3", "check_batch_job.py", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/config.json"]
        },
        {
            "name": "Parse batch job results",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            "command": ["python3", "parse_batch_job_results.py", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/parsed_output"]
        },
        {
            "name": "Enrich parsed data with YOLO data",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            "command": ["python3", "enrich-with-yolo-data.py", "resources/yolo.json", f"{batch_pipeline_directory}/parsed_output/success", f"{batch_pipeline_directory}/parsed_output_with_yolo"]
        },
        {
            "name": "Match extracted data against dataset",
            "command": ["cargo", "run", "--release", "--", "-c", "match-json-zip", "-s", "libris-v1_6", "-i", f"{batch_pipeline_directory}/parsed_output_with_yolo", "-o", f"{batch_pipeline_directory}/matched/outputfile.xlsx", "-F", "xlsx", "-O", "force-year", "-O", "include-source-data", "-O", "similarity-threshold=0.35", "-O", "z-threshold=7", "-O", "min-single-similarity=0.5", "-O", "min-multiple-similarity=0.43", "-v", "-O", "extended-output", "-O", "jaro-winkler-adjustment", "-O", "json-schema-version=2"],
            "working_dir": MATCH_WORKING_DIR
        },
        {
            "name": "Evaluate matches",
            # python3 generate_match_report.py --match_folder [match_folder] --matches_file [matches_file] --settings_file [settings_file] --ground_truth_file [groundtruth] --output_folder [output_folder] --job_name [job_name_string]
            "command": ["python3", "generate_match_report.py", "--match_directory", f"{batch_pipeline_directory}/matched", "--ground_truth_file", f"{batch_pipeline_directory}/gt.xlsx", "--output_directory", f"{batch_pipeline_directory}/evaluated"]
        }
    ]

    return pipeline_steps


def run_pipeline(pipeline_steps):
    """
    Executes each step in the PIPELINE_STEPS list in order.

    If any step fails (returns a non-zero exit code), the pipeline
    will stop and print the error.
    """
    print("--- Starting Pipeline ---")

    for i, step in enumerate(pipeline_steps):
        step_name = step["name"]
        command = step["command"]        
        target_working_dir = step.get("working_dir", os.getcwd())

        print(f"\n▶️  Running Step {i+1}: {step_name}")
        print(f"    Command: {" ".join(command)}")

        try:
            if target_working_dir:
                with change_dir(target_working_dir):
                    result = subprocess.run(
                        command,
                        check=True,
                        capture_output=True,
                        text=True
                    )
            if result.stdout:
                print("    --- Output ---")
                print(result.stdout.strip())
                print("    --------------")

            print(f"✅ Step Succeeded: {step_name}")

        except subprocess.CalledProcessError as e:
            # This block runs if the script returns a non-zero exit code
            print(f"\n❌ ERROR: Step Failed: {step_name}", file=sys.stderr)
            print(f"    Return Code: {e.returncode}", file=sys.stderr)

            if e.stdout:
                print("    --- Standard Output ---", file=sys.stderr)
                print(e.stdout.strip(), file=sys.stderr)
                print("    -----------------------", file=sys.stderr)

            if e.stderr:
                print("    --- Standard Error ---", file=sys.stderr)
                print(e.stderr.strip(), file=sys.stderr)
                print("    ----------------------", file=sys.stderr)

            print("\n--- Pipeline halted due to an error ---", file=sys.stderr)
            sys.exit(1) # Exit the orchestrator script with an error code

        except FileNotFoundError:
            # This block runs if the command itself (e.g., 'python' or 'step1_...py')
            # isn't found by the system.
            print(f"\n[!] ERROR: Command not found for step: {step_name}", file=sys.stderr)
            print(f"    Check if 'python' is in your PATH and the script '{command[1]}' exists.", file=sys.stderr)
            print("\n--- Pipeline Halted Due to Error ---", file=sys.stderr)
            sys.exit(1)

    print("\n--- Pipeline Finished Successfully ---")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run batch pipeline for processing, matching and evaluating library cards")
    parser.add_argument("batch_pipeline_directory", type=Path, help="Path to pipeline to run")
    parser.add_argument("input_directory", type=Path, help="Path to directory with images to process")

    args = parser.parse_args()

    batch_pipeline_directory = Path(f"jobs/{args.batch_pipeline_directory}").resolve()
    input_directory = args.input_directory

    pipeline_steps = define_pipeline_steps(batch_pipeline_directory, input_directory)

    run_pipeline(pipeline_steps)