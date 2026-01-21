import pytest

from rss_reader.rss.rss_api import import_from_rss_urls
from tests.mocks.network_repo_mock import NetworkRepoMock
from tests.test_rss_reader.factories import UserFactory
from tests.test_rss_reader.helpers import get_new_request_result


@pytest.fixture()
def user(db):
    return UserFactory()


@pytest.fixture()
def import_rss(user):
    network_repo = NetworkRepoMock(
        request_results=[
            get_new_request_result(
                url="http://example.com/feed.xml",
                file_name="test_feed.xml",
            ),
        ],
    )
    error_message = import_from_rss_urls(
        user,
        [
            "http://example.com/feed.xml",
        ],
        network_repo,
    )
    return error_message
