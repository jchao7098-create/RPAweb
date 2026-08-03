import sqlite3

from app import create_app, db


EXPECTED_COLUMNS = {'record_date', 'certificate', 'program_count', 'blockers'}


def test_startup_adds_progress_columns_to_legacy_learning_tables(tmp_path):
    database_path = tmp_path / 'legacy-assets.db'
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE weekly_reports (
            id INTEGER PRIMARY KEY,
            week_start DATE NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT,
            hours_tenths INTEGER,
            completion INTEGER,
            remark TEXT,
            draft_revision INTEGER NOT NULL DEFAULT 0,
            latest_submission_id INTEGER,
            state VARCHAR(24) NOT NULL DEFAULT 'draft',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE weekly_report_submissions (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL,
            source_revision INTEGER NOT NULL,
            content TEXT NOT NULL,
            hours_tenths INTEGER NOT NULL,
            completion INTEGER NOT NULL,
            remark TEXT,
            submitted_at DATETIME NOT NULL
        );
    """)
    connection.close()

    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_BINDS': {'assets': f'sqlite:///{database_path.as_posix()}'},
        'LEARNING_TOKEN_SECRET': 'test-learning-secret',
        'LEARNING_BOOTSTRAP_ON_STARTUP': False,
    })

    with app.app_context():
        report_columns = {
            row[1] for row in db.engines['assets'].connect().exec_driver_sql(
                'PRAGMA table_info(weekly_reports)'
            )
        }
        submission_columns = {
            row[1] for row in db.engines['assets'].connect().exec_driver_sql(
                'PRAGMA table_info(weekly_report_submissions)'
            )
        }
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()

    assert EXPECTED_COLUMNS <= report_columns
    assert EXPECTED_COLUMNS <= submission_columns
