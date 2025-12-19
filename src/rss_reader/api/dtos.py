from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RssUrlArgs:
    """
    Dataclass for making requests for rss urls
    """

    url: str
    etag: str = ""
    modified: str = ""
    delay: int = 0  # to avoid hammering the same server


@dataclass
class RequestResult:
    url: str
    headers: dict
    status: int = 0
    content: str = ""
    error_message: str = ""
