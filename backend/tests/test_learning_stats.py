import csv
import io
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event

from app import db
from app.learning.auth import issue_learning_token
from app.learning.errors import LearningConflictError, LearningValidationError
from app.learning.exports import recent_week_csv
from app.learning.reports import expire_return_if_needed, return_report
from app.learning.roles import ensure_roster_week
from app.learning.serializers import serialize_report
from app.learning.stats import user_trend, weekly_stats
from app.learning.time import utc_now
from app.models.learning import UserRole, WeeklyReport, WeeklyReportSubmission
from app.models.models import User


WEEK = date(2026, 7, 20)
NOW = datetime(2026, 7, 27, 9, tzinfo=timezone.utc)
EXPORT_NOW = datetime(2026, 7, 22, 9, tzinfo=timezone.utc)


@pytest.fixture()
def roster(app):
    with app.app_context():
        users = []
        for index in range(3):
            user = User(username=f'stats-{index}', email=f'stats-{index}@example.com', password='secret1', created_at=utc_now())
            db.session.add(user)
            db.session.flush()
            db.session.add(UserRole(user_id=user.id, role='intern'))
            users.append(user)
        db.session.commit()
        ensure_roster_week(WEEK)
        db.session.commit()
        return [user.id for user in users]


def _submitted_report(user_id, hours_tenths, completion):
    report = WeeklyReport(week_start=WEEK, user_id=user_id, content='work', hours_tenths=hours_tenths, completion=completion,
                          draft_revision=1, state='submitted')
    db.session.add(report)
    db.session.flush()
    submission = WeeklyReportSubmission(report_id=report.id, source_revision=1, content='work', hours_tenths=hours_tenths,
                                        completion=completion)
    db.session.add(submission)
    db.session.flush()
    report.latest_submission_id = submission.id
    return report


def _submitted_progress_report(user_id, progress=50, program_count=1, blockers='流程卡点'):
    report = WeeklyReport(
        week_start=WEEK,
        user_id=user_id,
        content=blockers,
        hours_tenths=0,
        completion=progress,
        remark=blockers,
        record_date=date(2026, 7, 23),
        certificate='中级',
        program_count=program_count,
        blockers=blockers,
        draft_revision=1,
        state='submitted',
    )
    db.session.add(report)
    db.session.flush()
    submission = WeeklyReportSubmission(
        report_id=report.id,
        source_revision=1,
        content=blockers,
        hours_tenths=0,
        completion=progress,
        remark=blockers,
        record_date=date(2026, 7, 23),
        certificate='中级',
        program_count=program_count,
        blockers=blockers,
        submitted_at=datetime(2026, 7, 23, 2),
    )
    db.session.add(submission)
    db.session.flush()
    report.latest_submission_id = submission.id
    return report


def test_weekly_stats_uses_roster_and_latest_submissions_only(app, roster):
    with app.app_context():
        _submitted_report(roster[0], 105, 50)
        _submitted_report(roster[1], 200, 100)
        db.session.commit()
        result = weekly_stats(WEEK)
        assert result['submitted_count'] == 2
        assert result['unsubmitted_count'] == 1
        assert result['total_hours'] == 30.5
        assert result['average_completion'] == 75.0


def test_weekly_stats_exposes_progress_record_fields(app, roster):
    with app.app_context():
        _submitted_progress_report(roster[0], progress=35, program_count=2, blockers='选择器卡点')
        db.session.commit()

        result = weekly_stats(WEEK)

        assert result['total_program_count'] == 2
        assert result['rows'][0]['record_date'] == date(2026, 7, 23)
        assert result['rows'][0]['certificate'] == '中级'
        assert result['rows'][0]['program_count'] == 2
        assert result['rows'][0]['blockers'] == '选择器卡点'


def test_returned_and_expired_reports_are_excluded_until_resubmitted(app, roster):
    with app.app_context():
        report = _submitted_report(roster[0], 100, 80)
        db.session.commit()
        returned = return_report(report.id, operator_id=99, reason='add detail',
                                 edit_deadline='2026-07-28T17:00:00+08:00', now_utc=NOW)
        assert weekly_stats(WEEK, now_utc=NOW)['submitted_count'] == 0
        assert returned.state == 'returned'
        assert serialize_report(returned, now_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc))['state'] == 'return_expired'
        assert expire_return_if_needed(returned, now_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc)) is False
        assert weekly_stats(WEEK, now_utc=NOW)['submitted_count'] == 0
        assert return_report(report.id, 99, 'again', '2026-07-29T17:00:00+08:00', now_utc=NOW).state == 'returned'


def test_return_requires_nonblank_reason_and_future_shanghai_deadline(app, roster):
    with app.app_context():
        report = _submitted_report(roster[0], 100, 80)
        db.session.commit()
        with pytest.raises(LearningValidationError):
            return_report(report.id, 99, ' ', '2026-07-28T17:00:00+08:00', now_utc=NOW)
        with pytest.raises(LearningValidationError):
            return_report(report.id, 99, 'detail', '2026-07-27T16:00:00+08:00', now_utc=NOW)


def test_empty_stats_has_null_average(app, roster):
    with app.app_context():
        result = weekly_stats(WEEK)
        assert result['submitted_count'] == 0
        assert result['unsubmitted_count'] == 3
        assert result['average_completion'] is None


def test_default_trend_has_twelve_monday_buckets_and_gaps(app, roster):
    with app.app_context():
        result = user_trend(roster[0], None, None, now_utc=NOW)
        assert len(result['points']) == 12
        assert result['points'][0]['week_start'].weekday() == 0
        assert all(point['hours'] is None for point in result['points'])


def test_trend_rejects_non_monday_or_reversed_range(app, roster):
    with app.app_context(), pytest.raises(LearningValidationError):
        user_trend(roster[0], date(2026, 7, 21), WEEK, now_utc=NOW)


def test_weekly_stats_endpoint_uses_iso_week_start(client, app, roster):
    with app.app_context():
        db.session.get(UserRole, roster[0]).role = 'hr'
        db.session.commit()
        token = issue_learning_token(roster[0], 'admin')
    response = client.get('/learning/admin/weekly-stats?week_start=2026-07-20', headers={
        'Authorization': f'Bearer {token}',
    })
    assert response.status_code == 200
    assert response.json['week_start'] == '2026-07-20'


def test_employee_role_admin_can_read_weekly_stats_and_user_trend(client, app, roster):
    with app.app_context():
        db.session.get(UserRole, roster[0]).role = 'employee'
        db.session.commit()
        token = issue_learning_token(roster[0], 'admin')
    headers = {'Authorization': f'Bearer {token}'}

    stats_response = client.get(
        '/learning/admin/weekly-stats?week_start=2026-07-20',
        headers=headers,
    )
    trend_response = client.get(
        f'/learning/admin/users/{roster[1]}/trend?to_week=2026-07-20',
        headers=headers,
    )

    assert stats_response.status_code == 200
    assert trend_response.status_code == 200
    assert trend_response.json['user_id'] == roster[1]


def test_user_surface_cannot_read_weekly_stats(client, app, roster):
    with app.app_context():
        token = issue_learning_token(roster[0], 'user')
    response = client.get(
        '/learning/admin/weekly-stats?week_start=2026-07-20',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == 403
    assert response.json == {'error': 'Learning login surface is not permitted'}


def test_weekly_stats_uses_bounded_queries_for_small_and_large_rosters(app, roster):
    with app.app_context():
        asset_statements = []
        main_statements = []

        def count_assets(*_args):
            asset_statements.append(1)

        def count_main(*_args):
            main_statements.append(1)

        event.listen(db.engines['assets'], 'before_cursor_execute', count_assets)
        event.listen(db.engine, 'before_cursor_execute', count_main)
        try:
            weekly_stats(WEEK)
            small_count = len(asset_statements) + len(main_statements)
            for index in range(17):
                user = User(username=f'large-{index}', email=f'large-{index}@example.com', password='secret1', created_at=utc_now())
                db.session.add(user)
                db.session.flush()
                db.session.add(UserRole(user_id=user.id, role='intern'))
            db.session.commit()
            ensure_roster_week(date(2026, 7, 27))
            db.session.commit()
            asset_statements.clear()
            main_statements.clear()
            weekly_stats(date(2026, 7, 27))
            large_count = len(asset_statements) + len(main_statements)
        finally:
            event.remove(db.engines['assets'], 'before_cursor_execute', count_assets)
            event.remove(db.engine, 'before_cursor_execute', count_main)
        assert small_count <= 6
        assert large_count <= 6


def test_recent_week_csv_includes_formal_and_unsubmitted_rows(app, roster):
    with app.app_context():
        report = _submitted_progress_report(
            roster[0],
            progress=50,
            program_count=1,
            blockers='=流程卡点, 需要协助',
        )
        submission = db.session.get(WeeklyReportSubmission, report.latest_submission_id)
        submission.submitted_at = datetime(2026, 7, 22, 3)
        db.session.commit()

        payload, week_start = recent_week_csv(EXPORT_NOW)
        rows = list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))

    assert payload.startswith(b'\xef\xbb\xbf')
    assert week_start == WEEK
    assert rows[0] == [
        '统计周', '时间', '用户名', '邮箱', '提交状态', '证书', '进度（%）',
        '已编/在编程序数', '学习卡点', '正式提交时间',
    ]
    assert len(rows) == 4
    assert rows[1] == [
        '2026年07月20日—2026年07月26日', '2026-07-23', 'stats-0',
        'stats-0@example.com', '已提交', '中级', '50', '1',
        "'=流程卡点, 需要协助", '2026-07-22 11:00',
    ]
    assert rows[2][4:] == ['未提交', '', '', '', '', '']


def test_recent_week_csv_includes_every_formal_submission_version(app, roster):
    with app.app_context():
        report = _submitted_progress_report(
            roster[0],
            progress=35,
            program_count=2,
            blockers='首次提交卡点',
        )
        older = db.session.get(WeeklyReportSubmission, report.latest_submission_id)
        older.submitted_at = datetime(2026, 7, 22, 2)
        latest = WeeklyReportSubmission(
            report_id=report.id,
            source_revision=2,
            content='再次提交卡点',
            hours_tenths=0,
            completion=65,
            remark='再次提交卡点',
            record_date=date(2026, 7, 24),
            certificate='高级',
            program_count=4,
            blockers='再次提交卡点',
            submitted_at=datetime(2026, 7, 22, 4),
        )
        db.session.add(latest)
        db.session.flush()
        report.latest_submission_id = latest.id
        db.session.commit()

        payload, _ = recent_week_csv(EXPORT_NOW)
        rows = list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))

    user_rows = [row for row in rows[1:] if row[2] == 'stats-0']
    assert len(rows) == 5
    assert len(user_rows) == 2
    assert [row[1] for row in user_rows] == ['2026-07-24', '2026-07-23']
    assert [row[5:9] for row in user_rows] == [
        ['高级', '65', '4', '再次提交卡点'],
        ['中级', '35', '2', '首次提交卡点'],
    ]
    assert [row[9] for row in user_rows] == ['2026-07-22 12:00', '2026-07-22 10:00']


def test_recent_week_export_requires_admin_login_surface(client, app, roster):
    with app.app_context():
        admin_token = issue_learning_token(roster[0], 'admin')
        user_token = issue_learning_token(roster[0], 'user')

    allowed = client.get('/learning/admin/export/recent-week', headers={
        'Authorization': f'Bearer {admin_token}',
    })
    forbidden = client.get('/learning/admin/export/recent-week', headers={
        'Authorization': f'Bearer {user_token}',
    })

    assert allowed.status_code == 200
    assert allowed.data.startswith(b'\xef\xbb\xbf')
    assert allowed.content_type.startswith('text/csv')
    assert 'intern_rpa_learning_' in allowed.headers['Content-Disposition']
    assert forbidden.status_code == 403


def test_admin_can_read_formal_progress_history_but_user_surface_cannot(client, app, roster):
    with app.app_context():
        report = _submitted_progress_report(
            roster[0],
            progress=35,
            program_count=2,
            blockers='选择器卡点',
        )
        older = db.session.get(WeeklyReportSubmission, report.latest_submission_id)
        older.submitted_at = datetime(2026, 7, 22, 2)
        latest = WeeklyReportSubmission(
            report_id=report.id,
            source_revision=2,
            content='最新卡点',
            hours_tenths=0,
            completion=45,
            remark='最新卡点',
            record_date=date(2026, 7, 23),
            certificate='中级',
            program_count=3,
            blockers='最新卡点',
            submitted_at=datetime(2026, 7, 23, 2),
        )
        db.session.add(latest)
        db.session.flush()
        report.latest_submission_id = latest.id
        db.session.commit()
        admin_token = issue_learning_token(roster[1], 'admin')
        user_token = issue_learning_token(roster[1], 'user')

    allowed = client.get(f'/learning/admin/users/{roster[0]}/history', headers={
        'Authorization': f'Bearer {admin_token}',
    })
    forbidden = client.get(f'/learning/admin/users/{roster[0]}/history', headers={
        'Authorization': f'Bearer {user_token}',
    })

    assert allowed.status_code == 200
    assert len(allowed.json['items']) == 2
    assert [item['blockers'] for item in allowed.json['items']] == ['最新卡点', '选择器卡点']
    assert [item['program_count'] for item in allowed.json['items']] == [3, 2]
    assert len({item['submission_id'] for item in allowed.json['items']}) == 2
    assert forbidden.status_code == 403
