# Team 4 Term Project DAEN 328 Fall 2026 

## Phase 1

## Docker setup

Install Docker and the Docker Compose plugin, then start PostgreSQL:

```sh
docker compose up -d db
docker compose run --rm app
```

The database is available on localhost port 5432 and its data persists in a
Docker volume. For local development the database, user, and password default
to `ncvs`. Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, or
`POSTGRES_PORT` in the environment (or a local `.env` file) to change them.
Database initialization settings apply when the volume is first created.

