import re
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from vendoring.html_sanitizer.sanitizer import sanitize_html

if TYPE_CHECKING:
    from rss_reader.use_cases.rss.rss_parser import RssParsedData

_class_pattern = re.compile(r'(?s)class="(.*?)"')


def filter_parsed_data(rss_data: RssParsedData, site_url: str):
    result = []
    entries_data = rss_data.entries
    for entry in entries_data:
        link = entry["link"]
        if "youtube.com/shorts/" in link:  # YouTube shorts are bad
            continue
        content = entry["content"]
        summary = entry["summary"]

        if content:
            if content.startswith(summary[:100]):
                # summary is often the same as content - skip it
                summary = ""

            content = clean_html(content)
            content = resolve_urls(content, site_url)
            content = sanitize_html(content, "utf-8", "text/html")

        if summary:
            summary = clean_html(summary)
            summary = resolve_urls(summary, site_url)
            summary = sanitize_html(summary, "utf-8", "text/html")

        entry["content"] = content
        entry["summary"] = summary

        result.append(entry)

    return result


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
