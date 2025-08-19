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


def resolve_miniwdl(path: Optional[Path]) -> Path:
    if path is None:
        path = Path(shutil.which("miniwdl"))
    if path is None:
        raise Exception("Cannot find miniwdl on system path")
    if not path.exists():
        raise Exception(f"Executable does not exist: {path}")
    if not os.access(path, os.X_OK):
        raise Exception(f"Path is not executable: {path}")
    return path


def check(config: dict, miniwdl_path: Path, test_dir: Path, strict: bool, no_warn: bool, deprecated_optional: bool) -> Result:
    command = [str(miniwdl_path), "check"]
    if strict:
        command.append("--strict")
    command.append(str(config["path"]))
    p = subby.cmd(command, shell=True, cwd=test_dir, raise_on_error=False)
    if p.returncode == 0:
        return Result.PASS
    elif config["priority"] == "ignore":
        return Result.IGNORE
    elif config["fail"] and no_warn:
        return Result.WARN
    elif deprecated_optional and "deprecated" in config.get("tags", []):
        return Result.WARN
    else:
        fail = config["fail"]
        title = f"{config['path']}: {'WARNING' if fail else 'ERROR'}"
        print(title)
        print("-" * len(title))
        print(p.output or p.error)
        print()
        return Result.WARN if fail else Result.FAIL


def run_test(config: dict, miniwdl_path: Path, test_dir: Path, data_dir: Path,
             output_dir: Optional[Path], no_warn: bool, deprecated_optional: bool) -> Result:

    if config["priority"] == "ignore":
        return Result.IGNORE

    input_json = json.dumps(config.get("input", {}))

    command = [str(miniwdl_path), "run", "-p", str(test_dir), "-i", input_json]

    if output_dir:
        command.extend(["-d", str(output_dir)])

    if config["type"] == "task":
        command.extend(["--task", str(config["target"])])

    command.append(str(config["path"]))

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
        if expected_rc != "*" and rc != expected_rc:
            print(f"ERROR: Test '{config['path']}' failed with different return code.")
            return Result.FAIL
        elif actual_failed:
            print(f"ERROR: Test '{config['path']}' failed unexpectedly.")
            return Result.FAIL

    # Check outputs
    invalid = []
    try:
        output = json.loads(p.output)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON output from miniwdl:\n{p.output or p.error}")
        return Result.FAIL

    outputs = output.get("outputs", {})
    actual_output_dir = output_dir or (test_dir / "out")

    def normalize_output(val, base_dir):
        """
        Convert a MiniWDL output value to a path relative to base_dir,
        recursively listing directory contents if it's a directory.
        """
        if isinstance(val, str):
            path_obj = Path(val)
            if path_obj.is_dir():
                return sorted(str(f.relative_to(base_dir)) for f in path_obj.rglob("*") if f.is_file())
            else:
                try:
                    return str(path_obj.relative_to(base_dir))
                except ValueError:
                    return str(path_obj)
        elif isinstance(val, list):
            return [normalize_output(v, base_dir) for v in val]
        else:
            return val

    for key, value in outputs.items():
        if key in config.get("exclude_output", []):
            continue
        expected_value = config["output"].get(key)
        if expected_value is None:
            invalid.append((key, value, None))
            continue

        value_norm = normalize_output(value, actual_output_dir)

        if isinstance(value_norm, list) and isinstance(expected_value, list):
            if value_norm != expected_value:
                invalid.append((key, value_norm, expected_value))
        else:
            if value_norm != expected_value:
                invalid.append((key, value_norm, expected_value))

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
    parser.add_argument("--miniwdl-path", type=Path, default=None)
    parser.add_argument("--check-only", action="store_true", default=False)
    parser.add_argument("--strict", action="store_true", default=False)
    parser.add_argument("--no-warn", action="store_true", default=False)
    parser.add_argument("--deprecated-optional", action="store_true", default=False)
    args = parser.parse_args()

    miniwdl_path = resolve_miniwdl(args.miniwdl_path)
    test_dir = args.test_dir
    data_dir = args.data_dir or test_dir / "data"
    test_config = args.test_config or test_dir / "test_config.json"

    with open(test_config, "r") as f:
        configs = json.load(f)
    if args.num_tests is not None:
        configs = configs[: args.num_tests]

    results = defaultdict(int)
    failed_tests = []

    for config in configs:
        if args.check_only:
            result = check(config, miniwdl_path, test_dir, args.strict, args.no_warn, args.deprecated_optional)
        else:
            result = run_test(config, miniwdl_path, test_dir, data_dir, args.output_dir, args.no_warn, args.deprecated_optional)
            if result == Result.FAIL:
                failed_tests.append(config["path"])
        results[result] += 1

    # Save failed tests
    if failed_tests:
        failed_tests_file = test_dir / "failed_tests.txt"
        with open(failed_tests_file, "w") as f:
            for test in failed_tests:
                f.write(f"{test}\n")
        print(f"\nFailed tests written to: {failed_tests_file}")

    # Print summary
    print(f"Total tests: {sum(results.values())}")
    print(f"Passed: {results.get(Result.PASS, 0)}")
    print(f"Warnings: {results.get(Result.WARN, 0)}")
    print(f"Failures: {results.get(Result.FAIL, 0)}")
    print(f"Invalid outputs: {results.get(Result.INVALID, 0)}")
    print(f"Ignored: {results.get(Result.IGNORE, 0)}")


if __name__ == "__main__":
    main()
