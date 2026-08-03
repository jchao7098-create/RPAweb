from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.learning.errors import LearningConflictError, LearningNotFoundError, LearningValidationError
from app.learning.time import to_shanghai_iso, week_start_for
from app.models.learning import ROLES, RoleChangeLog, UserRole, WeeklyRoster, WeeklyRosterWeek
from app.models.models import User

EMPLOYMENT_TYPES = ('employee', 'intern')


def get_role(user_id):
    row = UserRole.query.filter_by(user_id=int(user_id)).first()
    return row.role if row else 'employee'


def employment_type_for_role(role):
    return 'intern' if role == 'intern' else 'employee'


def _validate_employment_type(employment_type):
    if not isinstance(employment_type, str) or employment_type not in EMPLOYMENT_TYPES:
        raise LearningValidationError('employment_type must be employee or intern')
    return employment_type


def _existing_employment_type(user_id, requested):
    role_row = db.session.get(UserRole, int(user_id))
    if role_row is None:
        return None
    fixed = employment_type_for_role(role_row.role)
    if fixed != requested:
        raise LearningConflictError(
            'Employment type is fixed; contact an administrator to change it'
        )
    return fixed


def confirm_initial_employment_type(user_id, employment_type, week_start=None):
    requested = _validate_employment_type(employment_type)
    user_id = int(user_id)
    fixed = _existing_employment_type(user_id, requested)
    if fixed is not None:
        return fixed

    roster_week = _week_start(week_start)
    ensure_roster_week(roster_week)
    db.session.add(UserRole(
        user_id=user_id,
        role=requested,
        assigned_by_user_id=user_id,
    ))
    db.session.add(RoleChangeLog(
        target_user_id=user_id,
        old_role='employee',
        new_role=requested,
        operator_user_id=user_id,
        source='self_selection',
    ))
    if requested == 'intern':
        db.session.add(WeeklyRoster(week_start=roster_week, user_id=user_id))
    try:
        db.session.commit()
        return requested
    except IntegrityError:
        db.session.rollback()
        fixed = _existing_employment_type(user_id, requested)
        if fixed is not None:
            return fixed
        raise
    except Exception:
        db.session.rollback()
        raise


def _week_start(value=None):
    if value is None:
        return week_start_for()
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise LearningValidationError('week_start must be a date')
    return value - timedelta(days=value.weekday())


def ensure_roster_week(week_start=None):
    week_start = _week_start(week_start)
    roster_week = db.session.get(WeeklyRosterWeek, week_start)
    if roster_week:
        return roster_week

    try:
        with db.session.begin_nested():
            roster_week = WeeklyRosterWeek(week_start=week_start)
            db.session.add(roster_week)
            db.session.flush()
            intern_ids = [
                row.user_id
                for row in UserRole.query.with_entities(UserRole.user_id).filter_by(role='intern')
            ]
            db.session.add_all(
                WeeklyRoster(week_start=week_start, user_id=user_id)
                for user_id in intern_ids
            )
            db.session.flush()
        return roster_week
    except IntegrityError:
        roster_week = db.session.get(WeeklyRosterWeek, week_start)
        if roster_week:
            return roster_week
        raise


def is_roster_member(user_id, week_start):
    return WeeklyRoster.query.filter_by(
        week_start=_week_start(week_start), user_id=int(user_id)
    ).first() is not None


def get_identity(user_id, login_surface):
    week_start = _week_start()
    ensure_roster_week(week_start)
    role = get_role(user_id)
    roster_member = is_roster_member(user_id, week_start)
    is_user_surface = login_surface == 'user'
    is_admin_surface = login_surface == 'admin'
    return {
        'user_id': int(user_id),
        'role': role,
        'login_surface': login_surface,
        'week_start': week_start.isoformat(),
        'week_end': (week_start + timedelta(days=6)).isoformat(),
        'is_current_roster_member': roster_member,
        'can_view_learning_report': is_user_surface and (role == 'intern' or roster_member),
        'can_submit_current_week': is_user_surface and roster_member,
        'can_view_learning_stats': is_admin_surface,
        'can_manage_learning': is_admin_surface and role in ('hr', 'boss'),
    }


def _validate_role(role):
    if not isinstance(role, str) or role not in ROLES:
        raise LearningValidationError('role must be employee, intern, hr, or boss')


def change_role(target_user_id, new_role, operator_user_id, week_start=None):
    _validate_role(new_role)
    target_user_id = int(target_user_id)
    if db.session.get(User, target_user_id) is None:
        raise LearningNotFoundError('user was not found')

    roster_week = _week_start(week_start)
    ensure_roster_week(roster_week)
    role_row = db.session.get(UserRole, target_user_id)
    old_role = role_row.role if role_row else 'employee'
    if old_role == new_role:
        return {'user_id': target_user_id, 'old_role': old_role, 'role': old_role}

    if role_row is None:
        db.session.add(UserRole(
            user_id=target_user_id,
            role=new_role,
            assigned_by_user_id=int(operator_user_id),
        ))
    else:
        role_row.role = new_role
        role_row.assigned_by_user_id = int(operator_user_id)
    db.session.add(RoleChangeLog(
        target_user_id=target_user_id,
        old_role=old_role,
        new_role=new_role,
        operator_user_id=int(operator_user_id),
        source='manual',
    ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {'user_id': target_user_id, 'old_role': old_role, 'role': new_role}


def bootstrap_initial_bosses():
    from flask import current_app

    emails = {
        email.strip().lower()
        for email in str(current_app.config.get('INITIAL_BOSS_EMAILS', '')).split(',')
        if email.strip()
    }
    if not emails:
        return 0

    users = User.query.filter(func.lower(User.email).in_(emails)).all()
    if not users:
        return 0
    existing_user_ids = {
        row.user_id
        for row in UserRole.query.with_entities(UserRole.user_id).filter(
            UserRole.user_id.in_([user.id for user in users])
        )
    }
    new_users = [user for user in users if user.id not in existing_user_ids]
    if not new_users:
        return 0

    for user in new_users:
        db.session.add(UserRole(user_id=user.id, role='boss'))
        db.session.add(RoleChangeLog(
            target_user_id=user.id,
            old_role='employee',
            new_role='boss',
            operator_user_id=None,
            source='bootstrap',
        ))
    db.session.commit()
    return len(new_users)


def list_users(page=1, per_page=50):
    page = _positive_int(page, 'page')
    per_page = _positive_int(per_page, 'per_page', maximum=100)
    pagination = User.query.order_by(User.id.asc()).paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items
    role_by_user_id = {
        row.user_id: row.role
        for row in UserRole.query.filter(UserRole.user_id.in_([user.id for user in users]))
    } if users else {}
    return {
        'items': [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role_by_user_id.get(user.id, 'employee'),
            }
            for user in users
        ],
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
    }


def list_role_change_logs(page=1, per_page=50):
    page = _positive_int(page, 'page')
    per_page = _positive_int(per_page, 'per_page', maximum=100)
    pagination = RoleChangeLog.query.order_by(
        RoleChangeLog.changed_at.desc(), RoleChangeLog.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [
            {
                'id': row.id,
                'target_user_id': row.target_user_id,
                'old_role': row.old_role,
                'new_role': row.new_role,
                'operator_user_id': row.operator_user_id,
                'source': row.source,
                'changed_at': to_shanghai_iso(row.changed_at),
            }
            for row in pagination.items
        ],
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
    }


def _positive_int(value, name, maximum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise LearningValidationError(f'{name} must be an integer')
    if result < 1 or (maximum is not None and result > maximum):
        raise LearningValidationError(f'{name} is out of range')
    return result
