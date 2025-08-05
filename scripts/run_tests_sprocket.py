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


def resolve_sprocket(path: Optional[Path]) -> Path:
    if path is None:
        path = Path(shutil.which("sprocket"))
    if path is None:
        raise Exception("Cannot find sprocket on system path")
    if not path.exists():
        raise Exception(f"Executable does not exist: {path}")
    if not os.access(path, os.X_OK):
        raise Exception(f"Path is not executable: {path}")
    return path


def check(
    config: dict,
    sprocket_path: Path,
    test_dir: Path,
    strict: bool,
    no_warn: bool,
    deprecated_optional: bool,
) -> Result:
    command = [str(sprocket_path), "check", str(Path.cwd() / config["path"]), str(input_path)]

    p = subby.cmd(command, shell=True, raise_on_error=False)

    if p.returncode == 0:
        return Result.PASS
    elif config["priority"] == "ignore":
        return Result.IGNORE
    elif config["fail"] and no_warn:
        return Result.WARN
    elif deprecated_optional and "deprecated" in config["tags"]:
        return Result.WARN
    else:
        fail = config["fail"]
        title = f"{config['path']}: {'WARNING' if fail else 'ERROR'}"
        print(title)
        print("-" * len(title))
        print(p.output or p.error)
        print()
        return Result.WARN if fail else Result.FAIL


def run_test(
    config: dict,
    sprocket_path: Path,
    test_dir: Path,
    data_dir: Path,
    output_dir: Optional[Path],
    no_warn: bool,
    deprecated_optional: bool,
) -> Result:
    if config["priority"] == "ignore":
        return Result.IGNORE

    input_path = test_dir / "inputs.json"
    with open(input_path, "w") as f:
        json.dump(config["input"], f)

    command = [str(sprocket_path), "run", str(Path.cwd() / config["path"]), str(input_path), "--output", str(output_dir / config['id']) ]

    command.extend(["--entrypoint", str(config["target"])])

    print("Executing command:", " ".join(command))
    p = subby.cmd(command, shell=True, raise_on_error=False)

    expected_to_fail = config.get("fail", False)
    actual_failed = p.returncode != 0
    rc = p.returncode
    expected_rc = config.get("returnCodes", 0)

    if expected_to_fail:
        if actual_failed:
            print(f"Test '{config['path']}' was expected to fail and did — PASS")
            return Result.PASS
        else:
            print(f"ERROR: Test '{config['path']}' was expected to fail but passed!")
            return Result.FAIL
    else:
        if expected_rc == "*" or rc == expected_rc:
            if actual_failed:
                print(f"ERROR: Test '{config['path']}' failed unexpectedly.")
                return Result.FAIL
        else:
            print(f"ERROR: Return code mismatch ({rc} != {expected_rc})")
            return Result.FAIL

    try:
        output = json.loads(p.output)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON output from sprocket:\n{p.output or p.error}")
        return Result.FAIL

    outputs = output.get("outputs", {})
    invalid = []
    for key, value in outputs.items():
        if key not in config["exclude_output"]:
            if key not in config["output"]:
                invalid.append((key, value, None))
            else:
                expected_value = config["output"][key]

                def get_filename_if_path(val):
                    if isinstance(val, str):
                        path_obj = Path(val)
                        return path_obj.name if path_obj.exists() else val
                    return val

                value_name = get_filename_if_path(value)
                expected_name = get_filename_if_path(expected_value)

                if value_name != expected_name:
                    invalid.append((key, value, expected_value))

    if invalid:
        title = f"{config['path']}: ERROR"
        print(title)
        print("-" * len(title))
        print("Invalid output(s):")
        for key, actual, expected in invalid:
            print(f"  {key}: {actual} != {expected}")
        return Result.FAIL

    return Result.PASS


def main():
    parser = ArgumentParser()
    parser.add_argument("-T", "--test-dir", type=Path, default=Path("."))
    parser.add_argument("-c", "--test-config", type=Path, default=None)
    parser.add_argument("-D", "--data-dir", type=Path, default=None)
    parser.add_argument("-O", "--output-dir", type=Path, default=None)
    parser.add_argument("-n", "--num-tests", type=int, default=None)
    parser.add_argument("--sprocket-path", type=Path, default=None)
    parser.add_argument("--check-only", action="store_true", default=False)
    parser.add_argument("--strict", action="store_true", default=False)
    parser.add_argument("--no-warn", action="store_true", default=False)
    parser.add_argument("--deprecated-optional", action="store_true", default=False)
    args = parser.parse_args()

    sprocket_path = resolve_sprocket(args.sprocket_path)
    test_dir = args.test_dir
    data_dir = args.data_dir or test_dir / "data"
    test_config = args.test_config or test_dir / "test_config.json"

    with open(test_config, "r") as i:
        configs = json.load(i)

    if args.num_tests is not None:
        configs = configs[: args.num_tests]

    results = defaultdict(int)
    failed_tests = []

    for config in configs:
        if args.check_only:
            result = check(
                config,
                sprocket_path,
                test_dir,
                args.strict,
                args.no_warn,
                args.deprecated_optional,
            )
            results[result] += 1
        else:
            result = run_test(
                config,
                sprocket_path,
                test_dir,
                data_dir,
                args.output_dir,
                args.no_warn,
                args.deprecated_optional,
            )
            results[result] += 1
            if result == Result.FAIL:
                failed_tests.append(config["path"])

    if failed_tests:
        failed_tests_file = test_dir / "failed_tests.txt"
        with open(failed_tests_file, "w") as f:
            for test in failed_tests:
                f.write(f"{test}\n")
        print(f"\nFailed tests written to: {failed_tests_file}")

    print(f"Total tests: {sum(results.values())}")
    print(f"Passed: {results.get(Result.PASS, 0)}")
    print(f"Warnings: {results.get(Result.WARN, 0)}")
    print(f"Failures: {results.get(Result.FAIL, 0)}")
    print(f"Invalid outputs: {results.get(Result.INVALID, 0)}")
    print(f"Ignored: {results.get(Result.IGNORE, 0)}")


if __name__ == "__main__":
    main()
