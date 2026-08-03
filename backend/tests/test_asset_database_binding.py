import pytest

from app import _validate_asset_database_binding, db
from app.learning.auth import issue_learning_token
from app.models.models import User


MAIN_MYSQL = 'mysql+pymysql://user:password@172.16.50.20:3306/rpa_web'


def _config(*, main=MAIN_MYSQL, asset=MAIN_MYSQL, testing=False):
    return {
        'TESTING': testing,
        'SQLALCHEMY_DATABASE_URI': main,
        'SQLALCHEMY_BINDS': {'assets': asset},
        'ASSET_DATABASE_REQUIRED_HOST': '172.16.50.20',
        'ASSET_DATABASE_REQUIRED_PORT': 3306,
        'ASSET_DATABASE_REQUIRED_NAME': 'rpa_web',
    }


def test_production_accepts_main_rpa_web_mysql_asset_database():
    _validate_asset_database_binding(_config())


@pytest.mark.parametrize(
    'asset_uri',
    [
        'sqlite:///assets.db',
        'mysql+pymysql://user:password@172.16.50.20:3306/other_database',
        'mysql+pymysql://user:password@127.0.0.1:3306/rpa_web',
    ],
)
def test_production_rejects_sqlite_or_separate_asset_database(asset_uri):
    with pytest.raises(RuntimeError, match='must use the main MySQL'):
        _validate_asset_database_binding(_config(asset=asset_uri))


def test_production_rejects_another_main_database_server():
    other_server = 'mysql+pymysql://user:password@127.0.0.1:3306/rpa_web'
    with pytest.raises(RuntimeError, match='must use the main MySQL'):
        _validate_asset_database_binding(
            _config(main=other_server, asset=other_server)
        )


def test_testing_can_keep_isolated_sqlite_asset_database():
    _validate_asset_database_binding(
        _config(main='sqlite://', asset='sqlite:///assets-test.db', testing=True)
    )


def test_asset_submission_writes_through_assets_bind(client, app):
    with app.app_context():
        user = User(
            id=42,
            username='binding-check-user',
            email='binding-check@example.com',
            password='test-only-password',
        )
        db.session.add(user)
        db.session.commit()
        token = issue_learning_token(user.id, 'user')
    headers = {'Authorization': f'Bearer {token}'}

    response = client.post('/user/assets', data={
        'user_id': '42',
        'asset_type': 'python_plugin',
        'name': 'binding-check',
        'department': '技术部',
        'submitter': '测试用户',
        'version': '1.0',
        'description': '验证资产提交只写入 assets bind',
        'file_name': 'binding_check.py',
    }, headers=headers)

    assert response.status_code == 201
    with app.app_context():
        with db.engines['assets'].connect() as connection:
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM assets WHERE name = 'binding-check'"
            ).scalar_one()
        with db.engine.connect() as connection:
            main_has_assets_table = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type = 'table' AND name = 'assets'"
            ).scalar_one()

    assert count == 1
    assert main_has_assets_table == 0
