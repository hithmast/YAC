from urllib.parse import unquote


def reverse_url_encoding(encoded_url: str) -> str:
    """Undo the percent-encoding the config parser applies to login_url.

    parser.read_website_config() quote()s login_url so it can live safely
    inside an INI value; every backend needs the real URL back before use.
    """
    return unquote(encoded_url)
