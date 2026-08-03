"""Build a full-platform, spreadsheet-friendly data archive.

The archive intentionally excludes authentication secrets: website password
hashes, requirement login passwords, SMTP credentials, and token keys are never
exported. The application currently records Skill/Python filenames only, so the
archive contains their metadata rather than source-file contents.
"""

import csv
import io
import json
import zipfile
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import selectinload

from app.departments import normalize_department
from app.learning.exports import STATUS_LABELS
from app.models.learning import (
    ReportReturnLog,
    RoleChangeLog,
    UserRole,
    WeeklyReport,
    WeeklyReportSubmission,
    WeeklyRoster,
    WeeklyRosterWeek,
)
from app.models.models import (
    Asset,
    MaintenanceItem,
    MaintenanceLog,
    MaintenanceRecord,
    Progress,
    Project,
    ProjectLog,
    Requirement,
    User,
)
from app.project_status import display_status_for_project

INTERN_LEARNING_HEADERS = [
    '统计周',
    '用户ID',
    '用户名',
    '邮箱',
    '当前角色',
    '提交状态',
    '记录日期',
    '证书',
    '进度（%）',
    '已编/在编程序数',
    '学习卡点',
    '正式提交时间',
    '周报创建时间',
    '周报更新时间',
]


def _safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def _csv_bytes(headers, rows):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows([[_safe_cell(cell) for cell in row] for row in rows])
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


def _learning_rows():
    rosters = WeeklyRoster.query.order_by(WeeklyRoster.week_start, WeeklyRoster.user_id).all()
    user_ids = {row.user_id for row in rosters}
    users = {
        user.id: user
        for user in User.query.filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    roles = {
        role.user_id: role.role
        for role in UserRole.query.filter(UserRole.user_id.in_(user_ids)).all()
    } if user_ids else {}
    reports = {
        (report.week_start, report.user_id): report
        for report in WeeklyReport.query.filter(WeeklyReport.user_id.in_(user_ids)).all()
    } if user_ids else {}
    report_ids = [report.id for report in reports.values()]
    submissions_by_report = defaultdict(list)
    if report_ids:
        for submission in (
            WeeklyReportSubmission.query
            .filter(WeeklyReportSubmission.report_id.in_(report_ids))
            .order_by(WeeklyReportSubmission.submitted_at, WeeklyReportSubmission.id)
            .all()
        ):
            submissions_by_report[submission.report_id].append(submission)

    rows = []
    for roster in rosters:
        user = users.get(roster.user_id)
        report = reports.get((roster.week_start, roster.user_id))
        submissions = submissions_by_report.get(report.id, []) if report else []
        records = submissions or [None]
        for submission in records:
            rows.append([
                roster.week_start,
                roster.user_id,
                user.username if user else '',
                user.email if user else '',
                roles.get(roster.user_id, 'intern'),
                STATUS_LABELS.get(report.state, report.state) if report else '未提交',
                submission.record_date if submission else (report.record_date if report else ''),
                submission.certificate if submission else (report.certificate if report else ''),
                submission.completion if submission else (report.completion if report else ''),
                submission.program_count if submission else (report.program_count if report else ''),
                (
                    submission.blockers or submission.remark or submission.content
                    if submission
                    else (report.blockers or report.remark or report.content if report else '')
                ),
                submission.submitted_at if submission else '',
                report.created_at if report else '',
                report.updated_at if report else '',
            ])
    return rows


def all_intern_learning_csv():
    """Return every roster week and every formal intern submission as one CSV."""
    return _csv_bytes(INTERN_LEARNING_HEADERS, _learning_rows())


def build_full_platform_archive():
    """Return a ZIP containing full-platform CSV datasets."""
    projects = (
        Project.query
        .options(selectinload(Project.logs))
        .order_by(Project.id)
        .all()
    )
    datasets = [
        (
            '01_用户账号.csv',
            ['用户ID', '用户名', '邮箱', '注册时间'],
            (
                [row.id, row.username, row.email, row.created_at]
                for row in User.query.order_by(User.id).all()
            ),
        ),
        (
            '02_RPA需求.csv',
            [
                '需求ID', '用户ID', '标题', '描述', '部门', '需求人', '紧急程度',
                '反馈时间', '期望完成时间', '平台', '操作链接', '附件', '审核状态',
                '创建时间', '更新时间',
            ],
            (
                [
                    row.id, row.user_id, row.title, row.description,
                    normalize_department(row.department), row.requester, row.priority,
                    row.feedback_time, row.expected_finish_time, row.platform,
                    row.operation_link, row.attachments, row.status,
                    row.created_at, row.updated_at,
                ]
                for row in Requirement.query.order_by(Requirement.id).all()
            ),
        ),
        (
            '03_RPA项目.csv',
            ['项目ID', '名称', '描述', '创建人ID', '状态', '进度', '创建时间'],
            (
                [
                    row.id, row.name, row.description, row.created_by,
                    display_status_for_project(row), row.progress, row.created_at,
                ]
                for row in projects
            ),
        ),
        (
            '04_开发日志.csv',
            ['日志ID', '项目ID', '开发人ID', '状态', '备注', '日志时间'],
            (
                [
                    row.id, row.project_id, row.developer_id,
                    row.status, row.remark, row.log_time,
                ]
                for row in ProjectLog.query.order_by(ProjectLog.id).all()
            ),
        ),
        (
            '05_维护任务.csv',
            ['任务ID', '标题', '描述', '进度', '状态', '创建时间'],
            (
                [
                    row.id, row.title, row.description, row.progress,
                    row.status, row.created_at,
                ]
                for row in MaintenanceItem.query.order_by(MaintenanceItem.id).all()
            ),
        ),
        (
            '06_维护日志.csv',
            ['日志ID', '维护任务ID', '操作人ID', '状态', '备注', '日志时间'],
            (
                [
                    row.id, row.maintenance_id, row.operator_id,
                    row.status, row.remark, row.log_time,
                ]
                for row in MaintenanceLog.query.order_by(MaintenanceLog.id).all()
            ),
        ),
        (
            '07_维护记录.csv',
            [
                '记录ID', '项目ID', '项目名称', '维护人ID', '维护人',
                '需求人ID', '需求人', '维护日期', '维护内容', '创建时间',
            ],
            (
                [
                    row.id, row.project_id, row.project_name,
                    row.maintainer_id, row.maintainer_name,
                    row.requester_id, row.requester_name,
                    row.maintenance_date, row.maintenance_details, row.created_at,
                ]
                for row in MaintenanceRecord.query.order_by(MaintenanceRecord.id).all()
            ),
        ),
        (
            '08_Skill与Python资产.csv',
            [
                '资产ID', '用户ID', '类型', '名称', '部门', '提交人', '版本',
                '描述', '文件名', '文件大小', '审核状态', '生命周期状态',
                '开发进度', '拒绝原因', '创建时间',
            ],
            (
                [
                    row.id, row.user_id, row.asset_type, row.name,
                    normalize_department(row.department), row.submitter,
                    row.version, row.description, row.file_name, row.file_size,
                    row.status, row.lifecycle_status, row.progress,
                    row.reject_reason, row.created_at,
                ]
                for row in Asset.query.order_by(Asset.id).all()
            ),
        ),
        (
            '09_实习生学习情况.csv',
            INTERN_LEARNING_HEADERS,
            _learning_rows(),
        ),
        (
            '10_学习退回记录.csv',
            [
                '记录ID', '周报ID', '退回人ID', '退回原因',
                '修改截止时间', '退回时间', '重新提交时间',
            ],
            (
                [
                    row.id, row.report_id, row.returned_by_user_id, row.reason,
                    row.edit_deadline, row.returned_at, row.resubmitted_at,
                ]
                for row in ReportReturnLog.query.order_by(ReportReturnLog.id).all()
            ),
        ),
        (
            '11_角色变更记录.csv',
            ['记录ID', '用户ID', '原角色', '新角色', '操作人ID', '来源', '变更时间'],
            (
                [
                    row.id, row.target_user_id, row.old_role, row.new_role,
                    row.operator_user_id, row.source, row.changed_at,
                ]
                for row in RoleChangeLog.query.order_by(RoleChangeLog.id).all()
            ),
        ),
        (
            '12_历史进度表.csv',
            ['记录ID', '需求ID', '阶段', '进度详情'],
            (
                [row.id, row.requirement_id, row.phase, row.progress_detail]
                for row in Progress.query.order_by(Progress.id).all()
            ),
        ),
        (
            '13_当前人员角色.csv',
            ['用户ID', '当前角色', '分配人ID', '创建时间', '更新时间'],
            (
                [
                    row.user_id, row.role, row.assigned_by_user_id,
                    row.created_at, row.updated_at,
                ]
                for row in UserRole.query.order_by(UserRole.user_id).all()
            ),
        ),
        (
            '14_实习生周名单.csv',
            ['记录ID', '统计周', '用户ID', '创建时间'],
            (
                [row.id, row.week_start, row.user_id, row.created_at]
                for row in WeeklyRoster.query.order_by(
                    WeeklyRoster.week_start,
                    WeeklyRoster.user_id,
                ).all()
            ),
        ),
        (
            '15_学习周报原始数据.csv',
            [
                '周报ID', '统计周', '用户ID', '内容', '学习时长（十分之一小时）',
                '进度（%）', '备注', '记录日期', '证书', '程序数', '学习卡点',
                '草稿版本', '最新正式提交ID', '状态', '创建时间', '更新时间',
            ],
            (
                [
                    row.id, row.week_start, row.user_id, row.content,
                    row.hours_tenths, row.completion, row.remark, row.record_date,
                    row.certificate, row.program_count, row.blockers,
                    row.draft_revision, row.latest_submission_id, row.state,
                    row.created_at, row.updated_at,
                ]
                for row in WeeklyReport.query.order_by(
                    WeeklyReport.week_start,
                    WeeklyReport.user_id,
                ).all()
            ),
        ),
        (
            '16_学习正式提交历史.csv',
            [
                '提交ID', '周报ID', '来源版本', '内容', '学习时长（十分之一小时）',
                '进度（%）', '备注', '记录日期', '证书', '程序数', '学习卡点',
                '正式提交时间',
            ],
            (
                [
                    row.id, row.report_id, row.source_revision, row.content,
                    row.hours_tenths, row.completion, row.remark, row.record_date,
                    row.certificate, row.program_count, row.blockers, row.submitted_at,
                ]
                for row in WeeklyReportSubmission.query.order_by(
                    WeeklyReportSubmission.submitted_at,
                    WeeklyReportSubmission.id,
                ).all()
            ),
        ),
        (
            '17_学习统计周.csv',
            ['统计周', '创建时间'],
            (
                [row.week_start, row.created_at]
                for row in WeeklyRosterWeek.query.order_by(WeeklyRosterWeek.week_start).all()
            ),
        ),
    ]

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, headers, rows in datasets:
            archive.writestr(filename, _csv_bytes(headers, rows))
        archive.writestr(
            'README.txt',
            (
                'AI Tools web 全平台数据导出\n'
                f'生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n'
                '说明：CSV 文件均为 UTF-8 BOM，可直接用 Excel 打开。\n'
                '安全说明：不包含网站登录密码、需求登录密码、邮箱授权码或令牌密钥。\n'
                'Skill/Python 当前仅登记文件名，因此导出的是资产元数据，不含源文件内容。\n'
            ).encode('utf-8'),
        )
    return output.getvalue()
