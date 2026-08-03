from datetime import date, timedelta

from app import db
from app.learning.errors import LearningValidationError
from app.learning.reports import _now
from app.learning.time import to_shanghai_iso, week_start_for
from app.models.learning import ReportReturnLog, WeeklyReport, WeeklyReportSubmission, WeeklyRoster
from app.models.models import User


def _monday(value, field):
    if not isinstance(value, date) or value.weekday() != 0:
        raise LearningValidationError(f'{field} must be a Monday date')
    return value


def _expire_returned_reports(reports, now_utc):
    returned_ids = [report.id for report in reports if report.state == 'returned']
    if not returned_ids:
        return
    logs = ReportReturnLog.query.filter(
        ReportReturnLog.report_id.in_(returned_ids), ReportReturnLog.resubmitted_at.is_(None)
    ).all()
    expired_ids = {row.report_id for row in logs if now_utc >= row.edit_deadline}
    if expired_ids:
        for report in reports:
            if report.id in expired_ids:
                report.state = 'return_expired'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


def _record_date(submission, fallback):
    if submission is None:
        return None
    if submission.record_date is not None:
        return submission.record_date
    if submission.submitted_at is not None:
        return date.fromisoformat(to_shanghai_iso(submission.submitted_at)[:10])
    return fallback


def _blockers(submission):
    if submission is None:
        return None
    if submission.blockers is not None:
        return submission.blockers
    return submission.remark or submission.content or ''


def weekly_stats(week_start, now_utc=None):
    week_start = _monday(week_start, 'week_start')
    now_utc = _now(now_utc)
    roster_ids = [row.user_id for row in WeeklyRoster.query.filter_by(week_start=week_start).all()]
    if not roster_ids:
        return {
            'week_start': week_start,
            'roster_count': 0,
            'submitted_count': 0,
            'unsubmitted_count': 0,
            'total_hours': 0.0,
            'total_program_count': 0,
            'average_completion': None,
            'rows': [],
        }
    reports = WeeklyReport.query.filter(
        WeeklyReport.week_start == week_start, WeeklyReport.user_id.in_(roster_ids)
    ).all()
    _expire_returned_reports(reports, now_utc)
    reports_by_user = {report.user_id: report for report in reports}
    submission_ids = [report.latest_submission_id for report in reports if report.latest_submission_id]
    submissions = WeeklyReportSubmission.query.filter(WeeklyReportSubmission.id.in_(submission_ids)).all() if submission_ids else []
    submissions_by_id = {submission.id: submission for submission in submissions}
    users_by_id = {user.id: user for user in User.query.filter(User.id.in_(roster_ids)).all()}

    rows = []
    active_submissions = []
    for user_id in roster_ids:
        report = reports_by_user.get(user_id)
        submission = submissions_by_id.get(report.latest_submission_id) if report else None
        active = report is not None and report.state == 'submitted' and submission is not None
        if active:
            active_submissions.append(submission)
        user = users_by_id.get(user_id)
        rows.append({
            'user_id': user_id,
            'username': user.username if user else None,
            'email': user.email if user else None,
            'report_id': report.id if report else None,
            'state': report.state if report else 'missing',
            'submitted': active,
            'hours': submission.hours_tenths / 10 if active else None,
            'completion': submission.completion if active else None,
            'record_date': _record_date(submission, week_start) if active else None,
            'certificate': submission.certificate if active else None,
            'program_count': submission.program_count if active else None,
            'blockers': _blockers(submission) if active else None,
        })
    submitted_count = len(active_submissions)
    total_tenths = sum(submission.hours_tenths for submission in active_submissions)
    return {
        'week_start': week_start,
        'roster_count': len(roster_ids),
        'submitted_count': submitted_count,
        'unsubmitted_count': len(roster_ids) - submitted_count,
        'total_hours': total_tenths / 10,
        'total_program_count': sum(submission.program_count or 0 for submission in active_submissions),
        'average_completion': (
            sum(submission.completion for submission in active_submissions) / submitted_count
            if submitted_count else None
        ),
        'rows': rows,
    }


def user_trend(user_id, from_week=None, to_week=None, now_utc=None):
    now_utc = _now(now_utc)
    if to_week is None:
        to_week = week_start_for(now_utc)
    if from_week is None:
        from_week = to_week - timedelta(weeks=11)
    from_week = _monday(from_week, 'from_week')
    to_week = _monday(to_week, 'to_week')
    if from_week > to_week:
        raise LearningValidationError('from_week must not be after to_week')
    reports = WeeklyReport.query.filter(
        WeeklyReport.user_id == int(user_id),
        WeeklyReport.week_start >= from_week,
        WeeklyReport.week_start <= to_week,
    ).all()
    _expire_returned_reports(reports, now_utc)
    submission_ids = [report.latest_submission_id for report in reports if report.latest_submission_id]
    submissions_by_id = {
        submission.id: submission
        for submission in WeeklyReportSubmission.query.filter(WeeklyReportSubmission.id.in_(submission_ids)).all()
    } if submission_ids else {}
    reports_by_week = {report.week_start: report for report in reports}
    points = []
    week = from_week
    while week <= to_week:
        report = reports_by_week.get(week)
        submission = submissions_by_id.get(report.latest_submission_id) if report and report.state == 'submitted' else None
        points.append({
            'week_start': week,
            'hours': submission.hours_tenths / 10 if submission else None,
            'completion': submission.completion if submission else None,
            'record_date': _record_date(submission, week),
            'certificate': submission.certificate if submission else None,
            'program_count': submission.program_count if submission else None,
            'blockers': _blockers(submission),
        })
        week += timedelta(weeks=1)
    return {'user_id': int(user_id), 'from_week': from_week, 'to_week': to_week, 'points': points}


def submission_history(user_id, now_utc=None):
    now_utc = _now(now_utc)
    reports = WeeklyReport.query.filter(
        WeeklyReport.user_id == int(user_id),
    ).order_by(WeeklyReport.week_start.desc(), WeeklyReport.id.desc()).all()
    _expire_returned_reports(reports, now_utc)
    reports_by_id = {report.id: report for report in reports}
    report_ids = list(reports_by_id)
    submissions = WeeklyReportSubmission.query.filter(
        WeeklyReportSubmission.report_id.in_(report_ids)
    ).order_by(
        WeeklyReportSubmission.submitted_at.desc(),
        WeeklyReportSubmission.id.desc(),
    ).all() if report_ids else []

    items = []
    for submission in submissions:
        report = reports_by_id.get(submission.report_id)
        if report is None:
            continue
        items.append({
            'submission_id': submission.id,
            'report_id': report.id,
            'week_start': report.week_start,
            'record_date': _record_date(submission, report.week_start),
            'state': report.state,
            'certificate': submission.certificate,
            'progress': submission.completion,
            'program_count': submission.program_count,
            'blockers': _blockers(submission),
            'submitted_at': to_shanghai_iso(submission.submitted_at),
        })
    return {'user_id': int(user_id), 'items': items}


def user_history(user_id, now_utc=None):
    return submission_history(user_id, now_utc=now_utc)
