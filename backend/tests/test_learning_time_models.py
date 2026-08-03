from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.learning.time import week_start_for
from app.models.learning import (
    RoleChangeLog,
    UserRole,
    WeeklyReportSubmission,
    WeeklyRosterWeek,
    WeeklyRoster,
)


def assert_commit_rejected(message):
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    else:
        db.session.rollback()
        raise AssertionError(message)


def test_week_start_uses_shanghai_timezone():
    assert week_start_for(datetime(2026, 7, 19, 16, 30)).isoformat() == '2026-07-20'


def test_empty_roster_week_is_persisted(app):
    with app.app_context():
        db.session.add(WeeklyRosterWeek(week_start=date(2026, 7, 20)))
        db.session.commit()
        assert WeeklyRosterWeek.query.count() == 1
        assert WeeklyRoster.query.count() == 0


def test_user_role_rejects_unknown_role(app):
    with app.app_context():
        db.session.add(UserRole(user_id=7, role='administrator'))
        assert_commit_rejected('unknown role was accepted')


def test_role_change_log_rejects_unknown_old_role(app):
    with app.app_context():
        db.session.add(RoleChangeLog(
            target_user_id=7,
            old_role='administrator',
            new_role='employee',
        ))
        assert_commit_rejected('unknown old role was accepted')


def test_role_change_log_rejects_unknown_new_role(app):
    with app.app_context():
        db.session.add(RoleChangeLog(
            target_user_id=7,
            old_role='employee',
            new_role='administrator',
        ))
        assert_commit_rejected('unknown new role was accepted')


def test_role_change_log_requires_old_role(app):
    with app.app_context():
        db.session.add(RoleChangeLog(
            target_user_id=7,
            old_role=None,
            new_role='employee',
        ))
        assert_commit_rejected('missing old role was accepted')


def test_weekly_report_submission_rejects_out_of_range_hours(app):
    with app.app_context():
        db.session.add(WeeklyReportSubmission(
            report_id=1,
            source_revision=0,
            content='report',
            hours_tenths=1681,
            completion=100,
        ))
        assert_commit_rejected('out-of-range submission hours were accepted')


def test_weekly_report_submission_rejects_out_of_range_completion(app):
    with app.app_context():
        db.session.add(WeeklyReportSubmission(
            report_id=1,
            source_revision=0,
            content='report',
            hours_tenths=1680,
            completion=101,
        ))
        assert_commit_rejected('out-of-range submission completion was accepted')
