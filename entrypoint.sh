#!/bin/sh

python manage.py migrate --no-input

python manage.py collectstatic --no-input

# TODO: fastwsgi, granian?
# TODO: потестить с https://github.com/rakyll/hey
gunicorn django_rss_reader.wsgi --bind 0.0.0.0:8000