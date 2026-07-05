from urllib.parse import quote

from utils.urlutil import reverse_url_encoding


def test_reverse_url_encoding_roundtrip():
    original = "https://example.com/login?x=1&y=2 3"
    encoded = quote(original, safe=":/?=&%")
    assert reverse_url_encoding(encoded) == original


def test_reverse_url_encoding_plain_url_unchanged():
    url = "https://example.com/login"
    assert reverse_url_encoding(quote(url, safe=":/?=&%")) == url
