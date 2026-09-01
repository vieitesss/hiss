from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

from . import api_bp
from .errors import bad_request, conflict
from ..extensions import db
from ..models import Project


def _project_to_dict(p: Project) -> dict:
    return {"id": p.id, "key": p.key, "name": p.name}


@api_bp.route("/projects", methods=["GET"])
def list_projects():
    projects = Project.query.order_by(Project.id).all()
    return jsonify([_project_to_dict(p) for p in projects]), 200


@api_bp.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json(silent=True)
    if data is None:
        return bad_request("invalid JSON body")
    key = (data.get("key") or "").strip() if isinstance(data.get("key"), str) else data.get("key")
    name = (
        (data.get("name") or "").strip() if isinstance(data.get("name"), str) else data.get("name")
    )

    # Validate required fields
    if not key or not isinstance(key, str):
        return bad_request("key is required")
    if not name or not isinstance(name, str):
        return bad_request("name is required")

    # Check duplicate before insert for clean 409
    if Project.query.filter_by(key=key).first() is not None:
        return conflict(f"project key '{key}' already exists")

    project = Project(key=key, name=name)
    db.session.add(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return conflict(f"project key '{key}' already exists")

    return jsonify(_project_to_dict(project)), 201
