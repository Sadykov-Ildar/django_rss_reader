class MainUseCase:
    def __init__(self, repo):
        self.repo = repo

    def get_main_page(self, user):
        user_feeds = self.repo.get_ordered_user_feeds(user)
        user_feeds = list(user_feeds)
        feed = None
        user_entries = []
        if user_feeds:
            feed = user_feeds[0]
            user_entries = self.repo.get_filtered_user_entries(feed)

        return user_feeds, feed, user_entries
