from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_table(
        "local_account",
        sa.Column("username", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("app_user.id"), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "community_work",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("course_id", sa.String(), sa.ForeignKey("course.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("reported", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_community_work_user_id", "community_work", ["user_id"])


def downgrade():
    raise RuntimeError("Restore reviewed backup instead of destructive downgrade")
