#!/usr/bin/env python3
from argparse import ArgumentParser
import json
from pathlib import Path
import re
import shutil
from typing import Optional


TEST_RE = re.compile(
    r"^<details>\s*<summary>\s*Example: (.+?)\s*```wdl(.+?)```\s*</summary>\s*(?:<p>\s*(?:Example input:\s*```json(.*?)```)?\s*(?:Example output:\s*```json(.*?)```)?\s*(?:Test config:\s*```json(.*?)```)?\s*</p>\s*)?</details>$",
    re.I | re.S,
)
FILENAME_RE = re.compile(r"(.+?)(_fail)?(_task)?.wdl")
VERSION_RE = re.compile(r"version ([\d.]+)")


def write_test_files(m: re.Match, output_dir: Path, version: str, config: list):
    file_name, wdl, input_json, output_json, config_json = m.groups()

    if file_name is None:
        raise Exception("Missing file name")
    f = FILENAME_RE.match(file_name)
    if f is None:
        raise Exception(f"Invalid file name: {file_name}")
    target, is_fail, is_task = f.groups()

    wdl = wdl.strip()
    v = VERSION_RE.search(wdl)

    if v is None:
        raise Exception("WDL does not contain version statement")
    elif str(v.group(1)) != str(version):
        raise Exception(f"Invalid WDL version {wdl}")

    wdl_file = output_dir / file_name
    if wdl_file.exists():
        raise Exception(f"Test file already exists: {wdl_file}")
    with open(wdl_file, "w") as o:
        o.write(wdl)

    if config_json is not None:
        config_entry = json.loads(config_json)
    else:
        config_entry = {}

    config_entry["id"] = target
    config_entry["path"] = str(wdl_file)
    if "type" not in config_entry:
        config_entry["type"] = "task" if is_task else "workflow"
    if "target" not in config_entry:
        config_entry["target"] = target
    if "priority" not in config_entry:
        config_entry["priority"] = "required"
    if "fail" not in config_entry:
        config_entry["fail"] = bool(is_fail)
    if "exclude_output" not in config_entry:
        config_entry["exclude_output"] = []
    elif isinstance(config_entry["exclude_output"], str):
        config_entry["exclude_output"] = [config_entry["exclude_output"]]
    if "returnCodes" not in config_entry:
        config_entry["returnCodes"] = "*"
    elif isinstance(config_entry["returnCodes"], str):
        config_entry["returnCodes"] = [config_entry["returnCodes"]]
    if "dependencies" not in config_entry:
        config_entry["dependencies"] = []
    elif isinstance(config_entry["dependencies"], str):
        config_entry["dependencies"] = [config_entry["dependencies"]]
    if "tags" not in config_entry:
        config_entry["tags"] = []
    elif isinstance(config_entry["tags"], str):
        config_entry["tags"] = [config_entry["tags"]]

    if input_json is not None:
        input_json = input_json.strip()
    if input_json:
        config_entry["input"] = json.loads(input_json)
    else:
        config_entry["input"] = {}

    if output_json is not None:
        output_json = output_json.strip()
    if output_json:
        config_entry["output"] = json.loads(output_json)
    else:
        config_entry["output"] = {}

    config.append(config_entry)


def extract_tests(spec: Path, data_dir: Optional[Path], output_dir: Path, version: str):
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    config = []
    with open(spec) as s:
        buf = None
        for line in s:
            if buf is None and "<details>" in line:
                buf = [line]
            elif buf is not None:
                buf.append(line)
                if "</details>" in line:
                    ex = "".join(buf)
                    buf = None
                    m = TEST_RE.match(ex)
                    if m is None:
                        raise Exception(f"Regex does not match example {ex}")
                    else:
                        try:
                            write_test_files(m, output_dir, version, config)
                        except Exception as e:
                            raise Exception(
                                f"Error writing files for example {ex}"
                            ) from e

    config_file = output_dir / "test_config.json"
    with open(config_file, "w") as o:
        json.dump(config, o, indent=2)

    if data_dir is not None and data_dir.exists():
        dest1 = Path.cwd()
        dest2 = output_dir / data_dir.name
        shutil.copytree(data_dir, dest1, symlinks=True, dirs_exist_ok=True)
        shutil.copytree(data_dir, dest2, symlinks=True, dirs_exist_ok=True)


def main():
    parser = ArgumentParser(
        usage="%(prog)s [options]",
        description=(
            "Extracts conforming examples from a Markdown file, such as a WDL specification, into "
            "a test directory structure for use with an automated test harness."
        ),
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=Path,
        default=Path("SPEC.md"),
        help="Path to the input Markdown file",
    )
    parser.add_argument(
        "-d",
        "--data-dir",
        type=Path,
        default=None,
        help="Path to the test data directory (if any)",
    )
    parser.add_argument(
        "-O",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Path to the directory where test files will be written",
    )
    parser.add_argument(
        "-v",
        "--version",
        choices=["1.0", "1.1", "1.2", "2.0", "development"],
        default="1.1",
        help="WDL version of extracted test files",
    )
    args = parser.parse_args()
    extract_tests(args.input_file, args.data_dir, args.output_dir, args.version)


if __name__ == "__main__":
    main()
