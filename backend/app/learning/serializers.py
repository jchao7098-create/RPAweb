from app.learning.reports import _latest_return, _now, _report_is_editable, expire_return_if_needed
from app.learning.time import to_shanghai_iso
from app.models.learning import ReportReturnLog, WeeklyReportSubmission
from app import db


def _submission_payload(submission):
    if submission is None:
        return None
    return {
        'id': submission.id,
        'source_revision': submission.source_revision,
        'content': submission.content,
        'hours': submission.hours_tenths / 10,
        'completion': submission.completion,
        'remark': submission.remark,
        'record_date': submission.record_date.isoformat() if submission.record_date else None,
        'certificate': submission.certificate,
        'progress': submission.completion,
        'program_count': submission.program_count,
        'blockers': (
            submission.blockers
            if submission.blockers is not None
            else (submission.remark or submission.content or '')
        ),
        'submitted_at': to_shanghai_iso(submission.submitted_at),
    }


def serialize_report(report, now_utc=None):
    now_utc = _now(now_utc)
    expire_return_if_needed(report, now_utc)
    latest_submission = db.session.get(WeeklyReportSubmission, report.latest_submission_id) if report.latest_submission_id else None
    return_logs = ReportReturnLog.query.filter_by(report_id=report.id).order_by(
        ReportReturnLog.returned_at.desc(), ReportReturnLog.id.desc()
    ).all()
    unresolved_return = _latest_return(report)
    has_unsubmitted_changes = bool(
        latest_submission and report.draft_revision > latest_submission.source_revision
    )
    display_status = 'returned-modifying' if report.state == 'returned' else report.state
    return {
        'id': report.id,
        'user_id': report.user_id,
        'week_start': report.week_start.isoformat(),
        'state': report.state,
        'display_status': display_status,
        'content': report.content,
        'hours': report.hours_tenths / 10 if report.hours_tenths is not None else None,
        'completion': report.completion,
        'remark': report.remark,
        'record_date': report.record_date.isoformat() if report.record_date else report.week_start.isoformat(),
        'certificate': report.certificate,
        'progress': report.completion,
        'program_count': report.program_count,
        'blockers': (
            report.blockers
            if report.blockers is not None
            else (report.remark or report.content or '')
        ),
        'draft_revision': report.draft_revision,
        'latest_submission': _submission_payload(latest_submission),
        'has_unsubmitted_changes': has_unsubmitted_changes,
        'is_editable': _report_is_editable(report, now_utc),
        'return_deadline': to_shanghai_iso(unresolved_return.edit_deadline) if unresolved_return else None,
        'return_history': [
            {
                'id': row.id,
                'reason': row.reason,
                'returned_by_user_id': row.returned_by_user_id,
                'returned_at': to_shanghai_iso(row.returned_at),
                'edit_deadline': to_shanghai_iso(row.edit_deadline),
                'resubmitted_at': to_shanghai_iso(row.resubmitted_at),
            }
            for row in return_logs
        ],
    }
