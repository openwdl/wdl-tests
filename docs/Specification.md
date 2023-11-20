# WDL Test Specification

This specification describes the directory structure, file naming conventions, and configuration parameters for creating a WDL test suite.

## Directory structure

```
tests
|_ data
|  |_ input1.txt
|  |_ output1.txt
|_ foo.wdl
|_ bar_task.wdl
|_ ...
|_ test_config.json
```

A test suite is a directory structure containing WDL files, configuration, and input/output data files (if necessary).

The default directory name is `tests`, but an alternate name may be used.

## Test cases

Within the `tests` directory are any number of test cases.
Each test case is a separate file named `<target>.wdl`, where `target` is the name of the workflow or task within the example that should be executed by the test framework.

Each test case must be valid WDL, including a `version` header.
All test cases in the same folder must use the same WDL version.
A test case may import any other WDL in the same directory.

### File naming conventions

The following naming conventions are used for test cases:

* If the file name is of the form `<target>_task.wdl` then it is assumed that `target` is a task, otherwise it is assumed to be a workflow (unless the `type` configuration parameter is specified).
* If the file name is of the form `<target>_fail.wdl` then it is assumed that the test is expected to fail (unless the `fail` configuration parameter is specified).
* If the file name is of the form `<target>_fail_task.wdl` then it is both `type: "task"` and `fail: true` are assumed unless the configuration parameters specify differently.
* If the file name ends with `_resource.wdl` then it not executed as a test. Such resource WDLs are intended only to be imported by other examples.

## Test configuration

The `tests` directory may contain a `test_config.json` file that contains a JSON array of test case configuration objects.
If a configuration object is not provided for a test case, then that test case's configuration consists of the default values for all parameters.

```json
[
  {
    "id": "foo",
    "path": "foo.wdl",
    "target": "foo",
    "type": "workflow",
    "priority": "required",
    "fail": false,
    "return_code": "*",
    "exclude_output": [],
    "dependencies": [],
    "input": {
      "foo.x": 1
    },
    "output": {
      "foo.y": true
    }
  },
  {
    "id": "bar",
    ...
  }
]
```

The following are the configuration parameters that must be supported by all test frameworks.
Test frameworks may support additional parameters, and should ignore any unrecognized parameters.

* `path`: The path to the WDL file.
* `target`: The name of the workflow or task the test framework should execute. Defaults to the file name (the last element of `path`) without the `.wdl` extension or any of the [special suffixes](#file-naming-conventions). Required if the target name is different from the file name, even if the test only contains a single workflow/task.
* `id`: The unique identifier of the test case. Defaults to `target`.
* `type`: One of `"task"`, `"workflow"`, or `"resource"`. The default is `"workflow"`, unless the file name ends with `_task` or `_resource`. Must be set explicitly if the example does not contain a workflow, if the test framework should only execute a specific task (which should be specified using the `target` parameter), or if the example should not be executed at all and only contains definitions that should be available for import by other examples (`type: "resource"`).
* `priority`: The priority of the test. Must be one of the following values. Defaults to `"required"`.
    * `"required"`: The test framework must execute the test. If the test fails, it must be reported as an error.
    * `"optional"`: The test framework can choose whether to execute the test. If the test fails, it must be reported as a warning.
    * `"ignore"`: The test framework must not execute the test.
* `fail`: Whether the test is expected to fail. If `true` then a failed execution is treated as a successful test, and a successful execution is treated as a failure. Defaults to `false`.
* `exclude_output`: A name or array of names of output parameters that should be ignored when comparing the expected and actual outputs of the test.
* `return_code`: The expected return code of the task. If a task marked `fail: true` fails but with a different return code, then the test is treated as a failure. My either be an integer or an array of integers. The value `"*"` indicates that any return code is allowed. Defaults to `"*"`.
* `dependencies`: An array of the test's dependencies. If the test framework is unable to satisfy any dependency of a required test, then the test is instead treated as optional. At a minimum, the test framework should recognize dependencies based on runtime attributes. For example, `dependencies: ["cpu", "memory"]` indicates that the task has CPU and/or memory requirements that the test framework might not be reasonably expected to provide, and thus if the test fails due to lack of CPU or memory resources it should be reported as a warning rather than an error.
* `tags`: Arbitrary string or array of string tags that can be used to filter tests. For example, a time-consuming test could have `tags: "long"`, and the test framework could be executed with `--exclude-tags "long"` to exclude running such tests.
* `input`: The input object to the test case. Must conform to the [standard input specification](../SPEC.md#input-and-output-formats).
* `output`: The expected output object from executing the test case with the given inputs. Must conform to the [standard output specification](../SPEC.md#input-and-output-formats).

For a workflow test, `return_code` and `dependencies` configuration parameters apply to any subworkflow or task called by the workflow, to any level of nesting.
For example, if a workflow has `dependencies: ["gpu"]` and it calls a task that has `gpu: true` in its runtime section, and the test framework is not executing on a system that provides a GPU, then the test is treated as optional.

The following is an example of a task test that is optional and expected to fail with a return code of `1`:

```wdl
version 1.1
task optional_fail {
  command <<<
    exit 1
  >>>
}
```

```json
{
  "type": "task",
  "priority": "optional",
  "fail": true,
  "return_code": 1
}
```

## Input/output files

The `data` directory is an optional directory under `tests` that contains any input or output files used by the tests.
If a test case has a `File` type input or output, then the path assigned to that parameter - whether in the WDL code itself or in the test input/output JSON object - must be relative to the `data` directory.

For example, the following test case (`example1.wdl`) references files shown in the [example directory struture](#directory-structure).

```wdl
version 1.1
workflow example1 {
  input {
    File infile
  }

  output {
    File outfile
  }

  ...
}
```

```json
[
  {
    "path": "example1.wdl",
    "input": {
      "example1.infile": "input1.txt"
    },
    "output": {
      "example1.outfile": "output1.txt"
    }
  }
]
``` 
