from datetime import date

import pytest

from app import create_app, db
from app.learning.auth import issue_learning_token
from app.learning.errors import LearningConflictError, LearningValidationError
from app.learning.roles import (
    bootstrap_initial_bosses,
    change_role,
    confirm_initial_employment_type,
    ensure_roster_week,
    get_identity,
    is_roster_member,
)
from app.learning.time import utc_now
from app.models.learning import RoleChangeLog, UserRole, WeeklyRoster, WeeklyRosterWeek
from app.models.models import User


WEEK_START = date(2026, 7, 20)


@pytest.fixture(autouse=True)
def fixed_current_week(monkeypatch):
    """Keep time-sensitive role tests stable after the fixture week has passed."""
    monkeypatch.setattr('app.learning.roles.week_start_for', lambda: WEEK_START)


@pytest.fixture()
def users(app):
    with app.app_context():
        records = [
            User(id=1, username='operator', email='operator@example.com', password='secret1', created_at=utc_now()),
            User(id=2, username='target', email='target@example.com', password='secret1', created_at=utc_now()),
            User(id=3, username='intern', email='intern@example.com', password='secret1', created_at=utc_now()),
            User(id=4, username='employee', email='employee@example.com', password='secret1', created_at=utc_now()),
        ]
        db.session.add_all(records)
        db.session.commit()
        return {record.username: record.id for record in records}


@pytest.fixture()
def hr_headers(app, users):
    with app.app_context():
        db.session.add(UserRole(user_id=users['operator'], role='hr'))
        db.session.commit()
        token = issue_learning_token(users['operator'], 'admin')
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def employee_headers(app, users):
    with app.app_context():
        token = issue_learning_token(users['employee'], 'admin')
    return {'Authorization': f'Bearer {token}'}


def test_empty_week_stays_frozen_after_midweek_intern_assignment(app, users):
    with app.app_context():
        week = ensure_roster_week(WEEK_START)
        change_role(target_user_id=users['target'], new_role='intern', operator_user_id=users['operator'],
                    week_start=WEEK_START)
        assert WeeklyRoster.query.filter_by(week_start=week.week_start).count() == 0


def test_first_employee_selection_creates_explicit_mapping_and_audit(app, users):
    with app.app_context():
        result = confirm_initial_employment_type(users['employee'], 'employee', WEEK_START)
        assert result == 'employee'
        assert db.session.get(UserRole, users['employee']).role == 'employee'
        audit = RoleChangeLog.query.filter_by(target_user_id=users['employee']).one()
        assert audit.source == 'self_selection'
        assert audit.operator_user_id == users['employee']


def test_first_intern_selection_joins_frozen_current_week_immediately(app, users):
    with app.app_context():
        ensure_roster_week(WEEK_START)
        result = confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert result == 'intern'
        assert is_roster_member(users['target'], WEEK_START) is True


def test_same_initial_selection_is_idempotent(app, users):
    with app.app_context():
        confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert RoleChangeLog.query.filter_by(target_user_id=users['target']).count() == 1
        assert WeeklyRoster.query.filter_by(
            week_start=WEEK_START, user_id=users['target']
        ).count() == 1


def test_fixed_position_rejects_a_different_login_selection(app, users):
    with app.app_context():
        confirm_initial_employment_type(users['target'], 'employee', WEEK_START)
        with pytest.raises(LearningConflictError, match='fixed'):
            confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert db.session.get(UserRole, users['target']).role == 'employee'


@pytest.mark.parametrize('value', [None, '', 'boss', 7])
def test_initial_position_rejects_invalid_values(app, users, value):
    with app.app_context(), pytest.raises(LearningValidationError):
        confirm_initial_employment_type(users['target'], value, WEEK_START)


def test_new_week_snapshots_current_interns_once(app, users):
    with app.app_context():
        db.session.add(UserRole(user_id=users['intern'], role='intern'))
        db.session.commit()
        week = ensure_roster_week(WEEK_START)
        db.session.add(UserRole(user_id=users['target'], role='intern'))
        db.session.commit()
        assert week.week_start == WEEK_START
        assert {row.user_id for row in WeeklyRoster.query.filter_by(week_start=WEEK_START)} == {users['intern']}
        assert ensure_roster_week(WEEK_START).week_start == WEEK_START
        assert WeeklyRosterWeek.query.filter_by(week_start=WEEK_START).count() == 1


def test_demoted_intern_remains_in_current_roster_and_leaves_next_week(app, users):
    with app.app_context():
        db.session.add(UserRole(user_id=users['intern'], role='intern'))
        db.session.commit()
        ensure_roster_week(WEEK_START)
        change_role(users['intern'], 'employee', users['operator'], WEEK_START)
        assert is_roster_member(users['intern'], WEEK_START) is True
        assert is_roster_member(users['intern'], date(2026, 7, 27)) is False
        ensure_roster_week(date(2026, 7, 27))
        assert is_roster_member(users['intern'], date(2026, 7, 27)) is False


def test_role_change_is_audited_in_same_transaction(app, users):
    with app.app_context():
        result = change_role(target_user_id=users['target'], new_role='hr', operator_user_id=users['operator'])
        assert result['old_role'] == 'employee'
        assert RoleChangeLog.query.filter_by(target_user_id=users['target']).one().new_role == 'hr'


def test_failed_role_audit_rolls_back_the_role_mapping(app, users):
    with app.app_context():
        db.session.connection(bind_arguments={'bind': db.engines['assets']}).exec_driver_sql(
            """CREATE TRIGGER reject_role_audit
            BEFORE INSERT ON role_change_logs
            WHEN NEW.source = 'manual'
            BEGIN SELECT RAISE(ABORT, 'audit rejected'); END;"""
        )
        db.session.commit()
        with pytest.raises(Exception, match='audit rejected'):
            change_role(users['target'], 'intern', users['operator'], WEEK_START)
        assert UserRole.query.filter_by(user_id=users['target']).count() == 0


def test_same_role_change_is_idempotent_without_false_audit(app, users):
    with app.app_context():
        result = change_role(users['target'], 'employee', users['operator'], WEEK_START)
        assert result == {'user_id': users['target'], 'old_role': 'employee', 'role': 'employee'}
        assert RoleChangeLog.query.count() == 0


@pytest.mark.parametrize('role', ['', 'administrator', None, 7])
def test_change_role_rejects_unknown_role(app, users, role):
    with app.app_context(), pytest.raises(Exception, match='role'):
        change_role(users['target'], role, users['operator'], WEEK_START)


def test_change_role_rejects_missing_target(app, users):
    with app.app_context(), pytest.raises(Exception, match='user'):
        change_role(99, 'intern', users['operator'], WEEK_START)


def test_identity_reflects_current_role_and_current_week_membership(app, users):
    with app.app_context():
        db.session.add(UserRole(user_id=users['intern'], role='intern'))
        db.session.commit()
        ensure_roster_week(WEEK_START)
        identity = get_identity(users['intern'], 'user')
        assert identity['user_id'] == users['intern']
        assert identity['role'] == 'intern'
        assert identity['week_start'] == WEEK_START.isoformat()
        assert identity['week_end'] == '2026-07-26'
        assert identity['is_current_roster_member'] is True
        assert identity['can_view_learning_report'] is True
        assert identity['can_submit_current_week'] is True
        assert identity['can_view_learning_stats'] is False
        assert identity['can_manage_learning'] is False


def test_identity_separates_stats_read_from_management(app, users):
    with app.app_context():
        identity = get_identity(users['employee'], 'admin')
    assert identity['login_surface'] == 'admin'
    assert identity['can_view_learning_stats'] is True
    assert identity['can_manage_learning'] is False
    assert identity['can_view_learning_report'] is False


def test_hr_can_assign_boss(client, hr_headers):
    response = client.patch('/learning/admin/users/2/role', json={'role': 'boss'}, headers=hr_headers)
    assert response.status_code == 200
    assert response.json['role'] == 'boss'


def test_role_admin_requires_hr_or_boss(client, employee_headers):
    response = client.get('/learning/admin/users', headers=employee_headers)
    assert response.status_code == 403
    assert response.json == {'error': 'Learning role is not permitted'}


def test_admin_user_list_merges_user_data_and_default_employee(client, hr_headers):
    response = client.get('/learning/admin/users', headers=hr_headers)
    assert response.status_code == 200
    target = next(item for item in response.json['items'] if item['id'] == 2)
    assert target == {
        'id': 2,
        'username': 'target',
        'email': 'target@example.com',
        'role': 'employee',
    }
    assert 'password' not in target


def test_role_change_endpoint_validates_json_and_target(client, hr_headers):
    invalid = client.patch('/learning/admin/users/2/role', json={'role': 'invalid'}, headers=hr_headers)
    absent = client.patch('/learning/admin/users/99/role', json={'role': 'intern'}, headers=hr_headers)
    assert invalid.status_code == 422
    assert absent.status_code == 404


def test_admin_role_logs_are_newest_first_and_paginated(client, app, hr_headers, users):
    with app.app_context():
        change_role(users['target'], 'intern', users['operator'], WEEK_START)
        change_role(users['target'], 'employee', users['operator'], WEEK_START)
    response = client.get('/learning/admin/role-change-logs?page=1&per_page=1', headers=hr_headers)
    assert response.status_code == 200
    assert response.json['total'] == 2
    assert response.json['items'][0]['new_role'] == 'employee'
    assert response.json['items'][0]['operator_user_id'] == users['operator']


def test_bootstrap_creates_only_missing_role_mappings(app, users):
    with app.app_context():
        app.config['INITIAL_BOSS_EMAILS'] = ' OPERATOR@example.com, target@example.com, missing@example.com '
        db.session.add(UserRole(user_id=users['target'], role='intern'))
        db.session.commit()
        assert bootstrap_initial_bosses() == 1
        assert UserRole.query.filter_by(user_id=users['operator']).one().role == 'boss'
        assert UserRole.query.filter_by(user_id=users['target']).one().role == 'intern'
        audit = RoleChangeLog.query.filter_by(target_user_id=users['operator']).one()
        assert audit.source == 'bootstrap'
        assert bootstrap_initial_bosses() == 0


def test_enabled_startup_persists_an_empty_current_week(tmp_path):
    assets_path = (tmp_path / 'startup-assets.db').as_posix()
    startup_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_BINDS': {'assets': f'sqlite:///{assets_path}'},
        'LEARNING_TOKEN_SECRET': 'test-learning-secret',
        'LEARNING_BOOTSTRAP_ON_STARTUP': True,
    })
    with startup_app.app_context():
        db.session.remove()
        assert WeeklyRosterWeek.query.filter_by(week_start=WEEK_START).count() == 1
