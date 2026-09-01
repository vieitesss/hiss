from flask import Flask, current_app
from sqlalchemy import text as sa_text

from ..extensions import db


def register_probes(app: Flask) -> None:
    """Register operational probes at the root.

    - GET /healthz (liveness, no DB)
    - GET /readyz  (readiness, real SELECT 1)
    - GET /version (returns APP_VERSION)
    """

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    @app.get("/readyz")
    def readyz():
        try:
            with db.engine.connect() as conn:
                conn.execute(sa_text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception as exc:  # pragma: no cover - DB down path
            return {"status": "error", "message": str(exc)}, 503

    @app.get("/version")
    def version():
        return {"version": current_app.config.get("APP_VERSION", "dev")}, 200
