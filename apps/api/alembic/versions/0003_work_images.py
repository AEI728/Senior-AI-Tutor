from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"


def upgrade():
    op.create_table(
        "work_media",
        sa.Column("work_id", sa.String(), sa.ForeignKey("community_work.id"), primary_key=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Restore reviewed backup instead")
