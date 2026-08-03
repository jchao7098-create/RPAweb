from datetime import datetime

import pytest

from app import db
from app.learning.auth import issue_learning_token
from app.models.learning import UserRole
from app.models.models import Asset, Project, ProjectLog, Requirement, User


def _user(username):
    user = User(
        username=username,
        email=f'{username}@example.com',
        password='not-used-in-route-tests',
    )
    db.session.add(user)
    db.session.flush()
    return user


def _requirement(user, *, title='客服部-日报', status='待审核'):
    requirement = Requirement(
        user_id=user.id,
        title=title,
        description='自动生成日报',
        department='客服部',
        requester=username_for(user),
        feedback_time=datetime(2026, 7, 28, 9, 0, 0),
        priority='中',
        expected_finish_time=datetime(2026, 8, 15, 18, 0, 0),
        platform='浏览器',
        operation_link='https://example.com',
        account='tester',
        password='original-secret',
        attachments=[],
        status=status,
    )
    db.session.add(requirement)
    db.session.flush()
    return requirement


def username_for(user):
    return user.username


def _authorization(user, surface='user'):
    return {'Authorization': f'Bearer {issue_learning_token(user.id, surface)}'}


def _seed_development_records(actor_role='employee'):
    actor = _user(f'progress-{actor_role}-actor')
    other = _user(f'progress-{actor_role}-other')
    db.session.add(UserRole(
        user_id=actor.id,
        role=actor_role,
        assigned_by_user_id=actor.id,
    ))

    own_project = Project(
        name='客服部-本人项目',
        description='本人项目',
        created_by=actor.id,
        status='在编',
        progress=20,
    )
    other_project = Project(
        name='项目部-他人项目',
        description='他人项目',
        created_by=other.id,
        status='在编',
        progress=40,
    )
    own_asset = Asset(
        user_id=actor.id,
        asset_type='skill',
        name='本人 Skill',
        department='客服部',
        submitter=actor.username,
        file_name='owner.md',
        status='已通过',
        lifecycle_status='在编',
        progress=30,
    )
    other_asset = Asset(
        user_id=other.id,
        asset_type='python_plugin',
        name='他人 Python',
        department='项目部',
        submitter=other.username,
        file_name='other.py',
        status='已通过',
        lifecycle_status='使用',
        progress=100,
    )
    rejected_asset = Asset(
        user_id=actor.id,
        asset_type='skill',
        name='本人拒绝资产',
        department='客服部',
        submitter=actor.username,
        file_name='rejected.md',
        status='已拒绝',
        lifecycle_status='在编',
        progress=0,
        reject_reason='private reason',
    )
    pending_asset = Asset(
        user_id=actor.id,
        asset_type='skill',
        name='本人待审核资产',
        department='客服部',
        submitter=actor.username,
        file_name='pending.md',
        status='待审核',
        lifecycle_status='在编',
        progress=0,
    )
    db.session.add_all([
        own_project,
        other_project,
        own_asset,
        other_asset,
        rejected_asset,
        pending_asset,
    ])
    db.session.commit()
    return {
        'actor_id': actor.id,
        'other_id': other.id,
        'user_headers': _authorization(actor),
        'admin_headers': _authorization(actor, 'admin'),
        'other_admin_headers': _authorization(other, 'admin'),
        'own_project_id': own_project.id,
        'other_project_id': other_project.id,
        'own_asset_id': own_asset.id,
        'other_asset_id': other_asset.id,
        'rejected_asset_id': rejected_asset.id,
        'pending_asset_id': pending_asset.id,
    }


def test_merged_management_routes_require_user_login_and_scope_records(app, client):
    with app.app_context():
        owner = _user('owner')
        other = _user('other')
        own_requirement = _requirement(owner, title='本人需求')
        _requirement(other, title='他人需求')
        db.session.commit()
        owner_headers = _authorization(owner)
        admin_headers = _authorization(owner, 'admin')
        own_requirement_id = own_requirement.id

    assert client.get('/user/manage/requirements').status_code == 401
    assert client.get('/user/manage/requirements', headers=admin_headers).status_code == 403

    response = client.get('/user/manage/requirements', headers=owner_headers)
    assert response.status_code == 200
    assert [item['id'] for item in response.get_json()] == [own_requirement_id]


def test_my_rpa_uploads_require_login_and_ignore_forged_user_ids(app, client):
    with app.app_context():
        owner = _user('upload-owner')
        other = _user('upload-other')
        older = _requirement(owner, title='本人较早提交')
        newer = _requirement(owner, title='本人最新提交', status='已拒绝')
        foreign = _requirement(other, title='他人提交')
        older.created_at = datetime(2026, 7, 29, 9, 0, 0)
        newer.created_at = datetime(2026, 7, 30, 9, 0, 0)
        foreign.created_at = datetime(2026, 7, 31, 9, 0, 0)
        db.session.commit()
        headers = _authorization(owner)
        owner_id = owner.id
        other_id = other.id

    assert client.get(
        '/user/get_my_requirements',
        query_string={'user_id': owner_id},
    ).status_code == 401
    assert client.get(
        '/user/get_my_requirements',
        query_string={'user_id': other_id},
        headers=headers,
    ).status_code == 403

    response = client.get(
        '/user/get_my_requirements',
        query_string={'user_id': owner_id},
        headers=headers,
    )
    assert response.status_code == 200
    assert [item['title'] for item in response.get_json()['data']] == [
        '本人最新提交',
        '本人较早提交',
    ]
    assert all('password' not in item and 'credentials' not in item
               for item in response.get_json()['data'])


def test_rpa_submission_is_owned_by_the_signed_in_user(app, client):
    with app.app_context():
        owner = _user('submit-owner')
        other = _user('submit-other')
        db.session.commit()
        headers = _authorization(owner)
        owner_id = owner.id
        other_id = other.id

    payload = {
        'user_id': other_id,
        'title': '客服部-自动日报',
        'description': '生成日报',
        'department': '客服部',
        'requester': '提交人',
        'priority': '中',
        'feedback_time': '2026-07-30 09:00:00',
        'expected_finish_time': '2026-08-15 18:00:00',
    }
    assert client.post('/user/submit_requirement', data=payload).status_code == 401
    assert client.post(
        '/user/submit_requirement',
        data=payload,
        headers=headers,
    ).status_code == 403

    payload['user_id'] = owner_id
    response = client.post(
        '/user/submit_requirement',
        data=payload,
        headers=headers,
    )
    assert response.status_code == 201
    with app.app_context():
        created = Requirement.query.filter_by(title='客服部-自动日报').one()
        assert created.user_id == owner_id


def test_user_can_update_own_unapproved_requirement_without_schema_changes(app, client):
    with app.app_context():
        owner = _user('owner')
        other = _user('other')
        editable = _requirement(owner, status='已拒绝')
        locked = _requirement(owner, title='已通过需求', status='已通过')
        foreign = _requirement(other, title='他人需求')
        db.session.commit()
        headers = _authorization(owner)
        owner_id = owner.id
        editable_id = editable.id
        locked_id = locked.id
        foreign_id = foreign.id

    payload = {
        'user_id': owner_id,
        'title': '客服部-日报修订',
        'description': '修订后的自动日报需求',
        'department': '客服部',
        'requester': 'owner',
        'priority': '高',
        'feedback_time': '2026-07-28 10:00:00',
        'expected_finish_time': '2026-08-10 18:00:00',
        'platform': '浏览器',
        'operation_link': 'https://example.com/new',
        'account': 'tester-new',
        'password': '',
    }
    assert client.patch(
        f'/user/requirements/{editable_id}',
        json=payload,
    ).status_code == 401

    response = client.patch(
        f'/user/requirements/{editable_id}',
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['status'] == '待审核'
    assert response.get_json()['data']['editable'] is True

    with app.app_context():
        updated = db.session.get(Requirement, editable_id)
        assert updated.title == '客服部-日报修订'
        assert updated.priority == '高'
        assert updated.password == 'original-secret'

    assert client.patch(
        f'/user/requirements/{foreign_id}',
        json=payload,
        headers=headers,
    ).status_code == 404
    assert client.patch(
        f'/user/requirements/{locked_id}',
        json=payload,
        headers=headers,
    ).status_code == 409


def test_self_review_can_approve_once_and_only_creates_one_project(app, client):
    with app.app_context():
        owner = _user('owner')
        other = _user('other')
        requirement = _requirement(owner)
        foreign = _requirement(other, title='他人需求')
        db.session.commit()
        headers = _authorization(owner)
        owner_id = owner.id
        requirement_id = requirement.id
        foreign_id = foreign.id

    response = client.post(
        '/user/manage/requirements/approve',
        json={'id': requirement_id},
        headers=headers,
    )
    assert response.status_code == 200

    duplicate = client.post(
        '/user/manage/requirements/approve',
        json={'id': requirement_id},
        headers=headers,
    )
    assert duplicate.status_code == 409

    foreign_response = client.post(
        '/user/manage/requirements/approve',
        json={'id': foreign_id},
        headers=headers,
    )
    assert foreign_response.status_code == 404
    foreign_reject_response = client.post(
        '/user/manage/requirements/reject',
        json={'id': foreign_id, 'reason': '不得审核他人需求'},
        headers=headers,
    )
    assert foreign_reject_response.status_code == 404

    with app.app_context():
        assert Project.query.filter_by(created_by=owner_id).count() == 1


def test_regular_user_can_view_company_progress_but_only_update_own_records(app, client):
    with app.app_context():
        records = _seed_development_records()

    assert client.post(
        '/user/manage/update_progress',
        json={'project_id': records['other_project_id'], 'progress': 50},
    ).status_code == 401
    assert client.post(
        '/user/manage/assets/progress',
        json={'id': records['other_asset_id'], 'progress': 50},
    ).status_code == 401

    projects_response = client.get(
        '/user/manage/get_projects?scope=all',
        headers=records['user_headers'],
    )
    assert projects_response.status_code == 200
    projects = projects_response.get_json()['data']
    ownership = {item['id']: item['is_owned'] for item in projects}
    assert ownership[records['own_project_id']] is True
    assert ownership[records['other_project_id']] is False

    assets_response = client.get(
        '/user/manage/assets?scope=all',
        headers=records['user_headers'],
    )
    assert assets_response.status_code == 200
    assets = assets_response.get_json()['data']
    assert {item['id'] for item in assets} == {
        records['own_asset_id'],
        records['other_asset_id'],
    }
    assert all('reject_reason' not in item for item in assets)
    assert {item['id']: item['is_owned'] for item in assets} == {
        records['own_asset_id']: True,
        records['other_asset_id']: False,
    }

    own_project_update = client.post(
        '/user/manage/update_progress',
        json={
            'project_id': records['own_project_id'],
            'progress': 35,
            'status': '大修',
            'remark': '本人更新',
        },
        headers=records['user_headers'],
    )
    assert own_project_update.status_code == 200
    assert own_project_update.get_json()['progress'] == 35

    foreign_project_update = client.post(
        '/user/manage/update_progress',
        json={
            'project_id': records['other_project_id'],
            'progress': 55,
            'status': '大修',
            'remark': '跨所有者更新',
        },
        headers=records['user_headers'],
    )
    assert foreign_project_update.status_code == 403

    own_asset_update = client.post(
        '/user/manage/assets/progress',
        json={
            'id': records['own_asset_id'],
            'progress': 65,
            'lifecycle_status': '大修',
        },
        headers=records['user_headers'],
    )
    assert own_asset_update.status_code == 200
    assert own_asset_update.get_json()['progress'] == 65

    foreign_asset_update = client.post(
        '/user/manage/assets/progress',
        json={
            'id': records['other_asset_id'],
            'progress': 65,
            'lifecycle_status': '大修',
        },
        headers=records['user_headers'],
    )
    assert foreign_asset_update.status_code == 403

    pending_asset_update = client.post(
        '/user/manage/assets/progress',
        json={
            'id': records['pending_asset_id'],
            'progress': 30,
            'lifecycle_status': '在编',
        },
        headers=records['user_headers'],
    )
    assert pending_asset_update.status_code == 409
    rejected_asset_update = client.post(
        '/user/manage/assets/progress',
        json={
            'id': records['rejected_asset_id'],
            'progress': 30,
            'lifecycle_status': '在编',
        },
        headers=records['user_headers'],
    )
    assert rejected_asset_update.status_code == 409
    assert client.post(
        '/user/manage/assets/approve',
        json={'id': records['other_asset_id']},
        headers=records['user_headers'],
    ).status_code == 404
    assert client.post(
        '/user/manage/assets/reject',
        json={'id': records['other_asset_id'], 'reason': '不得审核他人资产'},
        headers=records['user_headers'],
    ).status_code == 404

    with app.app_context():
        own_project = db.session.get(Project, records['own_project_id'])
        other_project = db.session.get(Project, records['other_project_id'])
        own_asset = db.session.get(Asset, records['own_asset_id'])
        other_asset = db.session.get(Asset, records['other_asset_id'])
        unchanged_rejected_asset = db.session.get(Asset, records['rejected_asset_id'])
        unchanged_pending_asset = db.session.get(Asset, records['pending_asset_id'])
        own_project_log = (
            ProjectLog.query
            .filter_by(project_id=records['own_project_id'])
            .order_by(ProjectLog.id.desc())
            .first()
        )
        assert own_project.progress == 35
        assert own_project.status == '大修'
        assert other_project.progress == 40
        assert other_project.status == '在编'
        assert own_asset.progress == 65
        assert own_asset.lifecycle_status == '大修'
        assert other_asset.progress == 100
        assert other_asset.lifecycle_status == '使用'
        assert unchanged_rejected_asset.progress == 0
        assert unchanged_rejected_asset.lifecycle_status == '在编'
        assert unchanged_pending_asset.progress == 0
        assert unchanged_pending_asset.lifecycle_status == '在编'
        assert own_project_log is not None
        assert own_project_log.developer_id == records['actor_id']
        assert ProjectLog.query.filter_by(
            project_id=records['other_project_id'],
        ).count() == 0


@pytest.mark.parametrize('role', ['hr', 'boss'])
def test_hr_and_boss_can_update_company_progress_from_user_workbench(
    app,
    client,
    role,
):
    with app.app_context():
        records = _seed_development_records(role)

    project_response = client.post(
        '/user/manage/update_progress',
        json={
            'project_id': records['other_project_id'],
            'progress': 55,
            'status': '大修',
            'remark': f'{role} 跨所有者更新',
        },
        headers=records['user_headers'],
    )
    assert project_response.status_code == 200
    assert project_response.get_json()['progress'] == 55
    assert project_response.get_json()['status'] == '大修'

    asset_response = client.post(
        '/user/manage/assets/progress',
        json={
            'id': records['other_asset_id'],
            'progress': 65,
            'lifecycle_status': '大修',
        },
        headers=records['user_headers'],
    )
    assert asset_response.status_code == 200
    assert asset_response.get_json()['progress'] == 65
    assert asset_response.get_json()['lifecycle_status'] == '大修'

    with app.app_context():
        assert db.session.get(Project, records['other_project_id']).progress == 55
        assert db.session.get(Asset, records['other_asset_id']).progress == 65
        project_log = ProjectLog.query.filter_by(
            project_id=records['other_project_id'],
        ).one()
        assert project_log.developer_id == records['actor_id']


def test_admin_progress_writes_require_admin_role(app, client):
    with app.app_context():
        records = _seed_development_records('boss')

    project_payload = {
        'project_id': records['other_project_id'],
        'progress': 55,
        'status': '大修',
        'remark': '管理员更新',
    }
    asset_payload = {
        'id': records['other_asset_id'],
        'progress': 65,
        'lifecycle_status': '大修',
    }

    assert client.post(
        '/admin/update_progress',
        json=project_payload,
    ).status_code == 401
    assert client.post(
        '/admin/assets/progress',
        json=asset_payload,
    ).status_code == 401
    assert client.post(
        '/admin/update_progress',
        json=project_payload,
        headers=records['other_admin_headers'],
    ).status_code == 403
    assert client.post(
        '/admin/assets/progress',
        json=asset_payload,
        headers=records['other_admin_headers'],
    ).status_code == 403

    project_response = client.post(
        '/admin/update_progress',
        json=project_payload,
        headers=records['admin_headers'],
    )
    asset_response = client.post(
        '/admin/assets/progress',
        json=asset_payload,
        headers=records['admin_headers'],
    )
    assert project_response.status_code == 200
    assert asset_response.status_code == 200

    with app.app_context():
        assert db.session.get(Project, records['other_project_id']).progress == 55
        assert db.session.get(Asset, records['other_asset_id']).progress == 65
        project_log = ProjectLog.query.filter_by(
            project_id=records['other_project_id'],
        ).one()
        assert project_log.developer_id == records['actor_id']
