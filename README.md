# RSS Reader

Django-based RSS reader, mostly for reading blogs. Made for myself, to learn a bunch of stuff.

Backend: Django, PostgreSQL for DB, Redis for cache

Frontend: HTMX

## Configuration

Configuration is stored in `.env`, example can be found in `.env.example`

## Installing

Make .env file, change what you need
```bash
cp .env.example .env
````

Configure postgres and redis. It's convenient to use docker and docker-compose:
```bash
docker compose up -d
```

Make db_password.txt that contains password for PostgreSQL


Create superuser:
```bash
docker compose exec app python manage.py createsuperuser
```

Site will be accessible at http://127.0.0.1:8080

Testing:
```bash
docker compose --profile test run tests
```

Turning it off:
```bash
docker compose down
```

## What I've learned: 
* HTMX (super cool)
* docker, docker compose (hate it)
* dependency injection (learned it for writing tests)
* testing (need more practice, especially testing with pytest-django)
* websockets (only the very basic stuff)

### What could be improved:
* scalability of background tasks (one task that processes everything every hour)
* usage of websockets
* could add more tests
