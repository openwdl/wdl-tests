#!/usr/bin/env python3
from argparse import ArgumentParser
from collections import defaultdict
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subby
from typing import Optional

class Result(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INVALID = "invalid"
    IGNORE = "ignore"

# ------------------ Helper functions ------------------

def resolve_cromwell(path: Optional[Path]) -> Path:
    if path is None:
        path = Path(shutil.which("cromwell.jar"))
    if path is None or not path.exists():
        raise Exception(f"Cannot find Cromwell JAR: {path}")
    return path

def load_cromwell_outputs(metadata_file: Path) -> dict:
    """
    Read Cromwell metadata JSON and return workflow outputs.
    Combines 'outputs' and all 'calls.*.outputs' for robustness.
    """
    if not metadata_file.exists():
        raise FileNotFoundError(f"Cromwell metadata file does not exist: {metadata_file}")

    with open(metadata_file, "r") as f:
        metadata = json.load(f)

    outputs = metadata.get("outputs", {})

    calls = metadata.get("calls", {})
    for call_name, call_list in calls.items():
        for call in call_list:
            call_outputs = call.get("outputs", {})
            for key, value in call_outputs.items():
                # Prefix with call name
                outputs[f"{call_name}.{key}"] = value

    return outputs

def get_filename_if_path(val):
    """Return the filename if val is a valid path, otherwise return val."""
    if isinstance(val, str):  # Only process string values
        path_obj = Path(val)
        return path_obj.name if path_obj.exists() else val
    return val  # Return as-is if not a string

# ------------------ Core test runner ------------------

def run_test(
    config: dict,
    cromwell_jar: Path,
    test_dir: Path,
    data_dir: Path,
    output_dir: Optional[Path],
    no_warn: bool,
    deprecated_optional: bool,
) -> Result:
    if config.get("priority") == "ignore":
        return Result.IGNORE

    # Prepare inputs JSON
    input_file = test_dir / "inputs.json"
    with open(input_file, "w") as f:
        json.dump(config.get("input", {}), f, indent=2)

    # Output directory
    run_dir = output_dir or (test_dir / "cromwell_results")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Options JSON
    options_file = run_dir / "cromwell_options.json"
    options_content = {
        "final_workflow_outputs_dir": str(run_dir.resolve())
    }
    with open(options_file, "w") as f:
        json.dump(options_content, f, indent=2)

    # Metadata output path
    workflow_name = config.get("name", Path(config["path"]).stem)
    metadata_output = run_dir / workflow_name / "outputs.json"
    metadata_output.parent.mkdir(parents=True, exist_ok=True)

    # Build and run Cromwell command
    command = [
        "java", "-jar", str(cromwell_jar),
        "run", str(config["path"]),
        "-i", str(input_file),
        "--options", str(options_file),
        "--metadata-output", str(metadata_output), "-v", "development"
    ]
    print("Executing command:", " ".join(command))
    p = subby.cmd(command, shell=True, raise_on_error=False)

    # Check return code
    rc = p.returncode
    expected_rc = config.get("returnCodes", 0)
    expected_to_fail = config.get("fail", False)
    actual_failed = rc != 0

    if expected_to_fail:
        if actual_failed:
            return Result.PASS
        else:
            print(f"ERROR: Test '{config['path']}' expected to fail but passed!")
            return Result.FAIL
    else:
        if expected_rc != "*" and rc != expected_rc:
            print(f"ERROR: Test '{config['path']}' returned {rc}, expected {expected_rc}")
            return Result.FAIL
        elif actual_failed:
            print(f"ERROR: Test '{config['path']}' failed unexpectedly.")
            return Result.FAIL

    # Parse outputs
    try:
        outputs = load_cromwell_outputs(metadata_output)
    except Exception as e:
        print(f"ERROR: Failed to parse Cromwell outputs: {e}")
        return Result.FAIL

    # Validate outputs against expected
    invalid = []
    for key, expected_value in config.get("output", {}).items():
        actual_value = outputs.get(key)

        # Extract filenames only for valid path-like strings
        value_name = get_filename_if_path(actual_value)
        expected_name = get_filename_if_path(expected_value)

        if value_name != expected_name:
            invalid.append((key, value_name, expected_name))

    if invalid:
        print(f"{config['path']}: ERROR")
        for key, actual, expected in invalid:
            print(f"  {key}: {actual} != {expected}")
        return Result.FAIL

    return Result.PASS

# ------------------ Main ------------------

def main():
    parser = ArgumentParser()
    parser.add_argument("-T", "--test-dir", type=Path, default=Path("."))
    parser.add_argument("-c", "--test-config", type=Path, default=None)
    parser.add_argument("-D", "--data-dir", type=Path, default=None)
    parser.add_argument("-O", "--output-dir", type=Path, default=None)
    parser.add_argument("--cromwell-jar", type=Path, default=None)
    parser.add_argument("-n", "--num-tests", type=int, default=None)
    parser.add_argument("--no-warn", action="store_true", default=False)
    parser.add_argument("--deprecated-optional", action="store_true", default=False)
    args = parser.parse_args()

    cromwell_jar = resolve_cromwell(args.cromwell_jar)
    test_dir = args.test_dir
    data_dir = args.data_dir or test_dir / "data"
    test_config_file = args.test_config or test_dir / "test_config.json"

    with open(test_config_file, "r") as f:
        configs = json.load(f)
    if args.num_tests is not None:
        configs = configs[: args.num_tests]

    results = defaultdict(int)
    failed_tests = []

    for config in configs:
        result = run_test(
            config,
            cromwell_jar,
            test_dir,
            data_dir,
            args.output_dir,
            args.no_warn,
            args.deprecated_optional
        )
        results[result] += 1
        if result == Result.FAIL:
            failed_tests.append(config["path"])

    # Save failed tests
    failed_file = (args.output_dir or test_dir / "cromwell_results") / "failed_tests.txt"
    failed_file.parent.mkdir(parents=True, exist_ok=True)
    with open(failed_file, "w") as f:
        for t in failed_tests:
            f.write(f"{t}\n")
    print(f"Failed tests written to: {failed_file}")

    # Print summary
    print(f"Total tests: {sum(results.values())}")
    print(f"Passed: {results.get(Result.PASS, 0)}")
    print(f"Warnings: {results.get(Result.WARN, 0)}")
    print(f"Failures: {results.get(Result.FAIL, 0)}")
    print(f"Invalid outputs: {results.get(Result.INVALID, 0)}")
    print(f"Ignored: {results.get(Result.IGNORE, 0)}")

if __name__ == "__main__":
    main()
