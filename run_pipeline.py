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


def define_pipeline_steps():
    pipeline_steps = [
        {
            "key":  "create-input",
            "name": "Create batch input file",
            # python3 create_batch_input_file.py [input_directory] [output_directory] [pipeline_directory] --start_index [start_image_number] --end_index [end_image_number]
            "command": (
                lambda args: ["python3", "create_batch_input_file.py", str(args["input_directory"]), str(args["pipeline_directory"]) + "/extract", str(args["pipeline_directory"])]
            )
        },
        {
            "key": "create-job",
            "name": "Create batch job",
            # python3 create_batch_job.py [input_directory] [output_directory] [pipeline_directory]
            "command": (
                lambda args: ["python3", "create_batch_job.py", str(args["pipeline_directory"]) + "/extract/batch_input.jsonl", str(args["pipeline_directory"]) + "/extract", str(args["pipeline_directory"])]
            )
        },
        {
            "key": "check-job",
            "name": "Check batch job",
            # python3 check_batch_job.py [batch_job_info_file] [output_directory]
            "command": (
                lambda args: ["python3", "check_batch_job.py", str(args["pipeline_directory"]) + "/extract/batch_job_info.json", str(args["pipeline_directory"]) + "/extract"]
            )
        },
        {   "key": "parse",
            "name": "Parse batch job results",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            "command": (
                lambda args: ["python3", "parse_batch_job_results.py", str(args["pipeline_directory"]) + "/extract/", str(args["pipeline_directory"]) + "/parse"]
            )
        },
        {
            "key": "enrich",
            "name": "Enrich parsed data with YOLO data",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            "command": (
                lambda args: ["python3", "enrich-with-yolo-data.py", str(args["pipeline_directory"]) + "/yolo.json", str(args["pipeline_directory"]) + "/parse/success", str(args["pipeline_directory"]) + "/parse/with_yolo"]
            )
        },
        {
            "key": "match",
            "name": "Match extracted data against dataset",
            "command": (
                lambda args: ["cargo", "run", "--release", "--", "-c", "match-json-zip", "-s", "libris-v1_6", "-i", str(args["pipeline_directory"]) + "/parse/with_yolo", "-o", str(args["pipeline_directory"]) + "/match/outputfile.xlsx", "-F", "xlsx", "-C", str(args["pipeline_directory"]) + "/config.json"]
            ),
            "working_dir": MATCH_WORKING_DIR
        },
        {
            "key": "evaluate",
            "name": "Evaluate matches",
            # python3 generate_match_report.py --match_folder [match_folder] --matches_file [matches_file] --settings_file [settings_file] --ground_truth_file [groundtruth] --output_folder [output_folder] --job_name [job_name_string]
            "command": (
                lambda args: ["python3", "generate_match_report.py", "--match_directory", str(args["pipeline_directory"]) + "/match", "--ground_truth_file", str(args["pipeline_directory"]) + "/gt.xlsx", "--output_directory", str(args["pipeline_directory"]) + "/evaluate", "--job_name", args["pipeline_directory"].name]
            )
        }
    ]

    return pipeline_steps


def run_pipeline(pipeline_steps, pipeline_args, selected_steps):
    """
    Executes each step in the PIPELINE_STEPS list in order.

    If any step fails (returns a non-zero exit code), the pipeline
    will stop and print the error.
    """

    print("--- Starting Pipeline ---")

    for i, step in enumerate(pipeline_steps):
        if step["key"] in selected_steps:
            step_name = step["name"]
            command = step["command"](pipeline_args)
            target_working_dir = step.get("working_dir", os.getcwd())

            print(f"\n▶️  Running Step {i+1}: {step_name}")
            print(f"    Command: {" ".join(command)}")

            try:
                if target_working_dir:
                    with change_dir(target_working_dir):
                        print(command)
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

    pipeline_steps = define_pipeline_steps()
    step_keys = [step["key"] for step in pipeline_steps]


    parser = argparse.ArgumentParser(description="Run batch pipeline for processing, matching and evaluating library cards")
    parser.add_argument("pipeline", type=Path, help="Name of pipeline to run")
    parser.add_argument("input_directory", type=Path, help="Path to directory with images to process")
    parser.add_argument("--steps", nargs="+", choices=step_keys, help="Pipeline steps to run")

    args = parser.parse_args()

    pipeline_args = {
        "pipeline_directory": Path(f"jobs/{args.pipeline}").resolve(),
        "input_directory": args.input_directory        
    }

    selected_steps = args.steps or step_keys

    print(selected_steps)

    run_pipeline(pipeline_steps, pipeline_args, selected_steps)