import csv
import io
from datetime import datetime, timedelta

from app.learning.stats import weekly_stats
from app.learning.time import to_shanghai_iso, week_start_for
from app.models.learning import WeeklyReportSubmission


HEADERS = [
    '统计周',
    '时间',
    '用户名',
    '邮箱',
    '提交状态',
    '证书',
    '进度（%）',
    '已编/在编程序数',
    '学习卡点',
    '正式提交时间',
]

STATUS_LABELS = {
    'missing': '未提交',
    'draft': '未提交',
    'submitted': '已提交',
    'returned': '退回修改中',
    'return_expired': '退回逾期',
}


def _safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def _submission_time(value):
    if value is None:
        return ''
    return datetime.fromisoformat(to_shanghai_iso(value)).strftime('%Y-%m-%d %H:%M')


def _record_date(submission):
    if submission is None:
        return ''
    if submission.record_date is not None:
        return submission.record_date.isoformat()
    if submission.submitted_at is not None:
        return to_shanghai_iso(submission.submitted_at)[:10]
    return ''


def _blockers(submission):
    if submission is None:
        return ''
    if submission.blockers is not None:
        return submission.blockers
    return submission.remark or submission.content or ''


def recent_week_csv(now_utc=None):
    week_start = week_start_for(now_utc)
    week_end = week_start + timedelta(days=6)
    week_label = f'{week_start:%Y年%m月%d日}—{week_end:%Y年%m月%d日}'
    stats = weekly_stats(week_start, now_utc=now_utc)

    report_ids = [
        row['report_id']
        for row in stats['rows']
        if row['report_id']
    ]
    submissions = (
        WeeklyReportSubmission.query.filter(
            WeeklyReportSubmission.report_id.in_(report_ids)
        ).order_by(
            WeeklyReportSubmission.submitted_at.desc(),
            WeeklyReportSubmission.id.desc(),
        ).all()
        if report_ids
        else []
    )
    submissions_by_report_id = {}
    for submission in submissions:
        submissions_by_report_id.setdefault(submission.report_id, []).append(submission)

    rows = [HEADERS]
    for row in sorted(
        stats['rows'],
        key=lambda item: ((item['username'] or '').lower(), item['user_id']),
    ):
        report_submissions = submissions_by_report_id.get(row['report_id']) or [None]
        for submission in report_submissions:
            rows.append([
                week_label,
                _record_date(submission),
                row['username'] or '',
                row['email'] or '',
                STATUS_LABELS.get(row['state'], row['state']),
                submission.certificate if submission and submission.certificate else '',
                submission.completion if submission else '',
                submission.program_count if submission and submission.program_count is not None else '',
                _blockers(submission),
                _submission_time(submission.submitted_at) if submission else '',
            ])

    buffer = io.StringIO(newline='')
    csv.writer(buffer).writerows([
        [_safe_cell(cell) for cell in row]
        for row in rows
    ])
    return ('\ufeff' + buffer.getvalue()).encode('utf-8'), week_start
