# WDL Tests

Test cases and tools for testing WDL implementations.

## Specification Tests

Starting with [WDL 1.1.1](https://github.com/openwdl/wdl/tree/wdl-1.1), nearly all the examples in the WDL specification are also test cases that conform to the [WDL markdown test specification](docs/MarkdownTests.md).
This means that a [script](scripts/extract_tests.py) can be used to extract the examples into WDL files and configuration matching the [specification](docs/Specification.md). These can then be used for automated testing.

The extracted example tests are available here:

* [WDL 1.1](spec/wdl-1.1/)

See [this script](scripts/run_tests_miniwdl.py) for an example of running the tests using [MiniWDL](https://github.com/chanzuckerberg/miniwdl).