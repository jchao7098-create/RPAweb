import csv
import io
import zipfile
from datetime import datetime, timedelta

from app import db
from app.learning.auth import issue_learning_token
from app.learning.time import week_start_for
from app.models.learning import (
    UserRole,
    WeeklyReport,
    WeeklyReportSubmission,
    WeeklyRoster,
    WeeklyRosterWeek,
)
from app.models.models import Project, ProjectLog, Requirement, User


def _user(name):
    user = User(
        username=name,
        email=f'{name}@example.com',
        password=f'{name}-website-secret',
    )
    db.session.add(user)
    db.session.flush()
    return user


def _requirement(user, title):
    row = Requirement(
        user_id=user.id,
        title=title,
        description=f'{title}描述',
        department='客服',
        requester=user.username,
        feedback_time=datetime(2026, 7, 28, 9),
        priority='中',
        expected_finish_time=datetime(2026, 8, 8, 18),
        platform='浏览器',
        operation_link='https://example.com',
        account=f'{user.username}-operation-account',
        password=f'{user.username}-operation-secret',
        attachments=[],
        status='待审核',
    )
    db.session.add(row)
    return row


def _headers(user):
    return {'Authorization': f'Bearer {issue_learning_token(user.id, "user")}'}


def test_user_export_routes_use_full_platform_scope(app, client):
    with app.app_context():
        owner = _user('owner')
        other = _user('other')
        _requirement(owner, '本人需求')
        _requirement(other, '他人需求')
        db.session.commit()
        headers = _headers(owner)

    response = client.get('/user/manage/export/upload_names', headers=headers)

    assert response.status_code == 200
    text = response.data.decode('utf-8-sig')
    assert '本人需求' in text
    assert '他人需求' in text


def test_full_archive_contains_platform_and_learning_data_without_passwords(app, client):
    with app.app_context():
        owner = _user('owner')
        learner = _user('learner')
        _requirement(owner, '全平台导出需求')
        week_start = week_start_for()
        db.session.add(UserRole(user_id=learner.id, role='intern'))
        db.session.add(WeeklyRosterWeek(week_start=week_start))
        db.session.add(WeeklyRoster(week_start=week_start, user_id=learner.id))
        report = WeeklyReport(
            week_start=week_start,
            user_id=learner.id,
            content='学习流程自动化',
            blockers='选择器定位',
            completion=60,
            program_count=2,
            draft_revision=1,
            state='submitted',
        )
        db.session.add(report)
        db.session.flush()
        submission = WeeklyReportSubmission(
            report_id=report.id,
            source_revision=1,
            content='学习流程自动化',
            hours_tenths=50,
            completion=60,
            program_count=2,
            blockers='选择器定位',
        )
        db.session.add(submission)
        db.session.flush()
        report.latest_submission_id = submission.id
        db.session.commit()
        headers = _headers(owner)

    response = client.get('/user/manage/export/full_archive', headers=headers)

    assert response.status_code == 200
    assert response.content_type == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        names = set(archive.namelist())
        assert {
            '01_用户账号.csv',
            '02_RPA需求.csv',
            '08_Skill与Python资产.csv',
            '09_实习生学习情况.csv',
            'README.txt',
        }.issubset(names)
        users_csv = archive.read('01_用户账号.csv').decode('utf-8-sig')
        requirements_csv = archive.read('02_RPA需求.csv').decode('utf-8-sig')
        learning_csv = archive.read('09_实习生学习情况.csv').decode('utf-8-sig')
        readme = archive.read('README.txt').decode('utf-8')

    assert 'owner@example.com' in users_csv
    assert 'learner@example.com' in users_csv
    assert '全平台导出需求' in requirements_csv
    assert '客服部' in requirements_csv
    assert 'operation-secret' not in requirements_csv
    assert 'website-secret' not in users_csv
    assert 'learner' in learning_csv
    assert '选择器定位' in learning_csv
    assert '不包含网站登录密码' in readme


def test_user_can_export_all_historical_intern_learning_data(app, client):
    with app.app_context():
        owner = _user('owner')
        learner = _user('learner')
        week_start = week_start_for()
        previous_week = week_start - timedelta(days=7)
        db.session.add(UserRole(user_id=learner.id, role='intern'))
        db.session.add(WeeklyRosterWeek(week_start=week_start))
        db.session.add(WeeklyRosterWeek(week_start=previous_week))
        db.session.add(WeeklyRoster(week_start=week_start, user_id=learner.id))
        db.session.add(WeeklyRoster(week_start=previous_week, user_id=learner.id))
        db.session.commit()
        headers = _headers(owner)

    assert client.get('/user/manage/export/intern_learning').status_code == 401
    response = client.get('/user/manage/export/intern_learning', headers=headers)

    assert response.status_code == 200
    assert response.content_type.startswith('text/csv')
    text = response.data.decode('utf-8-sig')
    assert 'learner@example.com' in text
    assert week_start.isoformat() in text
    assert previous_week.isoformat() in text


def test_legacy_admin_export_requires_an_admin_surface_token(app, client):
    with app.app_context():
        user = _user('admin-exporter')
        db.session.commit()
        user_headers = _headers(user)
        admin_headers = {
            'Authorization': f'Bearer {issue_learning_token(user.id, "admin")}',
        }

    assert client.get('/admin/export/full_archive').status_code == 401
    assert client.get('/admin/export/full_archive', headers=user_headers).status_code == 403
    assert client.get('/admin/export/full_archive', headers=admin_headers).status_code == 200


def test_project_export_uses_latest_log_status_instead_of_progress(app, client):
    with app.app_context():
        owner = _user('project-exporter')
        project = Project(
            name='导出状态口径测试',
            description='进度与状态独立',
            created_by=owner.id,
            status='使用',
            progress=100,
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(ProjectLog(
            developer_id=owner.id,
            project_id=project.id,
            status='大修',
            remark='最新日志进入大修',
            log_time=datetime(2026, 7, 29, 12),
        ))
        db.session.commit()
        project_id = project.id
        headers = _headers(owner)

    response = client.get('/user/manage/export/full_archive', headers=headers)

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        project_filename = next(
            name for name in archive.namelist() if name.startswith('03_')
        )
        rows = list(csv.reader(io.StringIO(
            archive.read(project_filename).decode('utf-8-sig')
        )))

    exported = next(row for row in rows[1:] if int(row[0]) == project_id)
    assert exported[4] == '大修'
    assert exported[5] == '100.0'
