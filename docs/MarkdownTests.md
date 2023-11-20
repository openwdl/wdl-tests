# WDL Markdown Test Specification

Example WDL code in a Markdown file that conforms to the format described below can be automatically extracted into a structure matching the [WDL test specification](Specification.md).
This can then be used with automated testing tools.

````html
<details>
  <summary>
  Example: {file name}

  ```wdl
  {WDL code}
  ```
  </summary>
  <p>
  Example input:

  ```json
  {input json}
  ```

  Example output:

  ```json
  {output json}
  ```

  Test config:

  ```json
  {config json}
  ```
  </p>
</details>
````

Each example must appear within an [HTML `details` element](https://www.w3.org/TR/2011/WD-html5-author-20110809/the-details-element.html).

The `summary` element must contain the example name and the WDL code.

The example name must appear first, and must be formatted as `Example: {name}` and appear on a line by itself.
The name must be globally unique within the Markdown file.

* If the name is of the form `<target>_task` then it is assumed that `target` is a task, otherwise it is assumed to be a workflow (unless the `type` configuration parameter is specified).
* If the name is of the form `<target>_fail` then it is assumed that the test is expected to fail (unless the `fail` configuration parameter is specified).
* If the name is of the form `<target>_fail_task` then it is both `type: "task"` and `fail: true` are assumed unless the configuration parameters specify differently.
* If the name ends with `_resource` then it not executed as a test. Such resource WDLs are intended only to be imported by other examples.

The WDL code must be valid, runnable code, and it must appear in a [fenced code block](https://spec.commonmark.org/0.30/#fenced-code-blocks) with the info string `wdl`.

One example may import another example using its name suffixed by `.wdl`.

````html
<details>
  <summary>
  Example: example1.wdl

  ```wdl
  task example1 {
    ...
  }
  ```
  </summary>
  <p>...</p>
</details>

<details>
  <summary>
  Example: example2.wdl

  ```wdl
  import "example1.wdl"

  workflow example2 {
    call example1.mytask { ... }
  }
  ```
  </summary>
  <p>...</p>
</details>
````

Additional information that conforms to the [specification](Specification.md) may be provided in a [paragraph (`<p></p>`)](https://www.w3.org/TR/2011/WD-html5-author-20110809/content-models.html#paragraphs) block between the end of the summary (`</summary>`) and the end of the details (`</details>`).
Each of these sections is optional, but if provided must conform to the format described below.

Each section begins with a header on a line by itself, and ending with a colon, e.g., `Example input:`.
Following the header must be a fenced code block with the info string `json`.
The code block must contain a valid JSON object that conforms to the specification.

````html
<details>
  <summary>
  Example: empty

  ```wdl
  task both_empty {
    input {
        File f
        String s = ""
    }

    command <<<
    echo -n ~{s} > foo
    if [ -s ~{f} ] || [ -s foo ]; then
        echo "false" > both_empty
    else
        echo "true" > both_empty
    fi
    >>>

    output {
        Boolean b = read_boolean(both_empty)
    }
  }
  ```
  </summary>
  <p>
  Example input:

  ```json
  {
    empty.f = "not_empty.txt"
  }
  ```

  Example output:

  ```json
  {
    empty.b = false
  }
  ```

  Test config:

  ```json
  {
    "type": "task",
    "priority": "optional"
  }
  ```
  </p>
</details>
````

The `Example input` section provides the test inputs.
The input JSON object must be written according to the [standard input specification](../SPEC.md#input-and-output-formats), i.e., with the workflow/task name as a prefix for all parameter names.
If the workflow/task does not contain any required inputs, the `Example input` section may be omitted.

The `Example output` sections provides the expected outputs from running the workflow/task with the test inputs.
The output JSON object must be written according to the The input JSON object must be written according to the [standard input specification](../SPEC.md#input-and-output-formats).
If the workflow/task does not produce any outputs, the `Example output` section may be omitted.
If an output should not be validated, it must be listed in the `exclude_outputs` configuration parameter.

A `File` input or output may be assigned a path relative to a test data directory (either in the WDL code itself or in the `Example input/output` object).
The path to the data directory must be specified when running the script to extract the tests cases.

The `Test config` section specifies metadata used by the testing framework.
The allowed configuration parameters and their types, allowed values, and default values, are specified in the [WDL test specification](Specification.md).
The `Test config` section is optional.
If any configuration parameters are not specified, then they have their default values.
