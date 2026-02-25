"""
Huey task queue configuration with SQLite backend.
"""
from huey import SqliteHuey
from app.config import Config

# Create Huey instance with SQLite backend
huey = SqliteHuey(
    filename=str(Config.HUEY_DATABASE_PATH),
    immediate=Config.HUEY_IMMEDIATE,  # Don't process immediately in web process
)

# Worker settings are configured in run_huey_worker.py
# - Single worker for SQLite (concurrent writes not supported)
# - Exponential backoff when idle: 1s -> 2s -> 4s -> 8s -> max 30s
# - Immediate processing when tasks appear
