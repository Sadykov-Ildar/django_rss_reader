from collections import Counter

from bs4 import BeautifulSoup

from rss_reader.use_cases.rss.dtos import RssUrlArgs
from rss_reader.use_cases.rss.helpers import is_soup_html, extract_feed_urls_from_html
from rss_reader.exceptions import URLValidationError
from rss_reader.helpers.urls import get_base_url


def import_from_rss_urls(user, rss_urls: list[str], feed_repo, network_repo) -> str:
    """
    Requests urls and creates user feeds and entries.

    :param user: User
    :param rss_urls: List of urls
    :return: Error message
    """
    error_messages = []

    rss_urls_args = []
    for rss_url in rss_urls:
        try:
            created = feed_repo.check_and_create_user_feed(rss_url, user)
            if not created:
                rss_urls_args.append(RssUrlArgs(url=rss_url))
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")

    parsed_results = network_repo.get_parsed_results(rss_urls_args)

    for request_result, parsed_data in parsed_results:
        error_message = request_result.error_message
        url = request_result.url
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        else:
            try:
                feed_repo.create_feed_and_entries(user, parsed_data)
            except URLValidationError as e:
                error_messages.append(f"{url}: {e.message}")

    error_message = "<br>".join(error_messages)

    return error_message


def process_rss_url(request, rss_url: str, feed_repo, network_repo, rss_parser):
    """
    Creates Feed by one RSS URL, done synchronously by user request

    :return: Error message
    """
    rss_url = rss_url.strip()
    user = request.user

    try:
        created = feed_repo.check_and_create_user_feed(rss_url, user)
    except URLValidationError as e:
        return e.message
    if created:
        # Done without errors
        return ""

    requests_results = network_repo.send_requests([RssUrlArgs(url=rss_url)])
    request_result = requests_results[0]
    error_message = request_result.error_message
    if error_message:
        return error_message

    soup = BeautifulSoup(request_result.content, "lxml")
    is_html = False
    if is_soup_html(soup):
        # HTML - need to get feed urls from contents
        rss_urls = extract_feed_urls_from_html(rss_url, soup)
        if rss_urls:
            error_message = import_from_rss_urls(
                user, rss_urls, feed_repo, network_repo
            )
            is_html = True

    if not is_html:
        parsed_results = rss_parser.parse(requests_results)
        request_result, parsed_data = parsed_results[0]
        error_message = request_result.error_message
        if error_message:
            return error_message
        try:
            feed_repo.create_feed_and_entries(user, parsed_data)
        except URLValidationError as e:
            return e.message

    return error_message


def refresh_feeds(feed_repo, network_repo) -> str:
    """
    Refresh all feeds that are due to update.
    Used in background task.

    :return: Error message
    """
    feeds_by_urls = {}
    rss_urls_args = []
    feeds = feed_repo.get_feeds_for_refresh()
    site_urls_counter = Counter()
    for feed in feeds:
        site_url = get_base_url(feed.rss_url)

        feeds_by_urls[feed.rss_url] = feed
        rss_urls_args.append(
            RssUrlArgs(
                url=feed.rss_url,
                etag=feed.etag,
                modified=feed.modified,
                delay=site_urls_counter[site_url],
            )
        )
        site_urls_counter[site_url] += 1

    error_messages = []
    parsed_results = network_repo.get_parsed_results(rss_urls_args)
    for request_result, parsed_data in parsed_results:
        error_message = request_result.error_message
        url = request_result.url
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        feed = feeds_by_urls[url]
        feed_repo.refresh_feed(feed, parsed_data, request_result)

    error_message = "<br>".join(error_messages)

    return error_message
