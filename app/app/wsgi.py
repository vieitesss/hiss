"""Alternative WSGI entrypoint inside the Flask package.

Usage:
  FLASK_APP=app/app/wsgi flask run
  FLASK_APP=app/app flask run
"""

from . import create_app

app = create_app()
