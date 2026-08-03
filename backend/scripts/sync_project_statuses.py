"""Synchronize stored RPA statuses from the newest project log.

The command is a dry run unless ``--apply`` is supplied.  Progress percentages
are intentionally ignored: ``project_logs`` is the lifecycle status authority.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, select, update


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Config  # noqa: E402
from app.project_status import (  # noqa: E402
    PROJECT_LIFECYCLE_STATUSES,
    PROJECT_STATUS_IN_DEVELOPMENT,
    latest_lifecycle_status_from_logs,
    normalize_project_status,
)


def _status_enum_changes(engine):
    schema = inspect(engine)
    changes = {}
    for table_name in ('projects', 'project_logs'):
        column = next(
            column for column in schema.get_columns(table_name)
            if column['name'] == 'status'
        )
        values = list(getattr(column['type'], 'enums', ()) or ())
        missing = [status for status in PROJECT_LIFECYCLE_STATUSES if status not in values]
        if values and missing:
            changes[table_name] = [*values, *missing]
    return changes


def _extend_status_enums(engine, changes):
    quote = engine.dialect.identifier_preparer.quote
    with engine.begin() as conn:
        for table_name, values in changes.items():
            enum_values = ','.join(
                "'" + value.replace("'", "''") + "'"
                for value in values
            )
            conn.exec_driver_sql(
                f'ALTER TABLE {quote(table_name)} '
                f'MODIFY COLUMN {quote("status")} ENUM({enum_values}) NOT NULL'
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--apply',
        action='store_true',
        help='persist latest-log statuses; otherwise only print a plan',
    )
    args = parser.parse_args()

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    try:
        from sqlalchemy import MetaData, Table

        metadata = MetaData()
        projects = Table('projects', metadata, autoload_with=engine)
        project_logs = Table('project_logs', metadata, autoload_with=engine)
        enum_changes = _status_enum_changes(engine)
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    projects.c.id,
                    projects.c.status,
                    projects.c.progress,
                )
            ).mappings().all()
            log_rows = conn.execute(
                select(
                    project_logs.c.id,
                    project_logs.c.project_id,
                    project_logs.c.status,
                    project_logs.c.log_time,
                )
            ).mappings().all()

        logs_by_project = defaultdict(list)
        for row in log_rows:
            logs_by_project[row['project_id']].append(SimpleNamespace(**row))

        changes = []
        for row in rows:
            latest = latest_lifecycle_status_from_logs(
                logs_by_project.get(row['id'], ())
            )
            new_status = latest or normalize_project_status(
                row['status'],
                default=PROJECT_STATUS_IN_DEVELOPMENT,
            )
            if row['status'] != new_status:
                changes.append({
                    'id': row['id'],
                    'old_status': row['status'],
                    'new_status': new_status,
                    'progress': float(row['progress'] or 0),
                    'source': 'latest_log' if latest else 'stored_status',
                })

        summary = Counter(change['new_status'] for change in changes)
        backup_path = None

        if args.apply and changes:
            backup_dir = BACKEND_ROOT / 'var' / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / (
                f'project_statuses_before_sync_{datetime.now():%Y%m%d_%H%M%S}.json'
            )
            backup_path.write_text(
                json.dumps({
                    'created_at': datetime.now().isoformat(timespec='seconds'),
                    'projects': [
                        {
                            'id': row['id'],
                            'status': row['status'],
                            'progress': float(row['progress'] or 0),
                        }
                        for row in rows
                    ],
                }, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            if enum_changes:
                _extend_status_enums(engine, enum_changes)
            with engine.begin() as conn:
                for change in changes:
                    conn.execute(
                        update(projects)
                        .where(projects.c.id == change['id'])
                        .values(status=change['new_status'])
                    )

        print(json.dumps({
            'mode': 'applied' if args.apply else 'dry-run',
            'status_source': 'latest_project_log',
            'project_count': len(rows),
            'change_count': len(changes),
            'changes_by_new_status': dict(summary),
            'enum_tables_extended': sorted(enum_changes),
            'backup': str(backup_path) if backup_path else None,
        }, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
