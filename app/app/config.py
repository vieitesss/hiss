import os


def _parse_feature_flag(value: str | None) -> bool:
    """Parse FEATURE_LABEL_FILTERING env var (case-insensitive).

    Truthy:  true, 1, yes, on
    Falsy:   false, 0, no, off
    Default: true when unset or unrecognised (keeps filtering on).
    """
    if value is None:
        return True
    lower = value.strip().lower()
    if lower in ("true", "1", "yes", "on"):
        return True
    if lower in ("false", "0", "no", "off"):
        return False
    # Fallback to True for backwards-compat / unknown strings
    return True


def _to_psycopg_uri(uri: str) -> str:
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return uri


class Config:
    """Centralised env-driven config. Values are read at import time
    for defaults but create_app re-reads env on every call so tests
    can toggle flags without reload.
    """

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    FEATURE_LABEL_FILTERING: bool = _parse_feature_flag(
        os.getenv("FEATURE_LABEL_FILTERING", "true")
    )

    # Flask-SQLAlchemy
    SQLALCHEMY_DATABASE_URI: str = _to_psycopg_uri(DATABASE_URL or "sqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
