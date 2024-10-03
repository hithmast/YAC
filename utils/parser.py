import configparser
from urllib.parse import quote
from configparser import ExtendedInterpolation

def read_website_config(config_file):
    config = configparser.ConfigParser(interpolation=ExtendedInterpolation())
    config.read(config_file)
    websites = {}

    for section in config.sections():
        website = {}
        headers = {}
        payload = {}
        # Read all configuration parameters for each website
        for key, value in config.items(section):
            if key == 'login_url':
                # Encode the login_url to handle special characters
                website[key] = quote(value, safe=':/?=&')
            elif key in ['success_indicators', 'failure_indicators']:
                website[key] = value.split(',')
            elif key.startswith('h_'):
                # Extra header
                headers[key[2:]] = value
            elif key.startswith('p_'):
                # Extra payload field
                payload[key[2:]] = value
            else:
                website[key] = value

        # Add the website, headers, and payload to the dictionary
        websites[section] = {
            'website': website,
            'headers': headers,
            'payload': payload
        }

    return websites
