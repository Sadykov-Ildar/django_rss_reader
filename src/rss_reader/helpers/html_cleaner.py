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
        href = a.get("href")
        if href and isinstance(href, str):
            a["href"] = urljoin(url, href)
    for link in soup.find_all("link"):
        href = link.get("href")
        if href and isinstance(href, str):
            link["href"] = urljoin(url, href)
    for img in soup.find_all("img"):
        href = img.get("src")
        if href and isinstance(href, str):
            img["src"] = urljoin(url, href)
    content = str(soup)

    return content
