import hashlib
import hmac
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app.learning.auth import ensure_learning_token_secret


_RESET_TOKEN_SALT = 'rpa-password-reset-v1'
_RESET_TOKEN_PURPOSE = 'password-reset'
_HASH_PREFIXES = ('scrypt:', 'pbkdf2:')
_VALID_AUDIENCES = ('user', 'admin')


class PasswordResetError(Exception):
    pass


class PasswordResetDeliveryError(PasswordResetError):
    pass


def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored_password, candidate_password):
    """Accept new Werkzeug hashes while keeping historical plaintext accounts usable."""
    if not stored_password or not candidate_password:
        return False
    if stored_password.startswith(_HASH_PREFIXES):
        try:
            return check_password_hash(stored_password, candidate_password)
        except ValueError:
            return False
    return hmac.compare_digest(stored_password, candidate_password)


def _password_fingerprint(stored_password):
    return hashlib.sha256(stored_password.encode('utf-8')).hexdigest()


def _serializer():
    secret = (
        current_app.config.get('PASSWORD_RESET_SECRET')
        or ensure_learning_token_secret(current_app)
    )
    return URLSafeTimedSerializer(secret, salt=_RESET_TOKEN_SALT)


def issue_password_reset_token(user, audience='user'):
    if audience not in _VALID_AUDIENCES:
        raise PasswordResetError('无效的登录入口')
    return _serializer().dumps({
        'purpose': _RESET_TOKEN_PURPOSE,
        'user_id': int(user.id),
        'password_fingerprint': _password_fingerprint(user.password),
        'audience': audience,
    })


def load_password_reset_user(token):
    from app import db
    from app.models.models import User

    try:
        payload = _serializer().loads(
            token,
            max_age=current_app.config['PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS'],
        )
    except (BadSignature, SignatureExpired) as error:
        raise PasswordResetError('重置链接无效或已过期，请重新申请') from error

    if not isinstance(payload, dict) or payload.get('purpose') != _RESET_TOKEN_PURPOSE:
        raise PasswordResetError('重置链接无效或已过期，请重新申请')

    try:
        user_id = int(payload['user_id'])
    except (KeyError, TypeError, ValueError) as error:
        raise PasswordResetError('重置链接无效或已过期，请重新申请') from error

    user = db.session.get(User, user_id)
    fingerprint = payload.get('password_fingerprint')
    if (
        not user
        or not isinstance(fingerprint, str)
        or not hmac.compare_digest(fingerprint, _password_fingerprint(user.password))
    ):
        raise PasswordResetError('重置链接无效或已使用，请重新申请')

    audience = payload.get('audience')
    if audience not in _VALID_AUDIENCES:
        audience = 'user'
    return user, audience


def build_password_reset_url(token, audience='user'):
    base_url = current_app.config['PASSWORD_RESET_FRONTEND_URL'].rstrip('/')
    path = '/admin-forgot-password' if audience == 'admin' else '/forgot-password'
    return f'{base_url}{path}?{urlencode({"token": token})}'


def password_reset_delivery_configured():
    return bool(
        current_app.config.get('PASSWORD_RESET_EXPOSE_TOKEN')
        or (
            current_app.config.get('PASSWORD_RESET_SMTP_HOST')
            and current_app.config.get('PASSWORD_RESET_EMAIL_FROM')
        )
    )


def send_password_reset_email(user, reset_url):
    host = current_app.config.get('PASSWORD_RESET_SMTP_HOST')
    sender = current_app.config.get('PASSWORD_RESET_EMAIL_FROM')
    if not host or not sender:
        raise PasswordResetDeliveryError('密码找回邮件服务尚未配置')

    message = EmailMessage()
    message['Subject'] = 'AI Tools web 密码重置'
    message['From'] = sender
    message['To'] = user.email
    message.set_content(
        f'''您好，{user.username}：

我们收到了 AI Tools web 的密码重置申请。

请在 {current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS"] // 60} 分钟内打开下面的链接并设置新密码：
{reset_url}

如果不是您本人操作，请忽略本邮件，原密码不会改变。
'''
    )

    port = current_app.config['PASSWORD_RESET_SMTP_PORT']
    timeout = current_app.config['PASSWORD_RESET_SMTP_TIMEOUT_SECONDS']
    username = current_app.config.get('PASSWORD_RESET_SMTP_USERNAME')
    password = current_app.config.get('PASSWORD_RESET_SMTP_PASSWORD')
    use_ssl = current_app.config.get('PASSWORD_RESET_SMTP_USE_SSL')
    use_tls = current_app.config.get('PASSWORD_RESET_SMTP_USE_TLS')

    try:
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_class(host, port, timeout=timeout) as smtp:
            if use_tls and not use_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if username:
                smtp.login(username, password or '')
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise PasswordResetDeliveryError('密码重置邮件发送失败') from error
