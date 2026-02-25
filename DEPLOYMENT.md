# Deployment Metadata

Machine-readable deployment configuration for IVT Kinetics Analyzer.

| Key | Value |
|-----|-------|
| `app_name` | `ivt-kinetics-analyzer` |
| `framework` | `flask` (with Dash mounted on Flask) |
| `entrypoint_file` | `run.py` |
| `callable` | `wsgi:server` |
| `preferred_port` | `8050` |
| `health_path` | `/health` |
| `python_version` | `3.11` |

## Callable

`create_app()` returns a Dash application. The underlying Flask WSGI server
is exposed as `server` in `wsgi.py`:

```bash
# Development
python run.py

# Production (built-in server)
python run.py --production --host 0.0.0.0

# Production (Gunicorn — single worker recommended for SQLite)
gunicorn -w 1 -b 0.0.0.0:8050 wsgi:server
```

## Health Check

`GET /health` returns JSON with an overall status and individual component
checks (database, Huey worker, disk space):

```json
{
  "status": "healthy",
  "timestamp": "2026-02-24T12:00:00+00:00",
  "checks": {
    "database": { "status": "healthy" },
    "huey":     { "status": "healthy" },
    "disk":     { "status": "healthy" }
  },
  "version": "0.1.0"
}
```

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Full health check (200 healthy/degraded, 503 unhealthy) |
| `GET /health/live` | Liveness probe (200 if process is running) |
| `GET /health/ready` | Readiness probe (200 only if database is reachable) |

## Environment Configuration

The file `.env.example` contains all supported environment variables with
safe defaults (no real secrets). Copy it and fill in production values:

```bash
cp .env.example .env
```

### Required for production

| Variable | Purpose | Generate with |
|----------|---------|---------------|
| `SECRET_KEY` | Flask session signing | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `IVT_SIGNING_KEY` | HMAC signing for publication certificates | Same as above |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLASK_ENV` | `development` | `development`, `production`, or `testing` |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for production) |
| `PORT` | `8050` | Bind port |
| `DEBUG` | `true` | Enable hot reload and verbose errors — **set to `false` in production** |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `IVT_ACCESS_PIN` | _(none)_ | Optional PIN gate for UI access |

> **Production checklist**: set `FLASK_ENV=production`, `DEBUG=false`, and
> provide `SECRET_KEY` + `IVT_SIGNING_KEY`. Using `--production` flag or
> `FLASK_ENV=production` automatically disables debug mode.

## Background Worker

The Huey task queue worker must run alongside the web application for MCMC
analysis, curve fitting, and export tasks:

```bash
# Development
python scripts/run_huey_worker.py

# Production (systemd)
sudo systemctl start ivt-worker
```

## Database

SQLite with WAL mode. This is a single-tenant application designed for one
user or a small lab team — SQLite is sufficient for this workload. WAL mode
enables concurrent reads, but writes are serialized. Use a single Gunicorn
worker (`-w 1`) to avoid write contention; the Huey worker handles the
heaviest writes (MCMC, exports) sequentially in a separate process.

```bash
python scripts/init_db.py          # Run migrations (or create_all for fresh install)
python scripts/init_db.py --reset  # Drop and recreate
python scripts/init_db.py --nuke   # Full reset (DB + uploads + traces + logs)
```
