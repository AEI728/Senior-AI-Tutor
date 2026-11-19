from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"


def upgrade():
    op.create_table(
        "completed_skill",
        sa.Column("user_id", sa.String(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("skill_id", sa.String(), sa.ForeignKey("skill.id"), primary_key=True),
        sa.Column("completed_at", sa.String(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Restore reviewed backup instead")
