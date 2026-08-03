import os
import subprocess
import threading
import time

import pytest
from flask import jsonify
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.learning.auth import (
    decode_learning_token,
    ensure_learning_token_secret,
    issue_learning_token,
    learning_roles_required,
)
from app.learning.errors import LearningForbiddenError, LearningUnauthorizedError
from app.learning.time import utc_now
from app.models.models import User
from app.models.learning import UserRole


def test_user_login_returns_learning_token_and_default_role(client, app):
    with app.app_context():
        db.session.add(User(username='worker', email='worker@example.com', password='secret1', created_at=utc_now()))
        db.session.commit()
    response = client.post('/user/login', json={
        'username': 'worker', 'password': 'secret1', 'employment_type': 'employee',
    })
    assert response.status_code == 200
    assert response.json['message'] == '登录成功'
    assert response.json['user_id']
    assert response.json['learning_role'] == 'employee'
    assert response.json['employment_type'] == 'employee'
    assert response.json['learning_token']
    with app.app_context():
        assert UserRole.query.filter_by(
            user_id=response.json['user_id'], role='employee'
        ).count() == 1


def test_admin_login_returns_learning_token(client, app):
    with app.app_context():
        db.session.add(User(username='admin', email='admin@example.com', password='secret1', created_at=utc_now()))
        db.session.commit()
    response = client.post('/admin/login', json={'username': 'admin', 'password': 'secret1'})
    assert response.status_code == 200
    assert response.json['message'] == '登录成功'
    assert response.json['admin_id']
    assert response.json['learning_token']


def test_user_and_admin_login_tokens_preserve_the_login_surface(client, app):
    with app.app_context():
        db.session.add(User(
            username='surface-user',
            email='surface@example.com',
            password='secret1',
            created_at=utc_now(),
        ))
        db.session.commit()

    user_response = client.post('/user/login', json={
        'username': 'surface-user', 'password': 'secret1', 'employment_type': 'employee',
    })
    admin_response = client.post('/admin/login', json={
        'username': 'surface-user', 'password': 'secret1',
    })

    with app.app_context():
        assert decode_learning_token(user_response.json['learning_token']) == (
            user_response.json['user_id'], 'user',
        )
        assert decode_learning_token(admin_response.json['learning_token']) == (
            admin_response.json['admin_id'], 'admin',
        )


@pytest.mark.parametrize('value', [None, '', 'boss'])
def test_user_login_requires_a_valid_employment_type_after_credentials_pass(client, app, value):
    with app.app_context():
        db.session.add(User(
            username='position-required',
            email='position-required@example.com',
            password='secret1',
            created_at=utc_now(),
        ))
        db.session.commit()
    payload = {'username': 'position-required', 'password': 'secret1'}
    if value is not None:
        payload['employment_type'] = value
    response = client.post('/user/login', json=payload)
    assert response.status_code == 422


def test_first_intern_login_can_submit_in_the_current_week(client, app):
    with app.app_context():
        db.session.add(User(
            username='first-intern',
            email='first-intern@example.com',
            password='secret1',
            created_at=utc_now(),
        ))
        db.session.commit()
    login = client.post('/user/login', json={
        'username': 'first-intern',
        'password': 'secret1',
        'employment_type': 'intern',
    })
    profile = client.get('/learning/me', headers={
        'Authorization': f"Bearer {login.json['learning_token']}",
    })
    assert login.status_code == 200
    assert login.json['employment_type'] == 'intern'
    assert profile.json['can_view_learning_report'] is True
    assert profile.json['can_submit_current_week'] is True


def test_fixed_position_mismatch_returns_409_without_changing_role(client, app):
    with app.app_context():
        user = User(
            username='fixed-worker',
            email='fixed-worker@example.com',
            password='secret1',
            created_at=utc_now(),
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role='employee'))
        db.session.commit()
        user_id = user.id
    response = client.post('/user/login', json={
        'username': 'fixed-worker',
        'password': 'secret1',
        'employment_type': 'intern',
    })
    assert response.status_code == 409
    assert '职位已固定' in response.json['message']
    with app.app_context():
        assert db.session.get(UserRole, user_id).role == 'employee'


def test_legacy_token_without_login_surface_is_rejected(client, app):
    with app.app_context():
        legacy = URLSafeTimedSerializer(
            app.config['LEARNING_TOKEN_SECRET'], salt='rpa-learning-v1'
        ).dumps({'user_id': 17, 'purpose': 'learning'})

    response = client.get('/learning/me', headers={
        'Authorization': f'Bearer {legacy}',
    })

    assert response.status_code == 401
    assert response.json == {'error': 'Invalid learning token'}


@pytest.mark.parametrize('path', ['/user/login', '/admin/login'])
def test_login_failure_response_remains_unchanged(client, path):
    response = client.post(path, json={'username': 'absent', 'password': 'secret1'})
    assert response.status_code == 401
    assert response.json == {'message': '账号或密码错误'}


def test_valid_token_authenticates_learning_probe(client, app):
    with app.app_context():
        token = issue_learning_token(42, 'user')
    response = client.get('/learning/me', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    assert response.json['user_id'] == 42
    assert response.json['role'] == 'employee'
    assert response.json['is_current_roster_member'] is False


def test_token_rejects_tampering(client, app):
    with app.app_context():
        db.session.add(User(username='intern', email='intern@example.com', password='secret1', created_at=utc_now()))
        db.session.flush()
        user_id = User.query.filter_by(username='intern').one().id
        db.session.add(UserRole(user_id=user_id, role='intern'))
        db.session.commit()
    response = client.get('/learning/me', headers={'Authorization': 'Bearer broken.token'})
    assert response.status_code == 401
    assert response.json == {'error': 'Invalid or expired learning token'}


@pytest.mark.parametrize('authorization', ['', 'Basic abc', 'Bearer'])
def test_token_rejects_missing_or_malformed_authorization(client, authorization):
    response = client.get('/learning/me', headers={'Authorization': authorization})
    assert response.status_code == 401
    assert response.json == {'error': 'Missing learning token'}


def test_token_rejects_expiry_and_wrong_purpose(client, app):
    with app.app_context():
        expired = issue_learning_token(17, 'user')
        app.config['LEARNING_TOKEN_MAX_AGE_SECONDS'] = -1
    expired_response = client.get('/learning/me', headers={'Authorization': f'Bearer {expired}'})
    assert expired_response.status_code == 401
    assert expired_response.json == {'error': 'Invalid or expired learning token'}

    with app.app_context():
        app.config['LEARNING_TOKEN_MAX_AGE_SECONDS'] = 43200
        forged = URLSafeTimedSerializer(
            app.config['LEARNING_TOKEN_SECRET'], salt='rpa-learning-v1'
        ).dumps({'user_id': 17, 'purpose': 'other'})
    wrong_purpose_response = client.get('/learning/me', headers={'Authorization': f'Bearer {forged}'})
    assert wrong_purpose_response.status_code == 401
    assert wrong_purpose_response.json == {'error': 'Invalid learning token'}


def test_role_check_reads_current_sqlite_role_on_every_request(app):
    @learning_roles_required('boss')
    def boss_probe():
        return jsonify({'ok': True})

    with app.app_context():
        token = issue_learning_token(88, 'user')
        db.session.add(UserRole(user_id=88, role='intern'))
        db.session.commit()
    with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
        with pytest.raises(LearningForbiddenError):
            boss_probe()

    with app.app_context():
        UserRole.query.filter_by(user_id=88).one().role = 'boss'
        db.session.commit()
    with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
        assert boss_probe().json == {'ok': True}


def test_role_denial_uses_learning_blueprint_json_handler(client, app):
    original_view = app.view_functions['learning.me']

    @learning_roles_required('boss')
    def boss_only_me():
        return jsonify({'ok': True})

    app.view_functions['learning.me'] = boss_only_me
    try:
        with app.app_context():
            token = issue_learning_token(99, 'user')
            db.session.add(UserRole(user_id=99, role='intern'))
            db.session.commit()
        response = client.get('/learning/me', headers={'Authorization': f'Bearer {token}'})
    finally:
        app.view_functions['learning.me'] = original_view

    assert response.status_code == 403
    assert response.json == {'error': 'Learning role is not permitted'}


def test_fallback_secret_is_persisted_and_reused(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    app.config.update(
        LEARNING_TOKEN_SECRET=None,
        LEARNING_TOKEN_SECRET_FILE=str(secret_file),
    )
    first = ensure_learning_token_secret(app)
    app.config['LEARNING_TOKEN_SECRET'] = None
    second = ensure_learning_token_secret(app)
    assert first == second
    assert secret_file.read_text(encoding='utf-8') == first


def test_waits_for_complete_secret_when_final_file_is_in_progress(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    secret_file.write_text('', encoding='utf-8')
    app.config.update(LEARNING_TOKEN_SECRET=None, LEARNING_TOKEN_SECRET_FILE=str(secret_file))
    complete_secret = 'a' * 64
    caller_started = threading.Event()
    allow_completion = threading.Event()
    result = {}

    def caller():
        caller_started.set()
        try:
            result['secret'] = ensure_learning_token_secret(app)
        except Exception as error:
            result['error'] = error

    def complete_file():
        allow_completion.wait(timeout=2)
        temporary = tmp_path / 'complete-secret.tmp'
        temporary.write_text(complete_secret, encoding='utf-8')
        os.replace(temporary, secret_file)

    caller_thread = threading.Thread(target=caller)
    writer_thread = threading.Thread(target=complete_file)
    caller_thread.start()
    writer_thread.start()
    assert caller_started.wait(timeout=1)
    time.sleep(0.1)
    allow_completion.set()
    caller_thread.join(timeout=2)
    writer_thread.join(timeout=2)

    assert result == {'secret': complete_secret}


def test_concurrent_secret_callers_converge_on_one_persisted_value(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    app.config.update(LEARNING_TOKEN_SECRET=None, LEARNING_TOKEN_SECRET_FILE=str(secret_file))
    barrier = threading.Barrier(6)
    results = []

    def caller():
        barrier.wait(timeout=2)
        results.append(ensure_learning_token_secret(app))

    threads = [threading.Thread(target=caller) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert len(results) == 6
    assert len(set(results)) == 1
    assert secret_file.read_text(encoding='utf-8') == results[0]


def test_persisted_secret_has_restrictive_permissions(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    app.config.update(LEARNING_TOKEN_SECRET=None, LEARNING_TOKEN_SECRET_FILE=str(secret_file))
    ensure_learning_token_secret(app)

    if os.name == 'posix':
        assert secret_file.stat().st_mode & 0o777 == 0o600
    else:
        acl = subprocess.run(['icacls', str(secret_file)], capture_output=True, text=True, check=False)
        identity = subprocess.run(['whoami'], capture_output=True, text=True, check=False)
        assert acl.returncode == 0
        assert identity.returncode == 0
        assert identity.stdout.strip().lower() in acl.stdout.lower()
        assert '(I)' not in acl.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows ACL behavior')
def test_existing_explicit_windows_grant_is_removed_when_secret_is_reused(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    app.config.update(LEARNING_TOKEN_SECRET=None, LEARNING_TOKEN_SECRET_FILE=str(secret_file))
    ensure_learning_token_secret(app)

    grant = subprocess.run(
        ['icacls', str(secret_file), '/grant', '*S-1-1-0:(R)'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert grant.returncode == 0
    granted_acl = subprocess.run(['icacls', str(secret_file)], capture_output=True, text=True, check=False)
    assert granted_acl.returncode == 0
    assert 'everyone' in granted_acl.stdout.lower() or 's-1-1-0' in granted_acl.stdout.lower()

    app.config['LEARNING_TOKEN_SECRET'] = None
    ensure_learning_token_secret(app)

    acl = subprocess.run(['icacls', str(secret_file)], capture_output=True, text=True, check=False)
    identity = subprocess.run(['whoami'], capture_output=True, text=True, check=False)
    assert acl.returncode == 0
    assert identity.returncode == 0
    ace_lines = []
    for line in acl.stdout.splitlines():
        line = line.strip()
        if line.startswith(str(secret_file)):
            line = line[len(str(secret_file)):].strip()
        if line and 'Successfully processed' not in line:
            ace_lines.append(line)
    assert [line.lower() for line in ace_lines] == [f'{identity.stdout.strip()}:(F)'.lower()]


def test_incomplete_persisted_secret_fails_without_replacing_it(app, tmp_path):
    secret_file = tmp_path / 'learning_token_secret.key'
    secret_file.write_text('incomplete', encoding='utf-8')
    app.config.update(LEARNING_TOKEN_SECRET=None, LEARNING_TOKEN_SECRET_FILE=str(secret_file))

    with pytest.raises(LearningUnauthorizedError, match='unavailable'):
        ensure_learning_token_secret(app)

    assert secret_file.read_text(encoding='utf-8') == 'incomplete'


def test_decode_rejects_missing_token(app):
    with app.app_context(), pytest.raises(LearningUnauthorizedError):
        decode_learning_token('')
