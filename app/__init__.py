# Shim: allow `from app import create_app` when the repo root is on PYTHONPATH
# and the real Flask package lives at app/app (double-nested monorepo layout).
# This keeps both import styles working:
#   PYTHONPATH=app  -> `from app import create_app`  (inner directly)
#   repo root       -> `from app import create_app`  (outer shim) or `from app.app import create_app`
try:
    from app.app import create_app  # noqa: F401
    from app.app.extensions import db  # noqa: F401
except Exception:
    # Inner not yet importable (circular import guard during early init)
    pass
