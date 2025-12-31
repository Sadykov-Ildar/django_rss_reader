from rss_reader.rss.dtos import RssUrlArgs, RequestResult
from rss_reader.rss.rss_parser import RssParsedData, RssParser


class NetworkRepoMock:
    def __init__(self, request_results: list[RequestResult]):
        self.parser = RssParser()
        self.request_results = {x.url: x for x in request_results}

    def get_parsed_results(
        self, rss_urls_args: list[RssUrlArgs]
    ) -> list[tuple[RequestResult, RssParsedData]]:
        requests_results = []
        for rss_url_arg in rss_urls_args:
            url = rss_url_arg.url
            request_result = self.request_results[url]
            requests_results.append(request_result)

        result = self.parser.parse(requests_results)

        return result
