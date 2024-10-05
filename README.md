# YAC: Yet Another Checker - main.py

## Overview

The `yac` module of YAC (Yet Another Checker) is a command-line tool for checking the validity of login credentials across multiple websites. It supports customizable website configurations and logging capabilities, making it an efficient solution for automated credential validation.

## Features

- Perform single or multiple login checks on specified websites.
- Support for custom payloads and headers for each website.
- Logging of results with timestamps, including successful and failed login attempts.
- Save results to a CSV file.
- Command-line interface with argparse for ease of use.

## Prerequisites

- Python 3.6 or higher
- Required Python packages:
  - `requests`
  - `argparse`
  - Any other dependencies as specified in the `setup.py` file

## Installation

Clone the repository and install the package:

```bash
git clone -b package https://github.com/hithmast/YAC.git
cd YAC
sudo python setup.py install # or pip install . 
```

Ensure that you have the necessary configuration file located at `~/.yac/config/websites_config.ini`. The script will utilize this file to perform login checks.

## Usage

### Command-Line Interface

The script can be run from the command line with various options:

```bash
yac [options]
```

### Options

- `-c`, `--config`: Print a list of websites in the config file.
- `-s`, `--single`: Perform a single check on the specified website number.
- `-m`, `--multiple`: Perform multiple checks on specified website numbers (comma-separated).
- `-C`, `--combo`: Path to a credentials file for a single check.
- `-o`, `--output`: Specify the output file for the results of a single check.

### Examples

#### Print Configured Websites

```bash
yac -c
```

#### Perform a Single Check

```bash
yac -s 1 -C credentials.csv -o output.csv
```

#### Perform Multiple Checks

```bash
python main.py -m 1,2,3
```

## Logging

The script generates a log file `output.log` in a `logs` directory, creating a subdirectory based on the current date. This log file contains detailed information about the execution, including successful and failed login attempts.

## Saving Results

Upon termination (either by completing the checks or by pressing `Ctrl+C`), the user will be prompted to save the results to a file named `results.csv`.

## Configuration

The website configurations should be defined in the `~/.yac/config/websites_config.ini` file. The configuration file should specify the login URLs, success and failure indicators, payloads, and headers for each website.

## Contributing

Contributions are welcome! Please fork the repository, make your changes, and submit a pull request. Ensure that your code follows the project’s coding standards and includes relevant tests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

**Ali Emara**  
[ali.emara175@gmail.com](mailto:ali.emara175@gmail.com)  
[GitHub](https://github.com/hithmast)
