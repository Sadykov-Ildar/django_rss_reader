import time
from contextlib import contextmanager

from django.core.cache import cache

from rss_reader.constants import MUTEX_TIMEOUT


@contextmanager
def redis_lock(lock_id, oid):
    timeout_at = time.monotonic() + MUTEX_TIMEOUT
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, MUTEX_TIMEOUT)
    try:
        yield status
    finally:
        # delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        if time.monotonic() < timeout_at and status:
            # don't release the lock if we exceeded the timeout
            # to lessen the chance of releasing an expired lock
            # owned by someone else
            # also don't release the lock if we didn't acquire it
            cache.delete(lock_id)
