"""0002: labels + issue_labels association (backward-compatible)

Revision ID: 0002
Revises: 0001
Create Date: 2025-09-01

Teaching demo: labels arrive in v1.1.0 as a backward-compatible addition.
Does not alter existing tables — purely additive.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_index("ix_labels_name", "labels", ["name"], unique=True)

    op.create_table(
        "issue_labels",
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["issue_id"], ["issues.id"], ondelete="CASCADE", name="fk_issue_labels_issue_id"
        ),
        sa.ForeignKeyConstraint(
            ["label_id"], ["labels.id"], ondelete="CASCADE", name="fk_issue_labels_label_id"
        ),
        sa.PrimaryKeyConstraint("issue_id", "label_id", name="pk_issue_labels"),
    )


def downgrade() -> None:
    op.drop_table("issue_labels")
    op.drop_index("ix_labels_name", table_name="labels")
    op.drop_table("labels")
