import os
import secrets
import subprocess
import time
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.learning.errors import LearningForbiddenError, LearningUnauthorizedError


_TOKEN_SALT = 'rpa-learning-v1'
_TOKEN_PURPOSE = 'learning'
_LOGIN_SURFACES = ('user', 'admin')
_PERSISTED_SECRET_LENGTH = 64
_SECRET_RETRY_COUNT = 25
_SECRET_RETRY_DELAY_SECONDS = 0.02


def _is_complete_persisted_secret(value):
    return (
        len(value) == _PERSISTED_SECRET_LENGTH
        and all(character.isalnum() or character in '-_' for character in value)
    )


def _read_complete_persisted_secret(secret_file):
    try:
        with open(secret_file, encoding='utf-8') as handle:
            secret = handle.read().strip()
    except (FileNotFoundError, OSError):
        return None
    return secret if _is_complete_persisted_secret(secret) else None


def _harden_secret_permissions(secret_file):
    try:
        if os.name == 'posix':
            os.chmod(secret_file, 0o600)
            return
        if os.name == 'nt':
            identity = subprocess.run(
                ['whoami'], capture_output=True, text=True, check=False
            )
            account = identity.stdout.strip()
            if identity.returncode != 0 or not account:
                raise OSError('current account unavailable')
            for arguments in (
                ['/reset'],
                ['/inheritance:r'],
                ['/grant:r', f'{account}:(F)'],
            ):
                result = subprocess.run(
                    ['icacls', secret_file, *arguments],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    raise OSError('icacls failed')
            return
    except OSError as error:
        raise LearningUnauthorizedError('Learning token secret is unavailable') from error

    raise LearningUnauthorizedError('Learning token secret permissions cannot be enforced')


def _load_or_create_persisted_secret(secret_file):
    secret_file = os.fspath(secret_file)
    secret_directory = os.path.dirname(os.path.abspath(secret_file))
    lock_file = secret_file + '.lock'
    try:
        os.makedirs(secret_directory, exist_ok=True)
    except OSError as error:
        raise LearningUnauthorizedError('Learning token secret is unavailable') from error

    for _ in range(_SECRET_RETRY_COUNT):
        secret = _read_complete_persisted_secret(secret_file)
        if secret:
            _harden_secret_permissions(secret_file)
            return secret
        if os.path.exists(secret_file):
            time.sleep(_SECRET_RETRY_DELAY_SECONDS)
            continue

        try:
            lock_descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            time.sleep(_SECRET_RETRY_DELAY_SECONDS)
            continue
        except OSError as error:
            raise LearningUnauthorizedError('Learning token secret is unavailable') from error

        temporary_file = None
        try:
            os.close(lock_descriptor)
            secret = _read_complete_persisted_secret(secret_file)
            if secret:
                _harden_secret_permissions(secret_file)
                return secret
            if os.path.exists(secret_file):
                continue

            secret = secrets.token_urlsafe(48)
            temporary_file = os.path.join(
                secret_directory,
                f'.{os.path.basename(secret_file)}.{os.getpid()}.{secrets.token_hex(8)}.tmp',
            )
            descriptor = os.open(temporary_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(secret)
                handle.flush()
                os.fsync(handle.fileno())
            _harden_secret_permissions(temporary_file)
            if os.path.exists(secret_file):
                continue
            os.replace(temporary_file, secret_file)
            temporary_file = None
            _harden_secret_permissions(secret_file)
            return secret
        except OSError as error:
            raise LearningUnauthorizedError('Learning token secret is unavailable') from error
        finally:
            if temporary_file:
                try:
                    os.remove(temporary_file)
                except FileNotFoundError:
                    pass
            try:
                os.remove(lock_file)
            except FileNotFoundError:
                pass

    raise LearningUnauthorizedError('Learning token secret is unavailable')


def ensure_learning_token_secret(app):
    secret = app.config.get('LEARNING_TOKEN_SECRET')
    if secret:
        return str(secret)

    secret = _load_or_create_persisted_secret(app.config['LEARNING_TOKEN_SECRET_FILE'])
    app.config['LEARNING_TOKEN_SECRET'] = secret
    return secret


def _serializer():
    return URLSafeTimedSerializer(
        ensure_learning_token_secret(current_app), salt=_TOKEN_SALT
    )


def _validate_login_surface(login_surface):
    if login_surface not in _LOGIN_SURFACES:
        raise LearningUnauthorizedError('Invalid learning token')
    return login_surface


def issue_learning_token(user_id, login_surface):
    return _serializer().dumps({
        'user_id': int(user_id),
        'purpose': _TOKEN_PURPOSE,
        'login_surface': _validate_login_surface(login_surface),
    })


def decode_learning_token(token):
    if not token:
        raise LearningUnauthorizedError('Missing learning token')
    try:
        payload = _serializer().loads(
            token,
            max_age=current_app.config['LEARNING_TOKEN_MAX_AGE_SECONDS'],
        )
    except (BadSignature, SignatureExpired):
        raise LearningUnauthorizedError('Invalid or expired learning token')

    if not isinstance(payload, dict) or payload.get('purpose') != _TOKEN_PURPOSE:
        raise LearningUnauthorizedError('Invalid learning token')
    try:
        user_id = int(payload['user_id'])
    except (KeyError, TypeError, ValueError):
        raise LearningUnauthorizedError('Invalid learning token')
    if isinstance(payload['user_id'], bool):
        raise LearningUnauthorizedError('Invalid learning token')
    return user_id, _validate_login_surface(payload.get('login_surface'))


def learning_auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not token:
            raise LearningUnauthorizedError('Missing learning token')
        g.learning_user_id, g.learning_login_surface = decode_learning_token(token)
        return view(*args, **kwargs)

    return wrapped


def learning_surface_required(*login_surfaces):
    invalid = set(login_surfaces) - set(_LOGIN_SURFACES)
    if invalid:
        raise ValueError('Unknown learning login surface')

    def decorator(view):
        @learning_auth_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.learning_login_surface not in login_surfaces:
                raise LearningForbiddenError('Learning login surface is not permitted')
            return view(*args, **kwargs)

        return wrapped

    return decorator


def learning_roles_required(*roles, login_surface=None):
    def decorator(view):
        @learning_auth_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            from app.learning.roles import get_role

            if login_surface is not None and g.learning_login_surface != login_surface:
                raise LearningForbiddenError('Learning login surface is not permitted')
            if get_role(g.learning_user_id) not in roles:
                raise LearningForbiddenError('Learning role is not permitted')
            return view(*args, **kwargs)

        return wrapped

    return decorator


def learning_login_fields(user_id, login_surface):
    from app.learning.roles import get_role

    return {
        'learning_token': issue_learning_token(user_id, login_surface),
        'learning_role': get_role(user_id),
    }
