from flask import Blueprint

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# Import route modules so they register on api_bp.
# Import order matters for error handlers registration last.
from . import errors  # noqa: F401, E402
from . import projects  # noqa: F401, E402
from . import issues  # noqa: F401, E402
from . import comments  # noqa: F401, E402
from . import labels  # noqa: F401, E402

# Register JSON error handlers on the blueprint
errors.register_error_handlers(api_bp)
