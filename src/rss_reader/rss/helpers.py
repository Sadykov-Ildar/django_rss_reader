from typing import TYPE_CHECKING
from urllib.parse import urljoin

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


def is_soup_html(soup: BeautifulSoup) -> bool:
    if len(soup.find_all()) > 2:  # More than just <html> and <body>
        return True
    # look for specific common HTML tags
    common_tags = ["div", "p", "a", "img", "span", "table", "h1", "head", "body"]
    for tag in common_tags:
        if soup.find(tag):
            return True
    return bool(soup.find())


def extract_feed_urls_from_html(url: str, soup: BeautifulSoup) -> list[str]:
    """
    Trying to parse HTML page and get links to RSS feeds.

    :param url: URL that we suspect to be HTML page, used to resolve relative urls from that page
    :param soup: BeautifulSoup of a contents of a page
    :return: list of absolute RSS urls
    """
    rss_urls = set()
    for link in soup.find_all(
        "link", rel="alternate", type=("application/rss+xml", "application/atom+xml")
    ):
        href = link.get("href", "")
        if href:
            assert isinstance(href, str)
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(url, href)
            rss_urls.add(href)

    for link in soup.find_all("link", rel="feed"):
        href = link.get("href", "")
        if href:
            assert isinstance(href, str)
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(url, href)
            rss_urls.add(href)

    rss_urls = list(rss_urls)
    return rss_urls
