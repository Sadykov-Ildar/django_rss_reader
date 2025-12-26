import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

_class_pattern = re.compile(r'(?s)class="(.*?)"')


def clean_html(content: str) -> str:
    """
    Removes CSS classes from HTML.
    """
    content = re.sub(_class_pattern, "", content)

    return content


def resolve_urls(content: str, url: str) -> str:
    """
    Replaces relative urls with absolute urls in HTML content.
    """
    soup = BeautifulSoup(content, "lxml")

    for a in soup.find_all("a"):
        # if this tag have href property
        if a.get("href"):
            # Make link in absolute format
            a["href"] = urljoin(url, a["href"])
    # Find all link tags
    for link in soup.find_all("link"):
        # if this tag have href property
        if link.get("href"):
            # Make link in absolute format
            link["href"] = urljoin(url, link["href"])
    for img in soup.find_all("img"):
        # if this tag have src property
        if img.get("src"):
            # Make link in absolute format
            img["src"] = urljoin(url, img["src"])
    content = str(soup)

    return content
