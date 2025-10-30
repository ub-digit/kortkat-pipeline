import subprocess
import sys
import argparse
from pathlib import Path


def define_pipeline_steps(batch_pipeline_directory, input_directory):
    pipeline_steps = [
        (
            "Create batch input file",
            # python3 create_batch_input_file.py [input_directory] [output_directory] [config_file] --start_index [start_image_number] --end_index [end_image_number]
            ["python3", "create_batch_input_file.py", f"{input_directory}", f"{batch_pipeline_directory}/batch_job_input", f"{batch_pipeline_directory}/config.json"]
        ),
        (
            "Create batch job",
            # python3 create_batch_job.py [input_directory] [output_directory] [config_file]
            ["python3", "create_batch_job.py", f"{batch_pipeline_directory}/batch_job_input", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/config.json"]
        ),
        (
            "Check batch job",
            # python3 check_batch_job.py [batch_job_directory] [config_file]
            ["python3", "check_batch_job.py", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/config.json"]
        ),
        (
            "Parse batch job results",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            ["python3", "parse_batch_job_results.py", f"{batch_pipeline_directory}/batch_job", f"{batch_pipeline_directory}/parsed_output"]
        ),
        (
            "Enrich parsed data with YOLO data",
            # python3 parse_batch_job_results.py [input_directory] [output_directory]
            ["python3", "enrich-with-yolo-data.py", "resources/yolo.json", f"{batch_pipeline_directory}/parsed_output/success", f"{batch_pipeline_directory}/parsed_output_with_yolo"]
        )        
    ]

    return pipeline_steps


def run_pipeline(pipeline_steps):
    """
    Executes each step in the PIPELINE_STEPS list in order.

    If any step fails (returns a non-zero exit code), the pipeline
    will stop and print the error.
    """
    print("--- Starting Pipeline ---")

    for name, command in pipeline_steps:
        print(f"\n▶️  Running Step: {name}")
        print(f"    Command: {' '.join(command)}")

        try:
            # Execute the command
            # - check=True: Raises CalledProcessError if the command fails
            # - capture_output=True: Captures stdout and stderr
            # - text=True: Decodes stdout/stderr as text (using default encoding)
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )

            # Print the standard output of the script if it's not empty
            if result.stdout:
                print("    --- Output ---")
                print(result.stdout.strip())
                print("    --------------")

            print(f"✅ Step Succeeded: {name}")

        except subprocess.CalledProcessError as e:
            # This block runs if the script returns a non-zero exit code
            print(f"\n❌ ERROR: Step Failed: {name}", file=sys.stderr)
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
            print(f"\n[!] ERROR: Command not found for step: {name}", file=sys.stderr)
            print(f"    Check if 'python' is in your PATH and the script '{command[1]}' exists.", file=sys.stderr)
            print("\n--- Pipeline Halted Due to Error ---", file=sys.stderr)
            sys.exit(1)

    print("\n--- Pipeline Finished Successfully ---")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run batch pipeline for processing, matching and evaluating library cards")
    parser.add_argument("batch_pipeline_directory", type=Path, help="Name of batch job, used to identify it")
    parser.add_argument("input_directory", type=Path, help="Path to directory with images to process")

    args = parser.parse_args()

    batch_pipeline_directory = Path(f"jobs/{args.batch_pipeline_directory}")
    input_directory = args.input_directory

    pipeline_steps = define_pipeline_steps(batch_pipeline_directory, input_directory)

    run_pipeline(pipeline_steps)