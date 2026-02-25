#!/usr/bin/env python
"""Start the Huey background task worker."""
import logging
import os
import signal
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging BEFORE importing Huey so consumer messages are visible.
# Without this, Huey logs at INFO level but Python's default threshold is
# WARNING, causing all task execution messages to be silently dropped.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)

from huey.consumer_options import ConsumerConfig
from app.tasks.huey_config import huey
from app.config import Config

PID_FILE = PROJECT_ROOT / "huey_worker.pid"


def _kill_stale_worker():
    """Kill any existing worker and clean up its PID file."""
    if not PID_FILE.exists():
        return

    try:
        old_pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return

    # Check if process is still alive
    try:
        os.kill(old_pid, 0)  # signal 0 = check existence
    except OSError:
        # Process already dead — clean up stale PID file
        PID_FILE.unlink(missing_ok=True)
        return

    print(f"Killing existing Huey worker (PID {old_pid})...")
    try:
        os.kill(old_pid, signal.SIGTERM)
        import time
        for _ in range(10):  # Wait up to 5 seconds
            time.sleep(0.5)
            try:
                os.kill(old_pid, 0)
            except OSError:
                break  # Process is gone
        else:
            # Still alive after timeout — force kill
            print(f"Worker {old_pid} did not terminate, sending SIGKILL...")
            os.kill(old_pid, signal.SIGKILL)
            time.sleep(0.5)
    except OSError:
        pass
    PID_FILE.unlink(missing_ok=True)


def _write_pid():
    """Write current PID to file for stale-worker detection."""
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid(*_args):
    """Remove PID file on exit."""
    PID_FILE.unlink(missing_ok=True)


def run_worker():
    """Run the Huey consumer worker."""
    _kill_stale_worker()
    _write_pid()

    # Clean up PID file on exit
    signal.signal(signal.SIGTERM, lambda *a: (_cleanup_pid(), sys.exit(0)))
    import atexit
    atexit.register(_cleanup_pid)

    print(f"Starting Huey worker (PID {os.getpid()})...")
    print(f"Database: {Config.HUEY_DATABASE_PATH}")
    print(f"Pending tasks: {huey.storage.queue_size()}")

    # Configure consumer
    config = ConsumerConfig(
        workers=1,  # Single worker for SQLite
        periodic=True,
        initial_delay=0.1,
        backoff=2.0,  # Exponential backoff
        max_delay=30.0,  # Max 30s delay when idle
    )

    # Start consumer
    consumer = huey.create_consumer(**config.values)
    consumer.run()


if __name__ == "__main__":
    run_worker()
