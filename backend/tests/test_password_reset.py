from app import db
from app.models.models import User
from app.passwords import PasswordResetDeliveryError, verify_password


def _create_user(app, *, username='worker', email='worker@example.com', password='old-secret'):
    with app.app_context():
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _request_token(client, email='worker@example.com', audience='user'):
    response = client.post('/user/password-reset/request', json={
        'email': email,
        'audience': audience,
    })
    assert response.status_code == 200
    return response.json['reset_token']


def test_password_reset_changes_password_and_invalidates_used_link(client, app):
    user_id = _create_user(app)
    token = _request_token(client)

    response = client.post('/user/password-reset/confirm', json={
        'token': token,
        'password': 'new-secret',
        'confirm_password': 'new-secret',
    })

    assert response.status_code == 200
    assert response.json['message'] == '密码已重置，请使用新密码登录'
    assert response.json['username'] == 'worker'
    with app.app_context():
        stored = db.session.get(User, user_id).password
        assert stored != 'new-secret'
        assert verify_password(stored, 'new-secret') is True
        assert verify_password(stored, 'old-secret') is False

    reused = client.post('/user/password-reset/confirm', json={
        'token': token,
        'password': 'another-secret',
        'confirm_password': 'another-secret',
    })
    assert reused.status_code == 400
    assert '已使用' in reused.json['message']


def test_reset_password_works_for_both_login_surfaces(client, app):
    _create_user(app)
    token = _request_token(client, audience='admin')
    reset = client.post('/user/password-reset/confirm', json={
        'token': token,
        'password': 'new-secret',
        'confirm_password': 'new-secret',
    })
    assert reset.json['audience'] == 'admin'

    user_login = client.post('/user/login', json={
        'username': 'worker',
        'password': 'new-secret',
        'employment_type': 'employee',
    })
    admin_login = client.post('/admin/login', json={
        'username': 'worker',
        'password': 'new-secret',
    })
    assert user_login.status_code == 200
    assert admin_login.status_code == 200


def test_unknown_email_uses_generic_response_without_token(client):
    response = client.post('/user/password-reset/request', json={
        'email': 'missing@example.com',
        'audience': 'user',
    })
    assert response.status_code == 200
    assert response.json == {
        'message': '如果该邮箱已注册，重置邮件会在几分钟内发送',
    }


def test_password_reset_rejects_invalid_inputs(client, app):
    _create_user(app)
    invalid_email = client.post('/user/password-reset/request', json={'email': 'invalid'})
    assert invalid_email.status_code == 400

    token = _request_token(client)
    short = client.post('/user/password-reset/confirm', json={
        'token': token,
        'password': '123',
        'confirm_password': '123',
    })
    mismatch = client.post('/user/password-reset/confirm', json={
        'token': token,
        'password': 'new-secret',
        'confirm_password': 'different',
    })
    tampered = client.post('/user/password-reset/confirm', json={
        'token': f'{token}broken',
        'password': 'new-secret',
        'confirm_password': 'new-secret',
    })
    assert short.status_code == 400
    assert mismatch.status_code == 400
    assert tampered.status_code == 400


def test_password_reset_reports_missing_delivery_configuration(client, app):
    with app.app_context():
        app.config.update(
            PASSWORD_RESET_EXPOSE_TOKEN=False,
            PASSWORD_RESET_SMTP_HOST=None,
            PASSWORD_RESET_EMAIL_FROM=None,
        )
    response = client.post('/user/password-reset/request', json={
        'email': 'worker@example.com',
        'audience': 'user',
    })
    assert response.status_code == 503
    assert '尚未配置' in response.json['message']


def test_mail_delivery_failure_does_not_reveal_registered_email(client, app, monkeypatch):
    _create_user(app)
    with app.app_context():
        app.config.update(
            PASSWORD_RESET_EXPOSE_TOKEN=False,
            PASSWORD_RESET_SMTP_HOST='smtp.example.com',
            PASSWORD_RESET_EMAIL_FROM='aitools@example.com',
        )

    def fail_delivery(*_args, **_kwargs):
        raise PasswordResetDeliveryError('delivery failed')

    monkeypatch.setattr('app.routes.user.send_password_reset_email', fail_delivery)
    registered = client.post('/user/password-reset/request', json={
        'email': 'worker@example.com',
        'audience': 'user',
    })
    missing = client.post('/user/password-reset/request', json={
        'email': 'missing@example.com',
        'audience': 'user',
    })
    assert registered.status_code == 200
    assert missing.status_code == 200
    assert registered.json == missing.json


def test_registration_hashes_password_and_legacy_plaintext_login_still_works(client, app):
    registration = client.post('/user/register', json={
        'username': 'new-user',
        'email': 'new-user@example.com',
        'password': 'secret1',
    })
    assert registration.status_code == 201
    with app.app_context():
        stored = User.query.filter_by(username='new-user').one().password
        assert stored != 'secret1'
        assert verify_password(stored, 'secret1') is True

    _create_user(
        app,
        username='legacy-user',
        email='legacy-user@example.com',
        password='legacy-secret',
    )
    legacy_login = client.post('/admin/login', json={
        'username': 'legacy-user',
        'password': 'legacy-secret',
    })
    assert legacy_login.status_code == 200
