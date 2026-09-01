"""Error helpers — thin wrappers around client error mapping for convenience."""

from hiss.client import handle_request_error, handle_response

__all__ = ["handle_response", "handle_request_error"]
