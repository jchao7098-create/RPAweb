import pytest

from app import create_app, db


@pytest.fixture()
def app(tmp_path):
    assets_path = (tmp_path / 'assets-test.db').as_posix()
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_BINDS': {'assets': f'sqlite:///{assets_path}'},
        'LEARNING_TOKEN_SECRET': 'test-learning-secret',
        'LEARNING_BOOTSTRAP_ON_STARTUP': False,
        'PASSWORD_RESET_EXPOSE_TOKEN': True,
        'PASSWORD_RESET_FRONTEND_URL': 'http://localhost:5173',
        'PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS': 900,
    })
    with app.app_context():
        db.create_all()
        engines = list(db.engines.values())
        try:
            yield app
        finally:
            try:
                db.session.remove()
                db.drop_all()
            finally:
                db.session.remove()
                for engine in engines:
                    engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()
