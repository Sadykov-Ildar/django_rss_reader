import pytest

from tests.mocks.network_repo_mock import NetworkRepoMock
from rss_reader.use_cases.rss.rss_api import refresh_feeds, import_from_rss_urls
from tests.test_rss_reader.helpers import get_new_request_result


@pytest.mark.django_db()
def test_refresh_no_new_data(import_rss, feed_repo, user):
    network_repo = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed.xml",
            ),
        ],
    )
    refresh_feeds(
        feed_repo,
        network_repo,
    )
    user_feeds = feed_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    user_entries = feed_repo.get_filtered_user_entries(user_feed)
    assert len(user_entries) == 9


@pytest.mark.django_db()
def test_refresh_new_data(import_rss, feed_repo, user):
    network_repo = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed_refresh_new_data.xml",
            ),
        ],
    )
    user_feeds = feed_repo.get_user_feeds(user)
    user_feed = user_feeds[0]

    user_entries = feed_repo.get_filtered_user_entries(user_feed)
    assert len(user_entries) == 9

    error_message = refresh_feeds(
        feed_repo,
        network_repo,
    )
    assert error_message == ""

    user_feeds = feed_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    user_entries = feed_repo.get_filtered_user_entries(user_feed)
    assert len(user_entries) == 10


@pytest.mark.django_db()
def test_refresh_410(import_rss, feed_repo, user):
    network_repo = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed.xml",
                status=410,
            ),
        ],
    )

    user_feeds = feed_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    assert user_feed.feed.updates_enabled

    error_message = refresh_feeds(
        feed_repo,
        network_repo,
    )
    assert error_message == ""

    user_feeds = feed_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    assert not user_feed.feed.updates_enabled


@pytest.mark.django_db()
def test_merging_feeds(feed_repo, user):
    network_repo_https = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed.xml",
            ),
            get_new_request_result(
                url="https://example.com/feed.xml",
                file_name="test_feed_https.xml",
            ),
        ],
    )
    error_message = import_from_rss_urls(
        user,
        [
            "http://example.com/feed.xml",
            "https://example.com/feed.xml",
        ],
        feed_repo,
        network_repo_https,
    )
    assert error_message == ""

    user_feeds = feed_repo.get_user_feeds(user)
    assert len(user_feeds) == 2

    network_repo_refresh = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed.xml",
                status=308,
                headers={
                    "Location": "https://example.com/feed.xml",
                },
            ),
            get_new_request_result(
                url="https://example.com/feed.xml",
                file_name="test_feed_https.xml",
            ),
        ],
    )

    error_message = refresh_feeds(
        feed_repo,
        network_repo_refresh,
    )
    assert error_message == ""

    user_feeds = feed_repo.get_user_feeds(user)
    assert len(user_feeds) == 1

    user_feed = user_feeds[0]
    assert user_feed.feed.rss_url == "https://example.com/feed.xml"
