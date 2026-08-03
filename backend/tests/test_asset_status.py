import pytest

from app import db
from app.learning.auth import issue_learning_token
from app.models.learning import UserRole
from app.models.models import Asset, User


def _authorization(user_id, *, surface='user', role='employee'):
    user = db.session.get(User, user_id)
    if user is None:
        db.session.add(User(
            id=user_id,
            username=f'asset-user-{user_id}',
            email=f'asset-user-{user_id}@example.com',
            password='test-only-password',
        ))
    user_role = db.session.get(UserRole, user_id)
    if user_role is None:
        db.session.add(UserRole(user_id=user_id, role=role))
    else:
        user_role.role = role
    db.session.commit()
    token = issue_learning_token(user_id, surface)
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def boss_headers(app):
    with app.app_context():
        return _authorization(1, surface='admin', role='boss')


def _asset(status='已通过', asset_type='skill', user_id=1):
    item = Asset(
        user_id=user_id,
        asset_type=asset_type,
        name=f'{asset_type}-status-test',
        department='测试部',
        submitter='测试人员',
        version='1.0',
        description='原始说明',
        file_name='test.zip',
        status=status,
    )
    db.session.add(item)
    db.session.commit()
    return item.id


def test_admin_can_update_asset_progress_disable_and_restore(app, client, boss_headers):
    with app.app_context():
        asset_id = _asset()

    disabled = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'progress': 60,
        'lifecycle_status': '停用',
    }, headers=boss_headers)
    assert disabled.status_code == 200
    assert disabled.get_json()['lifecycle_status'] == '停用'
    assert disabled.get_json()['progress'] == 60
    public_rows = client.get('/public/assets?asset_type=skill').get_json()['data']
    assert [row['id'] for row in public_rows] == [asset_id]
    assert public_rows[0]['lifecycle_status'] == '停用'
    assert public_rows[0]['progress'] == 60

    restored = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'progress': 100,
        'lifecycle_status': '使用',
    }, headers=boss_headers)
    assert restored.status_code == 200
    assert restored.get_json()['lifecycle_status'] == '使用'
    assert [row['id'] for row in client.get('/public/assets?asset_type=skill').get_json()['data']] == [asset_id]


def test_pending_asset_must_be_reviewed_before_lifecycle_change(app, client, boss_headers):
    with app.app_context():
        asset_id = _asset(status='待审核', asset_type='python_plugin')

    response = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'progress': 20,
        'lifecycle_status': '在编',
    }, headers=boss_headers)
    assert response.status_code == 409

    with app.app_context():
        assert db.session.get(Asset, asset_id).status == '待审核'


def test_asset_progress_endpoint_rejects_unknown_status(app, client, boss_headers):
    with app.app_context():
        asset_id = _asset()

    response = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'progress': 50,
        'lifecycle_status': '已完成',
    }, headers=boss_headers)
    assert response.status_code == 400


def test_asset_progress_uses_automatic_status_mapping(app, client, boss_headers):
    with app.app_context():
        asset_id = _asset(asset_type='python_plugin')

    response = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'progress': 100,
        'lifecycle_status': 'auto',
    }, headers=boss_headers)
    assert response.status_code == 200
    assert response.get_json()['lifecycle_status'] == '使用'


def test_asset_progress_endpoint_requires_progress(app, client, boss_headers):
    with app.app_context():
        asset_id = _asset()

    response = client.post('/admin/assets/progress', json={
        'id': asset_id,
        'lifecycle_status': '在编',
    }, headers=boss_headers)
    assert response.status_code == 400


def test_user_can_edit_own_approved_asset_and_resubmit_for_review(app, client):
    with app.app_context():
        headers = _authorization(7)
        asset_id = _asset(status='已通过', asset_type='skill', user_id=7)
        asset = db.session.get(Asset, asset_id)
        asset.progress = 100
        asset.lifecycle_status = '使用'
        db.session.commit()

    response = client.patch(f'/user/assets/{asset_id}', json={
        'user_id': 7,
        'name': '客服部-工单分类-skill',
        'department': '客服部',
        'submitter': '张三',
        'version': '1.1',
        'description': '修正后的用途与使用说明',
        'file_name': 'ticket-classifier.zip',
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['data']['status'] == '待审核'
    assert response.get_json()['data']['progress'] == 0
    assert response.get_json()['data']['lifecycle_status'] == '在编'

    with app.app_context():
        stored = db.session.get(Asset, asset_id)
        assert stored.name == '客服部-工单分类-skill'
        assert stored.version == '1.1'
        assert stored.status == '待审核'
        assert stored.reject_reason is None
        assert stored.progress == 0
        assert stored.lifecycle_status == '在编'

    assert client.get('/public/assets?asset_type=skill').get_json()['data'] == []


def test_editing_rejected_asset_clears_reason_and_returns_to_pending(app, client):
    with app.app_context():
        headers = _authorization(8)
        asset_id = _asset(status='已拒绝', asset_type='python_plugin', user_id=8)
        asset = db.session.get(Asset, asset_id)
        asset.reject_reason = '文件名不正确'
        db.session.commit()

    response = client.patch(f'/user/assets/{asset_id}', json={
        'user_id': 8,
        'name': '运营部-数据清洗-插件',
        'department': '运营部',
        'submitter': '李四',
        'version': '2.0',
        'description': '支持 Python 3.12，入口函数为 main',
        'file_name': 'data-cleaner.py',
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['data']['status'] == '待审核'
    assert response.get_json()['data']['reject_reason'] is None


def test_user_cannot_edit_another_users_asset(app, client):
    with app.app_context():
        headers = _authorization(10)
        asset_id = _asset(user_id=9)

    response = client.patch(f'/user/assets/{asset_id}', json={
        'user_id': 10,
        'name': '越权修改',
        'department': '测试部',
        'submitter': '测试人员',
        'version': '1.0',
        'description': '越权修改说明',
        'file_name': 'test.zip',
    }, headers=headers)
    assert response.status_code == 404
    with app.app_context():
        assert db.session.get(Asset, asset_id).name == 'skill-status-test'


def test_asset_edit_validates_required_fields_and_extension(app, client):
    with app.app_context():
        headers = _authorization(11)
        asset_id = _asset(asset_type='python_plugin', user_id=11)

    missing_description = client.patch(f'/user/assets/{asset_id}', json={
        'user_id': 11,
        'name': '插件',
        'department': '测试部',
        'submitter': '测试人员',
        'version': '',
        'description': '',
        'file_name': 'plugin.py',
    }, headers=headers)
    invalid_extension = client.patch(f'/user/assets/{asset_id}', json={
        'user_id': 11,
        'name': '插件',
        'department': '测试部',
        'submitter': '测试人员',
        'version': '',
        'description': '说明',
        'file_name': 'plugin.exe',
    }, headers=headers)
    assert missing_description.status_code == 400
    assert invalid_extension.status_code == 400
