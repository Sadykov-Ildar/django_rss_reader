from django.utils import timezone

from rss_reader.use_cases.rss.dtos import RequestResult
from rss_reader.helpers.date_helpers import get_datetime
from vendoring import fastfeedparser


class RssParsedData:
    def __init__(self):
        self.feed_data: dict = {
            "site_url": "",
            "rss_url": "",
            "title": "",
            "subtitle": "",
            "author": "",
            "feed_type": "",
            "image_url": "",
            "etag": "",
            "modified": "",
        }
        self.entries: list[dict] = []

    def fill_with_data(self, parsed_data: dict, request_result: RequestResult):
        self.feed_data["rss_url"] = request_result.url
        self.feed_data["etag"] = request_result.headers.get("Etag") or ""
        self.feed_data["modified"] = request_result.headers.get("Last-modified") or ""

        if parsed_data:
            self._make_feed_data(parsed_data)
            self._make_entries_data(parsed_data)

    def _make_feed_data(self, parsed_data: dict):
        feed_data: dict = parsed_data.get("feed", {})
        if feed_data:
            self.feed_data["site_url"] = feed_data["link"]
            self.feed_data["title"] = feed_data.get("title", "")
            self.feed_data["subtitle"] = feed_data.get("subtitle", "")
            self.feed_data["author"] = feed_data.get("author", "")
            self.feed_data["feed_type"] = parsed_data.get("feed_type", "rss")
            self.feed_data["image_url"] = feed_data.get("image_url", "")

    def _make_entries_data(self, parsed_data):
        entries_data = parsed_data.get("entries", [])
        for entry in entries_data:
            published = get_datetime(entry.get("published"))
            if published is None:
                published = timezone.now()

            summary = entry.get("description", "")
            content = entry.get("content")
            if content:
                content = content[0]["value"]
            self.entries.append(
                {
                    "link": entry.get("link", ""),
                    "title": entry.get("title", ""),
                    "published": published,
                    "author": entry.get("author", ""),
                    "content": content or "",
                    "summary": summary,
                }
            )


class RssParser:
    @staticmethod
    def parse(
        requests_results: list[RequestResult],
    ) -> list[tuple[RequestResult, RssParsedData]]:
        result = []

        for request_result in requests_results:
            rss_data = RssParsedData()
            parsed_data = {}
            if not request_result.error_message:
                if request_result.status != 304:
                    try:
                        parsed_data = fastfeedparser.parse(request_result.content)
                    except ValueError as e:
                        request_result.error_message = str(e)

                rss_data.fill_with_data(parsed_data, request_result)

            result.append((request_result, rss_data))

        return result
