# YAC (Yes Another Checker)

YAC is a script designed to perform login checks for multiple websites using a list of credentials. It supports both single and multiple website checks and logs the results, including successful and failed login attempts.

## Features

- **Single and Multiple Checks**: Users can choose to perform login checks on a single website or multiple websites at once.
- **CSV Input/Output**: The script reads credentials from a CSV file and outputs the results, including the status of each login attempt.
- **Logging**: All actions and results are logged in a log file for later review.
- **URL Decoding**: Handles URL decoding for login URLs to ensure proper requests are made.

## Requirements

- Python 3.x
- `requests` library
- `csv` module (built-in)
- `logging` module (built-in)
- A custom `parser` module for reading website configurations.

## Installation

1. Clone this repository:
   ```bash
   git clone -b main-line-args https://github.com/hithmast/YAC.git
   ```
   
2. Change to the project directory:
   ```bash
   cd YAC
   ```

3. Ensure you have the required libraries installed. You can install them using pip:
   ```bash
   pip install requests
   ```

## Configuration

1. Create a configuration file named `websites_config.ini` in the `config` directory. The file should include:
   - `credentials_file`: Path to the CSV file containing usernames and passwords.
   - `output_file`: Path to the output CSV file where results will be saved.
   - `login_url`: The URL for the login form (will be URL-encoded).
   - Any extra headers should start with `h_`, and any extra payload fields should start with `p_`.
   - `success_indicators`: Indicators to identify a successful login.
   - `failure_indicators`: Indicators to identify a failed login.

   Example structure of `websites_config.ini`:
   ```ini
   [WebsiteName]
   credentials_file = path/to/credentials.csv
   output_file = path/to/results.csv
   login_url = https://example.com/login
   h_User-Agent = Mozilla/5.0
   p_extra_field = extra_value
   success_indicators = login successful, welcome
   failure_indicators = invalid username, invalid password
   ```

2. Prepare a CSV file for credentials (`credentials.csv`):
   ```csv
   Username,Password
   user1,password1
   user2,password2
   ```

## Usage

1. Run the script:
   ```bash
   python main.py
   ```

2. You will be prompted to choose between performing single or multiple checks. Follow the on-screen instructions.

3. Upon completion, results will be saved in the specified output CSV file.

## Logging

Logs will be generated daily in the `logs` directory. The log file will contain details about login attempts, including successes and failures.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have suggestions or improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
