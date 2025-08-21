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
import subprocess


class Result(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INVALID = "invalid"
    IGNORE = "ignore"


def resolve_toil(path: Optional[Path]) -> Path:
    if path is None:
        path = Path(shutil.which("toil-wdl-runner"))
    if path is None:
        raise Exception("Cannot find toil-wdl-runner on system path")
    if not path.exists():
        raise Exception(f"Executable does not exist: {path}")
    if not os.access(path, os.X_OK):
        raise Exception(f"Path is not executable: {path}")
    return path


def resolve_wdl_path(config_path: str) -> Path:
    wdl_path = Path(config_path)
    if not wdl_path.is_absolute():
        wdl_path = (Path.cwd() / wdl_path).resolve()
    if not wdl_path.exists():
        raise FileNotFoundError(f"WDL file does not exist: {wdl_path}")
    return wdl_path


def normalize_paths(d: dict) -> dict:
    """Normalize string values that look like file paths to just the filename."""
    normalized = {}
    for k, v in d.items():
        if isinstance(v, str):
            p = Path(v)
            normalized[k] = p.name
        else:
            normalized[k] = v
    return normalized


def check(config: dict, toil_path: Path, test_dir: Path) -> Result:
    """Dry-run Toil WDL to check syntax using --print-graph"""
    wdl_path = resolve_wdl_path(config["path"])
    command = [str(toil_path), str(wdl_path), "--print-graph"]
    try:
        p = subby.cmd(command, shell=False, cwd=test_dir, raise_on_error=False)
    except Exception as e:
        print(f"ERROR executing check: {e}")
        return Result.FAIL

    if p.returncode == 0:
        return Result.PASS
    elif config.get("priority") == "ignore":
        return Result.IGNORE
    else:
        print(f"{config['path']} failed check:\n{p.error or p.output}")
        return Result.FAIL


def run_test(
    config: dict,
    toil_path: Path,
    test_dir: Path,
    data_dir: Path,
    output_dir: Optional[Path],
) -> Result:
    if config.get("priority") == "ignore":
        return Result.IGNORE

    wdl_path = resolve_wdl_path(config["path"])
    wdl_stem = wdl_path.stem
    wdl_output_dir = output_dir / wdl_stem if output_dir else Path(f"{wdl_stem}-out")
    wdl_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(toil_path),
        str(wdl_path),
        "--outputDirectory", str(wdl_output_dir),
        "-m", str(wdl_output_dir / "outputs.json"),
        "--clean", "onSuccess",
        "--realTimeLogging", "False"
    ]

    # Handle input JSON
    if config.get("input"):
        input_json_path = wdl_output_dir / f"{wdl_stem}.inputs.json"
        input_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(input_json_path, "w") as f:
            json.dump(config["input"], f)
        cmd.extend(["--inputs", str(input_json_path)])

    print("Executing:", " ".join(cmd))

    expected_to_fail = config.get("fail", False)

    try:
        p = subby.cmd(cmd, shell=False, cwd=test_dir, raise_on_error=not expected_to_fail)
        rc = p.returncode
    except subprocess.CalledProcessError as e:
        rc = e.returncode
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        if expected_to_fail:
            print(f"Test '{config['path']}' was expected to fail and returned {rc} — PASS")
            return Result.PASS
        else:
            print(f"ERROR: Subby failed with return code {rc}")
            return Result.FAIL
    except Exception as e:
        print(f"Unexpected error: {e}")
        if expected_to_fail:
            print(f"Test '{config['path']}' was expected to fail and errored — PASS")
            return Result.PASS
        return Result.FAIL

    # Handle expected-to-fail
    if expected_to_fail:
        if rc == 0:
            print(f"ERROR: Test '{config['path']}' was expected to fail but passed!")
            return Result.FAIL
        else:
            print(f"Test '{config['path']}' failed as expected — PASS")
            return Result.PASS

    # Check return code
    expected_rc = config.get("returnCodes", 0)
    if expected_rc != "*" and rc != expected_rc:
        print(f"ERROR: Test '{config['path']}' exited {rc}, expected {expected_rc}")
        return Result.FAIL

    if rc != 0:
        print(f"ERROR: Test '{config['path']}' failed unexpectedly")
        return Result.FAIL

    # Validate outputs.json if exists
    outputs_json_path = wdl_output_dir / "outputs.json"
    if outputs_json_path.exists():
        try:
            with open(outputs_json_path) as f:
                outputs = json.load(f)
        except Exception as e:
            print(f"ERROR: Invalid JSON output from toil: {e}")
            return Result.FAIL

        # Normalize paths to just filenames
        outputs_norm = normalize_paths(outputs)
        expected_norm = normalize_paths(config.get("output", {}))

        invalid = []
        for key, value in outputs_norm.items():
            if key not in config.get("exclude_output", []):
                expected = expected_norm.get(key)
                if expected is None or value != expected:
                    invalid.append((key, value, expected))

        if invalid:
            print(f"{config['path']}: output mismatch")
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
    parser.add_argument("--toil-path", type=Path, default=None)
    parser.add_argument("--check-only", action="store_true", default=False)
    args = parser.parse_args()

    toil_path = resolve_toil(args.toil_path)
    test_dir = args.test_dir.resolve()
    data_dir = (args.data_dir or test_dir / "data").resolve()
    output_dir = (args.output_dir or test_dir / "toil_results").resolve()
    test_config = args.test_config or test_dir / "test_config.json"

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(test_config, "r") as f:
        configs = json.load(f)

    if args.num_tests is not None:
        configs = configs[: args.num_tests]

    results = defaultdict(int)
    failed_tests = []

    for config in configs:
        if args.check_only:
            result = check(config, toil_path, test_dir)
        else:
            result = run_test(config, toil_path, test_dir, data_dir, output_dir)

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
