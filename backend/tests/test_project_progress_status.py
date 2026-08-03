from datetime import datetime

import pytest

from app import db
from app.learning.auth import issue_learning_token
from app.models.learning import UserRole
from app.models.models import Project, ProjectLog, User


@pytest.fixture()
def project(app):
    with app.app_context():
        db.session.add(User(
            id=1,
            username='progress-tester',
            email='progress-tester@example.invalid',
            password='test',
        ))
        item = Project(
            name='进度与状态独立测试',
            created_by=1,
            status='在编',
            progress=50,
        )
        db.session.add(item)
        db.session.commit()
        return item.id


@pytest.fixture(params=('hr', 'boss'))
def admin_headers(app, project, request):
    with app.app_context():
        db.session.add(UserRole(user_id=1, role=request.param))
        db.session.commit()
        token = issue_learning_token(1, 'admin')
    return {'Authorization': f'Bearer {token}'}


@pytest.mark.parametrize('progress', [0, 1, 99, 100])
def test_explicit_status_is_independent_from_progress(
    app,
    client,
    project,
    admin_headers,
    progress,
):
    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': progress,
        'status': '大修',
        'remark': f'进度更新为 {progress}',
    }, headers=admin_headers)

    assert response.status_code == 200
    assert response.get_json()['status'] == '大修'

    with app.app_context():
        stored = db.session.get(Project, project)
        assert stored.progress == progress
        assert stored.status == '大修'
        latest_log = (
            ProjectLog.query
            .filter_by(project_id=project)
            .order_by(ProjectLog.id.desc())
            .first()
        )
        assert latest_log.status == '大修'


def test_legacy_auto_request_keeps_latest_log_status(
    app,
    client,
    project,
    admin_headers,
):
    with app.app_context():
        db.session.add(ProjectLog(
            developer_id=1,
            project_id=project,
            status='停用',
            remark='暂停运行',
        ))
        db.session.commit()

    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 100,
        'status': 'auto',
        'remark': '只更新进度',
    }, headers=admin_headers)

    assert response.status_code == 200
    assert response.get_json()['status'] == '停用'
    with app.app_context():
        stored = db.session.get(Project, project)
        assert stored.progress == 100
        assert stored.status == '停用'
        statuses = [
            row.status
            for row in ProjectLog.query
            .filter_by(project_id=project)
            .order_by(ProjectLog.id)
        ]
        assert statuses == ['停用', '停用']


@pytest.mark.parametrize('progress', [-1, 101, 'not-a-number', None, float('inf')])
def test_update_progress_rejects_values_outside_range(
    app,
    client,
    project,
    admin_headers,
    progress,
):
    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': progress,
        'status': '在编',
    }, headers=admin_headers)

    assert response.status_code == 400
    assert response.get_json()['success'] is False
    with app.app_context():
        stored = db.session.get(Project, project)
        assert stored.progress == 50
        assert stored.status == '在编'


def test_admin_can_disable_and_resume_project(
    app,
    client,
    project,
    admin_headers,
):
    disabled = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 50,
        'status': '停用',
        'remark': '暂时停止使用',
    }, headers=admin_headers)
    assert disabled.status_code == 200
    assert disabled.get_json()['status'] == '停用'

    resumed = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 50,
        'status': '在编',
        'remark': '恢复开发',
    }, headers=admin_headers)
    assert resumed.status_code == 200
    assert resumed.get_json()['status'] == '在编'

    with app.app_context():
        statuses = [
            row.status
            for row in ProjectLog.query
            .filter_by(project_id=project)
            .order_by(ProjectLog.id.asc())
        ]
        assert statuses == ['停用', '在编']


@pytest.mark.parametrize('status', ['在编', '使用', '大修', '停用'])
def test_admin_can_manually_select_each_lifecycle_status(
    app,
    client,
    project,
    admin_headers,
    status,
):
    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 50,
        'status': status,
        'remark': f'切换为{status}',
    }, headers=admin_headers)

    assert response.status_code == 200
    assert response.get_json()['status'] == status
    with app.app_context():
        assert db.session.get(Project, project).status == status


def test_update_progress_rejects_unknown_manual_status(
    app,
    client,
    project,
    admin_headers,
):
    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 50,
        'status': '任意状态',
    }, headers=admin_headers)

    assert response.status_code == 400
    with app.app_context():
        stored = db.session.get(Project, project)
        assert stored.progress == 50
        assert stored.status == '在编'


def _seed_user_and_project(status='在编', progress=0):
    db.session.add(User(
        id=1,
        username='display-tester',
        email='display-tester@example.invalid',
        password='test',
    ))
    item = Project(
        name='展示状态测试',
        created_by=1,
        status=status,
        progress=progress,
    )
    db.session.add(item)
    db.session.commit()
    return item.id


def _project_from(response, project_id):
    payload = response.get_json()
    return next(row for row in payload['data'] if row['id'] == project_id)


def test_project_status_uses_log_time_then_id(app, client):
    with app.app_context():
        project_id = _seed_user_and_project(status='使用', progress=100)
        # Insert the newer timestamp first so its id is lower.  Timestamp, not id,
        # must decide which log is authoritative.
        db.session.add(ProjectLog(
            developer_id=1,
            project_id=project_id,
            status='大修',
            remark='返厂大修',
            log_time=datetime(2024, 2, 1),
        ))
        db.session.commit()
        db.session.add(ProjectLog(
            developer_id=1,
            project_id=project_id,
            status='使用',
            remark='补录旧日志',
            log_time=datetime(2024, 1, 1),
        ))
        db.session.commit()

    public_project = _project_from(
        client.get('/public/projects'),
        project_id,
    )
    admin_project = _project_from(
        client.get('/admin/get_projects'),
        project_id,
    )
    user_project = _project_from(
        client.get('/user/get_my_projects?user_id=1'),
        project_id,
    )

    assert public_project['status'] == '大修'
    assert admin_project['status'] == '大修'
    assert user_project['status'] == '大修'
    assert [row['status'] for row in public_project['logs']] == ['大修', '使用']


def test_same_log_time_uses_larger_id_as_tie_breaker(app, client):
    with app.app_context():
        project_id = _seed_user_and_project()
        same_time = datetime(2024, 1, 1)
        db.session.add_all([
            ProjectLog(
                developer_id=1,
                project_id=project_id,
                status='在编',
                log_time=same_time,
            ),
            ProjectLog(
                developer_id=1,
                project_id=project_id,
                status='停用',
                log_time=same_time,
            ),
        ])
        db.session.commit()

    project_row = _project_from(client.get('/public/projects'), project_id)
    assert project_row['status'] == '停用'
    assert [row['status'] for row in project_row['logs']] == ['停用', '在编']


@pytest.mark.parametrize(
    ('legacy_status', 'expected'),
    [
        ('新编', '在编'),
        ('开发中', '在编'),
        ('测试中', '在编'),
        ('已完成', '使用'),
        ('结束', '使用'),
        ('已取消', '停用'),
    ],
)
def test_latest_legacy_log_status_is_normalized(
    app,
    client,
    legacy_status,
    expected,
):
    with app.app_context():
        project_id = _seed_user_and_project(status='使用', progress=100)
        db.session.add(ProjectLog(
            developer_id=1,
            project_id=project_id,
            status=legacy_status,
            log_time=datetime(2024, 2, 1),
        ))
        db.session.commit()

    project_row = _project_from(client.get('/public/projects'), project_id)
    assert project_row['status'] == expected


def test_project_without_logs_uses_stored_status_not_progress(app, client):
    with app.app_context():
        project_id = _seed_user_and_project(status='大修', progress=100)

    project_row = _project_from(client.get('/public/projects'), project_id)
    assert project_row['status'] == '大修'


def test_project_without_logs_normalizes_legacy_stored_status(app, client):
    with app.app_context():
        project_id = _seed_user_and_project(status='开发中', progress=100)

    project_row = _project_from(client.get('/public/projects'), project_id)
    assert project_row['status'] == '在编'


def test_explicit_status_without_remark_still_creates_authoritative_log(
    app,
    client,
    project,
    admin_headers,
):
    response = client.post('/admin/update_progress', json={
        'project_id': project,
        'progress': 100,
        'status': '停用',
    }, headers=admin_headers)

    assert response.status_code == 200
    with app.app_context():
        log = ProjectLog.query.filter_by(project_id=project).one()
        assert log.status == '停用'
        assert log.remark == '状态更新'
