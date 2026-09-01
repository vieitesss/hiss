"""WSGI entrypoint for `flask run` and gunicorn.

Usage:
  FLASK_APP=app/wsgi flask run
  gunicorn app.wsgi:app
"""

from app.app import create_app

app = create_app()
