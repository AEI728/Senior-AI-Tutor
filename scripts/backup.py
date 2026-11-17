"""Consistent SQLite backup / restore-to-new-file and PostgreSQL pg_dump.
Backups contain personal data; kept outside source packages, never uploaded.
"""
import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime,timezone
from urllib.parse import urlsplit,unquote

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'apps/api'))
from app.config import settings  # noqa: E402

parser=argparse.ArgumentParser();parser.add_argument('--restore-to');parser.add_argument('--source');args=parser.parse_args()
cfg=settings();folder=root/'backups';folder.mkdir(exist_ok=True)
if cfg.database_url.startswith('sqlite:///'):
    source=Path(args.source or cfg.database_url.removeprefix('sqlite:///')).resolve()
    destination=Path(args.restore_to).resolve() if args.restore_to else folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.db')
    if destination.exists() or destination==source:raise SystemExit('Refusing to overwrite an existing database; choose a new restore target')
    if not source.is_file():raise SystemExit('Source database does not exist')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(destination) as target:
        src.backup(target);assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print('PASS: consistent database copy and integrity_check:',destination)
else:
    if args.restore_to:raise SystemExit('For PostgreSQL use pg_restore into a NEW database; see runbook')
    u=urlsplit(cfg.database_url.replace('postgresql+psycopg://','postgresql://'))
    env=dict(os.environ,PGPASSWORD=unquote(u.password or ''))
    file=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.dump')
    subprocess.run(['pg_dump','-h',u.hostname or 'localhost','-p',str(u.port or 5432),'-U',unquote(u.username or ''),'-d',u.path.lstrip('/'),'-Fc','-f',str(file)],env=env,check=True)
    print('PASS: pg_dump completed:',file)
