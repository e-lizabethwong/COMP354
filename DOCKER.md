# Docker Usage

This project can run inside Docker with Python dependencies and Playwright's Chromium browser installed in the image.

## Build

```bash
docker compose build
```

## Run The CLI

Show help:

```bash
docker compose run --rm app python main.py --help
```

Scrape a single site without an LLM API key:

```bash
docker compose run --rm app python main.py scrape --url https://conuhacks.io --output /app/data/test_emails.txt
# For Git Bash:
export MSYS_NO_PATHCONV=1
docker compose run --rm app python main.py scrape --url https://conuhacks.io --output /app/data/test_emails.txt
```

Git Bash automatically converts Linux-style argument into Windows paths before launching Docker. Linux containers receive the wrong path.

Run a pipeline stage that uses an LLM:

```bash
cp env.example .env
# Fill in LLM_PROVIDER and the matching API key in .env.
docker compose run --rm app python main.py discover
```

Export reports:

```bash
docker compose run --rm app python main.py export --output /app/results
```

Run tests:

```bash
docker run --rm -v "$(pwd):/app" -w /app comp354 sh scripts/docker-checks.sh
# when using Git Bash
export MSYS_NO_PATHCONV=1
docker run --rm -v "$(pwd):/app" -w /app comp354 sh scripts/docker-checks.sh

```

## Data

Compose mounts local directories into the container:

- `./data` -> `/app/data`
- `./results` -> `/app/results`

The container defaults to:

- `SPONSOR_DB_PATH=/app/data/sponsors.db`
- `HACKATHON_URLS_FILE=/app/data/hackathon_urls.txt`
- `SCRAPE_LOG_PATH=/app/data/log.txt`

Your `.env` file is not copied into the image. Docker Compose reads it locally and passes the relevant values as environment variables.

Avoid sharing `docker compose config` output if your local `.env` contains real API keys; some Docker Compose versions render env-file values in that output.
