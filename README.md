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

## Load the data

Run the full extraction, transformation, and database load with:

```sh
docker compose run --rm --build app python load.py
```

The first load creates the three tables. Later runs upsert records using their
primary keys; the entire database load is committed together. Each run fetches
the full dataset. To inspect the table counts:

```sh
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT (SELECT count(*) FROM respondents) AS respondents, (SELECT count(*) FROM offense_types) AS offense_types, (SELECT count(*) FROM victimizations) AS victimizations;"'
```

