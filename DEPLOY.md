# Class Schedule deployment bundle

This directory is self-contained. Copy or publish the entire directory,
keeping its folder structure intact.

## Run locally

```powershell
uv sync --frozen --no-dev
uv run uvicorn class_schedule.webapp:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Render

Push this directory as the root of a Git repository. Render can read
`render.yaml` directly. If configuring the service manually, use:

```text
Build: uv sync --frozen --no-dev
Start: uv run uvicorn class_schedule.webapp:app --host 0.0.0.0 --port $PORT
```

The free Render instance is useful for deployment testing, but the
OR-Tools solver is CPU- and memory-intensive. A production instance
should have approximately 1 CPU and 2 GB RAM.

## Docker

```powershell
docker build -t class-schedule .
docker run --rm -p 8000:8000 class-schedule
```

Platforms that accept a Dockerfile can deploy this directory without
Render-specific configuration.

## Runtime data

The application is stateless. Uploaded files and generated workbooks are
processed in memory or temporary directories. `output/logs/webapp.log`
is created at runtime and does not need to be copied between deployments.

The four files under `config/` are production configuration. Update them
before deployment when instructor preferences, rooms, or legal time slots
change.
