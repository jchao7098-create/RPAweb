import os


def _load_local_env():
    """Load backend/.env for local launches without overriding deployment env vars."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(backend_dir, '.env')
    try:
        with open(env_path, encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                if key:
                    os.environ.setdefault(key, value.strip())
    except FileNotFoundError:
        pass


_load_local_env()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


class Config:
    _BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _VAR_DIR = os.path.join(_BACKEND_DIR, 'var')
    SERVE_FRONTEND = _env_bool('SERVE_FRONTEND')
    FRONTEND_DIST_DIR = os.environ.get(
        'FRONTEND_DIST_DIR',
        os.path.join(os.path.dirname(_BACKEND_DIR), 'frontend', 'dist'),
    )

    # RPA 主业务库。连接凭据只能由 backend/.env 或部署环境变量提供，
    # 禁止把数据库密码提交到源代码仓库。
    SQLALCHEMY_DATABASE_URI = os.environ.get('RPA_DATABASE_URI')
    ASSET_DATABASE_REQUIRED_HOST = os.environ.get(
        'ASSET_DATABASE_REQUIRED_HOST',
        '172.16.50.20',
    )
    ASSET_DATABASE_REQUIRED_PORT = int(
        os.environ.get('ASSET_DATABASE_REQUIRED_PORT', '3306')
    )
    ASSET_DATABASE_REQUIRED_NAME = os.environ.get(
        'ASSET_DATABASE_REQUIRED_NAME',
        'rpa_web',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LEARNING_TOKEN_SECRET = os.environ.get('LEARNING_TOKEN_SECRET')
    LEARNING_TOKEN_SECRET_FILE = os.path.join(_VAR_DIR, 'learning_token_secret.key')
    LEARNING_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('LEARNING_TOKEN_MAX_AGE_SECONDS', '43200'))
    INITIAL_BOSS_EMAILS = os.environ.get('INITIAL_BOSS_EMAILS', '')
    LEARNING_BOOTSTRAP_ON_STARTUP = True
    PASSWORD_RESET_SECRET = os.environ.get('PASSWORD_RESET_SECRET')
    PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = int(
        os.environ.get('PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS', '900')
    )
    PASSWORD_RESET_FRONTEND_URL = os.environ.get(
        'PASSWORD_RESET_FRONTEND_URL',
        'http://172.16.30.91:8090',
    )
    # 阿里企业邮箱默认发信配置。账号和 SMTP 客户端密码仍必须由部署环境提供。
    PASSWORD_RESET_SMTP_HOST = os.environ.get(
        'PASSWORD_RESET_SMTP_HOST',
        'smtp.qiye.aliyun.com',
    )
    PASSWORD_RESET_SMTP_PORT = int(os.environ.get('PASSWORD_RESET_SMTP_PORT', '465'))
    PASSWORD_RESET_SMTP_USERNAME = os.environ.get('PASSWORD_RESET_SMTP_USERNAME')
    PASSWORD_RESET_SMTP_PASSWORD = os.environ.get('PASSWORD_RESET_SMTP_PASSWORD')
    PASSWORD_RESET_SMTP_USE_TLS = _env_bool('PASSWORD_RESET_SMTP_USE_TLS')
    PASSWORD_RESET_SMTP_USE_SSL = _env_bool('PASSWORD_RESET_SMTP_USE_SSL', True)
    PASSWORD_RESET_EMAIL_FROM = (
        os.environ.get('PASSWORD_RESET_EMAIL_FROM')
        or PASSWORD_RESET_SMTP_USERNAME
    )
    PASSWORD_RESET_SMTP_TIMEOUT_SECONDS = int(
        os.environ.get('PASSWORD_RESET_SMTP_TIMEOUT_SECONDS', '10')
    )
    # 仅供自动化测试/本机调试。生产环境不得开启，否则响应会直接返回重置链接。
    PASSWORD_RESET_EXPOSE_TOKEN = _env_bool('PASSWORD_RESET_EXPOSE_TOKEN')

    # 连接池：长时间运行 + 并发访问下的稳定性关键
    # - pool_pre_ping：借出连接前先探活，杜绝 MySQL 闲置断连后的 "server has gone away"
    # - pool_recycle：连接最长复用 280s（低于 MySQL 默认 wait_timeout），到期主动换新
    # - pool_size + max_overflow：常驻 10 条、突发再开 20 条；超出时最多排队 10s 报错，
    #   而不是无限挂起把前端请求也拖死
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 10,
    }

    # 资产与学习模型保留独立 bind key，以减少代码改动，但 bind 指向与
    # RPA 项目相同的 MySQL 数据库；所有业务数据由此统一落在 rpa_web。
    SQLALCHEMY_BINDS = {
        'assets': SQLALCHEMY_DATABASE_URI,
    }
    # 仅供一次性历史数据迁移脚本读取；应用运行时不再使用这个 SQLite 文件。
    LEGACY_ASSETS_DATABASE = os.path.join(_VAR_DIR, 'assets.db')
    # 上传文件落地目录（当前 Skill/插件只登记文件名，暂未用到，预留）
    UPLOAD_FOLDER = os.path.join(_VAR_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
