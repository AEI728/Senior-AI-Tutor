"""Development-only one-time materialization of static migration DDL."""
from pathlib import Path
import sys
from sqlalchemy import create_engine
from alembic.migration import MigrationContext
from alembic.autogenerate import produce_migrations, render_python_code
root = Path(__file__).resolve().parents[1]
if len(list((root/'apps/api/alembic/versions').glob('*.py'))) > 1:
    raise SystemExit('Initial migration is frozen; create a new revision instead')
sys.path.insert(0, str(root / 'apps/api'))
from app.db import Base  # noqa: E402
with create_engine('sqlite://').connect() as conn:
    migration = produce_migrations(MigrationContext.configure(conn), Base.metadata)
    code = render_python_code(migration.upgrade_ops)
output = '''"""Initial R1 static schema; generated once, independent of future ORM changes."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None


def upgrade():
'''+code+'''


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore reviewed database backup instead')
'''
(root / 'apps/api/alembic/versions/0001_initial.py').write_text(output, 'utf-8')
