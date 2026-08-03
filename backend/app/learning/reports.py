from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from app import db
from app.learning.errors import LearningConflictError, LearningForbiddenError, LearningNotFoundError, LearningValidationError
from app.learning.roles import ensure_roster_week, is_roster_member
from app.learning.time import SHANGHAI, parse_shanghai_datetime, utc_now, week_end_utc, week_start_for
from app.models.learning import ReportReturnLog, WeeklyReport, WeeklyReportSubmission


CONFLICT_MESSAGE = 'Report has been updated in another page; refresh and try again'


def _now(value=None):
    value = utc_now() if value is None else value
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _expected_revision(value):
    if isinstance(value, bool):
        raise LearningValidationError('draft_revision must be an integer')
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise LearningValidationError('draft_revision must be an integer')
    if result < 0 or str(result) != str(value).strip():
        raise LearningValidationError('draft_revision must be an integer')
    return result


def _hours_tenths(value, required=False):
    if value is None or value == '':
        if required:
            raise LearningValidationError('hours is required')
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LearningValidationError('hours must be numeric')
    if not decimal.is_finite():
        raise LearningValidationError('hours must be numeric')
    tenths = decimal * Decimal('10')
    if tenths != tenths.to_integral_value():
        raise LearningValidationError('hours must have at most one decimal place')
    result = int(tenths)
    if not 0 <= result <= 1680:
        raise LearningValidationError('hours must be between 0 and 168')
    return result


def _completion(value, required=False):
    if value is None or value == '':
        if required:
            raise LearningValidationError('completion is required')
        return None
    if isinstance(value, bool):
        raise LearningValidationError('completion must be an integer')
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LearningValidationError('completion must be an integer')
    if not decimal.is_finite() or decimal != decimal.to_integral_value():
        raise LearningValidationError('completion must be an integer')
    result = int(decimal)
    if not 0 <= result <= 100:
        raise LearningValidationError('completion must be between 0 and 100')
    return result


def _record_date(value, required=False):
    if value is None or value == '':
        if required:
            raise LearningValidationError('record_date is required')
        return None
    if isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    else:
        try:
            result = date.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise LearningValidationError('record_date must be YYYY-MM-DD')
    return result


def _program_count(value, required=False):
    if value is None or value == '':
        if required:
            raise LearningValidationError('program_count is required')
        return None
    if isinstance(value, bool):
        raise LearningValidationError('program_count must be an integer')
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LearningValidationError('program_count must be an integer')
    if not decimal.is_finite() or decimal != decimal.to_integral_value():
        raise LearningValidationError('program_count must be an integer')
    result = int(decimal)
    if not 0 <= result <= 9999:
        raise LearningValidationError('program_count must be between 0 and 9999')
    return result


def _text(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise LearningValidationError(f'{field} must be text')
    return value


def _normalise_draft(payload):
    if not isinstance(payload, dict):
        raise LearningValidationError('JSON object is required')
    progress_fields = {'record_date', 'certificate', 'progress', 'program_count', 'blockers'}
    if progress_fields.intersection(payload):
        blockers = _text(payload.get('blockers'), 'blockers')
        progress = payload.get('progress') if 'progress' in payload else payload.get('completion')
        return {
            'record_date': _record_date(payload.get('record_date')),
            'certificate': _text(payload.get('certificate'), 'certificate'),
            'program_count': _program_count(payload.get('program_count')),
            'completion': _completion(progress),
            'blockers': blockers,
            # Keep legacy non-null submission columns populated for old readers.
            'content': blockers or '',
            'hours_tenths': 0,
            'remark': blockers,
        }
    return {
        'content': _text(payload.get('content'), 'content'),
        'hours_tenths': _hours_tenths(payload.get('hours')),
        'completion': _completion(payload.get('completion')),
        'remark': _text(payload.get('remark'), 'remark'),
    }


def _latest_return(report):
    return ReportReturnLog.query.filter_by(report_id=report.id, resubmitted_at=None).order_by(
        ReportReturnLog.returned_at.desc(), ReportReturnLog.id.desc()
    ).first()


def expire_return_if_needed(report, now_utc=None):
    if report.state != 'returned':
        return False
    return_log = _latest_return(report)
    if return_log is None or _now(now_utc) < return_log.edit_deadline:
        return False
    report.state = 'return_expired'
    _commit()
    return True


def _report_is_editable(report, now_utc):
    now_utc = _now(now_utc)
    if report.state == 'returned':
        expire_return_if_needed(report, now_utc)
        if report.state != 'returned':
            return False
        return_log = _latest_return(report)
        return return_log is not None and now_utc < return_log.edit_deadline
    return (
        report.week_start == week_start_for(now_utc)
        and now_utc < week_end_utc(report.week_start)
        and is_roster_member(report.user_id, report.week_start)
    )


def _owned_report(user_id, report_id):
    report = db.session.get(WeeklyReport, int(report_id))
    if report is None:
        raise LearningNotFoundError('report was not found')
    if report.user_id != int(user_id):
        raise LearningForbiddenError('Learning report is not permitted')
    return report


def get_report(user_id, report_id, now_utc=None):
    report = _owned_report(user_id, report_id)
    expire_return_if_needed(report, now_utc)
    return report


def get_current_report(user_id, now_utc=None):
    now_utc = _now(now_utc)
    week_start = week_start_for(now_utc)
    ensure_roster_week(week_start)
    if not is_roster_member(user_id, week_start):
        raise LearningForbiddenError('Current-week roster membership is required')
    report = WeeklyReport.query.filter_by(week_start=week_start, user_id=int(user_id)).first()
    if report is not None:
        expire_return_if_needed(report, now_utc)
        return report
    local_date = now_utc.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).date()
    report = WeeklyReport(
        week_start=week_start,
        user_id=int(user_id),
        record_date=local_date,
        state='draft',
        draft_revision=0,
    )
    db.session.add(report)
    _commit()
    return report


def _report_for_write(user_id, report_id, now_utc):
    report = get_current_report(user_id, now_utc) if report_id is None else _owned_report(user_id, report_id)
    expire_return_if_needed(report, now_utc)
    if not _report_is_editable(report, now_utc):
        raise LearningConflictError('Learning report is locked')
    return report


def save_draft(user_id, payload, expected_revision, report_id=None, now_utc=None):
    now_utc = _now(now_utc)
    report = _report_for_write(user_id, report_id, now_utc)
    if report.draft_revision != _expected_revision(expected_revision):
        raise LearningConflictError(CONFLICT_MESSAGE)
    values = _normalise_draft(payload)
    for field, value in values.items():
        setattr(report, field, value)
    report.draft_revision += 1
    _commit()
    return report


def _validate_submission(report):
    progress_format = any((
        report.certificate is not None,
        report.program_count is not None,
        report.blockers is not None,
    ))
    if progress_format:
        record_date = _record_date(report.record_date, required=True)
        if not report.week_start <= record_date < report.week_start + timedelta(days=7):
            raise LearningValidationError('record_date must be within the report week')
        if not isinstance(report.certificate, str) or not report.certificate.strip():
            raise LearningValidationError('certificate is required')
        _program_count(report.program_count, required=True)
        _completion(report.completion, required=True)
        return
    if not isinstance(report.content, str) or not report.content.strip():
        raise LearningValidationError('content is required')
    _hours_tenths(report.hours_tenths / 10 if report.hours_tenths is not None else None, required=True)
    _completion(report.completion, required=True)


def submit_report(user_id, expected_revision, report_id=None, now_utc=None):
    now_utc = _now(now_utc)
    report = _report_for_write(user_id, report_id, now_utc)
    if report.draft_revision != _expected_revision(expected_revision):
        raise LearningConflictError(CONFLICT_MESSAGE)
    _validate_submission(report)
    submission = WeeklyReportSubmission(
        report_id=report.id,
        source_revision=report.draft_revision,
        content=report.content.strip(),
        hours_tenths=report.hours_tenths,
        completion=report.completion,
        remark=report.remark,
        record_date=report.record_date,
        certificate=report.certificate.strip() if isinstance(report.certificate, str) else None,
        program_count=report.program_count,
        blockers=report.blockers.strip() if isinstance(report.blockers, str) else report.blockers,
    )
    db.session.add(submission)
    db.session.flush()
    report.latest_submission_id = submission.id
    report.state = 'submitted'
    if report.week_start != week_start_for(now_utc):
        return_log = _latest_return(report)
        if return_log is not None:
            return_log.resubmitted_at = now_utc
    _commit()
    return report


def list_history(user_id, from_week=None, to_week=None):
    from app.learning.serializers import serialize_report

    if to_week is None:
        to_week = week_start_for()
    if from_week is None:
        from_week = to_week - timedelta(weeks=11)
    if from_week.weekday() != 0 or to_week.weekday() != 0 or from_week > to_week:
        raise LearningValidationError('history weeks must be ordered Mondays')
    query = WeeklyReport.query.filter_by(user_id=int(user_id))
    query = query.filter(WeeklyReport.week_start >= from_week, WeeklyReport.week_start <= to_week)
    return [serialize_report(report) for report in query.order_by(WeeklyReport.week_start.desc()).all()]


def return_report(report_id, operator_id, reason, edit_deadline, now_utc=None):
    now_utc = _now(now_utc)
    report = db.session.get(WeeklyReport, int(report_id))
    if report is None:
        raise LearningNotFoundError('report was not found')
    expire_return_if_needed(report, now_utc)
    if report.week_start >= week_start_for(now_utc) or report.latest_submission_id is None:
        raise LearningConflictError('Only locked submitted reports can be returned')
    if report.state not in ('submitted', 'return_expired'):
        raise LearningConflictError('Learning report cannot be returned')
    if not isinstance(reason, str) or not reason.strip():
        raise LearningValidationError('return reason is required')
    try:
        deadline = parse_shanghai_datetime(edit_deadline)
    except (TypeError, ValueError):
        raise LearningValidationError('edit_deadline must be a Shanghai datetime')
    if deadline <= now_utc:
        raise LearningValidationError('edit_deadline must be in the future')
    submission = db.session.get(WeeklyReportSubmission, report.latest_submission_id)
    if submission is None:
        raise LearningConflictError('Latest submission is unavailable')
    report.content = submission.content
    report.hours_tenths = submission.hours_tenths
    report.completion = submission.completion
    report.remark = submission.remark
    report.record_date = submission.record_date
    report.certificate = submission.certificate
    report.program_count = submission.program_count
    report.blockers = submission.blockers
    report.draft_revision = submission.source_revision
    report.state = 'returned'
    db.session.add(ReportReturnLog(
        report_id=report.id,
        returned_by_user_id=int(operator_id),
        reason=reason.strip(),
        edit_deadline=deadline,
    ))
    _commit()
    return report
