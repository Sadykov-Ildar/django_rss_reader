from celery import Celery
from celery.schedules import crontab

app = Celery("django_rss_reader", broker="amqp://rabbitmq")

app.conf.beat_schedule = {
    "rss_reader.refresh_feeds_task": {
        "task": "rss_reader.refresh_feeds_task",
        "schedule": crontab(
            minute=0,
            hour="*/1",
        ),
    },
    "rss_reader.delete_old_request_history_records": {
        "task": "rss_reader.delete_old_request_history_records",
        "schedule": crontab(
            minute=0,
            hour="*/6",
        ),
    },
}
