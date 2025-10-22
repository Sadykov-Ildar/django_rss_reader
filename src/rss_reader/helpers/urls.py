from urllib.parse import urlparse


def get_base_url(url: str) -> str:
    parsed_url = urlparse(url)
    site_url = parsed_url.scheme + "://" + parsed_url.netloc + "/"
    return site_url
