from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    flash,
    get_flashed_messages,
)
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Project, Issue, Comment, Label, IssueStatus, IssuePriority

from . import ui_bp

VALID_STATUSES = {e.value for e in IssueStatus}
VALID_PRIORITIES = {e.value for e in IssuePriority}


@ui_bp.route("/", methods=["GET"])
def index():
    projects = Project.query.order_by(Project.id).all()
    return render_template("index.html", projects=projects)


@ui_bp.route("/projects", methods=["POST"])
def create_project():
    key = (request.form.get("key") or "").strip()
    name = (request.form.get("name") or "").strip()

    if not key or not name:
        # Simple 400 with inline error; keep demo thin.
        projects = Project.query.order_by(Project.id).all()
        return (
            render_template("index.html", projects=projects, error="key and name are required"),
            400,
        )
    if Project.query.filter_by(key=key).first():
        projects = Project.query.order_by(Project.id).all()
        return (
            render_template("index.html", projects=projects, error=f"project key '{key}' already exists"),
            409,
        )

    project = Project(key=key, name=name)
    db.session.add(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        projects = Project.query.order_by(Project.id).all()
        return (
            render_template("index.html", projects=projects, error=f"project key '{key}' already exists"),
            409,
        )
    return redirect(url_for("ui.index"))


@ui_bp.route("/projects/<string:key>", methods=["GET"])
def project_issues(key: str):
    project = Project.query.filter_by(key=key).first()
    if project is None:
        return render_template("error.html", message=f"project '{key}' not found"), 404

    status_filter = request.args.get("status") or ""
    priority_filter = request.args.get("priority") or ""
    label_filter = request.args.get("label") or ""

    error = None
    # Validate enum filters (show error inline, but still list without that filter)
    if status_filter and status_filter not in VALID_STATUSES:
        error = f"invalid status '{status_filter}'"
        status_filter = ""
    if priority_filter and priority_filter not in VALID_PRIORITIES:
        error = f"invalid priority '{priority_filter}'"
        priority_filter = ""

    # Feature flag gating for ?label=
    if label_filter:
        flag = current_app.config.get("FEATURE_LABEL_FILTERING", True)
        if not flag:
            error = "label filtering is disabled (FEATURE_LABEL_FILTERING=false)"
            # Don't apply label filter when disabled; show error but still list unfiltered.
            label_filter = ""

    query = Issue.query.filter_by(project_id=project.id)
    if status_filter:
        query = query.filter(Issue.status == status_filter)
    if priority_filter:
        query = query.filter(Issue.priority == priority_filter)
    if label_filter:
        query = query.join(Issue.labels).filter(Label.name == label_filter)

    query = query.options(selectinload(Issue.labels)).order_by(Issue.id)
    issues = query.all()

    # If there was a flag error, we already cleared label_filter; but we need to preserve the original attempted label for display.
    attempted_label = request.args.get("label") or ""
    # When flag disabled and label was attempted, we want to show error and keep attempted_label in input.
    # So pass attempted_label separately if error about flag.
    display_label = attempted_label if error and "disabled" in error else label_filter

    return render_template(
        "project_issues.html",
        project=project,
        issues=issues,
        error=error,
        status_filter=status_filter,
        priority_filter=priority_filter,
        label_filter=display_label,
        all_statuses=sorted(VALID_STATUSES),
        all_priorities=sorted(VALID_PRIORITIES),
    )


@ui_bp.route("/projects/<string:key>/issues", methods=["POST"])
def create_issue(key: str):
    project = Project.query.filter_by(key=key).first()
    if project is None:
        return render_template("error.html", message=f"project '{key}' not found"), 404

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    priority = (request.form.get("priority") or "medium").strip()

    if not title:
        # Re-render project page with error
        issues = Issue.query.filter_by(project_id=project.id).order_by(Issue.id).all()
        return (
            render_template(
                "project_issues.html",
                project=project,
                issues=issues,
                error="title is required",
                status_filter="",
                priority_filter="",
                label_filter="",
                all_statuses=sorted(VALID_STATUSES),
                all_priorities=sorted(VALID_PRIORITIES),
            ),
            400,
        )
    if priority not in VALID_PRIORITIES:
        issues = Issue.query.filter_by(project_id=project.id).order_by(Issue.id).all()
        return (
            render_template(
                "project_issues.html",
                project=project,
                issues=issues,
                error=f"invalid priority '{priority}'",
                status_filter="",
                priority_filter="",
                label_filter="",
                all_statuses=sorted(VALID_STATUSES),
                all_priorities=sorted(VALID_PRIORITIES),
            ),
            400,
        )

    issue = Issue(
        project_id=project.id,
        title=title,
        description=description,
        priority=priority,
        status="open",
    )
    db.session.add(issue)
    db.session.commit()
    return redirect(url_for("ui.project_issues", key=key))


@ui_bp.route("/issues/<int:issue_id>", methods=["GET"])
def issue_detail(issue_id: int):
    issue = Issue.query.options(selectinload(Issue.labels)).filter_by(id=issue_id).first()
    if issue is None:
        return render_template("error.html", message=f"issue {issue_id} not found"), 404
    comments = Comment.query.filter_by(issue_id=issue_id).order_by(Comment.id).all()
    # For label attach form, also list all labels to help demo? Minimal: just show available.
    all_labels = Label.query.order_by(Label.name).all()
    return render_template(
        "issue_detail.html", issue=issue, comments=comments, all_labels=all_labels
    )


@ui_bp.route("/issues/<int:issue_id>/comments", methods=["POST"])
def add_comment(issue_id: int):
    issue = Issue.query.filter_by(id=issue_id).first()
    if issue is None:
        return render_template("error.html", message=f"issue {issue_id} not found"), 404
    body = (request.form.get("body") or "").strip()
    if not body:
        comments = Comment.query.filter_by(issue_id=issue_id).order_by(Comment.id).all()
        issue = Issue.query.options(selectinload(Issue.labels)).filter_by(id=issue_id).first()
        all_labels = Label.query.order_by(Label.name).all()
        return (
            render_template(
                "issue_detail.html",
                issue=issue,
                comments=comments,
                all_labels=all_labels,
                error="body is required",
            ),
            400,
        )
    comment = Comment(issue_id=issue_id, body=body)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for("ui.issue_detail", issue_id=issue_id))


@ui_bp.route("/issues/<int:issue_id>/labels", methods=["POST"])
def attach_label(issue_id: int):
    issue = Issue.query.options(selectinload(Issue.labels)).filter_by(id=issue_id).first()
    if issue is None:
        return render_template("error.html", message=f"issue {issue_id} not found"), 404
    name = (request.form.get("name") or "").strip()
    if not name:
        comments = Comment.query.filter_by(issue_id=issue_id).order_by(Comment.id).all()
        all_labels = Label.query.order_by(Label.name).all()
        return (
            render_template(
                "issue_detail.html",
                issue=issue,
                comments=comments,
                all_labels=all_labels,
                error="label name is required",
            ),
            400,
        )
    label = Label.query.filter_by(name=name).first()
    if label is None:
        comments = Comment.query.filter_by(issue_id=issue_id).order_by(Comment.id).all()
        all_labels = Label.query.order_by(Label.name).all()
        return (
            render_template(
                "issue_detail.html",
                issue=issue,
                comments=comments,
                all_labels=all_labels,
                error=f"label '{name}' not found",
            ),
            404,
        )
    if label not in issue.labels:
        issue.labels.append(label)
        db.session.commit()
    return redirect(url_for("ui.issue_detail", issue_id=issue_id))


@ui_bp.route("/issues/<int:issue_id>/labels/<string:name>/detach", methods=["POST"])
def detach_label(issue_id: int, name: str):
    issue = Issue.query.options(selectinload(Issue.labels)).filter_by(id=issue_id).first()
    if issue is None:
        return render_template("error.html", message=f"issue {issue_id} not found"), 404
    label = Label.query.filter_by(name=name).first()
    if label is None:
        return render_template("error.html", message=f"label '{name}' not found"), 404
    if label in issue.labels:
        issue.labels.remove(label)
        db.session.commit()
    return redirect(url_for("ui.issue_detail", issue_id=issue_id))
