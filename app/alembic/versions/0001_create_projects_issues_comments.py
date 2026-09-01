"""0001: projects, issues, comments

Revision ID: 0001
Revises:
Create Date: 2025-09-01

Teaching demo: first migration contains the core domain (Project/Issue/Comment).
No labels yet — those arrive in 0002 as a backward-compatible addition.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types — native Postgres enums with explicit names
issue_status_enum = sa.Enum("open", "in_progress", "done", name="issue_status", native_enum=True)
issue_priority_enum = sa.Enum("low", "medium", "high", name="issue_priority", native_enum=True)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
    )
    op.create_index("ix_projects_key", "projects", ["key"], unique=True)

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            issue_status_enum,
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "priority",
            issue_priority_enum,
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_issues_project_id"
        ),
    )
    op.create_index("ix_issues_project_id", "issues", ["project_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"], ["issues.id"], ondelete="CASCADE", name="fk_comments_issue_id"
        ),
    )
    op.create_index("ix_comments_issue_id", "comments", ["issue_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_comments_issue_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_issues_project_id", table_name="issues")
    op.drop_table("issues")
    op.drop_index("ix_projects_key", table_name="projects")
    op.drop_table("projects")

    # Drop enum types after tables (no-op on SQLite)
    issue_priority_enum.drop(op.get_bind(), checkfirst=True)
    issue_status_enum.drop(op.get_bind(), checkfirst=True)
