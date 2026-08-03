import pytest
from flask import Flask

from app import _register_frontend_routes


def _make_frontend_app(tmp_path):
    dist_dir = tmp_path / 'dist'
    assets_dir = dist_dir / 'assets'
    assets_dir.mkdir(parents=True)
    (dist_dir / 'index.html').write_text(
        '<!doctype html><title>RPA intranet</title>',
        encoding='utf-8',
    )
    (assets_dir / 'app.js').write_text(
        'window.rpaLoaded = true',
        encoding='utf-8',
    )

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SERVE_FRONTEND=True,
        FRONTEND_DIST_DIR=str(dist_dir),
    )
    app.get('/admin/get_projects')(lambda: {'source': 'api'})
    _register_frontend_routes(app)
    return app


def test_frontend_hosting_serves_index_assets_and_history_routes(tmp_path):
    app = _make_frontend_app(tmp_path)
    client = app.test_client()

    assert client.get('/').status_code == 200
    assert b'RPA intranet' in client.get('/').data
    assert client.get('/assets/app.js').data == b'window.rpaLoaded = true'
    assert b'RPA intranet' in client.get('/main/DevelopmentManagement').data
    assert b'RPA intranet' in client.get('/admin/DevelopmentProgress').data


def test_frontend_hosting_preserves_api_routes_and_api_404s(tmp_path):
    app = _make_frontend_app(tmp_path)
    client = app.test_client()

    response = client.get('/admin/get_projects')
    assert response.status_code == 200
    assert response.get_json() == {'source': 'api'}
    assert client.get('/public/not-an-endpoint').status_code == 404
    assert client.get('/learning/not-an-endpoint').status_code == 404


def test_frontend_hosting_requires_a_completed_build(tmp_path):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SERVE_FRONTEND=True,
        FRONTEND_DIST_DIR=str(tmp_path / 'missing-dist'),
    )

    with pytest.raises(RuntimeError, match='Frontend build not found'):
        _register_frontend_routes(app)
