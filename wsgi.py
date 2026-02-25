"""WSGI entry point for Gunicorn / external WSGI servers.

Usage:
    gunicorn -w 1 -b 0.0.0.0:8050 wsgi:server
"""
from dotenv import load_dotenv
load_dotenv()

from app import create_app  # noqa: E402

server = create_app().server
