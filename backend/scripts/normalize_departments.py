"""Normalize historical department names in the main DBserver database.

The command is a dry run unless ``--apply`` is supplied. It only updates the
department columns on RPA requirements and Skill/Python assets; project titles
remain untouched because their department prefix is normalized when displayed.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select, update


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Config  # noqa: E402
from app.departments import normalize_department  # noqa: E402


TABLE_NAMES = ('requirements', 'assets')


def _collect_changes(connection, table):
    rows = connection.execute(
        select(table.c.id, table.c.department)
    ).mappings()
    changes = []
    for row in rows:
        current = row['department'] or ''
        normalized = normalize_department(current, default='')
        if normalized and normalized != current:
            changes.append({
                'id': row['id'],
                'from': current,
                'to': normalized,
            })
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--apply',
        action='store_true',
        help='persist normalized names; otherwise only print the change plan',
    )
    args = parser.parse_args()

    if not Config.SQLALCHEMY_DATABASE_URI:
        raise SystemExit('RPA_DATABASE_URI is required')

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    schema = inspect(engine)
    metadata = MetaData()
    tables = {
        name: Table(name, metadata, autoload_with=engine)
        for name in TABLE_NAMES
        if schema.has_table(name)
    }

    with engine.connect() as connection:
        plan = {
            name: _collect_changes(connection, table)
            for name, table in tables.items()
        }

    if args.apply:
        with engine.begin() as connection:
            for name, changes in plan.items():
                table = tables[name]
                for change in changes:
                    connection.execute(
                        update(table)
                        .where(table.c.id == change['id'])
                        .values(department=change['to'])
                    )

    summary = {
        'mode': 'apply' if args.apply else 'dry-run',
        'total_changes': sum(len(changes) for changes in plan.values()),
        'tables': plan,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
