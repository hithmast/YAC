import time
import csv
import requests
from utils import parser
import logging
import os
from datetime import datetime
from urllib.parse import unquote


#Globals
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

def perform_login(username, password, website_info, success_indicators, failure_indicators):
    try:
        
        if not running:
            return False, "Paused"
        
        
        payload = {'username': username, 'password': password}
        payload.update(website_info['payload'])
        
        headers = website_info['headers']  
        response = requests.post(reverse_url_encoding(website_info['website']['login_url']), data=payload, headers=headers)
        
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
            
    except Exception as e:
        logging.error(f"Exception occurred during login for username: {username}: {str(e)}")
        return False, "Exception occurred"

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


def single_check(websites):
    print("Choose a website to perform a single check:")
    for i, (website_name, _) in enumerate(websites.items(), start=1):
        print(f"{i}. {website_name}")

    try:
        choice = int(input("Enter the number of the website: "))
        website_name, website_info = list(websites.items())[choice - 1]
        perform_check(website_name, website_info)
    except (IndexError, ValueError):
        logging.error("Invalid choice. Please enter a valid number.")

def multiple_check(websites):
    print("Choose multiple websites to perform checks (enter numbers separated by comma):")
    for i, (website_name, _) in enumerate(websites.items(), start=1):
        print(f"{i}. {website_name}")

    try:
        choices = input("Enter the numbers of the websites: ")
        choices = [int(choice.strip()) for choice in choices.split(',')]
        for choice in choices:
            website_name, website_info = list(websites.items())[choice - 1]
            perform_check(website_name, website_info)
    except (IndexError, ValueError):
        logging.error("Invalid choices. Please enter valid numbers separated by commas.")

def perform_check(website_name, website_info):
    global results  
    credentials_file = website_info['website']['credentials_file']
    output_file = website_info['website']['output_file']
    success_indicators = website_info['website']['success_indicators']
    failure_indicators = website_info['website']['failure_indicators']

    logging.info(f"Processing website: {website_name}")

    
    valid_logins = 0
    start_time = time.time()

    
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

#main Funcitons
def main():
    
    log_file = "output.log"
    setup_logging(log_file)

    
    websites = parser.read_website_config('config/websites_config.ini')

    
    while True:
        check_type = input("Do you want to perform single or multiple checks? (single/multiple): ").lower()
        if check_type == 'single':
            single_check(websites)
            break
        elif check_type == 'multiple':
            multiple_check(websites)
            break
        else:
            print("Invalid input. Please enter 'single' or 'multiple'.")

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
