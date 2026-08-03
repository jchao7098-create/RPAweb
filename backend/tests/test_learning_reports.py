from datetime import date, datetime, timezone

import pytest

from app import db
from app.learning.auth import issue_learning_token
from app.learning.errors import LearningConflictError, LearningForbiddenError, LearningValidationError
from app.learning.reports import get_current_report, list_history, save_draft, submit_report
from app.learning.roles import ensure_roster_week
from app.learning.serializers import serialize_report
from app.learning.time import utc_now
from app.models.learning import UserRole, WeeklyReport, WeeklyReportSubmission
from app.models.models import User


NOW = datetime(2026, 7, 22, 9, tzinfo=timezone.utc)
WEEK = date(2026, 7, 20)


@pytest.fixture()
def intern_id(app):
    with app.app_context():
        user = User(username='intern-report', email='intern-report@example.com', password='secret1', created_at=utc_now())
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role='intern'))
        db.session.commit()
        ensure_roster_week(WEEK)
        db.session.commit()
        return user.id


def test_draft_is_not_a_submission(app, intern_id):
    with app.app_context():
        report = save_draft(intern_id, {'content': '', 'hours': None, 'completion': None, 'remark': ''}, 0, now_utc=NOW)
        assert report.state == 'draft'
        assert report.latest_submission_id is None


def test_submitted_edit_keeps_previous_formal_version(app, intern_id):
    with app.app_context():
        report = save_draft(intern_id, {'content': 'foundation', 'hours': 12.5, 'completion': 60, 'remark': ''}, 0, now_utc=NOW)
        submit_report(intern_id, report.draft_revision, now_utc=NOW)
        old_submission_id = report.latest_submission_id
        save_draft(intern_id, {'content': 'advanced', 'hours': 16, 'completion': 75, 'remark': ''}, report.draft_revision, now_utc=NOW)
        assert report.latest_submission_id == old_submission_id
        assert serialize_report(report, now_utc=NOW)['has_unsubmitted_changes'] is True


def test_revision_conflict_is_409(app, intern_id):
    with app.app_context():
        save_draft(intern_id, {'content': 'A'}, 0, now_utc=NOW)
        with pytest.raises(LearningConflictError):
            save_draft(intern_id, {'content': 'B'}, 0, now_utc=NOW)


@pytest.mark.parametrize('hours', [0, 168])
def test_submission_accepts_hour_boundaries(app, intern_id, hours):
    with app.app_context():
        report = save_draft(intern_id, {'content': 'A', 'hours': hours, 'completion': 0, 'remark': ''}, 0, now_utc=NOW)
        submitted = submit_report(intern_id, report.draft_revision, now_utc=NOW)
        assert submitted.latest_submission_id is not None


def test_draft_rejects_more_than_one_decimal_hour(app, intern_id):
    with app.app_context(), pytest.raises(LearningValidationError):
        save_draft(intern_id, {'content': 'A', 'hours': '1.25', 'completion': 100}, 0, now_utc=NOW)


@pytest.mark.parametrize('completion', [0, 100])
def test_submission_accepts_completion_boundaries(app, intern_id, completion):
    with app.app_context():
        report = save_draft(intern_id, {'content': 'A', 'hours': 1, 'completion': completion}, 0, now_utc=NOW)
        submit_report(intern_id, report.draft_revision, now_utc=NOW)
        assert report.state == 'submitted'


def test_monday_locks_current_report(app, intern_id):
    with app.app_context():
        report = save_draft(intern_id, {'content': 'A'}, 0, now_utc=NOW)
        with pytest.raises(LearningConflictError):
            save_draft(intern_id, {'content': 'B'}, report.draft_revision,
                       now_utc=datetime(2026, 7, 26, 16, tzinfo=timezone.utc))


def test_non_roster_user_cannot_create_current_report(app):
    with app.app_context():
        user = User(username='not-rostered', email='not-rostered@example.com', password='secret1', created_at=utc_now())
        db.session.add(user)
        db.session.commit()
        with pytest.raises(LearningForbiddenError):
            get_current_report(user.id, now_utc=NOW)


def test_history_only_returns_own_reports(app, intern_id):
    with app.app_context():
        report = save_draft(intern_id, {'content': 'A'}, 0, now_utc=NOW)
        other = User(username='other-report', email='other-report@example.com', password='secret1', created_at=utc_now())
        db.session.add(other)
        db.session.flush()
        db.session.add(WeeklyReport(week_start=WEEK, user_id=other.id, content='secret'))
        db.session.commit()
        history = list_history(intern_id, from_week=WEEK, to_week=WEEK)
        assert [item['id'] for item in history] == [report.id]


def test_history_defaults_to_recent_twelve_weeks(app, intern_id):
    with app.app_context():
        old = WeeklyReport(week_start=date(2025, 1, 6), user_id=intern_id, content='old')
        db.session.add(old)
        db.session.commit()
        assert old.id not in [item['id'] for item in list_history(intern_id)]


def test_progress_record_fields_persist_in_draft_and_formal_submission(app, intern_id):
    with app.app_context():
        report = save_draft(intern_id, {
            'record_date': '2026-07-23',
            'certificate': '中级',
            'progress': 35,
            'program_count': 2,
            'blockers': '选择器定位不稳定',
        }, 0, now_utc=NOW)

        assert report.record_date == date(2026, 7, 23)
        assert report.certificate == '中级'
        assert report.completion == 35
        assert report.program_count == 2
        assert report.blockers == '选择器定位不稳定'

        submit_report(intern_id, report.draft_revision, now_utc=NOW)
        payload = serialize_report(report, now_utc=NOW)
        submission = db.session.get(WeeklyReportSubmission, report.latest_submission_id)

        assert submission.record_date == date(2026, 7, 23)
        assert payload['record_date'] == '2026-07-23'
        assert payload['progress'] == 35
        assert payload['program_count'] == 2
        assert payload['blockers'] == '选择器定位不稳定'
        assert payload['latest_submission']['certificate'] == '中级'


@pytest.mark.parametrize('program_count', [-1, 1.5, 'not-a-number'])
def test_progress_record_rejects_invalid_program_count(app, intern_id, program_count):
    with app.app_context(), pytest.raises(LearningValidationError):
        save_draft(intern_id, {
            'record_date': '2026-07-23',
            'certificate': '中级',
            'progress': 35,
            'program_count': program_count,
            'blockers': '无',
        }, 0, now_utc=NOW)


def test_user_submission_history_returns_every_formal_version(client, app, intern_id):
    with app.app_context():
        first = save_draft(intern_id, {
            'record_date': '2026-07-23',
            'certificate': '初级',
            'progress': 20,
            'program_count': 0,
            'blockers': '第一条卡点',
        }, 0, now_utc=NOW)
        submit_report(intern_id, first.draft_revision, now_utc=NOW)
        second = save_draft(intern_id, {
            'record_date': '2026-07-23',
            'certificate': '中级',
            'progress': 40,
            'program_count': 1,
            'blockers': '第二条卡点',
        }, first.draft_revision, now_utc=NOW)
        submit_report(intern_id, second.draft_revision, now_utc=NOW)
        token = issue_learning_token(intern_id, 'user')

    response = client.get('/learning/reports/submission-history', headers={
        'Authorization': f'Bearer {token}',
    })

    assert response.status_code == 200
    assert len(response.json['items']) == 2
    assert [item['blockers'] for item in response.json['items']] == ['第二条卡点', '第一条卡点']
    assert len({item['submission_id'] for item in response.json['items']}) == 2
