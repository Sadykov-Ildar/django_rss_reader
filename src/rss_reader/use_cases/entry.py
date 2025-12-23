class MarkEntriesAsReadUseCase:
    def __init__(self, repo):
        self.repo = repo

    def mark_entries_as_read(self, user, user_feed_id):
        user_feed = self.repo.get_user_feed_by_id(user_feed_id, user)
        if user_feed is None:
            return None, None

        self.repo.mark_user_feed_as_read(user_feed)

        user_entries = self.repo.get_filtered_user_entries(user_feed)

        return user_feed, user_entries
