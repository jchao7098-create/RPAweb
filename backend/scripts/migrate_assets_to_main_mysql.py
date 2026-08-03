"""Move legacy asset and learning rows from assets.db into the RPA MySQL database.

The command is a dry run unless --apply is supplied. Existing destination rows
with the same primary key are left unchanged, which makes an interrupted or
repeated migration safe to rerun.
"""

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Date, DateTime, create_engine, inspect, select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app, db  # noqa: E402
from app.config import Config  # noqa: E402


TABLE_ORDER = (
    'assets',
    'user_roles',
    'role_change_logs',
    'weekly_roster_weeks',
    'weekly_rosters',
    'weekly_reports',
    'weekly_report_submissions',
    'report_return_logs',
)


def _source_counts(source):
    tables = {
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    return {
        table_name: (
            source.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            if table_name in tables else None
        )
        for table_name in TABLE_ORDER
    }


def _target_counts(engine):
    schema = inspect(engine)
    with engine.connect() as conn:
        return {
            table_name: (
                conn.exec_driver_sql(
                    f'SELECT COUNT(*) FROM {engine.dialect.identifier_preparer.quote(table_name)}'
                ).scalar_one()
                if schema.has_table(table_name) else None
            )
            for table_name in TABLE_ORDER
        }


def _convert_value(value, column):
    if value is None:
        return None
    if isinstance(column.type, DateTime) and isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    if isinstance(column.type, Date) and not isinstance(column.type, DateTime) and isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _source_rows(source, table):
    source.row_factory = sqlite3.Row
    rows = source.execute(f'SELECT * FROM "{table.name}"').fetchall()
    target_columns = {column.name: column for column in table.columns}
    return [
        {
            name: _convert_value(row[name], target_columns[name])
            for name in row.keys()
            if name in target_columns
        }
        for row in rows
    ]


def _migrate_rows(source, target_engine):
    results = {}
    metadata = db.metadatas['assets']

    with target_engine.begin() as conn:
        for table_name in TABLE_ORDER:
            table = metadata.tables[table_name]
            source_rows = _source_rows(source, table)
            primary_key = list(table.primary_key.columns)
            existing_keys = {
                tuple(row)
                for row in conn.execute(select(*primary_key))
            }
            pending = [
                row for row in source_rows
                if tuple(row[column.name] for column in primary_key) not in existing_keys
            ]
            if pending:
                conn.execute(table.insert(), pending)
            results[table_name] = {
                'source': len(source_rows),
                'already_present': len(source_rows) - len(pending),
                'inserted': len(pending),
            }

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--source',
        type=Path,
        default=Path(Config.LEGACY_ASSETS_DATABASE),
        help='legacy SQLite database path',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='create destination tables and copy rows; otherwise only print a plan',
    )
    args = parser.parse_args()
    source_path = args.source.resolve()
    if not source_path.is_file():
        raise SystemExit(f'Legacy SQLite database not found: {source_path}')

    source = sqlite3.connect(f'file:{source_path.as_posix()}?mode=ro', uri=True)
    try:
        source_counts = _source_counts(source)
        if not args.apply:
            target_engine = create_engine(Config.SQLALCHEMY_BINDS['assets'])
            try:
                output = {
                    'mode': 'dry-run',
                    'source': str(source_path),
                    'source_counts': source_counts,
                    'target_counts': _target_counts(target_engine),
                }
            finally:
                target_engine.dispose()
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return

        app = create_app({'LEARNING_BOOTSTRAP_ON_STARTUP': False})
        with app.app_context():
            results = _migrate_rows(source, db.engines['assets'])
            target_counts = _target_counts(db.engines['assets'])
            db.session.remove()
        print(json.dumps({
            'mode': 'applied',
            'source': str(source_path),
            'results': results,
            'target_counts': target_counts,
        }, ensure_ascii=False, indent=2))
    finally:
        source.close()


if __name__ == '__main__':
    main()
