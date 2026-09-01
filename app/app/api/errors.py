from flask import jsonify


def error_response(error: str, message: str, status_code: int):
    """Consistent JSON error envelope: {"error": ..., "message": ...}"""
    return jsonify({"error": error, "message": message}), status_code


def bad_request(message: str):
    return error_response("bad_request", message, 400)


def not_found(message: str):
    return error_response("not_found", message, 404)


def conflict(message: str):
    return error_response("conflict", message, 409)


def feature_disabled(message: str):
    return error_response("feature_disabled", message, 400)


def register_error_handlers(bp):
    """Ensure API blueprint always returns JSON for common HTTP errors."""

    @bp.errorhandler(400)
    def handle_400(e):
        msg = getattr(e, "description", None) or "bad request"
        return error_response("bad_request", msg, 400)

    @bp.errorhandler(404)
    def handle_404(e):
        msg = getattr(e, "description", None) or "not found"
        return error_response("not_found", msg, 404)

    @bp.errorhandler(409)
    def handle_409(e):
        msg = getattr(e, "description", None) or "conflict"
        return error_response("conflict", msg, 409)

    @bp.errorhandler(405)
    def handle_405(e):
        return error_response("method_not_allowed", "method not allowed", 405)
