from pathlib import Path

from flask import Flask, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()

_SPA_ENTRY_ROUTES = {
    'department',
    'department-skills',
    'department-plugins',
    'login',
    'register',
    'forgot-password',
    'adminLogin',
    'adminregister',
    'admin-forgot-password',
    'admin',
    'main',
}


def _register_frontend_routes(app):
    """Serve the production Vue build from Flask when explicitly enabled."""
    if not app.config.get('SERVE_FRONTEND'):
        return

    dist_dir = Path(app.config['FRONTEND_DIST_DIR']).resolve()
    index_file = dist_dir / 'index.html'
    if not index_file.is_file():
        raise RuntimeError(
            f'Frontend build not found at {index_file}. Run "npm run build" first.'
        )

    @app.get('/')
    def frontend_index():
        return send_from_directory(dist_dir, 'index.html', max_age=0)

    @app.get('/<path:requested_path>')
    def frontend_asset_or_route(requested_path):
        candidate = (dist_dir / requested_path).resolve()
        try:
            candidate.relative_to(dist_dir)
        except ValueError:
            abort(404)

        if candidate.is_file():
            return send_from_directory(dist_dir, requested_path)

        first_segment = requested_path.split('/', 1)[0]
        if first_segment in _SPA_ENTRY_ROUTES:
            return send_from_directory(dist_dir, 'index.html', max_age=0)

        abort(404)


def _validate_asset_database_binding(config):
    """Require production asset writes to use the main rpa_web MySQL database."""
    if config.get('TESTING'):
        return

    binds = config.get('SQLALCHEMY_BINDS') or {}
    asset_uri = binds.get('assets')
    main_uri = config.get('SQLALCHEMY_DATABASE_URI')
    if not asset_uri or not main_uri:
        raise RuntimeError(
            'Production requires SQLALCHEMY_DATABASE_URI and the assets database bind.'
        )

    try:
        asset_url = make_url(asset_uri)
        main_url = make_url(main_uri)
    except Exception as error:
        raise RuntimeError('The configured asset database URI is invalid.') from error

    expected_target = (
        config.get('ASSET_DATABASE_REQUIRED_HOST', '172.16.50.20'),
        int(config.get('ASSET_DATABASE_REQUIRED_PORT', 3306)),
        config.get('ASSET_DATABASE_REQUIRED_NAME', 'rpa_web'),
    )
    asset_target = (asset_url.host, asset_url.port or 3306, asset_url.database)
    main_target = (
        main_url.host,
        main_url.port or 3306,
        main_url.database,
    )
    if (
        asset_url.get_backend_name() != 'mysql'
        or asset_target != expected_target
        or main_target != expected_target
        or asset_target != main_target
    ):
        raise RuntimeError(
            'Production Skill/Python assets must use the main MySQL '
            'rpa_web database; SQLite and separate asset databases are forbidden.'
        )


def _ensure_asset_schema():
    """Create and lightly migrate asset/learning tables on their configured bind."""
    db.create_all(bind_key='assets')
    engine = db.engines['assets']
    additions = {
        'assets': {
            'reject_reason': 'TEXT',
            'lifecycle_status': "VARCHAR(16) NOT NULL DEFAULT '在编'",
            'progress': 'FLOAT NOT NULL DEFAULT 0',
        },
        'weekly_reports': {
            'record_date': 'DATE',
            'certificate': 'VARCHAR(64)',
            'program_count': 'INTEGER',
            'blockers': 'TEXT',
        },
        'weekly_report_submissions': {
            'record_date': 'DATE',
            'certificate': 'VARCHAR(64)',
            'program_count': 'INTEGER',
            'blockers': 'TEXT',
        },
    }
    quote = engine.dialect.identifier_preparer.quote

    with engine.begin() as conn:
        schema = inspect(conn)
        for table_name, columns in additions.items():
            if not schema.has_table(table_name):
                continue
            existing = {column['name'] for column in schema.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    conn.exec_driver_sql(
                        f'ALTER TABLE {quote(table_name)} '
                        f'ADD COLUMN {quote(column_name)} {column_type}'
                    )

def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app)
    
    # 加载配置类
    from app.config import Config
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config.get('TESTING'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    _validate_asset_database_binding(app.config)

    # 初始化数据库
    db.init_app(app)
    from app.models import learning as _learning_models
    
    CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

    # 注册路由蓝图
    from app.routes import public, user, admin, learning
    app.register_blueprint(public.bp,url_prefix='/public')
    app.register_blueprint(user.user_bp, url_prefix='/user')
    app.register_blueprint(admin.admin_bp, url_prefix='/admin')
    # 管理功能并入用户工作台：复用同一套处理函数，/user/manage 下的请求
    # 由 admin 蓝图的 before_request 校验用户端签名令牌；读取范围由路由决定，
    # 写入则由资源所有权和 hr/boss 管理员角色共同控制。
    # 保留 /admin 前缀，兼容已有书签和旧版前端；不涉及任何数据库结构调整。
    app.register_blueprint(
        admin.admin_bp,
        url_prefix='/user/manage',
        name='user_management',
    )
    app.register_blueprint(learning.learning_bp, url_prefix='/learning')

    # 确保本地 var 目录存在（令牌密钥 / uploads 落地处）
    import os
    os.makedirs(app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'var', 'uploads')), exist_ok=True)

    # 资产和学习表通过 assets bind 建在 RPA 主库；测试可把该 bind 覆盖为 SQLite。
    with app.app_context():
        _ensure_asset_schema()
        if app.config.get('LEARNING_BOOTSTRAP_ON_STARTUP'):
            from app.learning.auth import ensure_learning_token_secret
            from app.learning.roles import bootstrap_initial_bosses, ensure_roster_week

            ensure_learning_token_secret(app)
            try:
                bootstrap_initial_bosses()
            except SQLAlchemyError:
                app.logger.warning('Learning role bootstrap skipped: user database unavailable')
                db.session.rollback()
            ensure_roster_week()

    _register_frontend_routes(app)

    return app
