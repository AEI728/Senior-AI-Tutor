from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"


def upgrade():
    op.create_table(
        "work_video",
        sa.Column("work_id", sa.String(), sa.ForeignKey("community_work.id"), primary_key=True),
        sa.Column("video_data", sa.LargeBinary(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
    )
    op.create_table(
        "feed_reaction",
        sa.Column("user_id", sa.String(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("target", sa.String(), primary_key=True),
        sa.Column("liked", sa.Boolean(), nullable=False),
        sa.Column("saved", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "feed_comment",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_feed_comment_user_id", "feed_comment", ["user_id"])
    op.create_index("ix_feed_comment_target", "feed_comment", ["target"])


def downgrade():
    raise RuntimeError("Restore reviewed backup instead")
