# WDL Tests

Test cases and tools for testing WDL implementations.

## Specification Tests

Starting with [WDL 1.1.1](https://github.com/openwdl/wdl/tree/wdl-1.1), nearly all the examples in the WDL specification are also test cases that conform to the [WDL markdown test specification](docs/MarkdownTests.md).
This means that a [script](scripts/extract_tests.py) can be used to extract the examples into WDL files and configuration matching the [specification](docs/Specification.md). These can then be used for automated testing.

The tests extracted from the WDL specifications are available here:

* [WDL 1.1](spec/wdl-1.1/)

See [this script](scripts/run_tests_miniwdl.py) for an example of running the tests using [MiniWDL](https://github.com/chanzuckerberg/miniwdl).

See [this script](scripts/run_tests_sprocket.py) for an example of running the tests using [Sprocket](https://github.com/stjude-rust-labs/sprocket).

## Contributing Test Suites

Contributions of additional test suites are greatly appreciated - especially those convering features/behaviors that are not already covered by existing test cases.
If you would like to request the addition of a test case/suite, please open an [issue](https://github.com/openwdl/wdl-tests/issues).
If you would like to contribute a test suite, please submit the WDL file(s) and test configuration matching the [specification](docs/Specification.md) in a [pull request](https://github.com/openwdl/wdl-tests/pulls).
Contributed tests should be placed in a subfolder of the [contributed](contributed/) folder.
You should also add a description of the test suite to the [README](contributed/README.md) file.
