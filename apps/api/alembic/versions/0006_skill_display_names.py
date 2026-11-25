"""Keep skill display names consistent with the application navigation."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"


def upgrade():
    for skill_id, name in {"home-gardening": "家庭园艺", "calligraphy": "书法", "photography": "摄影", "music": "乐器"}.items():
        op.execute(sa.text("UPDATE skill SET name = :name WHERE id = :id").bindparams(name=name, id=skill_id))


def downgrade():
    raise RuntimeError("Restore reviewed backup instead")
