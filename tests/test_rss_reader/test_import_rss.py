import pytest
from rss_reader.repos import db_repo


def test_import_rss(import_rss):
    assert import_rss == ""


def test_import_rss_url(import_rss, user):
    user_feeds = db_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    assert user_feed.feed.rss_url == "http://example.com/feed.xml"


@pytest.mark.django_db()
def test_has_user_feeds(import_rss, user):
    user_feeds = db_repo.get_user_feeds(user)
    assert len(user_feeds) == 1


@pytest.mark.django_db()
def test_has_user_entries(import_rss, user):
    user_feeds = db_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    user_entries = db_repo.get_filtered_user_entries(user_feed)
    assert len(user_entries) == 9


@pytest.mark.django_db()
def test_entry_link(import_rss, user):
    user_feeds = db_repo.get_user_feeds(user)
    user_feed = user_feeds[0]
    user_entries = db_repo.get_filtered_user_entries(user_feed)
    user_entry = user_entries[0]
    assert user_entry.entry.link == "http://www.feedforall.com/restaurant.htm"
